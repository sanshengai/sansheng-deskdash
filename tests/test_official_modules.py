# tests/test_official_modules.py — Task 5 官方三模块的确定性离线校验(不触网):
#   ① widget.json 过契约;② config.example 过 config.schema;③ band.inc 装配后过四布局不变量;
#   ④ 三模块拼板过不变量;⑤ clock-calendar collector 离线跑通且输出过 output.schema。
# 触网的 weather/net-latency collector 活体自验见 task-5-report(离线不测,避免 CI 抖动)。
import json
import os
import shutil
import subprocess
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "scripts"))
sys.path.insert(0, os.path.join(_REPO, "scripts", "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assemble as asm                                            # noqa: E402
from lib.contract import load_widget, validate_config, validate_output  # noqa: E402
from test_layout import check_all                                # noqa: E402

MODULES = ["clock-calendar", "weather", "net-latency"]
_MODROOT = os.path.join(_REPO, "modules")


def _mdir(mid):
    return os.path.join(_MODROOT, mid)


def _board_with(tmp_path, mids):
    board = tmp_path / "board"
    board.mkdir()
    for mid in mids:
        shutil.copytree(_mdir(mid), str(board / mid))
    return str(board)


def _assert_layout(text):
    bad = {k: v for k, v in check_all(text).items() if v}
    assert not bad, "布局不变量违规:%s" % bad


@pytest.mark.parametrize("mid", MODULES)
def test_widget_valid(mid):
    w = load_widget(_mdir(mid))                                  # 不合契约会抛 ContractError
    assert w["display"]["id"] == mid
    assert w["runtime"]["output"]["prefix"]


@pytest.mark.parametrize("mid", MODULES)
def test_config_example_valid(mid):
    w = load_widget(_mdir(mid))
    example = os.path.join(_mdir(mid), w["runtime"]["config"]["example"])
    schema = os.path.join(_mdir(mid), w["runtime"]["config"]["schema"])
    with open(example, encoding="utf-8") as f:
        cfg = json.load(f)
    errs = validate_config(cfg, schema)
    assert not errs, "%s config.example 不过 schema:%s" % (mid, errs)


@pytest.mark.parametrize("mid", MODULES)
def test_band_assembles_and_layout(tmp_path, mid):
    board = _board_with(tmp_path, [mid])
    res = asm.assemble(board, [mid], size="M")
    _assert_layout(res["ini_text"])


def test_three_module_board_layout(tmp_path):
    board = _board_with(tmp_path, MODULES)
    res = asm.assemble(board, MODULES, size="M")
    _assert_layout(res["ini_text"])
    assert res["height"] > 0


def test_clock_collector_offline_output_valid():
    """clock-calendar 零网络 → 离线可确定性跑通;输出过 output.schema(PIL 缺失则 CalReady=0 仍合法)。"""
    mdir = _mdir("clock-calendar")
    p = subprocess.run(
        [sys.executable, os.path.join(mdir, "collector.py"),
         "--config", os.path.join(mdir, "config.example.json")],
        capture_output=True, cwd=mdir, timeout=60)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
    data = json.loads(p.stdout.decode("utf-8").strip().splitlines()[-1])
    assert "ok" not in data, "collector 报错:%s" % data
    errs = validate_output(data, os.path.join(mdir, "output.schema.json"))
    assert not errs, errs
    assert data["CalReady"] in (0, 1)
