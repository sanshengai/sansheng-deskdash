# modules/todo/collector.py — 待办数据采集器(读 todos.json → 扁平变量;零网络零密钥)。
#
# 契约(与 orchestrator 的进程边界):`python collector.py --config <config.json>`,stdout 单行 JSON。
#   · 成功 = 扁平 outputs dict(键→标量);失败 = {"ok":false,"err":{kind,retryable,hint_for_agent}}。
#
# 职责拆分(交互旗舰模块,拆成两个脚本):
#   · collector.py(本文件)—— orchestrator 每轮跑:读 todos.json,渲染出 band 要用的扁平变量
#     (Row1Text/Row1Done/Row1Mark/… + Count),外加交互所需的部署变量(Config/Pyw/Script)。
#     这条路保证"冷启动 / 零交互"时看板也能显示当前待办(写进 data.inc)。
#   · todo_action.py —— 被 band.inc 的鼠标 Action 调用:add/click(双击防抖)/toggle/settext/del,
#     写回 todos.json 后立刻重渲 todos.inc(UTF-16,@Include2 覆盖 data.inc 同名变量)+ !Refresh,
#     给即时反馈(不必等 2 小时后的下一轮采集)。两条路共用 render_vars(),输出严格一致。
#
# 自包含:仅 stdlib;不 import 仓内 scripts/lib(模块在 board 里是扁平子目录,拿不到固定相对路径)。
# 安全铁律:无 eval/exec/shell=True;零网络零密钥;stdout 走 UTF-8 字节(Windows cp936 下 print 会乱码)。
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
TODOS = os.path.join(_HERE, "todos.json")          # 用户数据(gitignore);两脚本同源计算,路径一致
CLICKS = os.path.join(_HERE, ".clicks")            # 双击防抖点击流水(gitignore)

PREFIX = "Td"                                      # 输出变量前缀(与 widget.json output.prefix 一致)
MAX_ROWS = 6                                        # band.inc 固定 6 行;多余待办不显示(仍在 todos.json)


def _san(v):
    """变量值消毒:# / [ / ] 会被 Rainmeter 误解析,换行破坏 .inc 语法;None→空。
    与 lib/inc_writer._san 同语义(自包含内联,不 import lib)。"""
    if v is None:
        return ""
    return (str(v).replace("#", "＃").replace("[", "(").replace("]", ")")
            .replace("\n", " ").replace("\r", " ").strip())


def load_todos():
    """读 todos.json 的 todos 列表;缺文件/坏 JSON → 空列表(首次零待办也合法)。"""
    try:
        with open(TODOS, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("todos", []) if isinstance(data, dict) else []
        return items if isinstance(items, list) else []
    except (OSError, ValueError):
        return []


def save_todos(todos):
    """原子写 todos.json(先写临时文件再 os.replace,避免读方读到半截)。"""
    tmp = TODOS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"todos": todos}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, TODOS)


def render_vars(todos):
    """待办列表 → band 变量 dict(扁平标量;键不带 prefix)。collector 与 todo_action 共用,
    保证 data.inc 与 todos.inc 输出严格一致(单一真源,杜绝两处渲染漂移)。"""
    out = {"Count": len(todos), "Title": "待办", "AddLabel": "＋ 添加", "DelIcon": "✕"}
    for i in range(MAX_ROWS):
        n = i + 1
        t = todos[i] if i < len(todos) else None
        if t:
            done = 1 if t.get("done") else 0
            out["Row%dText" % n] = _san(t.get("t", ""))
            out["Row%dDone" % n] = done
            out["Row%dMark" % n] = "✓" if done else ""
            # 完成=灰(划线感)/未完成=亮;勾框描边色;删除× 可见色
            out["Row%dColor" % n] = "116,126,140,255" if done else "226,234,244,255"
            out["Row%dCheck" % n] = "52,199,120,255" if done else "255,255,255,70"
            out["Row%dDelColor" % n] = "150,160,172,200"
        else:                                       # 空槽位:变量存在但全透明(不显示)
            out["Row%dText" % n] = ""
            out["Row%dDone" % n] = 0
            out["Row%dMark" % n] = ""
            out["Row%dColor" % n] = "0,0,0,0"
            out["Row%dCheck" % n] = "0,0,0,0"
            out["Row%dDelColor" % n] = "0,0,0,0"
    return out


def _pythonw_path():
    """本机 pythonw.exe(GUI 无控制台,band Action 启动交互脚本不闪黑窗);无则退回当前解释器。"""
    exe = sys.executable or ""
    cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return cand if os.path.isfile(cand) else exe


def load_config(path):
    """读 config.json;缺失/坏 JSON → 默认。skin_name 供交互脚本 !Refresh 定向刷新。"""
    cfg = {"skin_name": "", "rainmeter_exe": ""}
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def collect(cfg):
    """采集待办 → 扁平 outputs。含 band Action 要用的部署变量(Config/Pyw/Script)。
    这些是本机运行时算出的绝对路径,只落 data.inc(gitignore),不入仓、不涉密钥。"""
    todos = load_todos()
    out = render_vars(todos)
    out["Config"] = str(cfg.get("skin_name") or "")
    out["Pyw"] = _pythonw_path()
    out["Script"] = os.path.join(_HERE, "todo_action.py")
    return out


def _emit(obj):
    """单行 JSON → stdout 强制 UTF-8 字节(避开 Windows cp936 与 orchestrator utf-8 解码不一致)。"""
    b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(b + b"\n")
    try:
        sys.stdout.buffer.flush()
    except OSError:
        pass


def _err(kind, retryable, hint):
    return {"ok": False, "err": {"kind": kind, "retryable": bool(retryable),
                                 "hint_for_agent": str(hint)}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="待办数据采集器(读 todos.json → 扁平变量)")
    ap.add_argument("--config", default=None, help="config.json 路径(可缺省)")
    args = ap.parse_args(argv)
    try:
        _emit(collect(load_config(args.config)))
        return 0
    except Exception as e:                          # 未预期异常 → 结构化 bug(不抛裸栈)
        _emit(_err("bug", False, "待办采集器未预期异常:%s" % type(e).__name__))
        return 1


if __name__ == "__main__":
    sys.exit(main())
