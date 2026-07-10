# tests/test_contract.py — 契约层单测:
#   1) validate_json 子集校验器各能力单测(type/required/enum/additionalProperties/
#      properties/items/minimum/maximum/pattern)
#   2) load_widget:合法 widget.json ≥3 通过、各类非法 ≥5 拒绝
import copy
import json
import os

import pytest

from lib.contract import (
    ContractError,
    load_widget,
    make_error,
    validate_config,
    validate_json,
    validate_output,
)


# ============================================================
# Part 1 — validate_json 子集校验器各能力单测
# ============================================================

# —— type(含 bool 不算 integer 的关键边界)——

def test_type_integer_ok_and_reject():
    assert validate_json(5, {"type": "integer"}) == []
    assert validate_json("5", {"type": "integer"}) != []
    assert validate_json(1.5, {"type": "integer"}) != []


def test_type_integer_rejects_bool():
    # bool 是 int 子类,integer 必须排除,否则 True 会被当 1 混过
    errs = validate_json(True, {"type": "integer"})
    assert errs != []


def test_type_number_and_boolean_and_string():
    assert validate_json(1.5, {"type": "number"}) == []
    assert validate_json(3, {"type": "number"}) == []
    assert validate_json(True, {"type": "number"}) != []       # bool 不是 number
    assert validate_json(True, {"type": "boolean"}) == []
    assert validate_json("hi", {"type": "string"}) == []
    assert validate_json(5, {"type": "string"}) != []


def test_type_object_and_array():
    assert validate_json({}, {"type": "object"}) == []
    assert validate_json([], {"type": "array"}) == []
    assert validate_json([], {"type": "object"}) != []
    assert validate_json({}, {"type": "array"}) != []


# —— required ——

def test_required():
    schema = {"type": "object", "required": ["a", "b"]}
    assert validate_json({"a": 1, "b": 2}, schema) == []
    errs = validate_json({"a": 1}, schema)
    assert len(errs) == 1 and "b" in errs[0]


# —— enum ——

def test_enum():
    schema = {"enum": ["interval", "daily_heavy", "on_demand"]}
    assert validate_json("interval", schema) == []
    assert validate_json("hourly", schema) != []


def test_enum_type_strict_no_bool_int_confusion():
    # 1 不应等于 True;enum 里只有 True 时,1 必须被拒
    assert validate_json(1, {"enum": [True]}) != []
    assert validate_json(True, {"enum": [True]}) == []


# —— additionalProperties: false ——

def test_additional_properties_false():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}},
              "additionalProperties": False}
    assert validate_json({"a": 1}, schema) == []
    errs = validate_json({"a": 1, "extra": 2}, schema)
    assert len(errs) == 1 and "extra" in errs[0]


# —— properties(递归)——

def test_properties_recurse():
    schema = {"type": "object",
              "properties": {"n": {"type": "integer"}, "s": {"type": "string"}}}
    assert validate_json({"n": 1, "s": "x"}, schema) == []
    errs = validate_json({"n": "bad", "s": "x"}, schema)
    assert len(errs) == 1 and "$.n" in errs[0]


# —— items(套到每个元素)——

def test_items_type():
    schema = {"type": "array", "items": {"type": "string"}}
    assert validate_json(["a", "b"], schema) == []
    errs = validate_json(["a", 2, "c"], schema)
    assert len(errs) == 1 and "[1]" in errs[0]


def test_items_enum_whitelist():
    schema = {"type": "array", "items": {"enum": ["requests", "Pillow"]}}
    assert validate_json([], schema) == []
    assert validate_json(["requests", "Pillow"], schema) == []
    assert validate_json(["requests", "numpy"], schema) != []


# —— minimum / maximum ——

def test_minimum_maximum():
    schema = {"type": "integer", "minimum": 1, "maximum": 120}
    assert validate_json(60, schema) == []
    assert validate_json(0, schema) != []
    assert validate_json(121, schema) != []


# —— pattern ——

def test_pattern():
    schema = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9]*$"}
    assert validate_json("Wx", schema) == []
    assert validate_json("Clock2", schema) == []
    assert validate_json("1bad", schema) != []
    assert validate_json("has-dash", schema) != []


