# clock-calendar · 时钟日历

桌面看板的时间地基:一行活的 HH:MM 时钟 + 日期星期 + 当月日历(高亮今天)。
零网络、零密钥,是「60 秒上墙」首个模块的首选(首次体验失败率设计为零)。

- **中文名**:时钟日历 / **英文名**:Clock & Calendar
- **prefix**:`Clk` / **分类**:time / **交互**:无

## 用途(what)

- **活时钟**:HH:MM 由带区内原生 `Measure=Time` 每秒刷新(皮肤 `Update=1000`),不依赖采集器,永不停摆。
- **日期星期**:如 `7月10日 周四`,采集器每轮输出(每天变一次)。
- **当月日历**:采集器用 Pillow 渲染 `assets/calendar.png`(今天红圈),经绝对路径变量 `#ClkCalPng#` 传入带区的 Image meter。

> 为什么日历走采集器而非 Rainmeter 自绘:Rainmeter 的 `MTick` 触发脆弱(`MReload` 每 600s `!Refresh` 会清零 MTick,日历永不自动重绘 —— 2026-07-10 实测停在旧日期五天)。改由 orchestrator(计划任务每 2h + 登录)可靠触发采集器渲染。

## 配置(config)

复制 `config.example.json` 为 `config.json`(可省略,全用默认):

| 字段 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `show_calendar` | `true` / `false` | `true` | 是否渲染显示当月日历 PNG |
| `week_start` | `monday` / `sunday` | `monday` | 每周起始日 |

无密钥字段(`secrets: []`)。

## 依赖与安全

- **依赖**:`Pillow`(白名单内;仅日历渲染用)。Pillow 缺失或字体异常时,时钟与日期照常工作,日历自动降级为不显示,不会拖垮整个模块。
- **网络**:无。**读本地**:无。**写本地**:仅模块自身 `assets/calendar.png`。
- 无 `eval` / `exec` / `shell=True`;字体路径优先微软雅黑(Windows 自带),缺失回退 PIL 默认位图字体。

## 自验

```bash
python collector.py --config config.example.json
# → 单行 JSON,含 DateText / YearMonth / CalPng(绝对路径)/ CalReady=1
```
