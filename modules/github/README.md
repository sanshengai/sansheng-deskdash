# github · GitHub 动态

把某个 GitHub 用户的公开仓库动态钉在桌面:最近更新的 5 个仓 + 各自 star / 语言色点 / 更新时间,表头汇总总 star 与开放 PR 数。单击仓名即在浏览器打开。

- **中文名**:GitHub 动态 / **英文名**:GitHub Activity
- **prefix**:`Gh` / **分类**:dev / **交互**:单击仓名开链接(非旗舰交互)

## 用途(what)

每行:语言色点 + 仓名(单击打开) + 右侧 `★ star · 最近更新`。表头右侧 `★ 总star · PR 开放数`。仓按最近更新降序,取前 5(带区固定 5 行)。自动排除私有仓、fork(可开)、以及与用户名同名的 profile README 仓。

## 数据源(双档自动降级)

| 档 | 触发 | 说明 |
|---|---|---|
| `gh` CLI(优先) | 本机装了 `gh` 且 `use_gh_cli≠false` | 复用 `gh` 已登录认证,配额高、稳定 |
| REST 匿名(降级) | 无 `gh` 或 gh 调用失败 | 直连 `api.github.com`,无需认证 |

### ⚠ REST 匿名限流

匿名 REST 有硬限流:**核心 API 60 次/小时**、**search API 10 次/分钟**。个人单板足够;批量/多板/频繁刷新会更快触顶。触顶时采集器返回 `rate_limit` 错误(可重试),提示装并登录 `gh`(`gh auth login`)以大幅提额。开放 PR 数走 search API,匿名下更易失败——失败即置 `-1`(表头不显示 PR 段),不拖累整模块。

> `doctor`(Task 7)会检测 `gh` 是否可用并在装配前告知;装了 `gh` 体验最佳。

## 配置(config)

复制 `config.example.json` 为 `config.json`:

```json
{
  "username": "octocat",
  "include_forks": false,
  "use_gh_cli": true
}
```

- `username`(必填):要展示的 GitHub 用户名。
- `include_forks`:是否包含 fork 仓,缺省 `false`。
- `use_gh_cli`:优先用 gh CLI,缺省 `true`;设 `false` 强制走 REST 匿名。
- 无密钥字段(`secrets: []`)——gh 的认证由本机 `gh` 自己管,不进本模块 config。

## 依赖与安全

- **依赖**:无(纯 stdlib:`subprocess` 调 gh / `urllib` 走 REST)。
- **网络**:仅 `api.github.com`(gh CLI 与 REST 都只打这个域;`privacy.network` 已声明)。**读/写本地**:无。
- 无 `eval` / `exec` / `shell=True`;`subprocess` 用 list 参数,不回显 gh stderr(可能含 token)。失败返回结构化错误(rate_limit / network / bug)。

## 自验

```bash
python collector.py --config config.example.json
# 联网(有 gh 更佳)→ 单行 JSON,含 Count / StarsTotal / Repo1Name / Repo1DotColor / Repo1Url ...
# 离线/限流 → {"ok":false,"err":{kind: network|rate_limit,...}}(代码路径完整,orchestrator 记 health)
```

纯逻辑(`lang_color` / `activity_label` / `filter_repos` / `flatten`)离线单测见 `tests/test_task6_modules.py`。
