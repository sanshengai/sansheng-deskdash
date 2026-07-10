# scripts/orchestrator.py — 调度器:按 refresh 契约调度各模块采集器,subprocess 隔离 +
# 强制超时,写 health.json,汇总各模块输出 → data.inc(UTF-16)。
#
# 与私有仓 collect.py 的最大架构差异:collect.py 是 import 各采集器函数调用;这里改为
# **subprocess 跑独立 collector.py**(资源隔离 + 强制 timeout_s 杀超时,单个挂死的采集器
# 不能拖垮整轮)。迁移保留的四套节流机制:
#   ① done_date 秒退      —— 今日重活全到位则后续触发退化为 net-only 快路径(只刷轻活)。
#   ② daily_heavy 每日一次 —— 重活模块按 last_heavy_date 每天首跑一次(无论成败标记日期,
#                            避免开机窗口每 10 分钟反复起 Chrome/触发风控 —— 源同款语义)。
#   ③ net-only 快路径     —— 仅跑 refresh.net_only_ok=true 的模块(对应源 _refresh_net_only)。
#   ④ interval 节流       —— 以模块自身上次成功时间戳(health.last_ok)作节流锚,interval_s=0
#                            每轮都跑;未到点沿用缓存(不重复起进程)。
#   ⑤ _try 式聚合         —— 每个采集器在独立进程里跑,失败只记 health 不炸整轮。
#
# 契约(与采集器的进程边界):
#   调用 `python <module_dir>/<entry> --config <config.json>`,采集器 stdout 打印单行 JSON:
#     · 成功 = 模块 outputs 的扁平 dict(如 {"TempNow": 32, "City": "长沙"});
#     · 失败 = {"ok": false, "err": {kind, retryable, hint_for_agent}}(设计稿 §4 错误约定)。
#   兼容 {"ok": true, "out": {...}} 写法(secret-canary 基座即此形态)。
#
# 安全铁律:纯 stdlib(subprocess/json/os/datetime);subprocess 用 list 参数、不 shell=True;
#   不把采集器 stdout/stderr 原文写进 health/日志(可能含密钥),只落规范化后的 hint_for_agent
#   (make_error 契约保证不含密钥值)。
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)                 # 让 `from lib.xxx import` 在 CLI/测试两种入口都可用

from lib.common import atomic_write, local_now                      # noqa: E402
from lib.contract import (ContractError, ERR_KINDS, load_widget,    # noqa: E402
                          make_error, validate_output)
from lib.inc_writer import to_inc                                   # noqa: E402


# —— 采集器 stdout 解析:哨兵表示无法解析 ——
_PARSE_FAIL = object()

# fail_streak 达到此阈值 → 向该模块 outputs 注入 Stale=1,供皮肤灰化(设计稿 §2/§4)
STALE_THRESHOLD = 3


class _Spec:
    """单模块调度所需的契约切片(load_widget 后固化,调度期只读)。"""

    __slots__ = ("id", "module_dir", "prefix", "mode", "interval_s", "net_only_ok",
                 "timeout_s", "collector_path", "config_path", "output_schema_path")

    def __init__(self, mid, module_dir, widget):
        rt = widget["runtime"]
        self.id = mid
        self.module_dir = module_dir
        self.prefix = rt["output"]["prefix"]
        self.mode = rt["refresh"]["mode"]
        self.interval_s = rt["refresh"]["interval_s"]
        self.net_only_ok = bool(rt["refresh"]["net_only_ok"])
        self.timeout_s = rt.get("timeout_s", 60)
        self.collector_path = os.path.join(module_dir, rt["entry"])
        self.output_schema_path = os.path.join(module_dir, rt["output"]["schema"])
        self.config_path = _resolve_config(module_dir, rt["config"].get("example"))


def _resolve_config(module_dir, example_name):
    """采集器 --config 指向:优先用户 config.json,缺失则退到 config.example.json(无密钥),
    再缺失则仍给出 config.json 路径(不存在也传,由采集器自行容错——零配置模块可无此文件)。"""
    cfg = os.path.join(module_dir, "config.json")
    if os.path.isfile(cfg):
        return cfg
    if example_name:
        exp = os.path.join(module_dir, example_name)
        if os.path.isfile(exp):
            return exp
    return cfg


