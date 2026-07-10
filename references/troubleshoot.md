# troubleshoot · 排障决策树

看板出问题时,先读 `<board>/health.json` 定位,再按 `err.kind` 分诊,或按症状查根因。面向用户说人话(禁术语见 SKILL §8),不吐 exit code / schema / UTF-16。

## 1. 先读诊断

- `<board>/health.json`:顶层 `done_date`/`generated_at`;`modules{<id>{last_ok, fail_streak, last_err{kind,retryable,hint_for_agent}, last_run, last_heavy_date}}`。
- 必要时看 `<board>/logs/orchestrator.log`(掉线只 log 一次,不刷屏)。
- 想看某模块真实失败:手跑 `python <board>/<id>/collector.py --config <board>/<id>/config.json`,读 stdout 的结构化 err。

## 2. 按 `err.kind` 分诊(五类)

| kind | 说人话 | 处置 |
|---|---|---|
| `auth` | "钥匙不对,取不回来了" | 引导用户换/补 key,重写 `config.json` 对应字段(**只报字段名,不回显值**) |
| `rate_limit` | "问得太勤,被限流了" | 拉长 `refresh.interval_s` 或让用户提额;github 无 gh 时提示装并登录 `gh` CLI 大幅提额 |
| `network` | "网络没通" | 查代理:**fake-IP 模式会让定位/域名解析漂移**(见 `data-sources.md`);测延迟用 **TLS 握手**而非 ping;必要时让用户临时关代理复测 |
| `provider` | "对方服务抽风了" | 多为可重试:手跑一次看是否自愈;超时类查 collector 有无**无超时**的网络调用 / 未自限的子进程 |
| `bug` | "这块的代码有问题" | 改 collector(输出不合 schema / 无法拍平为标量 / 解析失败),改完走 `validate_module.py` |

修好后:`orchestrator.py --board <board> --only <id>` 单模块重采集验证恢复 → `deploy_skin.ps1`。若是**社区模块通病**,提议回流 PR。

## 3. 按症状查根因(常见现象)

| 症状 | 根因 | 解法 |
|---|---|---|
| **看板不显示**(文件已部署,桌面没有) | 新皮肤第一次上墙没 `!ActivateConfig`;`!RefreshApp` 只刷**已激活**的皮肤 | 显式 `& "<Rainmeter.exe>" !ActivateConfig "Deskdash" "Deskdash.ini"`(exe 取自 `doctor` 的 `checks.rainmeter.path`) |
| **看板显得很小 / 挤成一团** | 用户在 `Rainmeter.exe` 的属性里**禁用了高 DPI 缩放**(勾了"替代高 DPI 缩放"),Rainmeter 按**物理像素**渲染,150% 屏上元素只有 2/3 大 | 让用户在 `Rainmeter.exe` → 属性 → 兼容性 → **取消**高 DPI 替代;Rainmeter 4.2+ 自带 DPI 缩放,交给它即可 |
| **中文变问号 / 乱码方块** | GBK 桥:中文经 Lua/`!SetOption` 退化 ANSI;或 `data.inc` 存成了 UTF-8 | 中文只走 `data.inc`(UTF-16)+ `#变量#`,不进命令通道;运行时文件必须 UTF-16(见 `encoding.md`) |
| **某块灰化 / 淡出** | 该模块 `fail_streak ≥ 3`,orchestrator 注入 `Stale=1` 触发皮肤灰化 | 读 `health.json` 看 `last_err.kind` → 回 §2 分诊;修好后 `fail_streak` 清零、恢复只 log 一次 |
| **计划任务不跑 / 数据不更新** | ① 登录触发有意加了 5 分钟延迟(网络未就绪不炸);② `install_task.ps1` 里 Python 路径不对 / 用了带控制台的 `python.exe` 闪窗;③ 任务名不符 | `doctor --task-name <名>` 确认注册;确认用 `pythonw.exe`;耐心等 5 分钟窗或手跑 `orchestrator` 验证 |
| **data.inc 冻结**(所有模块都不更新) | 某个坏模块输出无法拍平(嵌套 dict/list),**但已被逐模块隔离**:坏模块本轮缺席、其余照常落盘 | 若真全冻:看 `health.json` 找 `kind=bug`、`hint` 提"输出须为标量"的模块,修它;good 模块不应受连累(隔离是核心不变量) |
| **曲线/图形错位、盖住下一块** | Path meter 的 `Y=` 写成了 `#变量#` 被平移器漏移;或 band 声明的 `height` 低于真实内容 | Path/曲线 meter 的 `Y=` 用数字字面量;诚实声明 height;加 Path 越带底交叉校验(见 `layout.md §5/§6`) |
| **交互点了没反应 / 双击误切** | InputText 只认 Enter(点框外静默丢);或双击防抖没做,UpAction 触发两次 | 见 `interaction.md`:提交绑 `Command1`;单击走 `.clicks` 防抖判别窗 |

## 4. 分诊心法(第一性)

- 报错先问"为什么会这样"至少一层,分清**症状**与**根因**。"看板不显示"的症状下可能是没激活、也可能是布局越界、也可能是 collector 全挂——先读 `health.json` 定位断点,别对着症状打补丁。
- 二手结论(memory / 旧注释 / 用户描述)不当公理:存疑就手跑 collector 看真实 err。
- 够了就停:根因清楚、能正确修就动手,不为显得彻底而无限追问。
