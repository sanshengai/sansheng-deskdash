# tests/test_orchestrator.py — 调度器测试(纯本地,零真实网络)。
#
# 用内联 fixture 模块(真 collector.py 脚本,orchestrator 用 subprocess 真跑)覆盖:
#   四路径:正常并入 / 超时被杀记 fail / 坏 JSON 归 bug / 结构化 err 记 health;
#   validate_output 拒非法输出;{"ok":true,"out":{}} 兼容;
#   interval 节流(未到沿用缓存)/ daily_heavy 每日一次 / net-only 只跑标记模块 /
#   done_date 秒退 / fail_streak≥3 注入 Stale / 掉线只 log 一次 + 恢复 log 一次;
#   缺 lock 报错 / 坏 widget 只记不炸 / CLI main。
import json
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "scripts"))
import orchestrator as orch  # noqa: E402
from lib.common import local_now  # noqa: E402
from lib.contract import ContractError  # noqa: E402


# —— fixture 构造 ——

_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"Temp": {"type": "integer"}, "City": {"type": "string"}},
}

# 常用 collector 源(独立脚本,忽略 --config;打印单行 JSON)
def _ok_src(temp=32):
    return "import json\nprint(json.dumps({'Temp': %d, 'City': 'demo'}))\n" % temp

SRC_OK_OUT = "import json\nprint(json.dumps({'ok': True, 'out': {'Temp': 5}}))\n"
SRC_ERR = ("import json\nprint(json.dumps({'ok': False, 'err': "
           "{'kind': 'network', 'retryable': True, 'hint_for_agent': 'connect timeout'}}))\n")
SRC_BADJSON = "print('this is definitely not json')\n"
SRC_TIMEOUT = "import time\ntime.sleep(3)\n"
SRC_BAD_TYPE = "import json\nprint(json.dumps({'Temp': 'not-a-number'}))\n"


def _widget(mid, prefix, *, mode="interval", interval_s=0, net_only_ok=False,
            timeout_s=60, height=100):
    return {
        "display": {
            "id": mid, "name": mid, "name_en": mid, "version": "0.1.0",
            "author": "sansheng", "license": "MIT", "category": "system",
            "screenshot": "screenshot.png",
        },
        "runtime": {
            "entry": "collector.py",
            "refresh": {"mode": mode, "interval_s": interval_s, "net_only_ok": net_only_ok},
            "timeout_s": timeout_s,
            "deps": [],
            "output": {"prefix": prefix, "schema": "output.schema.json"},
            "config": {"schema": "config.schema.json", "example": "config.example.json",
                       "secrets": []},
            "privacy": {"network": [], "local_read": [], "local_write": []},
            "band": {"file": "band.inc", "height": height, "interactive": False},
        },
    }


def _mod(board, mid, prefix, src, *, widget=None, **kw):
    """在 board 下建一个模块目录(widget.json / output.schema.json / config.example.json /
    collector.py)。返回模块目录。可反复调用同一 mid 覆盖 collector.py(模拟采集器行为变化)。"""
    mdir = os.path.join(board, mid)
    os.makedirs(mdir, exist_ok=True)
    w = widget if widget is not None else _widget(mid, prefix, **kw)
    _dump(os.path.join(mdir, "widget.json"), w)
    _dump(os.path.join(mdir, "output.schema.json"), _OUTPUT_SCHEMA)
    _dump(os.path.join(mdir, "config.example.json"), {})
    with open(os.path.join(mdir, "collector.py"), "w", encoding="utf-8") as f:
        f.write(src)
    return mdir


def _set_collector(board, mid, src):
    with open(os.path.join(board, mid, "collector.py"), "w", encoding="utf-8") as f:
        f.write(src)


def _lock(board, ids, size="M"):
    _dump(os.path.join(board, "modules.lock.json"),
          {"version": 1, "size": size, "height": 999, "modules": list(ids)})


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def _health(board):
    with open(os.path.join(board, "health.json"), encoding="utf-8") as f:
        return json.load(f)


def _data_inc(board):
    with open(os.path.join(board, "data.inc"), encoding="utf-16") as f:
        return f.read()


# ============================================================
# 四路径
# ============================================================

