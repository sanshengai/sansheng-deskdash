# tests/test_assemble.py — 带区装配器测试。
# 两个最小 fixture 模块(demo-a/demo-b)装配:过四布局不变量、段偏移正确、
# prefix 冲突被拒、超预算报错含可裁模块名、modules.lock 回写。
import json
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "scripts"))
import assemble as asm  # noqa: E402
from assemble import AssembleError, SIZE_PROFILES, assemble  # noqa: E402
from test_layout import check_all, parse_sections  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


_board_seq = [0]


def _board(tmp_path, mods=("demo-a", "demo-b")):
    """把 fixture 模块拷进一个唯一命名的临时板目录(避免污染仓内 fixtures / 同测复用冲突)。"""
    _board_seq[0] += 1
    board = tmp_path / ("board%d" % _board_seq[0])
    board.mkdir()
    for mid in mods:
        shutil.copytree(os.path.join(_FIXTURES, mid), str(board / mid))
    return str(board)


def _section_y(sections, name):
    """取某段的数字 Y= 值(无则 None)。"""
    for l in sections.get(name, []):
        m = re.match(r"Y=(\d+)$", l)
        if m:
            return int(m.group(1))
    return None


# —— 装配产物过四不变量 ——

def test_assembled_passes_all_invariants(tmp_path):
    res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="M")
    v = check_all(res["ini_text"])
    assert all(x == [] for x in v.values()), v


def test_return_shape(tmp_path):
    res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="M")
    assert set(res) == {"ini_text", "height", "lock"}
    assert isinstance(res["ini_text"], str) and "[Rainmeter]" in res["ini_text"]
    assert res["lock"] == ["demo-a", "demo-b"]
    assert isinstance(res["height"], int)


# —— 段偏移正确:第二段顶 = 第一段顶 + 第一段高 + 段距 ——

def test_band_offsets(tmp_path):
    prof = SIZE_PROFILES["M"]
    res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="M")
    s = parse_sections(res["ini_text"])

    a_top = prof["first_y"]                     # 60
    b_top = a_top + 120 + prof["gap"]           # 60 + 120 + 20 = 200

    # demo-a 首个 meter Y=6 → a_top+6;demo-b 标题 Y=14 → b_top+14
    assert _section_y(s, "[DemoTime]") == a_top + 6
    assert _section_y(s, "[InfoTitle]") == b_top + 14
    # demo-a 定位 meter 的 Y= 落位,内部 shape 不动(仍 0,0)
    assert _section_y(s, "[DemoBar]") == a_top + 70
    assert "Shape=Rectangle 0,0,120,6,3 | FillColor #cAccent#" in res["ini_text"]
    # demo-b 无定位 meter 的 shape 绝对 y 落位:局部 4 → b_top+4
    assert ("Shape=Rectangle #PAD#,%d,388,90,8" % (b_top + 4)) in res["ini_text"]


def test_divider_between_bands(tmp_path):
    prof = SIZE_PROFILES["M"]
    res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="M")
    s = parse_sections(res["ini_text"])
    # 段间分隔线在间距中点:(60+120) + gap//2
    expect = (prof["first_y"] + 120) + prof["gap"] // 2
    assert "[BandDiv1]" in s
    assert ("Shape=Rectangle #PAD#,%d,(#W#-2*#PAD#),1" % expect) in res["ini_text"]


def test_total_height(tmp_path):
    prof = SIZE_PROFILES["M"]
    res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="M")
    # 末带区底 + 底部留白
    expect = (prof["first_y"] + 120 + prof["gap"] + 100) + prof["bottom"]
    assert res["height"] == expect
    # H 变量注入模板
    assert ("H=%d" % expect) in res["ini_text"]


def test_size_affects_height(tmp_path):
    s_res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="S")
    l_res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="L")
    assert s_res["height"] < l_res["height"]     # S 档间距/留白更小 → 更矮


# —— prefix 冲突被拒 ——

