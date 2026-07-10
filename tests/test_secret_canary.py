# tests/test_secret_canary.py — 密钥金丝雀基座(给后续所有模块复用)
#
# 安全铁律(设计稿 §4):密钥只进 gitignore 的 config.json,绝不进代码/日志/异常。
# 做法:往 config 注入一个假密钥 CANARY_SECRET_xyz,跑 collector 各分支(鉴权失败/网络失败/正常),
# 断言这个假密钥不出现在返回的 error dict、任何 stdout/stderr、序列化输出里。
#
# 后续每个"需密钥"模块的测试直接复用本文件的:
#   from test_secret_canary import CANARY_SECRET, canary_config, check_no_leak, assert_no_secret_leak
# 传入自己模块的 collector 各分支跑一遍即可(tests/ 下同级 import,pytest prepend 模式天然可达)。
import json

import pytest

from lib.contract import make_error

# 统一假密钥:够独特、不会撞真实字符串;各模块共用这一个便于全仓 grep 复核
CANARY_SECRET = "CANARY_SECRET_xyz"


def canary_config(**extra):
    """构造一份注入了假密钥的 config;把 CANARY_SECRET 塞进常见密钥字段名,覆盖面广一点。"""
    cfg = {"api_key": CANARY_SECRET, "token": CANARY_SECRET, "password": CANARY_SECRET}
    cfg.update(extra)
    return cfg


def assert_no_secret_leak(secret, *blobs):
    """核心断言:secret 不得出现在任何一个字符串 blob 里。泄漏即 AssertionError。"""
    for i, b in enumerate(blobs):
        assert secret not in (b or ""), "密钥泄漏:%r 出现在第 %d 个输出片段里 → %r" % (secret, i, b)


def check_no_leak(result, captured, secret=CANARY_SECRET):
    """把采集结果(dict,序列化)与捕获的 stdout/stderr 一并扫描,断言不含 secret。

    result: collector 返回的 dict(正常 {"ok":true,...} 或错误 {"ok":false,"err":{...}})。
    captured: pytest capsys.readouterr() 的返回(有 .out / .err)。
    这是所有模块 secret 测试的共同基座断言。
    """
    blob = json.dumps(result, ensure_ascii=False, default=str)
    assert_no_secret_leak(secret, blob, captured.out, captured.err)


# ============================================================
# 内联 mock collector —— 演示"需密钥采集器"的正确写法:
# 失败走 make_error,hint_for_agent 里只说"检查你的 key",绝不回显 key 本身。
# ============================================================

def mock_collector(config, mode):
    import sys
    api_key = config.get("api_key", "")
    # 真实 collector 会用 api_key 去请求;这里只演示:无论哪个分支,输出都不带 key
    if mode == "auth_fail":
        # 模拟 HTTP 401:哪怕明知是 key 的问题,也不把 key 值写进 hint
        print("[mock] auth failed (401)", file=sys.stderr)   # 日志也脱敏
        return make_error(
            "auth", retryable=False,
            hint_for_agent="鉴权失败(HTTP 401):config.json 里的 api_key 可能错误或过期,"
                           "请在 config.json 内更新,不要把 key 贴进对话。")
    if mode == "network_fail":
        print("[mock] connect timeout", file=sys.stderr)
        return make_error(
            "network", retryable=True,
            hint_for_agent="连不上 api.example.com:检查网络或稍后重试。")
    if mode == "ok":
        # 正常路径:业务输出里也不该出现密钥
        assert api_key, "collector 应拿到 key(但不外泄)"
        print("[mock] ok", file=sys.stderr)
        return {"ok": True, "out": {"Temp": 32, "City": "长沙"}}
    raise AssertionError("未知 mode: %r" % mode)


# —— 三分支各跑一遍,断言假密钥零泄漏 —— (基座核心用例)

@pytest.mark.parametrize("mode", ["auth_fail", "network_fail", "ok"])
def test_mock_collector_no_secret_leak(capsys, mode):
    cfg = canary_config()
    result = mock_collector(cfg, mode)
    captured = capsys.readouterr()
    check_no_leak(result, captured)


def test_auth_fail_is_structured_error_not_raw_exception():
    # 失败必须是结构化错误对象,不抛裸异常(设计稿 §4 错误约定)
    result = mock_collector(canary_config(), "auth_fail")
    assert result["ok"] is False
    assert result["err"]["kind"] == "auth"
    assert result["err"]["retryable"] is False
    assert set(result["err"]) == {"kind", "retryable", "hint_for_agent"}


def test_ok_branch_returns_payload():
    result = mock_collector(canary_config(), "ok")
    assert result["ok"] is True
    assert result["out"]["Temp"] == 32


# —— 负向对照:证明断言真的能抓到泄漏(不是永远通过的空测)——

def _leaky_collector(config, mode):
    """反面教材:把 key 拼进 hint —— 必须被金丝雀抓到。"""
    return make_error("auth", False, "鉴权失败,你的 key=%s 不对" % config.get("api_key", ""))


def test_canary_catches_a_real_leak(capsys):
    result = _leaky_collector(canary_config(), "auth_fail")
    captured = capsys.readouterr()
    with pytest.raises(AssertionError):
        check_no_leak(result, captured)


def test_assert_no_secret_leak_direct():
    assert_no_secret_leak(CANARY_SECRET, "干净的输出", "没有密钥")     # 不抛
    with pytest.raises(AssertionError):
        assert_no_secret_leak(CANARY_SECRET, "泄漏了 CANARY_SECRET_xyz 在这")
