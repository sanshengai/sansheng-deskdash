# net-latency · 网络延迟

对你关心的若干主机测「本机视角」的实时延迟,以状态色(绿/黄/红/灰)一目了然。
支持两种探测方式,专为「代理环境测不准」的坑设计。

- **中文名**:网络延迟 / **英文名**:Network Latency
- **prefix**:`Net` / **分类**:network / **交互**:无

## 用途(what)

每个目标一行:左边显示名,右边延迟(如 `184 ms` / `超时`),颜色随延迟变化(绿 <80ms,黄 <200ms,红 ≥200ms,灰=不通)。最多 5 个目标(带区固定 5 行,超出截断)。

两种探测方式(`kind`):

| kind | 测什么 | 适用 |
|---|---|---|
| `ping` | ICMP 平均延迟 | 国内域名、裸 IP |
| `tls` | 完整 TLS 握手耗时 | 境外站点 |

### ⚠ 为什么境外站要用 `tls` 而不是 `ping`

本机若走 Clash / 透明代理 TUN,ICMP/TCP 到**境外域名**会被 fake-IP 劫持成 `198.18.x`(测到的是本地回环,毫无意义)。只有 TLS 握手(ClientHello→ServerHello)必须经代理往返真源站,才能反映真实跨境延迟。国内域名 / 裸 IP 不被 fake-IP 劫持,用 `ping` 即可。(详见仓库 `references/data-sources.md`。)

## 配置(config)

复制 `config.example.json` 为 `config.json`:

```json
{
  "targets": [
    {"label": "百度", "host": "baidu.com", "kind": "ping"},
    {"label": "Cloudflare", "host": "1.1.1.1", "kind": "ping"},
    {"label": "GitHub", "host": "github.com", "kind": "tls"}
  ]
}
```

- `host` 必填;`label` 缺省用 host;`kind` 缺省 `ping`。
- 无密钥字段(`secrets: []`)。

## 依赖与安全

- **依赖**:无(纯 stdlib:`socket` / `ssl` / `subprocess`)。
- **网络**:仅访问你在 `config.targets` 里声明的主机(装前会向你朗读)。**读/写本地**:无。
- **自限子进程**:ping 用 `-n`/`-w`(Windows)或 `-c`/`-W`(*nix)限次数 + 单包超时,再叠加进程级硬超时;ping 不派生孙进程,无挂死孤儿隐患。无 `eval` / `exec` / `shell=True`。

## 自验

```bash
python collector.py --config config.example.json
# → 单行 JSON,含 Count / T1Label / T1Text / T1Color ...
```
