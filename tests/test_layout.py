# tests/test_layout.py — 皮肤布局四不变量(防"平移类"排版回归),参数化为对任意 skin 文本跑。
#
# 迁自私有仓 tests/test_skin_layout.py:原版硬绑单一皮肤文件,这里改成纯函数吃 skin 文本,
# 既测手写的好/坏样例,也测 assemble.py 的装配产物(见文件尾 + test_assemble.py 复用)。
#
# 四不变量:
#   1) 有 Y= 定位的 meter,内部 Shape 必须原点锚定(y ≤ 8)—— 双重平移会立即打破;
#   2) 无定位的 meter,Shape 携带绝对 y(≥ 40),否则会画进品牌栏(白名单例外);
#   3) 分隔线(段名含 Div)沿文件顺序严格递增且不重合;
#   4) 内容不超面板高度 H(最深顶 + 14 ≤ H)。
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "scripts"))
from shift_band import shift  # noqa: E402

_Y_PARAMS = {"Rectangle": [1], "Ellipse": [1], "Line": [1, 3]}
# 品牌栏(首条分隔线以上)少数 meter 以绝对小 y 作画,属已知例外;装配模板里是背景面板。
DEFAULT_BRAND_WHITELIST = frozenset({"[Panel]"})


# —— 解析与取坐标(纯函数,test_assemble 复用)——

def parse_sections(text):
    """skin 文本 → {段名: [段内行...]},保持出现顺序。"""
    out, sec = {}, None
    for l in text.splitlines():
        if l.startswith("["):
            sec = l.strip()
            out[sec] = []
        elif sec is not None:
            out[sec].append(l)
    return out


def _shape_ys(ls):
    """段内每条 Rectangle/Ellipse/Line 的数字 y 坐标 → (y, 行文本)。"""
    import re
    for l in ls:
        m = re.match(r"Shape\d*=(Rectangle|Ellipse|Line)\s+(.*)", l)
        if not m:
            continue
        ps = [p.strip() for p in m.group(2).split("|")[0].split(",")]
        for ix in _Y_PARAMS[m.group(1)]:
            if ix < len(ps) and re.fullmatch(r"-?\d+(\.\d+)?", ps[ix]):
                yield float(ps[ix]), l


def _has_y(ls):
    import re
    return any(re.match(r"Y=\d+$", l) for l in ls)


def violations_positioned_origin_anchored(sections):
    bad = []
    for sec, ls in sections.items():
        if not _has_y(ls):
            continue
        bad += ["%s: %s" % (sec, l[:60]) for y, l in _shape_ys(ls) if y > 8]
    return bad


def violations_unpositioned_absolute(sections, whitelist=DEFAULT_BRAND_WHITELIST):
    bad = []
    for sec, ls in sections.items():
        if sec in whitelist or _has_y(ls):
            continue
        bad += ["%s: %s" % (sec, l[:60]) for y, l in _shape_ys(ls) if y < 40]
    return bad


def violations_dividers_ascending(sections):
    """段名含 Div 的分隔线,沿文件顺序取各自首个 shape y,须严格递增。"""
    ys = []
    for sec, ls in sections.items():
        if "Div" not in sec:
            continue
        first = next((y for y, _ in _shape_ys(ls)), None)
        if first is not None:
            ys.append((sec, first))
    seq = [y for _, y in ys]
    if seq != sorted(seq) or len(set(seq)) != len(seq):
        return ["分隔线未严格递增: %s" % ys]
    return []


def violations_content_fits(sections):
    import re
    h = None
    for l in sections.get("[Variables]", []):
        m = re.match(r"H=(\d+)$", l)
        if m:
            h = int(m.group(1))
    if not h:
        return ["[Variables] 里找不到数字 H"]
    tops = []
    for sec, ls in sections.items():
        for l in ls:
            m = re.match(r"Y=(\d+)$", l)
            if m:
                tops.append((int(m.group(1)), sec))
        if not _has_y(ls):
            tops += [(int(y), sec) for y, _ in _shape_ys(ls)]
    if not tops:
        return []
    worst = max(tops)
    if worst[0] + 14 > h:
        return ["内容超出面板底部: %s Y=%d (H=%d)" % (worst[1], worst[0], h)]
    return []


def check_all(text, whitelist=DEFAULT_BRAND_WHITELIST):
    """跑齐四不变量,返回 {不变量名: [违规...]};全空 = 通过。"""
    s = parse_sections(text)
    return {
        "positioned_origin_anchored": violations_positioned_origin_anchored(s),
        "unpositioned_absolute": violations_unpositioned_absolute(s, whitelist),
        "dividers_ascending": violations_dividers_ascending(s),
        "content_fits": violations_content_fits(s),
    }


def assert_layout_ok(text, whitelist=DEFAULT_BRAND_WHITELIST):
    v = check_all(text, whitelist)
    bad = {k: x for k, x in v.items() if x}
    assert not bad, "布局不变量违规:\n" + "\n".join(
        "[%s]\n  %s" % (k, "\n  ".join(x)) for k, x in bad.items())


# ============================================================
# 样例:一张手写的、结构合法的最小皮肤
# ============================================================

