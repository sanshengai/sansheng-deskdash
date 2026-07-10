# scripts/shift_band.py — Rainmeter 皮肤纵向平移工具(带定位语义)。
#
# 装配器(assemble.py)复用本文件的 shift() 把每个模块的 band.inc(局部 Y,原点在带区顶)
# 整体下移到目标绝对 Y;也可作独立 CLI 对整张皮肤做补偿平移。
#
# 定位约定(布局铁律,tests/test_layout.py 强制,band.inc 作者必须遵守):
#   · meter 自带 Y= 选项定位  → 内部 Shape 一律相对坐标(原点锚定,y ≤ 8),平移只动 Y= 选项;
#   · meter 不带 Y=(默认 0,0)→ 内部 Shape 携带绝对 y,平移动 Shape 的 y 参数。
# 反例教训:一次性正则脚本把有 Y= 定位 meter 的相对 Shape 也一起 +dy(底板/色点双重下移),
# 自此所有纵向平移必须走本工具的 shift(),不再手写正则。
#
# 语义限制(band.inc 作者须知):
#   · 只认数字字面量的 Y=(\d+) 与 Rectangle/Ellipse/Line 的 y 参数;
#   · 动态定位(Y=(公式) / Y=#变量#)与 Path/自定义 shape 的坐标不会被平移 ——
#     需要被装配平移的坐标请用数字字面量;需要动态定位的 meter 请自行保证与带区顶相对无关。
import io
import os
import re
import sys

# Shape 类型 → 携带 y 的参数下标(从 0 数,首参 x)
_Y_PARAMS = {"Rectangle": [1], "Ellipse": [1], "Line": [1, 3]}


def _iter_sections(lines):
    """→ [(section名, [行号...])],便于按 meter 判断有无 Y= 选项。"""
    out, cur, idx = [], None, []
    for i, l in enumerate(lines):
        if l.startswith("["):
            if cur is not None:
                out.append((cur, idx))
            cur, idx = l.strip(), []
        elif cur is not None:
            idx.append(i)
    if cur is not None:
        out.append((cur, idx))
    return out


def shift(lines, from_y, dy):
    """把所有绝对 y ≥ from_y 的定位(Y= 选项 / 无定位 meter 的 Shape y)加上 dy。

    返回 (新行列表, 改动条数)。语义见文件头。
    装配用法:band.inc 局部坐标整体落位 → shift(band_lines, 0, 目标顶Y)。
    """
    lines = list(lines)
    changed = 0
    for sec, idx in _iter_sections(lines):
        has_y = any(re.match(r"Y=\d+$", lines[i]) for i in idx)
        for i in idx:
            m = re.match(r"^Y=(\d+)$", lines[i])
            if m and int(m.group(1)) >= from_y:
                lines[i] = "Y=%d" % (int(m.group(1)) + dy)
                changed += 1
                continue
            m = re.match(r"^(Shape\d*)=(Rectangle|Ellipse|Line)\s+(.*)$", lines[i])
            if m and not has_y:                     # 仅无定位 meter 的 Shape 才是绝对坐标
                head, *mods = [a.strip() for a in m.group(3).split("|")]
                ps = [p.strip() for p in head.split(",")]
                hit = False
                for ix in _Y_PARAMS[m.group(2)]:
                    if ix < len(ps) and re.fullmatch(r"-?\d+(\.\d+)?", ps[ix]) \
                            and float(ps[ix]) >= from_y:
                        ps[ix] = str(int(float(ps[ix])) + dy)
                        hit = True
                if hit:
                    lines[i] = "%s=%s %s" % (m.group(1), m.group(2),
                                             ",".join(ps) + "".join(" | " + x for x in mods))
                    changed += 1
    return lines, changed


def main():
    args = [a for a in sys.argv[1:] if a != "--dry"]
    if len(args) != 3:
        print("用法: shift_band.py <皮肤文件> <起始Y> <偏移量> [--dry]")
        sys.exit(2)
    src, from_y, dy = args[0], int(args[1]), int(args[2])
    lines = io.open(src, encoding="utf-8").read().splitlines()
    new, n = shift(lines, from_y, dy)
    print("改动 %d 处(起始Y=%d, dy=%+d)" % (n, from_y, dy))
    if "--dry" in sys.argv:
        for a, b in zip(lines, new):
            if a != b:
                print("  -", a[:70], "\n  +", b[:70])
        return
    io.open(src, "w", encoding="utf-8", newline="\n").write("\n".join(new) + "\n")
    print("已写盘;请跑 pytest 验证布局不变量后再部署。")


if __name__ == "__main__":
    main()