# —— JSON 状态文件(health / 缓存)读写:UTF-8;data.inc 才走 UTF-16 ——

def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=1))


def _blank_health():
    return {"last_ok": None, "fail_streak": 0, "last_err": None,
            "last_run": None, "last_heavy_date": None}


def _cache_path(board_dir, mid):
    return os.path.join(board_dir, "state", "%s.json" % mid)


def _load_cache(board_dir, mid):
    """上次成功的原始 outputs(dict);无则空 dict(UI 不闪空的兜底基线)。"""
    v = _read_json(_cache_path(board_dir, mid), {})
    return v if isinstance(v, dict) else {}


def _save_cache(board_dir, mid, outputs):
    _write_json(_cache_path(board_dir, mid), outputs)


# —— 采集器进程边界:跑 subprocess,强制 timeout,解析 stdout ——

def _invoke(spec):
    """跑一次采集器子进程,返回 (raw_outputs | None, err | None):恰一个非 None。

    强制 timeout_s 超时:subprocess.run 到点 kill 子进程再抛 TimeoutExpired;归一为 provider 失败
    (可能挂死或网络过慢)。不把 stdout/stderr 原文塞进错误(可能含密钥),只给结构化 hint。
    """
    cmd = [sys.executable, spec.collector_path, "--config", spec.config_path]
    kw = {"capture_output": True, "timeout": spec.timeout_s, "cwd": spec.module_dir}
    if sys.platform == "win32":
        # 计划任务用 pythonw 跑时,采集器起的控制台子程序会闪黑窗;统一叠加 CREATE_NO_WINDOW 根治
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(cmd, **kw)  # noqa: S603 (list 参数,非 shell)
    except subprocess.TimeoutExpired:
        return None, make_error(
            "provider", True,
            "采集器超时(>%ds 未返回),可能挂死或网络过慢;"
            "检查 %s 的 collector 是否有无限等待/无超时的网络调用。" % (spec.timeout_s, spec.id)
        )["err"]
    except OSError:
        return None, make_error(
            "bug", False,
            "无法启动采集器进程:检查 %s 的 entry 路径与 Python 环境。" % spec.id
        )["err"]

    out = (proc.stdout or b"").decode("utf-8", "replace")
    payload = _parse_stdout(out)
    if payload is _PARSE_FAIL:
        return None, make_error(
            "bug", False,
            "采集器输出无法解析为 JSON(退出码 %d);契约要求 stdout 打印单行 JSON。" % proc.returncode
        )["err"]
    return _interpret(payload)


def _parse_stdout(out):
    """整段 stdout 解析为 JSON;失败再退回"最后一行非空"再试(容忍采集器多打了日志行)。"""
    s = out.strip()
    if not s:
        return _PARSE_FAIL
    try:
        return json.loads(s)
    except ValueError:
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line:
                try:
                    return json.loads(line)
                except ValueError:
                    return _PARSE_FAIL
        return _PARSE_FAIL


def _interpret(payload):
    """把解析出的 JSON 归一为 (outputs | None, err | None)。

    · {"ok": false, "err": {...}} → 失败(err 结构不合规则归一为 bug)。
    · {"ok": true, "out": {...}}  → 成功,outputs=out(兼容 secret-canary 基座形态)。
    · 其他 dict                   → 直出契约:整个 dict 就是 outputs。
    """
    if not isinstance(payload, dict):
        return None, make_error("bug", False, "采集器输出必须是 JSON 对象(dict)。")["err"]

    if payload.get("ok") is False:
        err = payload.get("err")
        if isinstance(err, dict) and {"kind", "retryable", "hint_for_agent"} <= set(err):
            kind = err["kind"] if err.get("kind") in ERR_KINDS else "bug"
            return None, {"kind": kind, "retryable": bool(err.get("retryable")),
                          "hint_for_agent": str(err.get("hint_for_agent"))}
        return None, make_error(
            "bug", False,
            "采集器报告失败但 err 结构不合规(应含 kind/retryable/hint_for_agent)。")["err"]

    if payload.get("ok") is True:
        out = payload.get("out")
        if isinstance(out, dict):
            return out, None
        return {k: v for k, v in payload.items() if k != "ok"}, None

    return payload, None