GOOD_SKIN = """\
[Variables]
W=420
H=300
PAD=16
[Panel]
Meter=Shape
Shape=Rectangle 0,0,#W#,#H#,13 | FillColor 1,2,3
[BandDiv0]
Meter=Shape
Shape=Rectangle #PAD#,48,388,1 | FillColor 4,5,6
[CardBg]
Meter=Shape
Shape=Rectangle #PAD#,60,388,80,8 | FillColor 7,8,9
[Title]
Meter=String
X=28
Y=70
Text=hi
[Bar]
Meter=Shape
Y=100
Shape=Rectangle 0,0,120,6,3 | FillColor 1,1,1
[BandDiv1]
Meter=Shape
Shape=Rectangle #PAD#,160,388,1 | FillColor 4,5,6
[Foot]
Meter=String
X=28
Y=180
Text=bye
"""


def test_good_skin_passes_all_four():
    assert_layout_ok(GOOD_SKIN)


def test_check_all_shape():
    v = check_all(GOOD_SKIN)
    assert set(v) == {"positioned_origin_anchored", "unpositioned_absolute",
                      "dividers_ascending", "content_fits"}
    assert all(x == [] for x in v.values())


# —— 每个不变量的红灯样例 ——

def test_positioned_meter_double_shift_caught():
    # 回归:有 Y= 定位的 meter,内部 Shape 也被平移到大坐标(双重下移)。
    bad = GOOD_SKIN.replace("Shape=Rectangle 0,0,120,6,3 | FillColor 1,1,1",
                            "Shape=Rectangle 0,100,120,6,3 | FillColor 1,1,1")
    assert violations_positioned_origin_anchored(parse_sections(bad))


def test_unpositioned_small_coord_caught():
    # 无定位 meter 的图元跑到品牌栏(y<40 且不在白名单)。
    bad = GOOD_SKIN.replace("Shape=Rectangle #PAD#,60,388,80,8 | FillColor 7,8,9",
                            "Shape=Rectangle #PAD#,10,388,80,8 | FillColor 7,8,9")
    assert violations_unpositioned_absolute(parse_sections(bad))


def test_panel_whitelisted_not_flagged():
    # [Panel] 背景 y=0 属白名单例外,不应被 unpositioned 不变量误判。
    assert violations_unpositioned_absolute(parse_sections(GOOD_SKIN)) == []
    # 去掉白名单后 [Panel] 立即被抓 → 证明确实靠白名单豁免
    assert violations_unpositioned_absolute(parse_sections(GOOD_SKIN), whitelist=frozenset())


def test_dividers_out_of_order_caught():
    bad = GOOD_SKIN.replace("Shape=Rectangle #PAD#,160,388,1 | FillColor 4,5,6",
                            "Shape=Rectangle #PAD#,20,388,1 | FillColor 4,5,6")
    # BandDiv1 现在 y=20 < BandDiv0 y=48 → 非递增
    assert violations_dividers_ascending(parse_sections(bad))


def test_content_overflow_caught():
    bad = GOOD_SKIN.replace("H=300", "H=150")   # Foot@180 + 14 > 150
    assert violations_content_fits(parse_sections(bad))


# ============================================================
# shift() 工具语义(迁自私有仓,红灯锁定平移语义)
# ============================================================

def test_shift_band_tool_semantics():
    """定位 meter 只移 Y=,不动内部;无定位 meter 移 Shape y;起始线以上不动。"""
    lines = [
        "[A]", "Meter=Shape", "Y=500", "Shape=Rectangle 0,0,42,18,9 | FillColor 1,2,3",
        "[B]", "Meter=Shape", "Shape=Ellipse 60,499,5 | FillColor 1,2,3",
        "[C]", "Meter=String", "Y=100",
    ]
    new, n = shift(lines, 200, 16)
    assert "Y=516" in new                                          # 定位 meter:Y= 移
    assert "Shape=Rectangle 0,0,42,18,9 | FillColor 1,2,3" in new  # 内部不动
    assert "Shape=Ellipse 60,515,5 | FillColor 1,2,3" in new       # 无定位:绝对 y 移
    assert "Y=100" in new and n == 2                               # 起始线以上不动


def test_shift_band_local_to_absolute():
    """装配用法:from_y=0 时把整段局部坐标下移 dy(全部落位)。"""
    lines = [
        "[Card]", "Meter=Shape", "Shape=Rectangle 16,4,388,90,8 | FillColor 1,1,1",
        "[Title]", "Meter=String", "Y=14",
    ]
    new, n = shift(lines, 0, 200)
    assert "Shape=Rectangle 16,204,388,90,8 | FillColor 1,1,1" in new
    assert "Y=214" in new and n == 2


# ============================================================
# 装配产物过四不变量(与 test_assemble 互补:这里只认最终布局合规)
# ============================================================

def test_assembled_product_passes_layout(tmp_path):
    import shutil
    import assemble as asm
    fixtures = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    board = tmp_path / "board"
    board.mkdir()
    for mid in ("demo-a", "demo-b"):
        shutil.copytree(os.path.join(fixtures, mid), str(board / mid))
    res = asm.assemble(str(board), ["demo-a", "demo-b"], size="M")
    assert_layout_ok(res["ini_text"])
