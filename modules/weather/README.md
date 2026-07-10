# weather · 天气

桌面看板的天气模块:当前温度 + 今日降雨 + 未来 7 天高低温贝塞尔曲线。
双数据源(免密 / 升级档)、双定位(城市表 / IP),内置 40+ 城市经纬度表,免运行时 geocoding。

- **中文名**:天气 / **英文名**:Weather
- **prefix**:`Wx` / **分类**:weather / **交互**:无

## 用途(what)

- **实况行**:当前温度、城市、今日天气、体感、湿度。
- **7 天预报**:每列 周几 / 高温 / 低温,高低温用 CurveTo 贝塞尔曲线(D2D 原生平滑)分别以暖/冷色描出趋势。

## 数据源与定位

| provider | 需密钥 | 说明 |
|---|---|---|
| `open-meteo`(默认) | 否 | 免费免密,全球覆盖 |
| `caiyun`(彩云) | 是(`caiyun_token`) | 实况更细(体感/湿度/自然语言),免费档日预报仅 3 天,自动用 open-meteo 补齐后几天 |

| location_mode | 说明 |
|---|---|
| `manual`(默认) | 用内置城市表(北京/上海/广州/长沙…40+ 省会与主要城市) |
| `auto` | IP 定位。⚠ 走代理(Clash TUN)时会拿到代理出口位置(可能境外),非代理机器才准 |

内置城市表未命中时,回退 open-meteo geocoding 子域兜底一次。

## 配置(config)

复制 `config.example.json` 为 `config.json`:

```json
{
  "provider": "open-meteo",
  "caiyun_token": "",
  "location_mode": "manual",
  "city": "北京"
}
```

- 用彩云:`"provider": "caiyun"` 并在 `caiyun_token` 填入你的 token(在 [彩云开放平台](https://platform.caiyunapp.com/) 申请)。
- 也可用 `"lat"` / `"lon"` 显式经纬度(优先于 `city`)。
- 🔴 **密钥安全**:`caiyun_token` 只从 `config.json` 读(已 gitignore),绝不进代码/日志/错误消息;`config.example.json` 留空。

## 依赖与安全

- **依赖**:无(纯 stdlib `urllib`)。
- **网络**:`api.open-meteo.com`;彩云档加 `api.caiyunapp.com`;auto 定位加 `ip-api.com`;城市表未命中加 `geocoding-api.open-meteo.com`。**读/写本地**:无。
- 无 `eval` / `exec` / `shell=True`;失败返回结构化错误(auth / network / provider),不抛裸异常。

## 自验

```bash
python collector.py --config config.example.json
# → 单行 JSON,含 City / NowTempText / D1TmaxText.. / MaxPath(贝塞尔) 等
```

> ⚠ 几何耦合:`collector.py` 顶部的 `COLS_X` / `CURVE_Y_TOP/BOT` 必须与 `band.inc` 的列 X 和曲线 meter `Y=90` 一致,改一处须同步另一处。