def test_normal_merges_output(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", _ok_src(32))
    _lock(board, ["demo"])
    res = orch.run(board)

    assert res["ran"] == ["demo"] and res["skipped"] == []
    assert res["outputs"]["Demo"]["Temp"] == 32
    assert res["outputs"]["Demo"]["City"] == "demo"
    assert res["outputs"]["Demo"]["Stale"] == 0
    # health:成功 → fail_streak 0、有 last_ok、无 last_err
    h = _health(board)["modules"]["demo"]
    assert h["fail_streak"] == 0 and h["last_ok"] and h["last_err"] is None
    # data.inc 落盘 UTF-16,带前缀拍平
    inc = _data_inc(board)
    assert "DemoTemp=32" in inc and "DemoCity=demo" in inc and "DemoStale=0" in inc


def test_ok_out_form_supported(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", SRC_OK_OUT)
    _lock(board, ["demo"])
    res = orch.run(board)
    assert res["outputs"]["Demo"]["Temp"] == 5


def test_structured_err_recorded_in_health(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", SRC_ERR)
    _lock(board, ["demo"])
    res = orch.run(board)

    assert res["ran"] == ["demo"]               # 它跑了,只是失败
    h = _health(board)["modules"]["demo"]
    assert h["fail_streak"] == 1
    assert h["last_err"]["kind"] == "network"
    assert h["last_err"]["retryable"] is True
    assert h["last_ok"] is None
    # 首次失败无缓存 → 只有 Stale(streak<3 → 0)
    assert res["outputs"]["Demo"] == {"Stale": 0}
    # 掉线首次 log 一次
    assert sum(e.startswith("unavailable: demo") for e in res["events"]) == 1


def test_bad_json_is_bug(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", SRC_BADJSON)
    _lock(board, ["demo"])
    orch.run(board)
    assert _health(board)["modules"]["demo"]["last_err"]["kind"] == "bug"


def test_timeout_killed_and_recorded(tmp_path):
    board = str(tmp_path)
    _mod(board, "slow", "Slow", SRC_TIMEOUT, timeout_s=1)
    _lock(board, ["slow"])
    res = orch.run(board)
    h = _health(board)["modules"]["slow"]
    assert h["fail_streak"] == 1
    assert h["last_err"]["kind"] == "provider"       # 超时归 provider
    assert h["last_err"]["retryable"] is True
    assert "超时" in h["last_err"]["hint_for_agent"]
    assert res["outputs"]["Slow"] == {"Stale": 0}


def test_validate_output_rejects_bad_type(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", SRC_BAD_TYPE)          # Temp 是字符串,schema 要 integer
    _lock(board, ["demo"])
    orch.run(board)
    err = _health(board)["modules"]["demo"]["last_err"]
    assert err["kind"] == "bug"
    assert "schema" in err["hint_for_agent"]


# ============================================================
# 节流:interval / daily_heavy
# ============================================================

def test_interval_throttle_reuses_cache(tmp_path):
    board = str(tmp_path)
    _mod(board, "wx", "Wx", _ok_src(1), mode="interval", interval_s=300)
    _lock(board, ["wx"])
    t0 = local_now()

    r1 = orch.run(board, now=t0)
    assert r1["ran"] == ["wx"] and r1["outputs"]["Wx"]["Temp"] == 1

    # 改采集器输出为 2;间隔未到 → 跳过、沿用缓存(仍是 1,证明没起进程)
    _set_collector(board, "wx", _ok_src(2))
    r2 = orch.run(board, now=t0 + timedelta(seconds=100))
    assert r2["ran"] == [] and r2["skipped"] == ["wx"]
    assert r2["outputs"]["Wx"]["Temp"] == 1

    # 超过间隔 → 重跑,取到新值 2
    r3 = orch.run(board, now=t0 + timedelta(seconds=400))
    assert r3["ran"] == ["wx"] and r3["outputs"]["Wx"]["Temp"] == 2


def test_interval_zero_runs_every_round(tmp_path):
    board = str(tmp_path)
    _mod(board, "wx", "Wx", _ok_src(1), mode="interval", interval_s=0)
    _lock(board, ["wx"])
    t0 = local_now()
    assert orch.run(board, now=t0)["ran"] == ["wx"]
    assert orch.run(board, now=t0 + timedelta(seconds=1))["ran"] == ["wx"]


def test_daily_heavy_once_per_day(tmp_path):
    board = str(tmp_path)
    _mod(board, "hv", "Hv", _ok_src(1), mode="daily_heavy")
    _lock(board, ["hv"])
    t0 = local_now()

    r1 = orch.run(board, now=t0)
    assert r1["ran"] == ["hv"] and r1["outputs"]["Hv"]["Temp"] == 1
    assert _health(board)["done_date"] == t0.strftime("%Y-%m-%d")

    # 同日再触发 → 跳过(即便采集器已改成输出 2)
    _set_collector(board, "hv", _ok_src(2))
    r2 = orch.run(board, now=t0 + timedelta(hours=2))
    assert r2["skipped"] == ["hv"] and r2["outputs"]["Hv"]["Temp"] == 1

    # 次日 → 重跑,取新值 2
    r3 = orch.run(board, now=t0 + timedelta(days=1))
    assert r3["ran"] == ["hv"] and r3["outputs"]["Hv"]["Temp"] == 2


def test_daily_heavy_marks_date_even_on_failure(tmp_path):
    board = str(tmp_path)
    _mod(board, "hv", "Hv", SRC_ERR, mode="daily_heavy")   # 失败也标记当天(源同款:避免反复起重活)
    _lock(board, ["hv"])
    t0 = local_now()
    orch.run(board, now=t0)
    r2 = orch.run(board, now=t0 + timedelta(hours=1))
    assert r2["skipped"] == ["hv"]                          # 失败当天不再重试


# ============================================================
# net-only 快路径 + done_date 秒退
# ============================================================

def test_net_only_runs_only_marked_modules(tmp_path):
    board = str(tmp_path)
    _mod(board, "net", "Net", _ok_src(1), net_only_ok=True)
    _mod(board, "loc", "Loc", _ok_src(1), net_only_ok=False)
    _lock(board, ["net", "loc"])

    orch.run(board)                                # 先常规跑一轮,populate 两模块缓存
    _set_collector(board, "net", _ok_src(9))
    _set_collector(board, "loc", _ok_src(9))
    r = orch.run(board, net_only=True)
    assert r["net_only"] is True
    assert r["ran"] == ["net"] and r["skipped"] == ["loc"]
    assert r["outputs"]["Net"]["Temp"] == 9        # net 刷新了
    assert r["outputs"]["Loc"]["Temp"] == 1        # loc 沿用缓存,没起进程


def test_done_date_fast_exit_degrades_to_net_only(tmp_path):
    board = str(tmp_path)
    _mod(board, "hv", "Hv", _ok_src(1), mode="daily_heavy", net_only_ok=False)
    _mod(board, "net", "Net", _ok_src(1), mode="interval", interval_s=0, net_only_ok=True)
    _mod(board, "plain", "Plain", _ok_src(1), mode="interval", interval_s=0, net_only_ok=False)
    _lock(board, ["hv", "net", "plain"])
    t0 = local_now()

    r1 = orch.run(board, now=t0)
    assert set(r1["ran"]) == {"hv", "net", "plain"}
    assert _health(board)["done_date"] == t0.strftime("%Y-%m-%d")

    # 同日再触发:done_date==today 且有 net_only 模块 → 秒退为 net-only,
    # 连 interval_s=0 的 plain(平时每轮都跑)也被跳过,只剩 net 刷。
    r2 = orch.run(board, now=t0 + timedelta(minutes=30))
    assert r2["net_only"] is True
    assert r2["ran"] == ["net"]
    assert set(r2["skipped"]) == {"hv", "plain"}


# ============================================================
# fail_streak≥3 注入 Stale + 掉线只 log 一次 + 恢复 log 一次
# ============================================================

def test_fail_streak_injects_stale_and_logs_once(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", SRC_ERR)
    _lock(board, ["demo"])
    t0 = local_now()

    events_all = []
    for i in range(3):
        r = orch.run(board, now=t0 + timedelta(seconds=i))
        events_all += r["events"]

    h = _health(board)["modules"]["demo"]
    assert h["fail_streak"] == 3
    # 第 3 次失败后注入 Stale=1
    assert r["outputs"]["Demo"]["Stale"] == 1
    # 掉线只在 0→1 那次 log 一次(后两次静默)
    assert sum(e.startswith("unavailable: demo") for e in events_all) == 1


def test_recovery_logs_once(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", SRC_ERR)
    _lock(board, ["demo"])
    t0 = local_now()

    r1 = orch.run(board, now=t0)
    assert sum(e.startswith("unavailable") for e in r1["events"]) == 1

    _set_collector(board, "demo", _ok_src(7))
    r2 = orch.run(board, now=t0 + timedelta(seconds=1))
    assert sum(e.startswith("recovered: demo") for e in r2["events"]) == 1
    h = _health(board)["modules"]["demo"]
    assert h["fail_streak"] == 0 and h["last_err"] is None
    assert r2["outputs"]["Demo"]["Temp"] == 7 and r2["outputs"]["Demo"]["Stale"] == 0


def test_stale_cleared_after_recovery(tmp_path):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", SRC_ERR)
    _lock(board, ["demo"])
    t0 = local_now()
    for i in range(3):
        orch.run(board, now=t0 + timedelta(seconds=i))
    _set_collector(board, "demo", _ok_src(7))
    r = orch.run(board, now=t0 + timedelta(seconds=10))
    assert r["outputs"]["Demo"]["Stale"] == 0     # 恢复后灰化解除


# ============================================================
# on_demand / --only
# ============================================================

def test_on_demand_skipped_normally_but_only_forces(tmp_path):
    board = str(tmp_path)
    _mod(board, "od", "Od", _ok_src(1), mode="on_demand")
    _lock(board, ["od"])
    assert orch.run(board)["skipped"] == ["od"]                 # 常规轮次不跑
    assert orch.run(board, only=["od"])["ran"] == ["od"]        # 显式请求才跑


# ============================================================
# 守卫:缺 lock / 坏 widget
# ============================================================

def test_missing_lock_raises(tmp_path):
    with pytest.raises(ContractError):
        orch.run(str(tmp_path))


def test_broken_widget_skipped_not_crash(tmp_path):
    board = str(tmp_path)
    _mod(board, "good", "Good", _ok_src(1))
    # 坏模块:widget.json 非法(缺 runtime)
    bad = os.path.join(board, "bad")
    os.makedirs(bad)
    _dump(os.path.join(bad, "widget.json"), {"display": {}})
    _lock(board, ["good", "bad"])

    res = orch.run(board)                          # 不炸
    assert res["outputs"]["Good"]["Temp"] == 1     # 好模块照常并入
    assert "Good" in res["outputs"]
    # 坏模块记进 health(拿不到 prefix,不落 data.inc)
    hb = _health(board)["modules"]["bad"]
    assert hb["fail_streak"] == 1 and hb["last_err"]["kind"] == "bug"


def test_missing_module_dir_recorded(tmp_path):
    board = str(tmp_path)
    _mod(board, "good", "Good", _ok_src(1))
    _lock(board, ["good", "ghost"])                # ghost 目录不存在
    res = orch.run(board)
    assert res["outputs"]["Good"]["Temp"] == 1
    assert _health(board)["modules"]["ghost"]["last_err"]["kind"] == "bug"


# ============================================================
# 模块级隔离:坏输出(嵌套 dict/list)不崩整轮,好模块照常落盘
# ============================================================

# 输出含嵌套 dict + list:能过宽松 schema(type:object),但 to_inc 无法拍平为标量
SRC_NESTED = "import json\nprint(json.dumps({'Blob': {'a': 1}, 'Arr': [2, 3]}))\n"


def test_bad_nested_output_isolated_not_crash_whole_round(tmp_path):
    board = str(tmp_path)
    _mod(board, "good", "Good", _ok_src(21))                 # 正常标量模块
    bad = _mod(board, "bad", "Bad", SRC_NESTED)              # 嵌套输出模块
    _dump(os.path.join(bad, "output.schema.json"), {"type": "object"})  # 宽松 schema:放行嵌套
    _lock(board, ["good", "bad"])

    # ① run() 不抛异常,正常返回
    res = orch.run(board)
    assert res["outputs"]["Good"]["Temp"] == 21              # 好模块照常并入

    # ② data.inc 含正常模块变量;④ 不含坏模块半拉子内容(整段缺席,连前缀都不出现)
    inc = _data_inc(board)
    assert "GoodTemp=21" in inc and "GoodCity=demo" in inc and "GoodStale=0" in inc
    assert "Bad" not in inc

    # ③ 坏模块记了 health bug 失败
    hb = _health(board)["modules"]["bad"]
    assert hb["last_err"]["kind"] == "bug"
    assert hb["fail_streak"] == 1
    # 好模块 health 不受牵连
    hg = _health(board)["modules"]["good"]
    assert hg["fail_streak"] == 0 and hg["last_ok"]


# ============================================================
# CLI
# ============================================================

def test_cli_main_ok(tmp_path, capsys):
    board = str(tmp_path)
    _mod(board, "demo", "Demo", _ok_src(1))
    _lock(board, ["demo"])
    rc = orch.main(["--board", board])
    assert rc == 0
    assert "data.inc 已更新" in capsys.readouterr().out
    assert os.path.isfile(os.path.join(board, "data.inc"))


def test_cli_missing_board(capsys):
    rc = orch.main(["--board", os.path.join("no", "such", "board_xyz")])
    assert rc == 2
