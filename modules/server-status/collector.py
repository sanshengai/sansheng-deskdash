# modules/server-status/collector.py — 服务状态探测:对若干主机做 ①HTTP health URL 探测(状态码+响应时间)
#   ②ICMP ping 延迟。以状态色(绿/黄/红/灰)一目了然。
#
# 契约:`python collector.py --config <config.json>`,stdout 单行 JSON;成功=扁平 outputs,失败=err。
# 自包含 stdlib(urllib/socket/subprocess);无第三方依赖(deps: [])。无 eval/exec/shell=True。
#
# P0 边界:只做 HTTP 探测 + ping。**不做 SSH**(远端内存/磁盘采集留 P1)——避免把 VPS 私有采集细节带进公开仓,
#   也让本模块零远端凭证、零 SSH 依赖,陌生人填个 URL 就能用。
#
# config.hosts: [{label, url?, ping_host?}],每项:
#   · url      —— 有则做 HTTP GET,取状态码 + 响应耗时(健康检查语义:2xx/3xx 视为在线)。
#   · ping_host—— 无 url 时对它 ping(ICMP 平均延迟)。国内域名/裸 IP 用 ping 不被 fake-IP 劫持。
#   两者都给 → 以 url(HTTP)为准(更贴近"服务可用"而非"主机可达")。
#
# ⚠ 自限子进程(与 net-latency 同款,独立内联):ping 用 `-n`/`-w`(Windows)或 `-c`/`-W`(*nix)限次数+
#   单包超时,再叠加 subprocess.run(timeout=) 硬杀;ping 不派生孙进程,无挂死孤儿隐患。
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

MAX_HOSTS = 5                                        # band.inc 固定 5 行,多余截断
_IS_WIN = sys.platform == "win32"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _err(kind, retryable, hint):
    return {"ok": False, "err": {"kind": kind, "retryable": bool(retryable),
                                 "hint_for_agent": str(hint)}}


def _emit(obj):
    b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(b + b"\n")
    try:
        sys.stdout.buffer.flush()
    except OSError:
        pass


def load_config(path):
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None
    return {"hosts": []}


# —— HTTP 探测 ——

def http_probe(url, timeout=8):
    """GET url,返回 (status:int|None, ms:int|None)。HTTP 错误码(4xx/5xx)仍算"响应到了"→ 带状态+耗时;
    超时/连不上/DNS 失败 → (None, None)。不下载正文(读少量即弃)。"""
    req = urllib.request.Request(url, headers={"User-Agent": _UA}, method="GET")
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(64)                               # 触发响应但不下载全文
            ms = round((time.perf_counter() - t) * 1000)
            return int(getattr(r, "status", None) or r.getcode()), ms
    except urllib.error.HTTPError as e:              # 有响应但状态非 2xx/3xx(4xx/5xx)
        ms = round((time.perf_counter() - t) * 1000)
        return int(e.code), ms
    except Exception:                                # 超时/URLError/SSL/DNS → 视为不通
        return None, None


# —— ping 探测(与 net-latency 同款,独立内联;非 lib 算法,无需 drift-guard)——

def ping_ms(host):
    """ICMP 平均延迟 ms(下限 1);不通/超时/异常 → None。自限:限 2 包 + 单包 2s + 总 8s 硬杀。"""
    if _IS_WIN:
        cmd = ["ping", "-n", "2", "-w", "2000", host]
    else:
        cmd = ["ping", "-c", "2", "-W", "2", host]
    kw = {"capture_output": True, "timeout": 8}
    if _IS_WIN:
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        r = subprocess.run(cmd, **kw)                # noqa: S603 (list 参数,非 shell)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = r.stdout.decode("gbk" if _IS_WIN else "utf-8", errors="replace")
    nums = re.findall(r"(\d+)\s*ms", out)
    return max(1, int(nums[-1])) if (r.returncode == 0 and nums) else None


# —— 状态色 ——

def http_color(status, ms):
    """HTTP:2xx/3xx 在线(绿<500ms 否则黄);4xx/5xx 红;无响应灰。"""
    if status is None:
        return "120,130,145,255"
    if 200 <= status < 400:
        return "82,199,120,255" if (ms is None or ms < 500) else "230,180,80,255"
    return "232,110,110,255"


def ping_color(ms):
    """ping:绿<80,黄<200,红≥200,灰=不通(与 net-latency 同阈值)。"""
    if ms is None or ms < 0:
        return "120,130,145,255"
    if ms < 80:
        return "82,199,120,255"
    if ms < 200:
        return "230,180,80,255"
    return "232,110,110,255"


def measure_host(host):
    """单主机 → dict(status/ms/ok/color/text)。有 url 走 HTTP,否则 ping_host 走 ping;都无 → 灰空。"""
    url = str(host.get("url") or "").strip()
    ping_host = str(host.get("ping_host") or "").strip()
    if url:
        status, ms = http_probe(url)
        ok = status is not None and 200 <= status < 400
        if status is None:
            text = "超时"
        elif ms is None:
            text = str(status)
        else:
            text = "%d · %dms" % (status, ms)
        return {"status": ("%d" % status) if status is not None else "—",
                "ms": ms if ms is not None else -1, "ok": 1 if ok else 0,
                "color": http_color(status, ms), "text": text}
    if ping_host:
        ms = ping_ms(ping_host)
        ok = ms is not None and ms >= 0
        return {"status": "PING", "ms": ms if ok else -1, "ok": 1 if ok else 0,
                "color": ping_color(ms if ok else None),
                "text": ("%d ms" % ms) if ok else "超时"}
    return {"status": "—", "ms": -1, "ok": 0, "color": "0,0,0,0", "text": ""}


def collect(cfg):
    """采集各主机状态 → 扁平 outputs(Host1..Host{MAX} 槽位;未用槽位空白)。"""
    hosts = (cfg or {}).get("hosts") or []
    if not isinstance(hosts, list):
        return _err("bug", False, "config.hosts 必须是数组,每项含 label + url 或 ping_host。")
    hosts = hosts[:MAX_HOSTS]
    out = {"Title": "服务状态", "Count": len(hosts)}
    for i in range(MAX_HOSTS):
        n = i + 1
        if i < len(hosts):
            h = hosts[i]
            label = str(h.get("label") or h.get("url") or h.get("ping_host") or "主机%d" % n)
            m = measure_host(h)
            out["Host%dLabel" % n] = label
            out["Host%dStatus" % n] = m["status"]
            out["Host%dMs" % n] = m["ms"]
            out["Host%dText" % n] = m["text"]
            out["Host%dOk" % n] = m["ok"]
            out["Host%dColor" % n] = m["color"]
        else:                                        # 空槽位:变量存在但不显示
            out["Host%dLabel" % n] = ""
            out["Host%dStatus" % n] = ""
            out["Host%dMs" % n] = -1
            out["Host%dText" % n] = ""
            out["Host%dOk" % n] = 0
            out["Host%dColor" % n] = "0,0,0,0"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="服务状态探测器(HTTP health + ping)")
    ap.add_argument("--config", default=None, help="config.json 路径")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if cfg is None:
        _emit(_err("bug", False, "config.json 读取/解析失败:检查是否为合法 JSON。"))
        return 1
    try:
        res = collect(cfg)
        _emit(res)
        return 0 if "ok" not in res else 1
    except Exception as e:
        _emit(_err("bug", False, "服务状态探测器未预期异常:%s" % type(e).__name__))
        return 1


if __name__ == "__main__":
    sys.exit(main())
