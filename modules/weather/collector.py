# modules/weather/collector.py — 天气模块:最近7天 + 今日降雨。
# 双 provider(open-meteo 免 key 默认 / 彩云 token 升级档)+ 双定位(manual 城市 / auto IP)。
# 迁自私有仓 collectors/weather.py:入口改 `--config`,输出拍平为扁平标量(band.inc 直接引用),
# 错误走结构化 err(不抛裸异常);密钥(彩云 token)只从 config 读,示例用 open-meteo 免密。
#
# 契约:`python collector.py --config <config.json>`,stdout 单行 JSON;成功=扁平 outputs,失败=err。
# 自包含 stdlib(urllib);deps: [](urllib 属 stdlib)。无 eval/exec/shell=True。
#
# ⚠ 几何耦合:7 列 x 中心 COLS_X 与曲线相对 y 范围(CURVE_Y_TOP/BOT)必须与 band.inc 一致
#   (band.inc 的 [WxMaxCurve]/[WxMinCurve] meter Y=90,列 String 的 X 用同一组值)。改一处须同步。
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime

# —— 带区几何(须与 band.inc 一致)——
COLS_X = [44, 99, 155, 210, 265, 321, 376]     # 7 列中心 x(内区 16..404 均分)
CURVE_Y_TOP = 2.0                              # 曲线相对 meter 原点(meter Y=90)的上边界(高温靠上)
CURVE_Y_BOT = 30.0                             # 下边界(低温靠下)

CITY_LATLON = {
    "长沙": (28.23, 112.94), "北京": (39.90, 116.41), "上海": (31.23, 121.47),
    "广州": (23.13, 113.26), "深圳": (22.54, 114.06), "杭州": (30.27, 120.15),
    "成都": (30.57, 104.07), "武汉": (30.59, 114.31), "西安": (34.34, 108.94),
    "南京": (32.06, 118.80), "重庆": (29.56, 106.55), "天津": (39.34, 117.36),
    "苏州": (31.30, 120.62), "郑州": (34.75, 113.62), "长春": (43.82, 125.32),
    "沈阳": (41.81, 123.43), "哈尔滨": (45.80, 126.53), "济南": (36.65, 117.12),
    "青岛": (36.07, 120.38), "合肥": (31.82, 117.23), "福州": (26.07, 119.30),
    "厦门": (24.48, 118.09), "南昌": (28.68, 115.86), "昆明": (25.04, 102.71),
    "贵阳": (26.65, 106.63), "南宁": (22.82, 108.32), "太原": (37.87, 112.55),
    "石家庄": (38.04, 114.51), "兰州": (36.06, 103.83), "乌鲁木齐": (43.83, 87.62),
    "呼和浩特": (40.84, 111.75), "银川": (38.49, 106.23), "西宁": (36.62, 101.78),
    "海口": (20.04, 110.32), "拉萨": (29.65, 91.14), "宁波": (29.87, 121.55),
    "东莞": (23.02, 113.75), "无锡": (31.49, 120.31), "大连": (38.91, 121.61),
    "香港": (22.32, 114.17), "澳门": (22.19, 113.54), "台北": (25.03, 121.57),
}

_WEEKDAY = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_WMO = {  # WMO 天气码(Open-Meteo)→ 短中文
    0: "晴", 1: "多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾",
    51: "小雨", 53: "小雨", 55: "中雨", 56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "暴雨", 85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨", 99: "雷阵雨",
}

_SKYCON = {  # 彩云 skycon → 短中文
    "CLEAR_DAY": "晴", "CLEAR_NIGHT": "晴",
    "PARTLY_CLOUDY_DAY": "多云", "PARTLY_CLOUDY_NIGHT": "多云", "CLOUDY": "阴",
    "LIGHT_HAZE": "霾", "MODERATE_HAZE": "霾", "HEAVY_HAZE": "霾",
    "LIGHT_RAIN": "小雨", "MODERATE_RAIN": "中雨", "HEAVY_RAIN": "大雨", "STORM_RAIN": "暴雨",
    "FOG": "雾", "LIGHT_SNOW": "小雪", "MODERATE_SNOW": "中雪",
    "HEAVY_SNOW": "大雪", "STORM_SNOW": "暴雪", "DUST": "浮尘", "SAND": "沙尘", "WIND": "大风",
}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