# —— 调度决策 ——

def _should_run(spec, st, now, today, eff_net_only, only):
    """是否本轮跑该模块。显式 only 最优先;其次 net-only 快路径闸;再按 mode 节流。"""
    if spec.id in only:
        return True                                # 显式请求(含 on_demand 触发)绕过一切节流
    if eff_net_only and not spec.net_only_ok:
        return False                               # 快路径只跑标记了 net_only_ok 的模块
    if spec.mode == "on_demand":
        return False                               # 常规轮次不跑,只由 only 触发
    if spec.mode == "daily_heavy":
        return st.get("last_heavy_date") != today  # 每天首次(无论成败标记 → 见 _run_module)
    # interval
    if spec.interval_s <= 0:
        return True                                # 0=每轮都跑(跟随全局)
    last = st.get("last_ok")
    if not last:
        return True                                # 从未成功过 → 跑
    try:
        return (now - datetime.fromisoformat(last)).total_seconds() >= spec.interval_s
    except (ValueError, TypeError):
        return True                                # 时间戳坏 → 保守重跑


# —— 单模块执行 + health 记账 ——

def _run_module(spec, st, now, today, board_dir, events):
    """跑一次采集器,更新 health/缓存,返回本模块要并入 data.inc 的 outputs(含 Stale 标记)。"""
    st["last_run"] = now.isoformat(timespec="seconds")
    if spec.mode == "daily_heavy":
        st["last_heavy_date"] = today              # 重活:无论成败都标记当天已尝试(避免反复起重进程)

    outputs, err = _invoke(spec)
    if err is None:
        verrs = validate_output(outputs, spec.output_schema_path)
        if verrs:
            err = make_error(
                "bug", False,
                "采集器输出不符合 output schema:%s" % "; ".join(verrs[:3]))["err"]

    if err is None:
        _record_ok(spec, st, now, events)
        _save_cache(board_dir, spec.id, outputs)
        emitted = dict(outputs)
        emitted["Stale"] = 0
        return emitted

    _record_fail(spec, st, err, events)
    emitted = dict(_load_cache(board_dir, spec.id))   # 失败沿用上次值(UI 不闪空)
    emitted["Stale"] = 1 if st["fail_streak"] >= STALE_THRESHOLD else 0
    return emitted


def _emit_cached(spec, st, board_dir):
    """本轮跳过(节流/快路径未选中):沿用缓存,Stale 依当前 fail_streak 决定。"""
    emitted = dict(_load_cache(board_dir, spec.id))
    emitted["Stale"] = 1 if st.get("fail_streak", 0) >= STALE_THRESHOLD else 0
    return emitted


def _record_ok(spec, st, now, events):
    """成功记账:清 fail_streak;若此前处于掉线态,恢复只 log 一次(HA log-when-unavailable)。"""
    was_down = st.get("fail_streak", 0) > 0
    st["fail_streak"] = 0
    st["last_ok"] = now.isoformat(timespec="seconds")
    st["last_err"] = None
    if was_down:
        events.append("recovered: %s" % spec.id)


def _record_fail(spec, st, err, events):
    """失败记账:fail_streak+1;掉线只在 0→1 那次 log(后续静默,避免刷屏)。"""
    prev = st.get("fail_streak", 0)
    st["fail_streak"] = prev + 1
    st["last_err"] = err
    if prev == 0:
        events.append("unavailable: %s (%s) %s"
                      % (spec.id, err["kind"], err["hint_for_agent"]))


# —— 契约加载(broken widget 只记不炸)——

