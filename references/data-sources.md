# data-sources · 数据源实战坑:免费档上限 / 代理定位漂移 / TLS 测延迟 / 超时

采集器的可靠性大半栽在数据源与网络环境上。本篇记几条只有真机跑过才知道的坑,以及**采集器必须自带的超时与自限**纪律。

## 1. 彩云免费档 dailysteps 实测上限 3 天

- **现象**:调彩云 `weather?dailysteps=7` 想拿 7 天预报,**只回 3 天**。
- **根因**:彩云免费 token 的 `dailysteps` 实测被限到 3(2026-07 实测,请求 7 只回 3),不报错、只是静默少给。
- **解法**:采集器**按日期补齐**——用彩云已回的前几天,缺的后几天用 **open-meteo(免密)** 按 `date` 去重补上:
  ```python
  if len(data["days"]) < 7:
      om = _open_meteo(lat, lon)
      have = {d["date"] for d in data["days"]}
      data["days"] += [d for d in om["days"] if d["date"] not in have][:7 - len(data["days"])]
  ```
  补齐失败(open-meteo 也不通)不致命,保留彩云已有天数即可。**别信"文档说支持 7 天"就假定拿得到 7 天**(第一性:二手结论要实测)。

## 2. 代理(Clash TUN fake-IP)下测延迟必须用 TLS 握手

- **现象**:想测"本机到某境外站的真实访问延迟",用 `ping 域名` 或 `ping 1.1.1.1`,得到几十毫秒的漂亮数字——**但它是假的**。
- **根因**:本机若走 **Clash / 透明代理的 TUN 模式**,`auto-route` 把流量吸进代理:
  - **ICMP / TCP 到境外域名**被 **fake-IP 劫持**成 `198.18.x.x`(代理的假 IP 段)——你 ping 到的是**本地回环**,测的是本机自己,毫无意义;
  - `ping 1.1.1.1` 命中的是**就近 anycast 节点**(如 69ms),不反映到真实源站的跨境延迟。
- **解法**:境外目标测延迟用**完整 TLS 握手耗时**(`ClientHello → ServerHello`,取多次最小)。握手**必须经代理往返真源站**,才反映真实跨境延迟(实测某境外站 TLS≈184ms,正确地慢于国内假值)。
  ```python
  def _tls_ms(host, tries=2, timeout=5):
      ctx = ssl.create_default_context()
      best = None
      for _ in range(tries):
          try:
              t = time.perf_counter()
              raw = socket.create_connection((host, 443), timeout=timeout)
              s = ctx.wrap_socket(raw, server_hostname=host); s.do_handshake(); s.close()
              ms = (time.perf_counter() - t) * 1000
              best = ms if best is None else min(best, ms)
          except (OSError, ssl.SSLError):
              pass
      return round(best) if best is not None else None
  ```
- **反过来**:**国内域名 / 裸 IP 直连不被 fake-IP 劫持**,用 `kind=ping`(ICMP)即可,又快又准。所以 `net-latency` 让用户按目标选 `kind`:**境外站 `tls`,国内/IP `ping`**。

## 3. ip-api 定位在代理下漂到出口(可能境外)→ 手动城市优先

- **现象**:天气模块 `location_mode=auto`(IP 定位)在代理机上定位到境外城市,天气全错。
- **根因**:`ip-api.com` 按**出口 IP** 定位;走代理时出口是代理节点(可能在境外),定位自然漂。
- **解法**:**手动城市优先**——采集器内置省会/主要城市经纬度表,`location_mode=manual`(默认)直接查表,不依赖 IP 定位也不依赖 geocoding 子域(代理下易超时)。`auto` 只作为无手动配置时的兜底,且 README 明说"代理下可能不准"。

## 4. API 限流与双 provider 降级

- 免密公开源(open-meteo / GitHub REST 匿名)都有限流:GitHub REST 匿名 **60 次/小时**、search **10 次/分钟**;个人单板够用,批量/多板易触顶。
- **解法**:① 采集器把限流归类成 `rate_limit` 错误(可重试),hint 引导用户装 `gh` CLI 提额或稍后重试,**不升级成整模块死亡**;② 关键模块配**双 provider 自动降级**(weather = 彩云↔open-meteo;github = gh CLI↔REST 匿名),一档不通退下一档。

## 5. collector 网络调用**必须自带超时**;子进程必须**自限**

这是硬纪律,违反会留下挂死的孤儿进程拖垮整轮采集(orchestrator 虽有 `timeout_s` 硬杀,但杀的是采集器进程,采集器派生的**孙进程**未必被回收):

- **所有 `urllib`/`requests` 调用带 `timeout=`**(如 `urlopen(req, timeout=20)`)。无超时的网络调用在坏网络下会无限等待。
- **调外部命令自限次数 + 单步超时**:
  - `ping` 用 `-n <次数> -w <毫秒>`(Windows)或 `-c <次数> -W <秒>`(*nix),**别裸 ping**(默认无限/四包);
  - 再叠加 `subprocess.run(cmd, timeout=<秒>)` 硬杀兜底;
  - 选**不派生孙进程**的命令(ping 不派生,安全;能挂起子 shell 的要额外小心)。
- 采集器把"超时/挂死"归类成 `provider`(可重试),不抛裸异常。

> 记忆锚:**免费档别信文档要实测上限 · 代理下延迟用 TLS 不用 ping · IP 定位会漂手动优先 · 网络调用一律带超时、子进程一律自限。**
