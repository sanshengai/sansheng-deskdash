# lib/inc_writer.py — 把各模块输出拍平成 Rainmeter 变量文件(data.inc)文本
# 纯函数便于单测;orchestrator 汇总各模块 collector 输出后调 to_inc,原子写盘(UTF-16,
# 否则 Rainmeter 读中文乱码——GBK 桥,见 references/encoding.md)。
# 原生 skin 用 @Include 读取,取值写 [#VarName]。
from datetime import datetime


def _san(v):
    """变量值消毒:去掉会被 Rainmeter 误解析的字符;None→空。

    # 是 Rainmeter 变量引用符、[] 是节/measure 引用符,值里字面出现会被误解析;
    换行会把一条变量拆成两行,直接破坏 .inc 语法。
    """
    if v is None:
        return ""
    return (str(v).replace("#", "＃").replace("[", "(").replace("]", ")")
            .replace("\n", " ").replace("\r", " ").strip())


def fmt_time(iso):
    """ISO 时间(带时区)→ 'HH:MM';空/无法解析→''。各板块"更新 HH:MM"标注用绝对时间(不随显示漂移)。"""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def temp_points(temps, xs, y_top, y_bot, vmin, vmax):
    """温度序列 → 曲线锚点 [(x, y)](高温靠上 y 小)。max/min 共享 vmin/vmax 才可竖直比较。"""
    span = (vmax - vmin) or 1
    return [(x, y_bot - (v - vmin) / span * (y_bot - y_top))
            for x, v in zip(xs, temps) if v is not None]


def temp_curve(temps, xs, y_top, y_bot, vmin, vmax):
    """温度序列 → Rainmeter Path 贝塞尔曲线(每段一个 CurveTo,D2D 原生平滑)。<2 有效点 → 空串。
    密集短 LineTo 模拟曲线会有折线棱角/重影(2026-07-10 真机实证),CurveTo 根治。
    控制点由 Catmull-Rom 锚点精确换算:C1=P1+(P2-P0)/6, C2=P2-(P3-P1)/6。"""
    pts = temp_points(temps, xs, y_top, y_bot, vmin, vmax)
    if len(pts) < 2:
        return ""
    ext = [pts[0]] + pts + [pts[-1]]
    segs = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append("CurveTo %.1f,%.1f,%.1f,%.1f,%.1f,%.1f"
                    % (p2[0], p2[1], c1[0], c1[1], c2[0], c2[1]))
    return "%.1f,%.1f | " % pts[0] + " | ".join(segs)


def to_inc(outputs):
    """各模块输出 → data.inc 文本(以 [Variables] 开头)。

    outputs: dict[str, dict] —— {模块 prefix: {键: 标量值}},拍平为 `<Prefix><Key>=value` 行。
    - 值一律过 _san 消毒;bool 转 1/0(Rainmeter 无布尔,"True" 字面量喂 Calc 会炸)。
    - 值遇 list/tuple/set/嵌套 dict 抛 ValueError:模块须自行拍平为标量键
      (如 days[0]["tmax"] → "1Tmax"),to_inc 不猜任何拍平规则。
    - prefix 全局唯一由契约层/装配器把关(dict 键天然不重复,此处不重复校验)。
    """
    lines = ["[Variables]",
             "; 自动生成,勿手改 — orchestrator 每轮覆盖"]
    for prefix, kv in (outputs or {}).items():
        if not isinstance(kv, dict):
            raise ValueError("模块 %r 的输出须是 dict,收到 %s" % (prefix, type(kv).__name__))
        for key, v in kv.items():
            if not isinstance(key, str) or not key:
                raise ValueError("模块 %r 含非法输出键 %r:键须是非空字符串" % (prefix, key))
            if isinstance(v, (dict, list, tuple, set)):
                raise ValueError(
                    "模块 %r 的输出键 %r 是 %s;to_inc 不接受容器值,模块须自行拍平为标量"
                    % (prefix, key, type(v).__name__))
            if isinstance(v, bool):
                v = 1 if v else 0
            lines.append("%s%s=%s" % (prefix, key, _san(v)))
    return "\n".join(lines) + "\n"
