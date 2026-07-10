# scripts/gen_readme_gallery.py — 从 registry/registry.json 单源生成 README 的模块画廊表。
#
# 幂等:只覆盖 README 里 <!-- GALLERY:START --> 与 <!-- GALLERY:END --> 之间的内容,
# 其余内容原样保留;重跑结果稳定(可安全接进 CI / pre-commit)。
#
# 用法:
#   python scripts/gen_readme_gallery.py                 # 更新 README.md(中文) + README_EN.md(英文)
#   python scripts/gen_readme_gallery.py --check         # 只检查是否已是最新(不写盘;CI 用,漂了退非零)
#   python scripts/gen_readme_gallery.py --readme README.md --lang zh
#
# 纯 stdlib;无网络;只读 registry.json + 读写指定 README。
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_REGISTRY = os.path.join(_ROOT, "registry", "registry.json")

START = "<!-- GALLERY:START -->"
END = "<!-- GALLERY:END -->"

# tier 徽章(展示用;评级由社区机器人写 registry,作者禁自评 —— 见 references/contribution.md)
_TIER_BADGE = {"bronze": "🥉 Bronze", "silver": "🥈 Silver", "gold": "🥇 Gold"}

_HEADERS = {
    "zh": ("截图", "模块", "类目", "评级", "说明"),
    "en": ("Preview", "Module", "Category", "Tier", "What it does"),
}
_HINT = {
    "zh": "> 本表由 `scripts/gen_readme_gallery.py` 从 `registry/registry.json` 单源生成,请勿手改。",
    "en": "> This table is generated from `registry/registry.json` by `scripts/gen_readme_gallery.py`; do not edit by hand.",
}


def load_registry(path=_REGISTRY):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _thumb(screenshot):
    """截图缩略图 + 链接到原图(GitHub 渲染 <img>;缺图时退化为纯文本占位)。"""
    return ('<a href="%s"><img src="%s" width="220" alt="screenshot"></a>'
            % (screenshot, screenshot))


def build_table(registry, lang="zh"):
    h = _HEADERS[lang]
    lines = [_HINT[lang], "",
             "| %s | %s | %s | %s | %s |" % h,
             "|---|---|---|---|---|"]
    for m in registry.get("modules", []):
        name = m.get("name_en") if lang == "en" else m.get("name")
        name_alt = m.get("name") if lang == "en" else m.get("name_en")
        name_cell = "**%s**<br><sub>%s</sub>" % (name, name_alt)
        desc = m.get("description_en" if lang == "en" else "description", "")
        tier = _TIER_BADGE.get(m.get("tier", "bronze"), m.get("tier", ""))
        lines.append("| %s | %s | `%s` | %s | %s |"
                     % (_thumb(m.get("screenshot", "")), name_cell,
                        m.get("category", ""), tier, desc))
    return "\n".join(lines)


def render(readme_text, table):
    """把 README 里两标记之间的内容替换为新表;标记本身保留。找不到标记 → 报错(需先放标记)。"""
    if START not in readme_text or END not in readme_text:
        raise SystemExit(
            "README 缺少画廊标记;请在中文/英文 README 需要画廊处放置:\n%s\n%s" % (START, END))
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    return pattern.sub("%s\n\n%s\n\n%s" % (START, table, END), readme_text)


def _targets(args):
    if args.readme:
        return [(args.readme, args.lang or "zh")]
    return [("README.md", "zh"), ("README_EN.md", "en")]


def main(argv=None):
    ap = argparse.ArgumentParser(description="从 registry.json 生成 README 模块画廊(幂等)")
    ap.add_argument("--readme", default=None, help="指定单个 README 文件(默认同时更新中英两份)")
    ap.add_argument("--lang", default=None, choices=["zh", "en"], help="配合 --readme 指定语言")
    ap.add_argument("--check", action="store_true", help="只检查是否最新(不写盘),漂了退非零")
    args = ap.parse_args(argv)

    registry = load_registry()
    stale = []
    for rel, lang in _targets(args):
        path = os.path.join(_ROOT, rel)
        if not os.path.isfile(path):
            print("跳过(不存在):%s" % rel)
            continue
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        new = render(old, build_table(registry, lang))
        if new != old:
            stale.append(rel)
            if not args.check:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new)
                print("已更新画廊:%s(%s)" % (rel, lang))
        else:
            print("已是最新:%s(%s)" % (rel, lang))

    if args.check and stale:
        print("画廊已过期,请跑 gen_readme_gallery.py 重新生成:%s" % ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