class _NetError(Exception):
    """网络/HTTP 层失败(归一为 network 错误)。"""


class _AuthError(Exception):
    """provider 需密钥但未提供(归一为 auth 错误)。"""


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


# —— 曲线(迁自 lib/inc_writer,自包含复制)——

def _temp_points(temps, xs, y_top, y_bot, vmin, vmax):
    span = (vmax - vmin) or 1
    return [(x, y_bot - (v - vmin) / span * (y_bot - y_top))
            for x, v in zip(xs, temps) if v is not None]


def _temp_curve(temps, xs, y_top, y_bot, vmin, vmax):
    """温度序列 → Rainmeter Path 贝塞尔(CurveTo,D2D 原生平滑);<2 有效点 → 空串。
    控制点 Catmull-Rom:C1=P1+(P2-P0)/6, C2=P2-(P3-P1)/6。"""
    pts = _temp_points(temps, xs, y_top, y_bot, vmin, vmax)
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


# —— 数据源(迁自私有仓,_get 抛 _NetError)——

def _get(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        raise _NetError(type(e).__name__)


def _wmo_label(code):
    try:
        return _WMO.get(int(code), "—")
    except (TypeError, ValueError):
        return "—"


def _skycon_label(v):
    return _SKYCON.get(str(v or "").upper(), "—")


def _round_or_none(v):
    try:
        return round(float(v))
    except (TypeError, ValueError):
        return None


def _rain_level(mm):
    if mm >= 15:
        return "暴雨"
    if mm >= 8:
        return "大雨"
    if mm >= 2.5:
        return "中雨"
    if mm > 0:
        return "小雨"
    return ""


def _today_rain(times, precips):
    wet = [(t, p) for t, p in zip(times, precips) if (p or 0) > 0.1]
    if not wet:
        return {"raining": False, "summary": "今日无雨"}
    peak = max(p for _, p in wet)
    level = _rain_level(peak)
    s = int(str(wet[0][0])[11:13])
    e = int(str(wet[-1][0])[11:13])
    window = "%d时" % s if s == e else "%d-%d时" % (s, e)
    return {"raining": True, "summary": "今日 %s %s" % (window, level)}


def resolve_location(cfg):
    """→ (lat, lon, city_label)。显式经纬度 > auto(IP) > manual(内置表) > geocoding 兜底 > 长沙。"""
    if cfg.get("lat") is not None and cfg.get("lon") is not None:
        return float(cfg["lat"]), float(cfg["lon"]), cfg.get("city") or "手动"
    if cfg.get("location_mode") == "auto":
        try:
            # ⚠ 走代理(Clash TUN)时 IP 定位会拿到代理出口位置(可能境外);非代理机器才准。
            j = _get("http://ip-api.com/json/?fields=status,lat,lon,city&lang=zh-CN", timeout=10)
            if j.get("status") == "success" and j.get("lat") is not None:
                return float(j["lat"]), float(j["lon"]), j.get("city") or "本机"
        except _NetError:
            pass
    city = cfg.get("city") or "长沙"
    if city in CITY_LATLON:
        lat, lon = CITY_LATLON[city]
        return lat, lon, city
    try:                                   # 内置表没有 → geocoding 子域兜底(best-effort)
        g = _get("https://geocoding-api.open-meteo.com/v1/search?name="
                 + urllib.parse.quote(city) + "&count=1&language=zh", timeout=10)
        r = g["results"][0]
        return float(r["latitude"]), float(r["longitude"]), r.get("name") or city
    except (_NetError, KeyError, IndexError):
        return CITY_LATLON["长沙"][0], CITY_LATLON["长沙"][1], "长沙"


def _uv_desc(idx):
    try:
        idx = float(idx)
    except (TypeError, ValueError):
        return ""
    if idx >= 11:
        return "极强"
    if idx >= 8:
        return "很强"
    if idx >= 6:
        return "强"
    if idx >= 3:
        return "中等"
    return "弱"


def _open_meteo(lat, lon):
    u = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
         "&daily=weather_code,precipitation_probability_max,temperature_2m_max,"
         "temperature_2m_min,uv_index_max"
         "&hourly=precipitation"
         "&current=temperature_2m,apparent_temperature,relative_humidity_2m"
         "&forecast_days=7&timezone=auto") % (lat, lon)
    r = _get(u)
    d = r["daily"]
    days = []
    for i in range(min(7, len(d["time"]))):
        dt = datetime.fromisoformat(d["time"][i])
        days.append({"date": d["time"][i][5:], "weekday": _WEEKDAY[dt.weekday()],
                     "weather": _wmo_label(d["weather_code"][i]),
                     "rain_prob": d["precipitation_probability_max"][i] or 0,
                     "tmax": round(d["temperature_2m_max"][i]),
                     "tmin": round(d["temperature_2m_min"][i])})
    h = r["hourly"]
    today = _today_rain(h["time"][:24], h["precipitation"][:24])
    cur = r.get("current", {}) or {}
    today.update({
        "temp": _round_or_none(cur.get("temperature_2m")),
        "feels": _round_or_none(cur.get("apparent_temperature")),
        "humidity": _round_or_none(cur.get("relative_humidity_2m")),
        "uv": _uv_desc((d.get("uv_index_max") or [None])[0]),
    })
    return {"days": days, "today": today}


