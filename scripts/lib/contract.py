# lib/contract.py — 契约层:widget.json 校验 + stdlib JSON Schema 子集校验器 + 错误规范化
#
# 全项目校验地基。安全铁律:纯 stdlib(json/re),不引 jsonschema/pydantic 等第三方;
# 无 eval/exec/shell。密钥绝不进错误对象/日志(secret-canary 断言,见 tests/test_secret_canary.py)。
import json
import os
import re

# —— 校验器支持的 JSON Schema 子集(仅这些关键字有效,其余 schema 关键字被忽略)——
#   type / required / enum / additionalProperties(仅 false) / properties / items /
#   minimum / maximum / pattern
# 之所以自研而非引 jsonschema:契约是安全边界的一部分,校验地基必须零第三方、可审计。


class ContractError(Exception):
    """契约校验失败。message=人话主因;errors=逐条 schema 错误;hint=给 agent 的修复指引。

    抛出方保证 message/hint 里不含任何密钥值(错误来自结构校验,不回显配置值)。
    """

    def __init__(self, message, errors=None, hint=None):
        self.errors = list(errors or [])
        self.hint = hint
        full = message
        if self.errors:
            full += "\n- " + "\n- ".join(self.errors)
        if hint:
            full += "\n提示:" + hint
        super().__init__(full)


# bool 在 Python 里是 int 子类:integer/number 类型必须显式排除 bool,否则 True 会被当 1 通过。
_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}

_PY_NAME = {dict: "object", list: "array", str: "string", bool: "boolean",
            int: "integer", float: "number", type(None): "null"}


def _type_name(v):
    return _PY_NAME.get(type(v), type(v).__name__)


def _type_ok(value, t):
    """t 可为单个类型名或类型名列表(JSON Schema 允许);未知类型名不强制。"""
    names = t if isinstance(t, list) else [t]
    checks = [_TYPE_CHECKS.get(n) for n in names]
    known = [c for c in checks if c is not None]
    if not known:
        return True  # 全是未知类型名 → 不约束
    return any(c(value) for c in known)


