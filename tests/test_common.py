# tests/test_common.py — lib/common 单测:local_now 时区覆盖、原子写、http_get
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from lib.common import TZ_ENV, atomic_write, http_get, local_now


# —— local_now:默认系统本地时区 / DESKDASH_TZ 覆盖 / 显式参数最高优先 ——

def test_local_now_default_is_aware_local(monkeypatch):
    monkeypatch.delenv(TZ_ENV, raising=False)
    now = local_now()
    assert now.tzinfo is not None                       # aware,不是 naive
    assert now.utcoffset() is not None


def test_local_now_env_override(monkeypatch):
    monkeypatch.setenv(TZ_ENV, "Asia/Shanghai")
    assert local_now().utcoffset() == timedelta(hours=8)
    monkeypatch.setenv(TZ_ENV, "UTC")
    assert local_now().utcoffset() == timedelta(0)


def test_local_now_param_beats_env(monkeypatch):
    monkeypatch.setenv(TZ_ENV, "UTC")
    assert local_now("Asia/Shanghai").utcoffset() == timedelta(hours=8)


def test_local_now_bad_tz_raises(monkeypatch):
    monkeypatch.setenv(TZ_ENV, "Not/AZone")
    with pytest.raises(Exception):                      # ZoneInfoNotFoundError(KeyError 子类)
        local_now()


# —— atomic_write:落盘内容正确、覆盖旧文件、不留 .tmp 残渣 ——

def test_atomic_write_utf8_and_overwrite(tmp_path):
    p = tmp_path / "out.txt"
    atomic_write(str(p), "第一版\n")
    assert p.read_text(encoding="utf-8") == "第一版\n"
    atomic_write(str(p), "第二版:中文·符号°\n")
    assert p.read_text(encoding="utf-8") == "第二版:中文·符号°\n"
    assert [f.name for f in tmp_path.iterdir()] == ["out.txt"]   # 无 .tmp 残留


def test_atomic_write_utf16(tmp_path):
    p = tmp_path / "data.inc"
    atomic_write(str(p), "[Variables]\nWxCity=长沙\n", encoding="utf-16")
    assert p.read_bytes()[:2] in (b"\xff\xfe", b"\xfe\xff")      # UTF-16 BOM
    assert p.read_text(encoding="utf-16") == "[Variables]\nWxCity=长沙\n"


# —— http_get:对本地一次性 HTTP 服务发真实请求(不出外网) ——

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = "你好 deskdash".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):                          # 静默,别刷测试输出
        pass


def test_http_get_local_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        text = http_get("http://127.0.0.1:%d/" % srv.server_address[1], timeout=5)
        assert text == "你好 deskdash"
    finally:
        srv.shutdown()
