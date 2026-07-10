# tests/test_task6_modules.py — Task 6 三模块(todo/github/server-status)确定性离线校验(不触网):
#   ① widget.json 过契约;② config.example 过 config.schema;③ band.inc 装配后过四布局不变量;
#   ④ 六模块拼板过四不变量 + prefix 无冲突;⑤ todo collector 离线跑通且过 output.schema;
#   ⑥ github / server-status 纯逻辑离线单测(色/相对时间/过滤/拍平/探测分支)。
# 触网的 github/server-status collector 活体自验见 task-6-report(离线不测,避免 CI 抖动)。
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "scripts"))
sys.path.insert(0, os.path.join(_REPO, "scripts", "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assemble as asm                                            # noqa: E402
from lib.contract import load_widget, validate_config, validate_output  # noqa: E402
from test_layout import check_all                                 # noqa: E402

MODULES = ["todo", "github", "server-status"]
ALL_SIX = ["clock-calendar", "weather", "net-latency", "todo", "github", "server-status"]
_MODROOT = os.path.join(_REPO, "modules")


def _mdir(mid):
    return os.path.join(_MODROOT, mid)


def _load_collector(mid):
    """按路径把 <module>/collector.py 作为唯一命名的独立模块导入(不撞 todo_action 的 `import collector`)。"""
    path = os.path.join(_mdir(mid), "collector.py")
    name = "col_%s" % mid.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _board_with(tmp_path, mids):
    board = tmp_path / "board"
    board.mkdir()
    for mid in mids:
        shutil.copytree(_mdir(mid), str(board / mid))
    return str(board)


def _assert_layout(text):
    bad = {k: v for k, v in check_all(text).items() if v}
    assert not bad, "布局不变量违规:%s" % bad


# —— ① widget 契约 ——

@pytest.mark.parametrize("mid", MODULES)
def test_widget_valid(mid):
    w = load_widget(_mdir(mid))                                  # 不合契约会抛 ContractError
    assert w["display"]["id"] == mid
    assert w["runtime"]["output"]["prefix"]


def test_todo_marked_interactive():
    w = load_widget(_mdir("todo"))
    assert w["runtime"]["band"]["interactive"] is True           # 交互旗舰


# —— ② config.example 过 config.schema ——

@pytest.mark.parametrize("mid", MODULES)
def test_config_example_valid(mid):
    w = load_widget(_mdir(mid))
    example = os.path.join(_mdir(mid), w["runtime"]["config"]["example"])
    schema = os.path.join(_mdir(mid), w["runtime"]["config"]["schema"])
    with open(example, encoding="utf-8") as f:
        cfg = json.load(f)
    errs = validate_config(cfg, schema)
    assert not errs, "%s config.example 不过 schema:%s" % (mid, errs)


# —— ③ 单模块装配后过四布局不变量 ——

@pytest.mark.parametrize("mid", MODULES)
def test_band_assembles_and_layout(tmp_path, mid):
    board = _board_with(tmp_path, [mid])
    res = asm.assemble(board, [mid], size="M")
    _assert_layout(res["ini_text"])


# —— ④ 六模块拼板:四不变量 + prefix/段名无冲突(assemble 内部校验,冲突会抛)——

def test_six_module_board_layout(tmp_path):
    board = _board_with(tmp_path, ALL_SIX)
    res = asm.assemble(board, ALL_SIX, size="M")                 # prefix/段名/保留段冲突会在此抛 AssembleError
    _assert_layout(res["ini_text"])
    assert res["height"] > 0
    # prefix 全局唯一显式断言
    prefixes = [load_widget(_mdir(m))["runtime"]["output"]["prefix"] for m in ALL_SIX]
    assert len(set(prefixes)) == len(prefixes), "prefix 冲突:%s" % prefixes
    assert set(prefixes) == {"Clk", "Wx", "Net", "Td", "Gh", "Srv"}


# —— ⑤ todo collector 离线跑通(无 todos.json → Count=0)且过 output.schema ——

def test_todo_collector_offline_output_valid(tmp_path):
    mdir = _mdir("todo")
    env = dict(os.environ)
    p = subprocess.run(
        [sys.executable, os.path.join(mdir, "collector.py"),
         "--config", os.path.join(mdir, "config.example.json")],
        capture_output=True, cwd=str(tmp_path), timeout=60, env=env)   # cwd=tmp:避免读到仓内 todos.json
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
    data = json.loads(p.stdout.decode("utf-8").strip().splitlines()[-1])
    assert "ok" not in data, "collector 报错:%s" % data
    errs = validate_output(data, os.path.join(mdir, "output.schema.json"))
    assert not errs, errs
    assert data["Count"] == 0 and data["Title"] == "待办"


# ============================================================
# ⑥ github 纯逻辑(离线)
# ============================================================

def test_github_lang_color():
    gh = _load_collector("github")
    assert gh.lang_color("Python") == "53,114,165,255"           # 大小写无关
    assert gh.lang_color("python") == "53,114,165,255"
    assert gh.lang_color("") == gh._LANG_UNKNOWN
    assert gh.lang_color("Brainfuck") == gh._LANG_UNKNOWN         # 未知 → 灰


def test_github_activity_label():
    gh = _load_collector("github")
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    assert gh.activity_label("2026-07-10T00:00:00Z", now) == "今天更新"
    assert gh.activity_label("2026-07-09T00:00:00Z", now) == "昨天更新"
    assert gh.activity_label("2026-07-05T00:00:00Z", now) == "5天前更新"
    assert gh.activity_label("2026-05-01T00:00:00Z", now).endswith("个月前更新")
    assert gh.activity_label("", now) == ""                       # 空 → 空
    assert gh.activity_label("garbage", now) == ""                # 解析失败 → 空


def test_github_filter_repos():
    gh = _load_collector("github")
    repos = [
        {"name": "app", "is_fork": False, "is_private": False, "pushed_at": "2026-07-01"},
        {"name": "forked", "is_fork": True, "is_private": False, "pushed_at": "2026-07-09"},
        {"name": "secret", "is_fork": False, "is_private": True, "pushed_at": "2026-07-08"},
        {"name": "octocat", "is_fork": False, "is_private": False, "pushed_at": "2026-07-05"},  # profile 仓
        {"name": "newer", "is_fork": False, "is_private": False, "pushed_at": "2026-07-10"},
    ]
    out = gh.filter_repos(repos, "octocat", include_forks=False)
    names = [r["name"] for r in out]
    assert names == ["newer", "app"]                              # 去 fork/私有/profile,按 pushed 降序
    # include_forks=True 时保留 fork
    out2 = gh.filter_repos(repos, "octocat", include_forks=True)
    assert "forked" in [r["name"] for r in out2]


def test_github_flatten_schema_strict():
    gh = _load_collector("github")
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    repos = [{"name": "app%d" % i, "is_fork": False, "is_private": False,
              "pushed_at": "2026-07-0%d" % (i + 1), "stars": i * 3,
              "url": "https://github.com/octocat/app%d" % i, "language": "Python"}
             for i in range(7)]                                   # 7 个,取前 5
    out = gh.flatten(repos, 4, "octocat", "gh", now)
    errs = validate_output(out, os.path.join(_mdir("github"), "output.schema.json"))
    assert not errs, errs
    assert out["Count"] == 5 and out["OpenPrTotal"] == 4
    assert out["StarsTotal"] == sum(i * 3 for i in range(7))      # StarsTotal 计全部,不止展示的 5
    assert out["Repo1DotColor"] == "53,114,165,255"


def test_github_flatten_pr_unknown():
    gh = _load_collector("github")
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    out = gh.flatten([], -1, "octocat", "rest", now)             # PR 取不到 → -1,不显示 PR 段
    assert out["OpenPrTotal"] == -1 and out["OpenPrText"] == ""
    assert "PR" not in out["SummaryText"]


# ============================================================
# ⑥ server-status 纯逻辑(离线)
# ============================================================

def test_server_http_color():
    srv = _load_collector("server-status")
    assert srv.http_color(200, 80) == "82,199,120,255"           # 2xx 快 → 绿
    assert srv.http_color(200, 900) == "230,180,80,255"          # 2xx 慢 → 黄
    assert srv.http_color(301, 50) == "82,199,120,255"           # 3xx → 在线(绿)
    assert srv.http_color(503, 50) == "232,110,110,255"          # 5xx → 红
    assert srv.http_color(404, 50) == "232,110,110,255"          # 4xx → 红
    assert srv.http_color(None, None) == "120,130,145,255"       # 无响应 → 灰


def test_server_ping_color():
    srv = _load_collector("server-status")
    assert srv.ping_color(50) == "82,199,120,255"
    assert srv.ping_color(150) == "230,180,80,255"
    assert srv.ping_color(300) == "232,110,110,255"
    assert srv.ping_color(None) == "120,130,145,255"


def test_server_measure_host_empty():
    srv = _load_collector("server-status")
    m = srv.measure_host({"label": "x"})                         # 既无 url 也无 ping_host → 灰空(不触网)
    assert m["ok"] == 0 and m["ms"] == -1 and m["color"] == "0,0,0,0" and m["text"] == ""


def test_server_collect_bad_hosts():
    srv = _load_collector("server-status")
    res = srv.collect({"hosts": "notalist"})
    assert res.get("ok") is False and res["err"]["kind"] == "bug"


def test_server_collect_empty_schema_strict():
    srv = _load_collector("server-status")
    out = srv.collect({"hosts": []})                             # 零主机 → 全空槽位(不触网)
    errs = validate_output(out, os.path.join(_mdir("server-status"), "output.schema.json"))
    assert not errs, errs
    assert out["Count"] == 0 and out["Title"] == "服务状态"
