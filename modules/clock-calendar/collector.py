# modules/clock-calendar/collector.py — 时钟 + 当月日历采集器(零网络零密钥)。
#
# 契约(与 orchestrator 的进程边界):`python collector.py --config <config.json>`,stdout 打印单行 JSON。
#   · 成功 = 扁平 outputs dict(键→标量);失败 = {"ok":false,"err":{kind,retryable,hint_for_agent}}。
# 自包含:仅 stdlib + 可选 Pillow(deps 声明 ["Pillow"]);不 import 仓内 lib(模块在 board 里是
#   扁平子目录 board/<id>/,拿不到 ../../scripts/lib 的固定相对路径 —— 见设计稿抽取表)。
#
# 分工:活的 HH:MM 时钟由 band.inc 的原生 [ClkMeasureTime](Measure=Time)每秒刷(皮肤 Update=1000),
#   本采集器只出「日期/星期」文本 + 渲染当月日历 PNG(render_cal 迁自私有仓 todo.py)。
#   Rainmeter 的 MTick 触发脆弱(MReload 每 600s !Refresh 会清 MTick,日历永不自动重绘 —— 2026-07-10
#   实测),故由 orchestrator(计划任务每 2h + 登录)可靠触发本采集器保证日历随日期更新。
#
# 安全铁律:无 eval/exec/shell=True;零网络零密钥;只写自身目录(assets/calendar.png)。
import argparse
import calendar
import json
import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.join(_HERE, "assets")
_CAL_PNG = os.path.join(_ASSETS, "calendar.png")

_WEEKDAY = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _err(kind, retryable, hint):
    """规范化错误对象(与 lib.contract.make_error 同形);hint 内绝不拼密钥值。"""
    return {"ok": False, "err": {"kind": kind, "retryable": bool(retryable),
                                 "hint_for_agent": str(hint)}}


def _emit(obj):
    """单行 JSON 写 stdout —— 强制 UTF-8 字节(Windows 控制台默认 cp936,print 会让
    orchestrator 的 utf-8 解码乱码;直接写 buffer 根治)。"""
    b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(b + b"\n")
    try:
        sys.stdout.buffer.flush()
    except OSError:
        pass                                                      # 下游管道提前关闭(EINVAL)时不炸;进程退出仍会冲刷


def load_config(path):
    """读 config.json;缺失/坏 JSON → 用默认(零配置模块可无此文件)。"""
    cfg = {"show_calendar": True, "week_start": "monday"}
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def render_cal(now, week_start="monday", out_path=_CAL_PNG):
    """渲染当月日历 PNG(高亮今天),返回绝对路径;PIL 缺失/字体缺失 → 抛异常交上层降级。
    迁自私有仓 todo.py 的 render_cal:去 sandy 专属路径,加 week_start 与字体兜底。"""
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    first = 6 if str(week_start).lower() == "sunday" else 0        # 周日起 / 周一起(默认)
    weeks = calendar.Calendar(firstweekday=first).monthdayscalendar(now.year, now.month)
    while len(weeks) < 6:                                          # 补足 6 行,布局恒定
        weeks.append([0] * 7)
    heads = ["日", "一", "二", "三", "四", "五", "六"] if first == 6 else \
            ["一", "二", "三", "四", "五", "六", "日"]
    # 周末列下标(用于染色):周一起时 5/6;周日起时 0/6
    wknd = {0, 6} if first == 6 else {5, 6}

    W, top, row_h = 700, 96, 70
    H = top + 6 * row_h
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f_title, f_wk, f_day, f_dayb = _load_fonts()
    d.text((6, 4), "%d年%d月" % (now.year, now.month), font=f_title, fill=(230, 238, 247, 255))
    col_w = W / 7.0
    for i, w in enumerate(heads):
        cx = col_w * i + col_w / 2
        d.text((cx, 68), w, font=f_wk,
               fill=(235, 120, 120, 255) if i in wknd else (150, 160, 175, 255), anchor="mm")
    for r, week in enumerate(weeks):
        cy = top + r * row_h + row_h / 2
        for c, day in enumerate(week):
            if day == 0:
                continue
            cx = col_w * c + col_w / 2
            if day == now.day:
                rad = 25
                d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                          outline=(235, 80, 80, 255), width=3)
                d.text((cx, cy), str(day), font=f_dayb, fill=(246, 250, 255, 255), anchor="mm")
            else:
                col = (232, 150, 150, 235) if c in wknd else (203, 211, 220, 235)
                d.text((cx, cy), str(day), font=f_day, fill=col, anchor="mm")
    tmp = out_path + ".tmp.png"
    img.save(tmp)
    os.replace(tmp, out_path)
    return os.path.abspath(out_path)


def _load_fonts():
    """微软雅黑(Windows 自带);缺失 → PIL 默认位图字体兜底(不崩,只是丑)。"""
    from PIL import ImageFont
    try:
        return (ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 36),
                ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22),
                ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30),
                ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 30))
    except (OSError, IOError):
        d = ImageFont.load_default()
        return d, d, d, d


def collect(cfg):
    """采集时钟/日历变量 → 扁平 outputs dict。"""
    now = datetime.now().astimezone()                             # 系统本地时区(aware)
    out = {
        "DateText": "%d月%d日 %s" % (now.month, now.day, _WEEKDAY[now.weekday()]),
        "Weekday": _WEEKDAY[now.weekday()],
        "YearMonth": "%d年%d月" % (now.year, now.month),
        "Title": "日历",
        "CalPng": "",
        "CalReady": 0,
    }
    if cfg.get("show_calendar", True):
        try:
            out["CalPng"] = render_cal(now, cfg.get("week_start", "monday"))
            out["CalReady"] = 1
        except Exception:
            # PIL 缺失 / 字体异常 / 磁盘只读:时钟与日期仍可用(首次体验失败率设计为零),
            # 日历静默降级为不显示;不把它升级成整模块失败。
            out["CalPng"] = ""
            out["CalReady"] = 0
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="时钟+日历采集器")
    ap.add_argument("--config", default=None, help="config.json 路径(可缺省,零配置有默认)")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        _emit(collect(cfg))
        return 0
    except Exception as e:                                         # 任何未预期异常 → 结构化 bug(不抛裸栈)
        _emit(_err("bug", False, "时钟/日历采集器未预期异常:%s" % type(e).__name__))
        return 1


if __name__ == "__main__":
    sys.exit(main())