def _caiyun(lat, lon, token):
    """彩云 v2.6 weather(经度在前)。7 天温度 + 实况 + 关键点自然语言。"""
    u = ("https://api.caiyunapp.com/v2.6/%s/%s,%s/weather?dailysteps=7&hourlysteps=24"
         % (token, lon, lat))
    res = _get(u)["result"]
    daily = res["daily"]
    skycon, temps = daily["skycon"], daily["temperature"]
    precip_d = daily.get("precipitation", [])
    days = []
    for i in range(min(7, len(skycon))):
        dt = datetime.fromisoformat(skycon[i]["date"][:10])
        try:
            prob = round(precip_d[i].get("probability", 0))
        except (IndexError, TypeError, AttributeError):
            prob = 0
        days.append({"date": skycon[i]["date"][5:10], "weekday": _WEEKDAY[dt.weekday()],
                     "weather": _skycon_label(skycon[i]["value"]), "rain_prob": prob,
                     "tmax": round(temps[i]["max"]), "tmin": round(temps[i]["min"])})
    rt = res.get("realtime", {}) or {}
    hum = rt.get("humidity")
    today = {
        "summary": res.get("forecast_keypoint", "") or "今日无雨",
        "raining": (rt.get("precipitation", {}).get("local", {}) or {}).get("intensity", 0) > 0.03,
        "temp": _round_or_none(rt.get("temperature")),
        "feels": _round_or_none(rt.get("apparent_temperature")),
        "humidity": round(hum * 100) if isinstance(hum, (int, float)) else None,
    }
    return {"days": days, "today": today}


def _fetch(cfg):
    """按 provider 取原始 {days, today, city, provider};密钥缺失/网络失败抛结构化异常。"""
    lat, lon, city = resolve_location(cfg)
    provider = cfg.get("provider", "open-meteo")
    if provider == "caiyun":
        token = cfg.get("caiyun_token") or ""
        if not token:
            raise _AuthError("caiyun")
        data = _caiyun(lat, lon, token)
        if len(data["days"]) < 7:
            # 彩云免费档 dailysteps 实测上限 3 天(请求 7 只回 3)→ open-meteo 按日期补齐后几天。
            try:
                om = _open_meteo(lat, lon)
                have = {d.get("date") for d in data["days"]}
                data["days"] += [d for d in om["days"]
                                 if d.get("date") not in have][: 7 - len(data["days"])]
            except _NetError:
                pass
    else:
        provider = "open-meteo"
        data = _open_meteo(lat, lon)
    return dict(data, city=city, provider=provider)


