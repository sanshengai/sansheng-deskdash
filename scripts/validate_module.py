# scripts/validate_module.py — 模块校验门(P0 版,与未来 CI 同款本地自查 / VALIDATE 审阅点二)。
#
# 干什么(SKILL §2.2、references/contribution.md、references/security.md):
#   1) widget.json 过契约(load_widget);config.example 过 config.schema。
#   2) schema 关键字白名单:模块自写的 output/config schema 若用了校验器**不支持**的关键字
#      (minLength/format/oneOf/const…)→ 报错("假信心":该关键字会被静默忽略、并不真校验)。
#   3) AST 扫描(纯 `ast` 模块):
#      · URL 字面量域名 ⊆ privacy.network 声明(实际请求域必须与声明一致);
#      · 禁用调用检测(eval/exec/os.system/subprocess shell=True)。
#   4) network-opaque:subprocess 调外部二进制(如 gh)→ 网络行为静态不可核验,标记 + 查
#      "已知二进制→域名"白名单(内置 gh→api.github.com)背书。
#   5) VALIDATE dry-run:用 config.example 真跑一次采集器,打印【实际网络目标 + 输出预览 + 是否过 output.schema】。
#   6) 人话报告 + 退出码(0=绿,无 error;warning/note 不致命)。
#
# 安全铁律:纯 stdlib(ast/json/subprocess/urllib.parse);无 eval/exec/shell=True;只读模块,不改它。
import argparse
import ast
import json
import os
import subprocess
import sys
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lib.contract import (ContractError, load_widget,             # noqa: E402
                          validate_config, validate_output, validate_json)

# —— 校验器(lib/contract.validate_json)真正支持的 JSON Schema 子集关键字 ——
_SUPPORTED_KW = frozenset({
    "type", "required", "enum", "additionalProperties",
    "properties", "items", "minimum", "maximum", "pattern",
})
# 纯元数据/非约束关键字:出现无害,不校验也不该报"假信心"。
_METADATA_KW = frozenset({
    "$schema", "$id", "$comment", "title", "description", "examples", "default",
})
# 携带子 schema 的容器键(键名是定义名,值才是 schema,递归其值)。
_DEFS_KW = frozenset({"$defs", "definitions"})

# 已知外部二进制 → 它会连的域名(用于给 network-opaque 背书)。
KNOWN_BINARY_DOMAINS = {
    "gh": ["api.github.com"],
    "gh.exe": ["api.github.com"],
}
# subprocess 调"自己(python)"不算外部网络二进制。
_PY_BINARIES = frozenset({"python", "python3", "pythonw", "py",
                          "python.exe", "pythonw.exe", "python3.exe"})
# 禁用的裸函数名 / os.<attr>
_FORBIDDEN_NAMES = frozenset({"eval", "exec"})


