# tests/test_official_modules.py — Task 5 官方三模块的确定性离线校验(不触网):
#   ① widget.json 过契约;② config.example 过 config.schema;③ band.inc 装配后过四布局不变量;
#   ④ 三模块拼板过不变量;⑤ clock-calendar collector 离线跑通且输出过 output.schema。
# 触网的 weather/net-latency collector 活体自验见 task-5-report(离线不测,避免 CI 抖动)。
import importlib.util
import json
import os
import re
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
from lib.inc_writer import temp_curve as _lib_temp_curve         # noqa: E402
from test_layout import check_all, parse_sections                # noqa: E402


def _load_collector(mid):
    """按路径把 <module>/collector.py 作为独立模块导入(仅 import 顶层 stdlib,不触网)。"""
    path = os.path.join(_mdir(mid), "collector.py")
    spec = importlib.util.spec_from_file_location("collector_%s" % mid.replace("-", "_"), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _path_ys(path_str):
    """Rainmeter Path 字符串(首点 + 若干 CurveTo)→ 所有 y 坐标列表(奇数位为 y)。"""
    ys = []
    for tok in path_str.split("|"):
        tok = tok.replace("CurveTo", "").strip()
        if not tok:
            continue
        nums = [float(x) for x in tok.split(",") if x.strip()]
        ys += nums[1::2]
    return ys

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


# ============================================================
# Task 5-fix drift-guard:范本卫生几项的回归锁(全离线,不触网)
# ============================================================

def _read_band(mid):
    w = load_widget(_mdir(mid))
    with open(os.path.join(_mdir(mid), w["runtime"]["band"]["file"]), encoding="utf-8") as f:
        return f.read()


def test_weather_geometry_single_source():
    """Imp-3:列 x 单一真源 —— band.inc 的 7 天列 X 一律引用 collector 输出的 #WxColnX#,
    且 Col*X 值 == collector.COLS_X。任一处回退硬编码或值漂移即红灯。"""
    wx = _load_collector("weather")
    flat = wx._flatten({})                                       # 纯几何,不触网
    cols = {k: v for k, v in flat.items() if re.fullmatch(r"Col\d+X", k)}
    # (a) collector 输出 Col1X..Col7X,顺序与值等于 COLS_X
    assert [cols["Col%dX" % (i + 1)] for i in range(len(wx.COLS_X))] == wx.COLS_X
    assert len(cols) == len(wx.COLS_X), "Col*X 数量应与 COLS_X 一致:%s" % cols
    # (b) band.inc 的每个 7 天列 meter(Label/Tmax/Tmin)X 必须引用对应 #WxColnX#,不得硬编码
    seen = set()
    for name, lines in parse_sections(_read_band("weather")).items():
        m = re.match(r"\[WxD(\d)(Label|Tmax|Tmin)\]$", name)
        if not m:
            continue
        xline = next((l for l in lines if l.startswith("X=")), None)
        assert xline == "X=#WxCol%sX#" % m.group(1), \
            "%s 的 X 应引用 #WxCol%sX#(几何单源),收到 %r" % (name, m.group(1), xline)
        seen.add("Col%sX" % m.group(1))
    # (c) band 引用的列变量集合 == collector 输出的列变量集合(无遗漏/多余)
    assert seen == set(cols), "band 列引用 %s ≠ collector Col*X %s" % (seen, set(cols))


def test_weather_temp_curve_matches_lib():
    """Imp-4:weather collector 内联的 _temp_curve 与 lib/inc_writer.temp_curve 等价。
    内联是刻意的自包含拷贝(模块要能拷走独立运行),此测防两处 Catmull-Rom 算法漂移。"""
    wx = _load_collector("weather")
    xs = wx.COLS_X
    cases = [
        ([12, 15, 9, 20, 18, 7, 14], 7, 20),
        ([5, 5, 5, 5, 5, 5, 5], 5, 5),                # 平温(span=0 兜底)
        ([10, None, 14, None, 9, 11, 13], 9, 14),     # 含缺测点
        ([8, 12], 8, 12),                             # 恰 2 点
        ([None, 9], 9, 9),                            # <2 有效点 → 空串
    ]
    for temps, vmin, vmax in cases:
        args = (temps, xs[:len(temps)], wx.CURVE_Y_TOP, wx.CURVE_Y_BOT, vmin, vmax)
        got, exp = wx._temp_curve(*args), _lib_temp_curve(*args)
        assert got == exp, "temp_curve 漂移 temps=%s:\n collector=%r\n lib      =%r" % (temps, got, exp)


def test_weather_curve_path_fits_band():
    """Imp-2:布局四不变量只认 Rectangle/Ellipse/Line,不校验 Path meter(曲线越带底测不出)。
    这里交叉校验曲线 meter 的定位 Y= + 生成 Path 的最大相对 y ≤ 带区高度,补上布局盲区。"""
    wx = _load_collector("weather")
    band_h = load_widget(_mdir("weather"))["runtime"]["band"]["height"]
    tmax = [15, 18, 12, 22, 20, 10, 16]
    tmin = [8, 10, 5, 14, 12, 2, 9]                   # 含 vmin=2(exercise 曲线到 y_bot)
    raw = {"provider": "open-meteo", "city": "x", "today": {},
           "days": [{"tmax": tmax[i], "tmin": tmin[i], "weather": "晴",
                     "date": "07-%02d" % (i + 1), "weekday": "周一", "rain_prob": 0}
                    for i in range(7)]}
    out = wx._flatten(raw)                            # 跑真实生成路径(不触网)
    assert out["MaxPath"] and out["MinPath"], "固定序列应生成非空 Path"
    max_rel_y = max(_path_ys(out["MaxPath"]) + _path_ys(out["MinPath"]))
    curve_ys = [int(l[2:]) for name, lines in parse_sections(_read_band("weather")).items()
                if "Curve" in name for l in lines if re.fullmatch(r"Y=\d+", l)]
    assert curve_ys, "band.inc 未找到曲线 meter 的数字 Y="
    curve_y = max(curve_ys)
    assert curve_y + max_rel_y <= band_h, \
        "曲线越带底:meter Y=%d + Path 最大相对 y=%.1f > 带高 %d" % (curve_y, max_rel_y, band_h)


def test_weather_flatten_output_schema_strict():
    """Minor:weather 完整扁平输出(含新增 Col*X)在 additionalProperties:false 下全过 output.schema。"""
    wx = _load_collector("weather")
    tmax = [15, 18, 12, 22, 20, 10, 16]
    tmin = [8, 10, 5, 14, 12, 2, 9]
    raw = {"provider": "open-meteo", "city": "北京",
           "days": [{"tmax": tmax[i], "tmin": tmin[i], "weather": "晴",
                     "date": "07-%02d" % (i + 1), "weekday": "周一", "rain_prob": 30}
                    for i in range(7)],
           "today": {"temp": 20, "feels": 19, "humidity": 55, "summary": "今日无雨"}}
    errs = validate_output(wx._flatten(raw), os.path.join(_mdir("weather"), "output.schema.json"))
    assert not errs, errs
