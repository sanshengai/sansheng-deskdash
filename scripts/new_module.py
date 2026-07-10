# scripts/new_module.py — 模块脚手架生成器:拷 templates/module-skeleton/ → modules/<id>/,
# 替换占位符(id / prefix / name),产出一个**直接过 validate_module.py** 的骨架(除采集器
# 未实现处由 validate 提示"还是骨架桩")。
#
# 用法:
#   python scripts/new_module.py <id>                 # 生成到仓内 modules/<id>/
#   python scripts/new_module.py <id> --dest <board>  # 生成到某个板目录 <board>/<id>/
#   python scripts/new_module.py <id> --force         # 目标已存在时覆盖
#
# 安全铁律:纯 stdlib;无 eval/exec/shell;只写目标模块目录。
import argparse
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_SKELETON = os.path.join(_REPO, "templates", "module-skeleton")

# id 规则与 widget.schema.json 的 display.id 一致:小写字母开头,小写字母/数字/连字符。
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def derive_prefix(mid):
    """id → 输出变量 prefix(CamelCase)。'my-nas' → 'MyNas';满足 ^[A-Za-z][A-Za-z0-9]*$。

    连字符分段各首字母大写后拼接;去掉非字母数字。首字符若非字母(理论上 id 已保证字母开头)兜底加 M。
    """
    parts = [p for p in mid.split("-") if p]
    camel = "".join(p[:1].upper() + p[1:] for p in parts)
    camel = re.sub(r"[^A-Za-z0-9]", "", camel)
    if not camel or not camel[0].isalpha():
        camel = "M" + camel
    return camel


def _skeleton_files():
    """module-skeleton 下要拷的文件名(跳过点文件如 .gitkeep)。"""
    return [f for f in sorted(os.listdir(_SKELETON))
            if os.path.isfile(os.path.join(_SKELETON, f)) and not f.startswith(".")]


def generate(mid, dest_root, force=False):
    """在 dest_root/<mid>/ 生成骨架。返回目标目录绝对路径。冲突/非法 id → 抛 ValueError。"""
    if not _ID_RE.match(mid):
        raise ValueError("非法模块 id %r:须小写字母开头,仅含小写字母/数字/连字符(如 my-nas)。" % mid)
    if not os.path.isdir(_SKELETON):
        raise ValueError("找不到骨架目录:%s" % _SKELETON)

    target = os.path.abspath(os.path.join(dest_root, mid))
    if os.path.exists(target):
        if not force:
            raise ValueError("目标已存在:%s(加 --force 覆盖,或换个 id)。" % target)
    else:
        os.makedirs(target)

    prefix = derive_prefix(mid)
    # 展示名:kebab-id → 标题化(my-nas → My Nas),作者可自行改成中文名
    display_name = " ".join(w.capitalize() for w in mid.replace("_", "-").split("-") if w) or mid
    subs = {"__ID__": mid, "__PREFIX__": prefix, "__NAME__": display_name}

    written = []
    for fn in _skeleton_files():
        with open(os.path.join(_SKELETON, fn), "r", encoding="utf-8") as f:
            text = f.read()
        for k, v in subs.items():
            text = text.replace(k, v)
        with open(os.path.join(target, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        written.append(fn)
    return target, prefix, written


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # 输出含中文;避开 Windows cp936(见 references/encoding.md)
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="生成新模块骨架(拷 module-skeleton + 替换占位符)")
    ap.add_argument("id", help="模块 id(=目录名;小写字母/数字/连字符,字母开头)")
    ap.add_argument("--dest", default=None,
                    help="目标根目录;缺省为仓内 modules/。给板目录即生成到 <board>/<id>/")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    args = ap.parse_args(argv)

    dest_root = os.path.abspath(args.dest) if args.dest else os.path.join(_REPO, "modules")
    try:
        target, prefix, written = generate(args.id, dest_root, force=args.force)
    except ValueError as e:
        print("生成失败:%s" % e, file=sys.stderr)
        return 2

    print("已生成模块骨架:%s" % target)
    print("  prefix = %s(输出变量前缀,band.inc 用 #%sXxx# 引用)" % (prefix, prefix))
    print("  文件   = %s" % ", ".join(written))
    print("")
    print("下一步(照 references/contribution.md):")
    print("  1) 编辑 %s/collector.py 写真实采集逻辑(删掉 DESKDASH-SKELETON-STUB 标记行)。" % args.id)
    print("  2) 按输出补 %s/output.schema.json 与 %s/band.inc;填 widget.json 的 privacy/deps。" % (args.id, args.id))
    print("  3) 跑校验直到全绿:python scripts/validate_module.py %s" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