def validate_json(instance, schema, path="$"):
    """stdlib 实现的 JSON Schema 子集校验器 —— 全项目校验地基。

    支持:type(object/array/string/integer/number/boolean)、required、enum、
    additionalProperties:false、properties、items、minimum、maximum、pattern。
    返回错误信息列表(空列表=通过);不抛异常(便于聚合多条错误)。
    每个关键字独立判定,不因单条失败短路,以便一次给全所有问题。
    """
    errors = []

    if not isinstance(schema, dict):
        # 布尔 schema / 非法 schema 不在子集内,视为不约束
        return errors

    # 1) type
    if "type" in schema and not _type_ok(instance, schema["type"]):
        errors.append("%s: 期望类型 %s,实际是 %s" % (path, schema["type"], _type_name(instance)))

    # 2) enum
    if "enum" in schema:
        allowed = schema["enum"]
        # 用 type+值双重比较,避免 True==1 / 1==1.0 之类的宽松相等误判
        if not any(type(instance) is type(a) and instance == a for a in allowed):
            errors.append("%s: 值 %r 不在允许集合 %r 内" % (path, instance, allowed))

    # 3) pattern(仅字符串)
    # 用 fullmatch 而非 search:schema 模式多以 $ 收尾,而 Python 的 $ 匹配"串尾换行之前",
    # search 下 "Wx\n"/"1.0.0\n" 之类尾随换行会漏网。fullmatch 要求整串匹配,堵住此洞;
    # 模式里冗余的 ^/$ 锚点在 fullmatch 下无害(整串匹配语义兼容)。
    if "pattern" in schema and isinstance(instance, str):
        if re.fullmatch(schema["pattern"], instance) is None:
            errors.append("%s: 值 %r 不匹配格式 %s" % (path, instance, schema["pattern"]))

    # 4) minimum / maximum(仅数值,排除 bool)
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append("%s: %s 小于最小值 %s" % (path, instance, schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append("%s: %s 超过最大值 %s" % (path, instance, schema["maximum"]))

    # 5) 对象:properties / required / additionalProperties:false
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for key, subschema in props.items():
            if key in instance:
                errors += validate_json(instance[key], subschema, "%s.%s" % (path, key))
        for req in schema.get("required", []):
            if req not in instance:
                errors.append("%s: 缺少必填字段 '%s'" % (path, req))
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append("%s: 不允许的额外字段 '%s'" % (path, key))

    # 6) 数组:items(单一子 schema,套到每个元素)
    if isinstance(instance, list) and "items" in schema:
        item_schema = schema["items"]
        for i, elem in enumerate(instance):
            errors += validate_json(elem, item_schema, "%s[%d]" % (path, i))

    return errors


# —— widget.json 加载与校验 ——

# contract.py 在 <repo>/scripts/lib/contract.py;三层 dirname 回到仓根
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_WIDGET_SCHEMA_PATH = os.path.join(_REPO_ROOT, "schemas", "widget.schema.json")
_DEFAULT_TIMEOUT_S = 60

_widget_schema_cache = None


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _widget_schema():
    """懒加载并缓存 widget.schema.json。"""
    global _widget_schema_cache
    if _widget_schema_cache is None:
        _widget_schema_cache = _read_json(_WIDGET_SCHEMA_PATH)
    return _widget_schema_cache


def load_widget(module_dir):
    """读 <module_dir>/widget.json,用 widget.schema.json 校验,返回 dict。

    不合法/缺文件/JSON 语法错 → 抛 ContractError(含人话 hint)。
    校验通过后补 runtime.timeout_s 默认值 60(契约里 timeout_s 可省)。
    """
    wj = os.path.join(module_dir, "widget.json")
    if not os.path.isfile(wj):
        raise ContractError(
            "模块目录缺少 widget.json:%s" % module_dir,
            hint="每个模块目录必须有 widget.json(双段 display+runtime);参考 templates/module-skeleton。")
    try:
        data = _read_json(wj)
    except json.JSONDecodeError as e:
        raise ContractError(
            "widget.json 不是合法 JSON:%s" % wj,
            hint="JSON 语法错(第 %d 行第 %d 列附近):%s" % (e.lineno, e.colno, e.msg))

    errors = validate_json(data, _widget_schema())
    if errors:
        raise ContractError(
            "widget.json 不符合契约:%s" % wj,
            errors=errors,
            hint="按上面逐条修 widget.json;字段定义见 schemas/widget.schema.json 与设计稿 §4。")

    # 补默认:timeout_s 可省,缺省 60(校验已确保 runtime 是 dict)
    rt = data.get("runtime")
    if isinstance(rt, dict):
        rt.setdefault("timeout_s", _DEFAULT_TIMEOUT_S)
    return data


def validate_config(cfg, schema_path):
    """薄封装:读 config schema 文件,校验 cfg,返回错误列表(空=通过)。"""
    return validate_json(cfg, _load_schema_file(schema_path))


def validate_output(out, schema_path):
    """薄封装:读 output schema 文件,校验采集器输出 out,返回错误列表(空=通过)。"""
    return validate_json(out, _load_schema_file(schema_path))


def _load_schema_file(schema_path):
    if not os.path.isfile(schema_path):
        raise ContractError(
            "schema 文件不存在:%s" % schema_path,
            hint="检查 widget.json 里 output.schema / config.schema 的文件名是否与实际文件一致。")
    try:
        return _read_json(schema_path)
    except json.JSONDecodeError as e:
        raise ContractError(
            "schema 不是合法 JSON:%s" % schema_path,
            hint="JSON 语法错(第 %d 行):%s" % (e.lineno, e.msg))


# —— 错误对象规范化(供各模块 collector 复用)——

# 错误分类(设计稿 §4):供 agent 分诊
ERR_KINDS = ("auth", "rate_limit", "network", "provider", "bug")


def make_error(kind, retryable, hint_for_agent):
    """构造规范化错误对象:{"ok": false, "err": {kind, retryable, hint_for_agent}}。

    collector 各失败分支统一走这里,不抛裸异常。
    🔴 安全铁律:hint_for_agent 里绝不能拼进任何密钥值(secret-canary 会断言)。
    只描述"哪里出错、怎么修",不回显 config 里的 key/token/password。
    """
    if kind not in ERR_KINDS:
        raise ValueError("未知错误 kind %r;须是 %r 之一" % (kind, ERR_KINDS))
    return {
        "ok": False,
        "err": {
            "kind": kind,
            "retryable": bool(retryable),
            "hint_for_agent": str(hint_for_agent),
        },
    }
