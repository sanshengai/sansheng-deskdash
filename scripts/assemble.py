# scripts/assemble.py — 带区装配器(P0 核心新件)。
#
# 把若干模块各自的 band.inc(局部 Y,原点在带区顶)按 modules.lock 顺序自上而下拼成一整张
# Rainmeter 皮肤 .ini。不自研布局引擎:落位只走 shift_band.shift() 的平移语义,四布局不变量
# (tests/test_layout.py)兜底。
#
# 装配算法:
#   · 首带区顶 = 品牌行下方基线(size 档决定,见 SIZE_PROFILES.first_y);
#   · 第 i 带区顶 = 上带区顶 + 上带区 height + 段间距(gap);
#   · 每带区 band.inc 局部坐标整体平移 dy = 该带区顶(shift(lines, 0, 顶Y));
#   · 相邻带区之间插一条分隔线(位于间距中点);
#   · 总高 H = 末带区底 + 底部留白(bottom)。
#
# 编码:产出 UTF-8 源文本(部署转 UTF-16 由 Task 7 deploy 脚本负责,本模块不做转换)。
# 数据一律走 @Include 变量,皮肤段绝不内联中文(见 references/encoding.md 的 GBK 桥)。
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)                 # 让 `import shift_band` 在 CLI/测试两种入口都可用
if os.path.join(_HERE, "lib") not in sys.path:
    sys.path.insert(0, os.path.join(_HERE, "lib"))

from shift_band import shift                  # noqa: E402
try:                                          # 兼容两种导入根(conftest 把 scripts/ 入 path)
    from lib.contract import load_widget, ContractError
except ImportError:                           # 直接以 scripts/ 为根时
    from contract import load_widget, ContractError  # type: ignore


_TEMPLATE_PATH = os.path.join(os.path.dirname(_HERE), "templates", "skin-base", "Dash.ini.tpl")

# 尺寸档位:font=活动字号;first_y=首带区顶(须 > 首分隔线 y=48);gap=段间距;bottom=底部留白。
# size 主要调字号与间距/留白(带区自身 height 由各模块声明,平移不缩放内容);
# 换 S 档能压缩段间距与留白,给超预算腾一点空间(真正的内容压缩留 P1 的紧凑 band 变体)。
SIZE_PROFILES = {
    "S": {"font": 9,  "first_y": 54, "gap": 12, "bottom": 12},
    "M": {"font": 11, "first_y": 60, "gap": 20, "bottom": 16},
    "L": {"font": 13, "first_y": 66, "gap": 28, "bottom": 20},
}
_FIRST_DIVIDER_Y = 48   # 与模板 [BandDiv0] 一致;首带区必须落在它下方


class AssembleError(Exception):
    """装配失败(结构化)。message=人话主因;details=逐条清单;hint=给 agent 的下一步。

    agent 可读 .to_error() 拿到 {"ok":false,"err":{...}} 形态用于分诊/与用户商量。
    保证不回显任何密钥值(装配只读结构/坐标,不碰 config 密钥)。
    """

    def __init__(self, message, details=None, hint=None):
        self.message = message
        self.details = list(details or [])
        self.hint = hint
        full = message
        if self.details:
            full += "\n- " + "\n- ".join(self.details)
        if hint:
            full += "\n提示:" + hint
        super().__init__(full)

    def to_error(self):
        return {"ok": False, "err": {"kind": "bug", "retryable": False,
                                     "hint_for_agent": str(self)}}


def _read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _section_names(lines):
    """带区文本里的所有段头 [Xxx](含中括号)。"""
    return [l.strip() for l in lines if l.startswith("[")]


def _divider_section(name, y):
    """一条与模板首分隔线同款的段间分隔线(无定位 meter,绝对 y)。"""
    return "\n".join([
        "[%s]" % name,
        "Meter=Shape",
        "Shape=Rectangle #PAD#,%d,(#W#-2*#PAD#),1 | FillColor #cDivider#" % y,
        "DynamicVariables=1",
    ])


