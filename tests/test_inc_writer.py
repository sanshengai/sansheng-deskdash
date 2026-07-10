# tests/test_inc_writer.py — lib/inc_writer 单测:to_inc 拍平/拒容器、_san 消毒、贝塞尔曲线
import pytest

from lib.inc_writer import _san, fmt_time, temp_curve, temp_points, to_inc


# —— to_inc 正常路径(Task 1 验收样例) ——

def test_to_inc_basic():
    inc = to_inc({"Wx": {"TempNow": 32, "City": "长沙"}})
    assert inc.startswith("[Variables]")
    assert "WxTempNow=32" in inc
    assert "WxCity=长沙" in inc


def test_to_inc_multi_module_and_types():
    inc = to_inc({"Clock": {"Hour": 7, "Greeting": "早"},
                  "Net": {"ClaudeMs": 183.5, "Ok": True, "Down": False, "Hint": None}})
    for expect in ["ClockHour=7", "ClockGreeting=早",
                   "NetClaudeMs=183.5",
                   "NetOk=1", "NetDown=0",     # bool → 1/0,不落 "True"/"False" 字面量
                   "NetHint="]:                 # None → 空
        assert expect in inc, "缺少变量行: %s" % expect


def test_to_inc_value_sanitized():
    inc = to_inc({"Wx": {"Now": "现在 32° #标签 [注]\n第二行"}})
    assert "WxNow=现在 32° ＃标签 (注) 第二行" in inc


def test_to_inc_empty():
    assert to_inc({}).startswith("[Variables]")
    assert to_inc(None).startswith("[Variables]")


# —— to_inc 拒绝容器值:模块须自行拍平 ——

def test_to_inc_rejects_list():
    with pytest.raises(ValueError, match="自行拍平"):
        to_inc({"Wx": {"Days": [1, 2, 3]}})


def test_to_inc_rejects_nested_dict():
    with pytest.raises(ValueError, match="自行拍平"):
        to_inc({"Wx": {"Today": {"tmax": 35}}})


def test_to_inc_rejects_non_dict_module_output():
    with pytest.raises(ValueError, match="须是 dict"):
        to_inc({"Wx": [("City", "长沙")]})


def test_to_inc_rejects_bad_key():
    with pytest.raises(ValueError, match="非空字符串"):
        to_inc({"Wx": {1: "x"}})


# —— _san 消毒 ——

def test_san():
    assert _san(None) == ""
    assert _san("  边距  ") == "边距"
    assert _san("a#b[c]d") == "a＃b(c)d"                 # #/[] 是 Rainmeter 元字符
    assert _san("两\n行\r也一行") == "两 行 也一行"
    assert _san(0) == "0"


# —— fmt_time ——

def test_fmt_time():
    assert fmt_time("2026-07-10T08:05:00+08:00") == "08:05"
    assert fmt_time("") == ""
    assert fmt_time(None) == ""
    assert fmt_time("not-a-time") == ""


# —— 温度曲线:锚点换算 + 贝塞尔(迁自源仓 test_temp_curve_bezier_and_shared_scale) ——

def test_temp_points_shared_scale_and_none_skip():
    pts = temp_points([35, None, 20], [10, 20, 30], 100, 140, 20, 35)
    assert pts == [(10, 100.0), (30, 140.0)]             # None 跳过;vmax→y_top,vmin→y_bot


def test_temp_curve_bezier_and_shared_scale():
    assert temp_curve([None], [63], 118, 144, 20, 35) == ""       # <2 点→空
    p = temp_curve([35, 20], [63, 152], 118, 144, 20, 35)
    assert p.startswith("63.0,118.0 | ")                 # 最高温 35=vmax→y_top(118)
    assert "CurveTo 152.0,144.0," in p                   # 终点=最低温 20=vmin→y_bot(144)
    p3 = temp_curve([35, 20, 30], [63, 152, 241], 118, 144, 20, 35)
    assert p3.count("CurveTo") == 2                      # 每段一个贝塞尔,无密集折线
    assert "LineTo" not in p3
