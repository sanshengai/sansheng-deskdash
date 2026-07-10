# modules/__ID__/collector.py — 采集器骨架(new_module.py 生成;把 TODO 换成真实逻辑)。
# DESKDASH-SKELETON-STUB  ← 实现真实采集后删掉这行标记(validate 据它提示"还是骨架桩")。
#
# 契约(与 orchestrator 的进程边界):`python collector.py --config <config.json>`,stdout 单行 JSON。
#   · 成功 = 扁平 outputs dict(键→标量,过 output.schema.json);
#   · 失败 = {"ok": false, "err": {kind, retryable, hint_for_agent}}(不抛裸异常)。
#
# 铁律(照抄,别改):
#   · 自包含 stdlib —— **不 import 仓内 scripts/lib**(模块要能拷走独立跑);小工具内联复制。
#   · stdout 走 UTF-8 字节(_emit),**不用 print**(Windows cp936 会让中文乱码,见 references/encoding.md)。
#   · 输出**扁平标量**(值不是 dict/list);嵌套请自己拍平(days[0]['tmax'] → 键 "1Tmax")。
#   · 网络调用**必须带 timeout=**;调外部命令**必须自限**(ping -n/-w 等)。禁 eval/exec/shell=True。
#   · 密钥只从 config 读,**绝不进 stdout/日志/异常消息**。privacy.network 声明与实际请求域必须一致。
import argparse
import json
import os
import sys


def _err(kind, retryable, hint):
    """规范化错误对象;kind ∈ {auth,rate_limit,network,provider,bug};hint 内绝不拼密钥值。"""
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
    """读 config.json;缺失/坏 JSON → 用默认。把默认换成你模块真正需要的字段。"""
    cfg = {}  # TODO: 填模块默认配置,如 {"example_option": ""}
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def collect(cfg):
    """采集数据 → 扁平 outputs dict(键→标量)。骨架先返回占位输出,能过 output.schema。

    TODO: 把下面替换成真实采集逻辑。要点:
      · 网络请求带 timeout;失败按类别返回 _err("network"|"provider"|"auth"|"rate_limit", ...)。
      · 输出的每个键都要在 output.schema.json 里声明(additionalProperties:false)。
      · 中文文本原样放进值即可(经 data.inc 的 UTF-16 通道上屏),band.inc 用 #__PREFIX__键# 引用。
    """
    return {
        "Title": "__NAME__",
        "Status": "待实现",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="__ID__ 采集器")
    ap.add_argument("--config", default=None, help="config.json 路径(可缺省)")
    args = ap.parse_args(argv)
    try:
        res = collect(load_config(args.config))
    except Exception as e:  # 任何未预期异常 → 结构化 bug(不抛裸栈)
        res = _err("bug", False, "__ID__ 采集器未预期异常:%s" % type(e).__name__)
    _emit(res)
    return 0 if "ok" not in res else 1


if __name__ == "__main__":
    sys.exit(main())
