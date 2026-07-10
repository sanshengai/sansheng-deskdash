# modules/net-latency/collector.py — 网络延迟采集器:对若干目标测本机视角延迟(TLS 握手 / ICMP ping)。
#
# 契约:`python collector.py --config <config.json>`,stdout 单行 JSON;成功=扁平 outputs,失败=err 结构。
# 自包含 stdlib(socket/ssl/subprocess);无第三方依赖(deps: [])。无 eval/exec/shell=True。
#
# config.targets: [{label, host, kind}],kind ∈ {tls, ping}:
#   · tls  —— 完整 TLS 握手耗时(ClientHello→ServerHello),取多次最小。适合境外站(见下 fake-IP 坑)。
#   · ping —— ICMP 平均延迟。适合国内域名 / 裸 IP。
#
# ⚠ fake-IP 坑(references/data-sources.md 详载):本机若走 Clash/透明代理 TUN,ICMP/TCP 到「境外域名」
#   会被 fake-IP 劫持成 198.18.x(测到本地回环,无意义);ping 国内域名 / 裸 IP 不被劫持。境外站的真实
#   跨境延迟只有 TLS 握手能测到(握手必须经代理往返真源站)。故境外目标用 kind=tls,国内/IP 用 kind=ping。
#
# ⚠ 自限子进程(审阅加固):ping 用 `-n`/`-w`(Windows)或 `-c`/`-W`(*nix)限次数+单包超时,再叠加
#   subprocess.run(timeout=) 硬杀;ping 不派生孙进程,无挂死孤儿隐患。
import argparse
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time

MAX_TARGETS = 5                                                   # band.inc 固定 5 行,多余目标截断
_ALLOWED_KIND = ("tls", "ping")
_IS_WIN = sys.platform == "win32"


def _err(kind, retryable, hint):
    return {"ok": False, "err": {"kind": kind, "retryable": bool(retryable),
                                 "hint_for_agent": str(hint)}}


def _emit(obj):
    """单行 JSON → stdout 强制 UTF-8 字节(避开 Windows cp936 与 orchestrator utf-8 解码不一致)。"""
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
    return {"targets": []}


def _ping_ms(host):
    """ICMP 平均延迟 ms(下限 1);不通/超时/异常 → None。自限:限 2 包 + 单包 2s + 总 8s 硬杀。"""
    if _IS_WIN:
        cmd = ["ping", "-n", "2", "-w", "2000", host]
    else:
        cmd = ["ping", "-c", "2", "-W", "2", host]
    kw = {"capture_output": True, "timeout": 8}
    if _IS_WIN:
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW           # 计划任务 pythonw 下不闪黑窗
    try:
        r = subprocess.run(cmd, **kw)                               # noqa: S603 (list 参数,非 shell)
    except (OSError, subprocess.TimeoutExpired):
        return None
    # Windows 中文 ping 输出 GBK;英文/*nix 输出 ASCII/UTF-8。GBK 解码对 ASCII 也安全。
    out = r.stdout.decode("gbk" if _IS_WIN else "utf-8", errors="replace")
    nums = re.findall(r"(\d+)\s*ms", out)                           # 结尾"平均/Average = Xms"取最后一个
    return max(1, int(nums[-1])) if (r.returncode == 0 and nums) else None


def _tls_ms(host, tries=2, timeout=5):
    """完整 TLS 握手耗时 ms(取多次最小);不通 → None。反映境外真实跨境延迟(见文件头 fake-IP 坑)。"""
    ctx = ssl.create_default_context()
    best = None
    for _ in range(tries):
        try:
            t = time.perf_counter()
            raw = socket.create_connection((host, 443), timeout=timeout)
            s = ctx.wrap_socket(raw, server_hostname=host)
            s.do_handshake()
            s.close()
            ms = (time.perf_counter() - t) * 1000
            best = ms if best is None else min(best, ms)
        except (OSError, ssl.SSLError):
            pass
    return round(best) if best is not None else None


def _color(ms):
    """延迟 → 状态色(r,g,b,a)。灰=不通,绿<80,黄<200,红≥200。"""
    if ms is None or ms < 0:
        return "120,130,145,255"
    if ms < 80:
        return "82,199,120,255"
    if ms < 200:
        return "230,180,80,255"
    return "232,110,110,255"


def _measure(target):
    """单目标 → (ms|None)。kind 未知视为 ping。"""
    host = str(target.get("host") or "").strip()
    if not host:
        return None
    kind = str(target.get("kind") or "ping").lower()
    return _tls_ms(host) if kind == "tls" else _ping_ms(host)


def collect(cfg):
    """采集各目标延迟 → 扁平 outputs(T1..T{MAX} 槽位;未用槽位空白)。"""
    targets = (cfg or {}).get("targets") or []
    if not isinstance(targets, list):
        return _err("bug", False, "config.targets 必须是数组,每项含 label/host/kind。")
    targets = targets[:MAX_TARGETS]
    out = {"Title": "网络延迟", "Count": len(targets)}
    for i in range(MAX_TARGETS):
        n = i + 1
        if i < len(targets):
            t = targets[i]
            label = str(t.get("label") or t.get("host") or "目标%d" % n)
            ms = _measure(t)
            ok = ms is not None and ms >= 0
            out["T%dLabel" % n] = label
            out["T%dHost" % n] = str(t.get("host") or "")
            out["T%dKind" % n] = str(t.get("kind") or "ping").lower()
            out["T%dMs" % n] = ms if ok else -1
            out["T%dText" % n] = ("%d ms" % ms) if ok else "超时"
            out["T%dOk" % n] = 1 if ok else 0
            out["T%dColor" % n] = _color(ms if ok else None)
        else:                                                       # 空槽位:变量存在但不显示
            out["T%dLabel" % n] = ""
            out["T%dHost" % n] = ""
            out["T%dKind" % n] = ""
            out["T%dMs" % n] = -1
            out["T%dText" % n] = ""
            out["T%dOk" % n] = 0
            out["T%dColor" % n] = "0,0,0,0"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="网络延迟采集器")
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
        _emit(_err("bug", False, "网络延迟采集器未预期异常:%s" % type(e).__name__))
        return 1


if __name__ == "__main__":
    sys.exit(main())
