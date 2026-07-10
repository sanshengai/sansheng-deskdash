# server-status · 服务状态

盯你关心的若干服务/主机是否在线:HTTP health URL 探测(状态码 + 响应时间)或 ping 延迟,以状态色(绿/黄/红/灰)一眼看清。

- **中文名**:服务状态 / **英文名**:Server Status
- **prefix**:`Srv` / **分类**:system / **交互**:无

## 用途(what)

每行:左边显示名,右边状态文本,颜色随状态变化。最多 5 个主机(带区固定 5 行,超出截断)。

| 探测方式 | 触发 | 右侧文本示例 | 判定 |
|---|---|---|---|
| HTTP | 该项配了 `url` | `200 · 84ms` | 2xx/3xx=在线(绿,<500ms;否则黄),4xx/5xx=红,无响应=灰 |
| ping | 该项只配 `ping_host` | `84 ms` | 绿<80ms,黄<200ms,红≥200ms,不通=灰 |

> HTTP 探测更贴近「服务可用」(应用层健康),ping 只证「主机可达」。两者都配时以 `url`(HTTP)为准。

## P0 边界:不做 SSH

本模块 P0 **只做 HTTP + ping**,不做 SSH 远端采集(内存/磁盘/负载等留 P1)。这样零远端凭证、零 SSH 依赖——填个 URL 就能用,也不把任何私有远端采集细节带进公开仓。

## 配置(config)

复制 `config.example.json` 为 `config.json`:

```json
{
  "hosts": [
    {"label": "官网", "url": "https://example.com"},
    {"label": "API", "url": "https://example.com/health"},
    {"label": "源站", "ping_host": "1.1.1.1"}
  ]
}
```

- 每项 `label` 必填;`url` 与 `ping_host` 至少给一个(都给 → 用 `url`)。
- 无密钥字段(`secrets: []`)。

## 依赖与安全

- **依赖**:无(纯 stdlib:`urllib` / `subprocess` / `socket`)。
- **网络**:仅访问你在 `config.hosts` 里声明的主机(装前会向你朗读)。目标由用户 config 指定,故 `widget.json` 的 `privacy.network` 用机读哨兵 `"<user-configured>"` 表达「运行时目标集来自 `config.hosts`」——CI 的「AST 请求域 ⊆ privacy 声明」对本模块转为「请求域 ⊆ config.hosts 主机」校验。**读/写本地**:无。
- **自限子进程**:ping 用 `-n`/`-w`(Windows)或 `-c`/`-W`(*nix)限次数 + 单包超时,再叠加进程级硬超时;ping 不派生孙进程。无 `eval` / `exec` / `shell=True`。

## 自验

```bash
python collector.py --config config.example.json
# → 单行 JSON,含 Count / Host1Label / Host1Text / Host1Color ...
```

纯逻辑(`http_color` / `ping_color` / `measure_host`)离线单测见 `tests/test_task6_modules.py`。
