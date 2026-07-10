# lib/common.py — 公共工具:stdlib HTTP、原子写、本地时间(可 DESKDASH_TZ 覆盖)
# stdlib-only(安全铁律:collector deps ⊆ [requests, Pillow],本文件不依赖任何第三方包)。
import os
import tempfile
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

# 常见桌面浏览器 UA:不少公开 API/静态源对无 UA 的请求返回 403,统一带上
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 时区环境变量名:值为 IANA 时区名,如 "Asia/Shanghai"
TZ_ENV = "DESKDASH_TZ"


def local_now(tz=None):
    """当前时间(带时区的 aware datetime)。

    时区优先级:显式参数 tz > 环境变量 DESKDASH_TZ > 系统本地时区(默认)。
    tz / DESKDASH_TZ 的值是 IANA 时区名(如 "Asia/Shanghai"),用 zoneinfo 解析。

    注意:Windows 不自带 IANA 时区数据库,zoneinfo 解析 IANA 名依赖 pip 包 tzdata;
    未装 tzdata 时传入时区名会抛 ZoneInfoNotFoundError——不设 DESKDASH_TZ 走系统
    本地时区(默认路径)则永远可用,不依赖 tzdata。
    """
    name = tz or os.environ.get(TZ_ENV)
    if name:
        return datetime.now(ZoneInfo(name))
    # datetime.now().astimezone():无参调用取系统本地时区,返回 aware datetime
    return datetime.now().astimezone()


def http_get(url, timeout=15, headers=None):
    """GET 一个 URL,返回 utf-8 解码文本(解不动的字节 replace,不抛解码错)。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def atomic_write(path, text, encoding="utf-8", newline="\n"):
    """原子写文件:先写同目录临时文件再 os.replace,避免读方(Rainmeter)读到半截。

    data.inc/todos.inc 走 encoding="utf-16"(Rainmeter 中文不乱码);源码/JSON 用默认 utf-8。
    """
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