def _load_specs(board_dir, lock, hmods, now, events):
    """按 lock 顺序加载各模块契约切片;widget.json 缺失/非法的模块只记 health 并跳过
    (拿不到 prefix,无法在 data.inc 里落位,交由排障工作流修好)。"""
    specs = []
    for mid in lock:
        mdir = os.path.join(board_dir, mid)
        st = hmods.setdefault(mid, _blank_health())
        if not os.path.isdir(mdir):
            err = make_error("bug", False,
                             "modules.lock 里的模块目录不存在:%s/" % mid)["err"]
            _record_fail_load(st, err, mid, events)
            continue
        try:
            widget = load_widget(mdir)
        except ContractError as e:
            err = make_error("bug", False,
                             "%s 的 widget.json 不合契约,先修好再采集。" % mid)["err"]
            _record_fail_load(st, err, mid, events)
            _ = e
            continue
        specs.append(_Spec(mid, mdir, widget))
    return specs


def _record_fail_load(st, err, mid, events):
    prev = st.get("fail_streak", 0)
    st["fail_streak"] = prev + 1
    st["last_err"] = err
    if prev == 0:
        events.append("unavailable: %s (%s) %s" % (mid, err["kind"], err["hint_for_agent"]))


# —— 聚合前的模块级隔离拍平 ——

def _isolate_flattenable(outputs, prefix_spec, hmods, events):
    """逐 prefix 单独试跑 to_inc:能安全拍平的保留;抛 ValueError 的模块丢弃其本轮输出、
    记一次 health bug(hint 指向"输出须为标量、勿嵌套"),再继续处理其余模块。

    为何逐模块而非整体 try/except:整体 try 会因一个坏模块令整轮 data.inc 写失败、冻结所有
    好模块(退化成源 collect.py 的行为)。逐模块试跑才是真隔离——坏模块本轮缺席不落 data.inc,
    好模块照常落盘,单模块挂死不拖垮整轮(核心不变量)。
    """
    safe = {}
    for prefix, kv in (outputs or {}).items():
        try:
            to_inc({prefix: kv})            # 单模块试拍平:不落盘,只校验能否安全拍平为标量变量
        except ValueError:
            spec = prefix_spec.get(prefix)
            st = hmods.get(spec.id) if spec is not None else None
            if spec is not None and st is not None:
                err = make_error(
                    "bug", False,
                    "模块输出无法拍平为 Rainmeter 变量,可能含嵌套 dict/list;"
                    "请让每个 output 值为标量(如 days[0]['tmax'] 拆成键 1Tmax)。")["err"]
                _record_fail(spec, st, err, events)
            continue
        safe[prefix] = kv
    return safe


# —— 主流程 ——