def test_pattern_rejects_trailing_newline():
    # 回归:Python 的 $ 匹配"串尾换行之前",re.search 下尾随 \n 会漏网。
    # 校验器改用 re.fullmatch 后,尾随换行必须被拒(全项目校验地基,零容忍)。
    prefix_schema = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9]*$"}
    assert validate_json("Wx", prefix_schema) == []           # 正常值仍过
    assert validate_json("Wx\n", prefix_schema) != []         # 尾随换行必拒
    assert validate_json("collector.py\n", {"type": "string", "pattern": r"^[\w.\-]+\.py$"}) != []
    assert validate_json("collector.py", {"type": "string", "pattern": r"^[\w.\-]+\.py$"}) == []

    version_schema = {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"}
    assert validate_json("1.0.0", version_schema) == []       # 正常 semver 过
    assert validate_json("1.0.0\n", version_schema) != []     # 尾随换行必拒


def test_pattern_via_load_widget_trailing_newline(tmp_path):
    # 端到端:通过 load_widget 走真实 widget.schema.json,尾随换行的 prefix/version 必拒
    sub_a = tmp_path / "a"
    sub_a.mkdir()
    bad_prefix = _valid_weather()
    bad_prefix["runtime"]["output"]["prefix"] = "Wx\n"
    with pytest.raises(ContractError):
        load_widget(_write_widget(sub_a, bad_prefix))

    sub_b = tmp_path / "b"
    sub_b.mkdir()
    bad_version = _valid_weather()
    bad_version["display"]["version"] = "1.0.0\n"
    with pytest.raises(ContractError):
        load_widget(_write_widget(sub_b, bad_version))


def test_multiple_errors_aggregated():
    # 不短路:一次给全所有问题
    schema = {"type": "object", "required": ["a", "b"],
              "properties": {"a": {"type": "integer"}}, "additionalProperties": False}
    errs = validate_json({"a": "x", "c": 1}, schema)
    # a 类型错 + 缺 b + 多 c = 3 条
    assert len(errs) == 3


# ============================================================
# Part 2 — widget.json 合法/非法夹具
# ============================================================

def _valid_weather():
    """合法样例 1:天气(联网、interval、依赖 requests、有密钥)。"""
    return {
        "display": {
            "id": "weather", "name": "天气", "name_en": "Weather",
            "version": "1.0.0", "author": "sansheng", "license": "MIT",
            "category": "weather", "screenshot": "screenshot.png",
        },
        "runtime": {
            "entry": "collector.py",
            "refresh": {"mode": "interval", "interval_s": 1800, "net_only_ok": True},
            "timeout_s": 60,
            "deps": ["requests"],
            "output": {"prefix": "Wx", "schema": "output.schema.json"},
            "config": {"schema": "config.schema.json", "example": "config.example.json",
                       "secrets": ["CAIYUN_KEY"]},
            "privacy": {"network": ["api.example.com"], "local_read": [], "local_write": ["data.inc"]},
            "band": {"file": "band.inc", "height": 120, "interactive": False},
        },
    }


def _valid_clock():
    """合法样例 2:时钟日历(零网络、零密钥、依赖 Pillow、带 tags、省略 timeout_s)。"""
    return {
        "display": {
            "id": "clock-calendar", "name": "时钟日历", "name_en": "Clock & Calendar",
            "version": "0.1.0", "author": "sansheng", "license": "MIT",
            "category": "time", "screenshot": "shot.png", "tags": ["clock", "calendar"],
        },
        "runtime": {
            "entry": "collector.py",
            "refresh": {"mode": "interval", "interval_s": 0, "net_only_ok": False},
            # 故意省略 timeout_s → load_widget 补默认 60
            "deps": ["Pillow"],
            "output": {"prefix": "Clock", "schema": "output.schema.json"},
            "config": {"schema": "config.schema.json", "example": "config.example.json", "secrets": []},
            "privacy": {"network": [], "local_read": [], "local_write": ["cal.png"]},
            "band": {"file": "band.inc", "height": 200, "interactive": False},
        },
    }


def _valid_todo():
    """合法样例 3:待办(交互旗舰、on_demand、零依赖、零密钥)。"""
    return {
        "display": {
            "id": "todo", "name": "待办", "name_en": "Todo",
            "version": "2.3.1", "author": "sansheng", "license": "MIT",
            "category": "tasks", "screenshot": "screenshot.png",
        },
        "runtime": {
            "entry": "collector.py",
            "refresh": {"mode": "on_demand", "interval_s": 0, "net_only_ok": False},
            "timeout_s": 15,
            "deps": [],
            "output": {"prefix": "Todo", "schema": "output.schema.json"},
            "config": {"schema": "config.schema.json", "example": "config.example.json", "secrets": []},
            "privacy": {"network": [], "local_read": ["todos.json"], "local_write": ["todos.inc", "todos.json"]},
            "band": {"file": "band.inc", "height": 260, "interactive": True},
        },
    }


ALL_VALID = [_valid_weather, _valid_clock, _valid_todo]


def _write_widget(tmp_path, data):
    d = tmp_path / "mod"
    d.mkdir()
    (d / "widget.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(d)


# —— 合法 ≥3:直接过校验器 + 过 load_widget ——

@pytest.mark.parametrize("factory", ALL_VALID, ids=lambda f: f.__name__)
def test_valid_widgets_pass_schema(factory):
    from lib.contract import _widget_schema
    assert validate_json(factory(), _widget_schema()) == []


@pytest.mark.parametrize("factory", ALL_VALID, ids=lambda f: f.__name__)
def test_valid_widgets_load(tmp_path, factory):
    mod = _write_widget(tmp_path, factory())
    got = load_widget(mod)
    assert got["display"]["id"] == factory()["display"]["id"]


def test_load_widget_applies_timeout_default(tmp_path):
    mod = _write_widget(tmp_path, _valid_clock())      # 无 timeout_s
    got = load_widget(mod)
    assert got["runtime"]["timeout_s"] == 60


# —— 非法 ≥5:各类拒绝 ——

def test_invalid_missing_required(tmp_path):
    bad = _valid_weather()
    del bad["display"]["id"]                            # 缺 required
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError) as ei:
        load_widget(mod)
    assert "id" in str(ei.value)


def test_invalid_extra_field(tmp_path):
    bad = _valid_weather()
    bad["display"]["nickname"] = "小天"                 # additionalProperties:false
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError) as ei:
        load_widget(mod)
    assert "nickname" in str(ei.value)