# —— 拍平为扁平标量 outputs(全部字符串,band.inc 直接引用)——

def _flatten(raw):
    days = raw.get("days", [])[:7]
    today = raw.get("today", {}) or {}
    city = raw.get("city", "")
    out = {"City": city, "Provider": raw.get("provider", ""),
           "UpdatedAt": datetime.now().astimezone().strftime("%H:%M")}

    t = today.get("temp")
    out["NowTempText"] = ("%d°" % t) if t is not None else "—°"
    now_weather = days[0]["weather"] if days else "—"
    desc = "%s · %s" % (city, now_weather)
    feels = today.get("feels")
    if feels is not None:
        desc += "  体感%d°" % feels
    out["NowDesc"] = desc
    summary = today.get("summary", "") or ""
    hum = today.get("humidity")
    if hum is not None:
        summary = (summary + "  湿度%d%%" % hum).strip()
    out["NowSummary"] = summary

    for i in range(7):
        n = i + 1
        if i < len(days):
            d = days[i]
            out["D%dLabel" % n] = "今天" if i == 0 else d["weekday"]
            out["D%dDate" % n] = d.get("date", "")
            out["D%dWeather" % n] = d.get("weather", "")
            out["D%dTmaxText" % n] = "%d°" % d["tmax"]
            out["D%dTminText" % n] = "%d°" % d["tmin"]
            out["D%dProbText" % n] = "%d%%" % (d.get("rain_prob") or 0)
        else:
            out["D%dLabel" % n] = ""
            out["D%dDate" % n] = ""
            out["D%dWeather" % n] = ""
            out["D%dTmaxText" % n] = ""
            out["D%dTminText" % n] = ""
            out["D%dProbText" % n] = ""

    # 曲线:tmax/tmin 共享 vmin/vmax(竖直可比);<2 有效点 → 空串
    tmaxes = [d["tmax"] for d in days]
    tmins = [d["tmin"] for d in days]
    xs = COLS_X[:len(days)]
    both = [v for v in (tmaxes + tmins) if v is not None]
    if len(both) >= 2:
        vmin, vmax = min(both), max(both)
        out["MaxPath"] = _temp_curve(tmaxes, xs, CURVE_Y_TOP, CURVE_Y_BOT, vmin, vmax)
        out["MinPath"] = _temp_curve(tmins, xs, CURVE_Y_TOP, CURVE_Y_BOT, vmin, vmax)
    else:
        out["MaxPath"] = ""
        out["MinPath"] = ""
    return out


def load_config(path):
    cfg = {"provider": "open-meteo", "caiyun_token": "",
           "location_mode": "manual", "city": "长沙", "lat": None, "lon": None}
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def collect(cfg):
    """采集天气 → 扁平 outputs 或结构化 err。异常在此归类,绝不回显 token。"""
    try:
        raw = _fetch(cfg)
    except _AuthError:
        return _err("auth", False,
                    "provider=caiyun 需要 caiyun_token,但 config 未提供 token;"
                    "改用 provider=open-meteo(免密)或在 config.json 补上 caiyun_token。")
    except _NetError:
        return _err("network", True,
                    "天气 API 请求失败(网络/超时/被代理拦截);检查联网或代理设置后重试。")
    except (KeyError, IndexError, ValueError, TypeError) as e:
        return _err("provider", True,
                    "天气 API 返回结构异常(%s),可能是接口变更或该地点无数据。" % type(e).__name__)
    return _flatten(raw)


def main(argv=None):
    ap = argparse.ArgumentParser(description="天气采集器(open-meteo 免密 / 彩云 token)")
    ap.add_argument("--config", default=None, help="config.json 路径")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    try:
        res = collect(cfg)
    except Exception as e:
        res = _err("provider", True, "天气采集器未预期异常:%s" % type(e).__name__)
    _emit(res)
    return 0 if "ok" not in res else 1


if __name__ == "__main__":
    sys.exit(main())