def test_prefix_conflict_rejected(tmp_path):
    board = _board(tmp_path, mods=("demo-a",))
    # 克隆 demo-a 为 demo-c,但保留同一 prefix "Demo" → 冲突
    clone = os.path.join(board, "demo-c")
    shutil.copytree(os.path.join(_FIXTURES, "demo-a"), clone)
    wj = os.path.join(clone, "widget.json")
    data = json.load(open(wj, encoding="utf-8"))
    data["display"]["id"] = "demo-c"            # id 必须等目录名
    # prefix 保持 "Demo" 不变
    json.dump(data, open(wj, "w", encoding="utf-8"), ensure_ascii=False)

    with pytest.raises(AssembleError) as ei:
        assemble(board, ["demo-a", "demo-c"], size="M")
    msg = str(ei.value)
    assert "prefix" in msg and "Demo" in msg
    assert "demo-a" in msg and "demo-c" in msg


# —— 段名跨模块冲突被拒 ——

def test_section_name_conflict_rejected(tmp_path):
    board = _board(tmp_path, mods=("demo-a",))
    clone = os.path.join(board, "demo-d")
    shutil.copytree(os.path.join(_FIXTURES, "demo-a"), clone)
    wj = os.path.join(clone, "widget.json")
    data = json.load(open(wj, encoding="utf-8"))
    data["display"]["id"] = "demo-d"
    data["runtime"]["output"]["prefix"] = "Dee"   # 换 prefix,只留段名冲突
    json.dump(data, open(wj, "w", encoding="utf-8"), ensure_ascii=False)
    # band.inc 仍用 [DemoTime] 等段名 → 与 demo-a 段名冲突
    with pytest.raises(AssembleError) as ei:
        assemble(board, ["demo-a", "demo-d"], size="M")
    assert "段名" in str(ei.value)


# —— 超预算报错含可裁模块名 ——

def test_over_budget_names_tallest(tmp_path):
    with pytest.raises(AssembleError) as ei:
        assemble(_board(tmp_path), ["demo-a", "demo-b"], size="M", height_budget=100)
    msg = str(ei.value)
    assert "超预算" in msg
    assert "demo-a" in msg               # demo-a 高 120,是最高的可裁模块
    assert "120" in msg                  # 列出各模块高度
    # 结构化错误可被 agent 消费
    err = ei.value.to_error()
    assert err["ok"] is False and err["err"]["kind"] == "bug"


def test_under_budget_ok(tmp_path):
    res = assemble(_board(tmp_path), ["demo-a", "demo-b"], size="M", height_budget=10000)
    assert res["height"] < 10000


# —— modules.lock.json 回写 ——

def test_lock_written(tmp_path):
    board = _board(tmp_path)
    res = assemble(board, ["demo-a", "demo-b"], size="M")
    lock_path = os.path.join(board, "modules.lock.json")
    assert os.path.isfile(lock_path)
    lock = json.load(open(lock_path, encoding="utf-8"))
    assert lock["modules"] == ["demo-a", "demo-b"]
    assert lock["size"] == "M"
    assert lock["height"] == res["height"]


# —— 缺模块目录 / 未知档 / 空 lock 的守卫 ——

def test_missing_module_dir(tmp_path):
    with pytest.raises(AssembleError):
        assemble(_board(tmp_path), ["demo-a", "nope"], size="M")


def test_unknown_size(tmp_path):
    with pytest.raises(AssembleError):
        assemble(_board(tmp_path), ["demo-a"], size="XL")


def test_empty_lock(tmp_path):
    with pytest.raises(AssembleError):
        assemble(_board(tmp_path), [], size="M")


def test_id_dir_mismatch(tmp_path):
    board = _board(tmp_path, mods=("demo-a",))
    wj = os.path.join(board, "demo-a", "widget.json")
    data = json.load(open(wj, encoding="utf-8"))
    data["display"]["id"] = "somethingelse"      # id ≠ 目录名
    json.dump(data, open(wj, "w", encoding="utf-8"), ensure_ascii=False)
    with pytest.raises(AssembleError) as ei:
        assemble(board, ["demo-a"], size="M")
    assert "不一致" in str(ei.value)