def _load_modules(board_dir, modules_lock):
    """按 lock 顺序读齐每个模块的契约与 band.inc;返回统一结构列表。"""
    mods = []
    for mid in modules_lock:
        mdir = os.path.join(board_dir, mid)
        if not os.path.isdir(mdir):
            raise AssembleError(
                "找不到模块目录:%s" % mdir,
                hint="modules.lock 里的每个 id 必须对应 <board>/<id>/ 目录。")
        try:
            widget = load_widget(mdir)         # 结构非法直接抛 ContractError
        except ContractError as e:
            raise AssembleError(
                "模块 %s 的 widget.json 不合契约" % mid,
                details=[str(e)],
                hint="先修好该模块 widget.json 再装配(见 schemas/widget.schema.json)。")
        disp_id = widget["display"]["id"]
        if disp_id != mid:
            raise AssembleError(
                "模块目录名与 display.id 不一致:目录 %s ≠ id %s" % (mid, disp_id),
                hint="约定 id == 目录名;改目录名或改 widget.json 的 display.id 使其一致。")
        band = widget["runtime"]["band"]
        band_file = os.path.join(mdir, band["file"])
        if not os.path.isfile(band_file):
            raise AssembleError(
                "模块 %s 声明的带区文件不存在:%s" % (mid, band_file),
                hint="widget.json 的 runtime.band.file 要指向模块目录内真实存在的 .inc。")
        band_lines = _read_text(band_file).splitlines()
        mods.append({
            "id": mid,
            "prefix": widget["runtime"]["output"]["prefix"],
            "height": band["height"],
            "band_lines": band_lines,
        })
    return mods


def _check_uniqueness(mods):
    """输出 prefix 全局唯一 + 带区段名不跨模块重名(两者都会在最终 .ini 里静默互相覆盖)。"""
    # 1) prefix 唯一
    by_prefix = {}
    for m in mods:
        by_prefix.setdefault(m["prefix"], []).append(m["id"])
    dup_prefix = {p: ids for p, ids in by_prefix.items() if len(ids) > 1}
    if dup_prefix:
        details = ["prefix '%s' 被这些模块共用:%s" % (p, ", ".join(ids))
                   for p, ids in sorted(dup_prefix.items())]
        raise AssembleError(
            "输出 prefix 冲突(必须全局唯一)",
            details=details,
            hint="每个模块 runtime.output.prefix 唯一;改掉其中一个模块的 prefix(连带其 band.inc 变量名)。")
    # 2) 段名唯一
    by_section = {}
    for m in mods:
        for sec in _section_names(m["band_lines"]):
            by_section.setdefault(sec, []).append(m["id"])
    dup_sec = {s: ids for s, ids in by_section.items() if len(ids) > 1}
    if dup_sec:
        details = ["段名 %s 被这些模块共用:%s" % (s, ", ".join(ids))
                   for s, ids in sorted(dup_sec.items())]
        raise AssembleError(
            "带区段名跨模块冲突(会在最终 .ini 里互相覆盖)",
            details=details,
            hint="band.inc 的段名建议带模块 prefix 前缀(如 [Wx...]),保证跨模块唯一。")