class Report:
    """校验结果聚合。ok = 无 error(warning/note 不致命)。"""

    def __init__(self, module_dir):
        self.module_dir = module_dir
        self.errors = []
        self.warnings = []
        self.notes = []
        self.network_opaque = False
        self.url_domains = set()      # AST 从 URL 字面量提取的域名
        self.declared_net = []        # privacy.network
        self.dry_run = None           # dict:dry-run 结果概览

    def err(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warnings.append(m)

    def note(self, m):
        self.notes.append(m)

    @property
    def ok(self):
        return not self.errors


# ============================================================
#  1) schema 关键字白名单("假信心"检测)
# ============================================================

def _scan_schema(node, path, rep, schema_label):
    """把 node 当一个 JSON Schema 递归扫:非支持、非元数据的关键字 → 报"假信心"错误。

    只在"schema 位置"检查键名;properties/$defs 下的键是**名字**不是关键字,只递归其值。
    """
    if not isinstance(node, dict):
        return  # 布尔 schema / 叶子,无键可查
    for key, val in node.items():
        if key in _METADATA_KW:
            continue
        if key in _DEFS_KW:
            if isinstance(val, dict):
                for _, sub in val.items():
                    _scan_schema(sub, "%s.%s" % (path, key), rep, schema_label)
            continue
        if key == "properties":
            if isinstance(val, dict):
                for pname, sub in val.items():
                    _scan_schema(sub, "%s.properties.%s" % (path, pname), rep, schema_label)
            continue
        if key == "items":
            _scan_schema(val, "%s.items" % path, rep, schema_label)
            continue
        if key == "additionalProperties":
            if isinstance(val, dict):
                rep.warn("%s 的 %s.additionalProperties 用了对象子 schema 形式:"
                         "校验器只认 additionalProperties:false,子 schema 不会被校验(假信心)。"
                         % (schema_label, path))
                _scan_schema(val, "%s.additionalProperties" % path, rep, schema_label)
            # false / true 均合法,不处理
            continue
        if key in _SUPPORTED_KW:
            continue  # type/required/enum/minimum/maximum/pattern:支持,叶子值无需递归
        # 其余一律"假信心":校验器不认,会静默忽略
        rep.err("%s 用了不被校验器支持的关键字 %s(位置 %s):它不会被真正校验,是假信心。"
                "请改用子集内关键字(type/required/enum/properties/items/additionalProperties:false/"
                "minimum/maximum/pattern),或在 collector 里手动校验。"
                % (schema_label, key, path))


def _check_schema_keywords(module_dir, widget, rep):
    rt = widget["runtime"]
    for label, name in (("output.schema", rt["output"]["schema"]),
                        ("config.schema", rt["config"]["schema"])):
        p = os.path.join(module_dir, name)
        if not os.path.isfile(p):
            rep.err("%s 声明的 schema 文件不存在:%s" % (label, name))
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except ValueError as e:
            rep.err("%s(%s)不是合法 JSON:%s" % (label, name, e))
            continue
        _scan_schema(schema, "$", rep, label)


# ============================================================
#  2) AST 扫描:URL 字面量域名 / 禁用调用 / subprocess 外部二进制
# ============================================================

def _host_of(url):
    try:
        h = urllib.parse.urlparse(url).hostname
        return h.lower() if h else None
    except ValueError:
        return None


def _list_first_str(node):
    """从 subprocess 首参解出二进制名:支持 List / (["x"]+args 的 BinOp) / 裸字符串。"""
    if isinstance(node, ast.List) and node.elts:
        e0 = node.elts[0]
        return e0.value if isinstance(e0, ast.Constant) and isinstance(e0.value, str) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _list_first_str(node.left)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.split()[0] if node.value.strip() else None
    return None


def _scan_ast_file(path, rep, binaries, dynamic_subproc):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        rep.err("%s 无法解析(语法错,第 %s 行):%s" % (os.path.basename(path), e.lineno, e.msg))
        return

    for n in ast.walk(tree):
        # URL 字面量 → 域名
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and "://" in n.value:
            h = _host_of(n.value)
            if h:
                rep.url_domains.add(h)
        # 调用检查
        if isinstance(n, ast.Call):
            f = n.func
            # eval / exec
            if isinstance(f, ast.Name) and f.id in _FORBIDDEN_NAMES:
                rep.err("%s 调用了禁用函数 %s()(任意代码执行,硬红线)。"
                        % (os.path.basename(path), f.id))
            # os.system
            if isinstance(f, ast.Attribute) and f.attr == "system" \
                    and isinstance(f.value, ast.Name) and f.value.id == "os":
                rep.err("%s 调用了 os.system()(等价 shell 执行,硬红线);改用 subprocess + list 参数。"
                        % os.path.basename(path))
            # shell=True(任何调用)
            for kw in n.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    rep.err("%s 用了 shell=True(硬红线);subprocess 只允许 list 参数、shell=False。"
                            % os.path.basename(path))
            # subprocess.<run/Popen/...> 的外部二进制
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "subprocess" \
                    and f.attr in ("run", "Popen", "call", "check_output", "check_call"):
                if n.args:
                    b = _list_first_str(n.args[0])
                    if b is None:
                        dynamic_subproc.append(os.path.basename(path))
                    else:
                        base = os.path.basename(b).lower()
                        if base not in _PY_BINARIES:
                            binaries.add(base)


def _check_ast(module_dir, widget, rep):
    """扫模块内所有 .py(不止 entry:助手脚本也可能藏网络/禁用调用)。"""
    binaries = set()
    dynamic = []
    for fn in sorted(os.listdir(module_dir)):
        if fn.endswith(".py"):
            _scan_ast_file(os.path.join(module_dir, fn), rep, binaries, dynamic)

    declared = list(widget["runtime"]["privacy"]["network"])
    rep.declared_net = declared
    declared_set = set(declared)
    has_placeholder = any(("<" in d and ">" in d) or d == "*" for d in declared)

    # URL 字面量域名 ⊆ privacy.network(硬编码域名必须显式声明,占位符不为它开脱)
    for d in sorted(rep.url_domains):
        if d not in declared_set:
            rep.err("collector 里出现请求域名 %s 的 URL 字面量,但 privacy.network 未声明它;"
                    "声明与实际必须一致(把 %s 加进 widget.json 的 privacy.network,或删掉该请求)。"
                    % (d, d))

    # network-opaque:外部二进制
    for b in sorted(binaries):
        rep.network_opaque = True
        known = KNOWN_BINARY_DOMAINS.get(b)
        if known:
            if all(dom in declared_set for dom in known):
                rep.note("调外部二进制 %s(network-opaque):其已知域名 %s 已在 privacy.network 背书。"
                         % (b, ", ".join(known)))
            else:
                rep.warn("调外部二进制 %s(network-opaque):已知会连 %s,但 privacy.network 未覆盖;"
                         "请补声明或人工背书。" % (b, ", ".join(known)))
        elif has_placeholder:
            rep.note("调外部二进制 %s(network-opaque):网络目标由用户配置(privacy.network 含占位),"
                     "静态不可核验 —— 需人工/文档背书。" % b)
        else:
            rep.warn("调外部二进制 %s(network-opaque):网络行为无法静态核验;"
                     "维护『已知二进制→域名』白名单或在 README 背书其网络面。" % b)
    for fn in sorted(set(dynamic)):
        rep.network_opaque = True
        rep.note("%s 有 subprocess 动态命令(首元素非字面量):无法静态识别二进制,"
                 "请人工确认不是网络二进制。" % fn)


# ============================================================
#  3) config.example 过 config.schema
# ============================================================

def _check_config_example(module_dir, widget, rep):
    rt = widget["runtime"]
    example = os.path.join(module_dir, rt["config"]["example"])
    schema = os.path.join(module_dir, rt["config"]["schema"])
    if not os.path.isfile(example):
        rep.err("config.example 文件不存在:%s" % rt["config"]["example"])
        return
    try:
        with open(example, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except ValueError as e:
        rep.err("config.example(%s)不是合法 JSON:%s" % (rt["config"]["example"], e))
        return
    try:
        errs = validate_config(cfg, schema)
    except ContractError as e:
        rep.err("config schema 读取失败:%s" % e)
        return
    for m in errs:
        rep.err("config.example 不过 config.schema:%s" % m)


# ============================================================
#  4) VALIDATE dry-run
# ============================================================

def _dry_run(module_dir, widget, rep, timeout_cap):
    rt = widget["runtime"]
    entry = os.path.join(module_dir, rt["entry"])
    example = os.path.join(module_dir, rt["config"]["example"])
    timeout = min(int(rt.get("timeout_s", 60)), timeout_cap)
    cfg_arg = example if os.path.isfile(example) else os.path.join(module_dir, "config.json")

    kw = {"capture_output": True, "timeout": timeout, "cwd": module_dir}
    if sys.platform == "win32":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    info = {"ran": True, "schema_ok": None, "err_kind": None, "preview": ""}
    try:
        proc = subprocess.run([sys.executable, entry, "--config", cfg_arg], **kw)  # noqa: S603
    except subprocess.TimeoutExpired:
        rep.err("dry-run 采集器超时(>%ds):检查是否有无超时的网络调用 / 未自限的子进程。" % timeout)
        info["ran"] = False
        rep.dry_run = info
        return
    except OSError as e:
        rep.err("dry-run 无法启动采集器:%s(检查 entry 路径与 Python 环境)。" % e)
        info["ran"] = False
        rep.dry_run = info
        return

    out = (proc.stdout or b"").decode("utf-8", "replace")
    payload = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line:
            try:
                payload = json.loads(line)
                break
            except ValueError:
                continue
    if payload is None:
        rep.err("dry-run 输出无法解析为 JSON(退出码 %d):契约要求 stdout 打印单行 JSON。"
                % proc.returncode)
        rep.dry_run = info
        return

    info["preview"] = json.dumps(payload, ensure_ascii=False)[:400]
    if isinstance(payload, dict) and payload.get("ok") is False:
        err = payload.get("err") or {}
        info["err_kind"] = err.get("kind")
        rep.note("dry-run:采集器返回结构化错误(可能离线/需密钥/无数据,非致命):kind=%s hint=%s"
                 % (err.get("kind"), str(err.get("hint_for_agent"))[:120]))
        rep.dry_run = info
        return

    # 成功输出 → 过 output.schema
    out_dict = payload.get("out") if (isinstance(payload, dict) and isinstance(payload.get("out"), dict)) \
        else payload
    schema = os.path.join(module_dir, rt["output"]["schema"])
    try:
        errs = validate_output(out_dict, schema)
    except ContractError as e:
        rep.err("output schema 读取失败:%s" % e)
        rep.dry_run = info
        return
    if errs:
        info["schema_ok"] = False
        rep.err("dry-run 输出不过 output.schema:%s" % "; ".join(errs[:5]))
    else:
        info["schema_ok"] = True
        rep.note("dry-run:输出过 output.schema(%d 个键)。" % len(out_dict))
    rep.dry_run = info


# ============================================================
#  骨架桩提示
# ============================================================

def _check_stub(module_dir, widget, rep):
    entry = os.path.join(module_dir, widget["runtime"]["entry"])
    if os.path.isfile(entry):
        with open(entry, "r", encoding="utf-8") as f:
            if "DESKDASH-SKELETON-STUB" in f.read():
                rep.note("这是 new_module 生成的骨架桩,collector 尚未实现真实采集 —— "
                         "记得填真逻辑并删掉标记行(校验其余项已过,可继续开发)。")


# ============================================================
#  主入口
# ============================================================

def validate_module(module_dir, dry_run=True, timeout_cap=100):
    """校验一个模块目录,返回 Report。ok=无 error。"""
    module_dir = os.path.abspath(module_dir)
    rep = Report(module_dir)
    if not os.path.isdir(module_dir):
        rep.err("模块目录不存在:%s" % module_dir)
        return rep
    try:
        widget = load_widget(module_dir)
    except ContractError as e:
        rep.err("widget.json 不合契约:%s" % str(e).replace("\n", " "))
        return rep

    _check_config_example(module_dir, widget, rep)
    _check_schema_keywords(module_dir, widget, rep)
    _check_ast(module_dir, widget, rep)
    _check_stub(module_dir, widget, rep)
    if dry_run:
        _dry_run(module_dir, widget, rep, timeout_cap)
    return rep


def _print_report(rep, widget):
    mid = os.path.basename(rep.module_dir)
    print("=" * 60)
    print("VALIDATE 模块:%s" % mid)
    print("=" * 60)
    if widget:
        rt = widget["runtime"]
        pv = rt["privacy"]
        print("代码要点:entry=%s  prefix=%s  deps=%s  interactive=%s"
              % (rt["entry"], rt["output"]["prefix"], rt["deps"] or "无", rt["band"]["interactive"]))
        print("privacy 三元组:")
        print("  网络 network   : %s" % (pv["network"] or "无"))
        print("  本地读 local_read : %s" % (pv["local_read"] or "无"))
        print("  本地写 local_write: %s" % (pv["local_write"] or "无"))
        print("  密钥 secrets   : %s" % (rt["config"]["secrets"] or "无"))
    # 实际网络目标:声明 + 字面量域名
    targets = sorted(set(rep.declared_net) | rep.url_domains)
    print("实际网络目标(声明 + URL 字面量):%s" % (targets or "无"))
    if rep.url_domains:
        print("  -> AST 从 URL 字面量提取:%s" % ", ".join(sorted(rep.url_domains)))
    if rep.network_opaque:
        print("  [!] network-opaque:含外部二进制/动态命令,部分网络行为静态不可核验(见下方 notes)。")
    if rep.dry_run is not None:
        d = rep.dry_run
        print("dry-run:%s"
              % ("已跑" if d["ran"] else "未完成"))
        if d.get("preview"):
            print("  输出预览:%s%s" % (d["preview"], "…" if len(d["preview"]) >= 400 else ""))
        if d.get("schema_ok") is True:
            print("  过 output.schema:是")
        elif d.get("schema_ok") is False:
            print("  过 output.schema:否(见 errors)")
        elif d.get("err_kind"):
            print("  采集器返回结构化错误:kind=%s(非致命)" % d["err_kind"])

    def _blk(title, items, mark):
        if items:
            print("\n%s %s(%d)" % (mark, title, len(items)))
            for m in items:
                print("  - %s" % m)

    _blk("错误 errors", rep.errors, "[X]")
    _blk("警告 warnings", rep.warnings, "[!]")
    _blk("说明 notes", rep.notes, "[i]")
    print("\n结论:%s" % ("GREEN 绿灯(可回流 / 可接线)" if rep.ok
                          else "RED 红灯(%d 个错误需修)" % len(rep.errors)))


def main(argv=None):
    # 报告含中文;Windows 控制台默认 cp936,统一把 stdout 切 UTF-8 避免编码崩(见 references/encoding.md)。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="模块校验门(契约+schema假信心+AST+dry-run)")
    ap.add_argument("module_dir", help="模块目录(含 widget.json 等七件套)")
    ap.add_argument("--no-dry-run", action="store_true", help="跳过 dry-run(只做静态校验,快)")
    ap.add_argument("--timeout-cap", type=int, default=100, help="dry-run 单次上限秒(默认 100)")
    args = ap.parse_args(argv)

    rep = validate_module(args.module_dir, dry_run=not args.no_dry_run,
                          timeout_cap=args.timeout_cap)
    widget = None
    try:
        widget = load_widget(os.path.abspath(args.module_dir))
    except Exception:
        pass
    _print_report(rep, widget)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