def test_invalid_enum_out_of_range(tmp_path):
    bad = _valid_weather()
    bad["runtime"]["refresh"]["mode"] = "hourly"       # enum 越界
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError):
        load_widget(mod)


def test_invalid_prefix_pattern(tmp_path):
    bad = _valid_weather()
    bad["runtime"]["output"]["prefix"] = "1Wx"         # pattern 不匹配(数字开头)
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError):
        load_widget(mod)


def test_invalid_deps_not_whitelisted(tmp_path):
    bad = _valid_weather()
    bad["runtime"]["deps"] = ["requests", "numpy"]     # 白名单外包
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError) as ei:
        load_widget(mod)
    assert "numpy" in str(ei.value)


def test_invalid_timeout_over_max(tmp_path):
    bad = _valid_weather()
    bad["runtime"]["timeout_s"] = 150                  # > 120
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError):
        load_widget(mod)


def test_invalid_wrong_type(tmp_path):
    bad = _valid_weather()
    bad["runtime"]["band"]["height"] = "tall"          # 类型错(应 integer)
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError):
        load_widget(mod)


def test_invalid_version_not_semver(tmp_path):
    bad = _valid_weather()
    bad["display"]["version"] = "v1"                   # 非 X.Y.Z
    mod = _write_widget(tmp_path, bad)
    with pytest.raises(ContractError):
        load_widget(mod)


# —— load_widget 边界:缺文件 / JSON 语法错 ——

def test_load_widget_missing_file(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    with pytest.raises(ContractError) as ei:
        load_widget(str(d))
    assert "widget.json" in str(ei.value)


def test_load_widget_bad_json(tmp_path):
    d = tmp_path / "mod"
    d.mkdir()
    (d / "widget.json").write_text("{ not json,,,", encoding="utf-8")
    with pytest.raises(ContractError) as ei:
        load_widget(str(d))
    assert "JSON" in str(ei.value)


# ============================================================
# Part 3 — validate_config / validate_output 薄封装 + make_error
# ============================================================

def test_validate_config_and_output_via_file(tmp_path):
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"city": {"type": "string"}}, "required": ["city"]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(schema), encoding="utf-8")
    assert validate_config({"city": "长沙"}, str(sp)) == []
    assert validate_output({"city": 5}, str(sp)) != []          # 类型错
    assert validate_config({"city": "x", "k": 1}, str(sp)) != []  # 多字段


def test_validate_config_missing_schema_file_raises():
    with pytest.raises(ContractError):
        validate_config({}, os.path.join("nope", "missing.schema.json"))


def test_make_error_shape():
    e = make_error("network", True, "连不上,稍后重试")
    assert e == {"ok": False, "err": {"kind": "network", "retryable": True,
                                       "hint_for_agent": "连不上,稍后重试"}}


def test_make_error_coerces_retryable():
    assert make_error("bug", 0, "x")["err"]["retryable"] is False
    assert make_error("auth", 1, "x")["err"]["retryable"] is True


def test_make_error_rejects_unknown_kind():
    with pytest.raises(ValueError):
        make_error("weird", True, "x")