def assemble(board_dir, modules_lock, size="M", height_budget=None):
    """装配整张皮肤 .ini。

    参数:
      board_dir     板目录,其下每个 <id>/ 子目录含 widget.json + band.inc。
      modules_lock  list[str],模块 id 的自上而下顺序。
      size          "S"|"M"|"L",档位(字号 + 间距 + 留白)。
      height_budget int 或 None;给定且总高超预算 → 抛 AssembleError(含各模块高度与可裁模块)。

    返回 {"ini_text": <完整 .ini>, "height": <int 总高>, "lock": <回写的顺序 list>}。
    副作用:把 modules.lock.json 写到 board_dir。
    """
    if size not in SIZE_PROFILES:
        raise AssembleError(
            "未知尺寸档 %r" % size,
            hint="size 只能是 %s 之一。" % "/".join(sorted(SIZE_PROFILES)))
    if not modules_lock:
        raise AssembleError("modules_lock 为空:没有可装配的模块。",
                            hint="至少给一个模块 id;起步板见 templates/starter-boards/。")
    prof = SIZE_PROFILES[size]

    mods = _load_modules(board_dir, modules_lock)
    _check_uniqueness(mods)

    # —— 自上而下排布 ——
    blocks = []
    y = prof["first_y"]
    prev_bottom = None
    for i, m in enumerate(mods):
        if i > 0:
            div_y = prev_bottom + prof["gap"] // 2      # 间距中点插分隔线
            blocks.append(_divider_section("BandDiv%d" % i, div_y))
        shifted, _ = shift(m["band_lines"], 0, y)       # 局部坐标整体落位到 y
        blocks.append("; ---- band: %s (top=%d, height=%d) ----\n%s"
                      % (m["id"], y, m["height"], "\n".join(shifted)))
        prev_bottom = y + m["height"]
        y = prev_bottom + prof["gap"]
    total_h = prev_bottom + prof["bottom"]

    # —— 高度预算 ——
    if height_budget is not None and total_h > height_budget:
        by_h = sorted(mods, key=lambda m: m["height"], reverse=True)
        tallest = by_h[0]
        details = ["%s:高 %d" % (m["id"], m["height"]) for m in by_h]
        raise AssembleError(
            "总高 %d 超预算 %d(超 %d)" % (total_h, height_budget, total_h - height_budget),
            details=details,
            hint="建议裁掉最高的模块 %s(高 %d),或换 S 档压缩间距/留白后重装配。"
                 % (tallest["id"], tallest["height"]))

    # —— 填模板 ——
    data_inc = os.path.abspath(os.path.join(board_dir, "data.inc"))
    todos_inc = os.path.abspath(os.path.join(board_dir, "todos.inc"))
    tpl = _read_text(_TEMPLATE_PATH)
    ini_text = (tpl.replace("{{H}}", str(total_h))
                   .replace("{{SIZE_FONT}}", str(prof["font"]))
                   .replace("{{DATA_INC}}", data_inc)
                   .replace("{{TODOS_INC}}", todos_inc)
                   .replace("{{BANDS}}", "\n\n".join(blocks)))

    # —— 回写 modules.lock.json ——
    lock = {
        "version": 1,
        "generated_by": "scripts/assemble.py",
        "size": size,
        "height": total_h,
        "modules": list(modules_lock),
    }
    with open(os.path.join(board_dir, "modules.lock.json"), "w", encoding="utf-8") as f:
        json.dump(lock, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {"ini_text": ini_text, "height": total_h, "lock": list(modules_lock)}


# —— CLI ——

def _resolve_order(board_dir, modules_arg):
    """确定模块顺序:--modules 显式 > 现存 modules.lock.json > 扫描子目录(字母序)。"""
    if modules_arg:
        return [s.strip() for s in modules_arg.split(",") if s.strip()]
    lock_path = os.path.join(board_dir, "modules.lock.json")
    if os.path.isfile(lock_path):
        with open(lock_path, "r", encoding="utf-8") as f:
            return list(json.load(f).get("modules", []))
    subs = [d for d in sorted(os.listdir(board_dir))
            if os.path.isfile(os.path.join(board_dir, d, "widget.json"))]
    return subs


def main(argv=None):
    ap = argparse.ArgumentParser(description="装配带区为整张 Rainmeter 皮肤 .ini")
    ap.add_argument("--board", required=True, help="板目录(其下每个 <id>/ 含 widget.json+band.inc)")
    ap.add_argument("--size", default="M", choices=sorted(SIZE_PROFILES), help="尺寸档 S/M/L")
    ap.add_argument("--budget", type=int, default=None, help="高度预算(超则报错并给可裁模块)")
    ap.add_argument("--modules", default=None, help="逗号分隔的模块顺序(覆盖 lock/扫描)")
    ap.add_argument("--out", default=None, help="输出 .ini 路径(缺省打印到 stdout)")
    args = ap.parse_args(argv)

    board_dir = os.path.abspath(args.board)
    if not os.path.isdir(board_dir):
        print("板目录不存在:%s" % board_dir, file=sys.stderr)
        return 2
    order = _resolve_order(board_dir, args.modules)
    try:
        res = assemble(board_dir, order, size=args.size, height_budget=args.budget)
    except (AssembleError, ContractError) as e:
        print(json.dumps(e.to_error() if isinstance(e, AssembleError)
                         else {"ok": False, "err": {"kind": "bug", "retryable": False,
                                                    "hint_for_agent": str(e)}},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(res["ini_text"])
        print("已写出:%s(总高 %d,%d 个模块)" % (args.out, res["height"], len(res["lock"])))
    else:
        sys.stdout.write(res["ini_text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