def run(board_dir, net_only=False, only=None, now=None):
    """跑一轮采集调度:调度决策 → subprocess 采集 → health 记账 → 汇总写 data.inc。

    参数:
      board_dir  板目录(其下 modules.lock.json + 每个 <id>/ 子目录含 widget.json/collector.py/band.inc)。
      net_only   True=只跑 refresh.net_only_ok=true 的模块(快路径)。
      only       可迭代的模块 id 集合,强制本轮跑这些(绕过节流;用于 on_demand 触发/手动刷新)。
      now        注入的当前时间(aware datetime);缺省 local_now()。测试用它模拟时间流逝。

    返回结果 dict(供测试/agent 消费):
      {generated_at, net_only(生效值), outputs{prefix:{...}}, health, ran[], skipped[],
       errors[], events[], data_inc}
    """
    board_dir = os.path.abspath(board_dir)
    now = now or local_now()
    today = now.strftime("%Y-%m-%d")
    only = set(only or [])

    lock = _load_lock(board_dir)
    os.makedirs(os.path.join(board_dir, "state"), exist_ok=True)
    os.makedirs(os.path.join(board_dir, "logs"), exist_ok=True)

    health = _read_json(os.path.join(board_dir, "health.json"),
                        {"done_date": None, "modules": {}})
    if not isinstance(health, dict):
        health = {"done_date": None, "modules": {}}
    hmods = health.setdefault("modules", {})

    events = []
    specs = _load_specs(board_dir, lock, hmods, now, events)

    # done_date 秒退:今日重活已全到位 → 后续触发退化为 net-only(只刷 net_only_ok 轻活),
    # 对应源"skip(done)+net"。前提=板里有 net_only 模块可刷,否则退化无意义、照常跑。
    done_fast = (not net_only and health.get("done_date") == today
                 and any(s.net_only_ok for s in specs))
    eff_net_only = bool(net_only or done_fast)

    outputs, ran, skipped = {}, [], []
    for spec in specs:
        st = hmods[spec.id]
        if _should_run(spec, st, now, today, eff_net_only, only):
            outputs[spec.prefix] = _run_module(spec, st, now, today, board_dir, events)
            ran.append(spec.id)
        else:
            outputs[spec.prefix] = _emit_cached(spec, st, board_dir)
            skipped.append(spec.id)

    # 重活全到位则记 done_date(供下轮秒退);无 daily_heavy 模块则不置(无重活可省)
    heavy = [s for s in specs if s.mode == "daily_heavy"]
    if heavy and all(hmods[s.id].get("last_heavy_date") == today for s in heavy):
        health["done_date"] = today

    # 模块级隔离拍平:逐 prefix 试跑 to_inc,坏输出(嵌套容器/非法键)只丢该模块并记 health bug,
    # 不让一个坏模块的 ValueError 崩掉整轮、冻结所有好模块的新数据(须在写 health/汇总 errors 之前)。
    prefix_spec = {s.prefix: s for s in specs}
    safe_outputs = _isolate_flattenable(outputs, prefix_spec, hmods, events)

    health["generated_at"] = now.isoformat(timespec="seconds")
    _write_json(os.path.join(board_dir, "health.json"), health)

    # 汇总能安全拍平的模块 outputs → data.inc(UTF-16,Rainmeter 中文不乱码)
    data_inc = os.path.join(board_dir, "data.inc")
    atomic_write(data_inc, to_inc(safe_outputs), encoding="utf-16")

    errors = ["%s: %s: %s" % (mid, m["last_err"]["kind"], m["last_err"]["hint_for_agent"])
              for mid, m in hmods.items() if m.get("last_err")]
    events.append("%s net_only=%s ran=[%s] skipped=[%s] errors=%d"
                  % (now.isoformat(timespec="seconds"), eff_net_only,
                     ",".join(ran), ",".join(skipped), len(errors)))
    _append_log(board_dir, events)

    return {"generated_at": health["generated_at"], "net_only": eff_net_only,
            "outputs": outputs, "health": health, "ran": ran, "skipped": skipped,
            "errors": errors, "events": events, "data_inc": data_inc}


def _load_lock(board_dir):
    path = os.path.join(board_dir, "modules.lock.json")
    data = _read_json(path, None)
    if not isinstance(data, dict) or not isinstance(data.get("modules"), list):
        raise ContractError(
            "板目录缺少可用的 modules.lock.json:%s" % path,
            hint="先跑 scripts/assemble.py 装配生成 modules.lock.json,再跑 orchestrator。")
    return list(data["modules"])


def _append_log(board_dir, lines):
    try:
        with open(os.path.join(board_dir, "logs", "orchestrator.log"),
                  "a", encoding="utf-8") as f:
            for l in lines:
                f.write(l + "\n")
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="桌面看板调度器:调度各模块采集器 → 写 data.inc")
    ap.add_argument("--board", required=True, help="板目录(含 modules.lock.json 与各模块子目录)")
    ap.add_argument("--net-only", action="store_true",
                    help="只跑 refresh.net_only_ok=true 的模块(快路径,仅刷轻量联网活)")
    ap.add_argument("--only", default=None,
                    help="逗号分隔的模块 id,强制本轮跑这些(绕过节流;用于 on_demand/手动刷新)")
    args = ap.parse_args(argv)

    board_dir = os.path.abspath(args.board)
    if not os.path.isdir(board_dir):
        print("板目录不存在:%s" % board_dir, file=sys.stderr)
        return 2
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    try:
        res = run(board_dir, net_only=args.net_only, only=only)
    except ContractError as e:
        print(json.dumps({"ok": False, "err": {"kind": "bug", "retryable": False,
                                               "hint_for_agent": str(e)}},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print("data.inc 已更新:%s(跑 %d,跳过 %d,错误 %d)"
          % (res["data_inc"], len(res["ran"]), len(res["skipped"]), len(res["errors"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
