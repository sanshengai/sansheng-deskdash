---
name: sansheng-deskdash
description: Use when 用户在 Windows 上搭建、修改、修复或卸载 Rainmeter 常驻桌面看板，涉及天气、待办、服务器或 GitHub 模块；触发词：桌面看板、桌面挂件、改布局、看板不更新、卸载看板。浏览器或 Electron 仪表盘不用此 Skill。
---

# sansheng-deskdash

**一句话**:你说想看什么,我把它变成常驻桌面的一块——原生贴壁纸,不占浏览器,数据自己刷新,坏了自己会喊修。

**三楔子**(差异化,别当普通 dashboard):
1. **原生贴壁纸常驻**:Rainmeter 皮肤直接钉在壁纸上,不是浏览器标签、不是 Electron 大窗;关机重开自动在。
2. **现场造长尾采集器**:库里没有的数据源(自家 NAS、某个有 API 的小服务),我**当场写一个只读采集器**给你——这是全行业没人做的一层。
3. **自愈闭环**:模块连挂 3 次自动灰化并提示"对我说『修看板』";你一句话触发,我读诊断数据半自动重修。**绝不无人值守自动改码**(安全红线)。

---

## 路由:先认意图,再进对应工作流

| 用户意图信号 | 工作流 | 跳到 |
|---|---|---|
| 帮我搭个看板 / 从零开始 / 桌面空的 | ① 初装 | §1 |
| 加一块 X / 我想看 Y / 库里有没有 Z | ② 加模块 / 现场造 | §2 |
| 换个位置 / 调顺序 / 太挤了 / 换风格档 | ③ 改布局 | §3 |
| 看板坏了 / 不更新了 / X 显示不对 / 灰了 | ④ 排障 | §4 |
| 有新版吗 / 升级 / 卸载 / 删掉 | ⑤ 升级与卸载 | §5 |

**贯穿全程的三审阅点(§6)、禁止项(§7)、禁术语规则(§8)对所有工作流生效,动手前先扫一眼。**

### 通用速查(所有命令的真实签名)

- **board(板)** = 一个工作目录 `<board>`,里面每个子目录是一个模块(从本 skill 的 `modules/<id>/` 拷入),外加装配/运行生成的 `modules.lock.json`、`data.inc`、`health.json`、`state/`、`logs/`。**你新建它、把选中的模块拷进去**;它是用户数据,不在本仓内。
- `<board>` **默认建在 `%USERPROFILE%\Deskdash`**(用户没指定就用它,别每次即兴选路径);用绝对路径传给脚本。
- 脚本路径相对 skill 根目录;示例板名 `Deskdash`、示例主机 `example.com`、GitHub 用户 `octocat`。
- ps1 一律 `powershell -ExecutionPolicy Bypass -File <ps1> ...` 调用(不改系统策略、不下载)。
- 仓内源文件 UTF-8;皮肤部署副本与 `data.inc`/`todos.inc` 的 UTF-16 由脚本自动转,**你不手动碰编码**。

| 命令 | 签名 | 干什么 |
|---|---|---|
| 体检 | `python scripts/doctor.py [--board <board>] [--task-name <name>]` | 输出 JSON(`ok`/`height_budget`/`checks{python,platform,rainmeter,screen,gh,pillow,tzdata,scheduled_task,board}`)。退出码恒 0,**判定看 JSON 的 `ok`**。 |
| 装配 | `python scripts/assemble.py --board <board> --size M [--budget <N>] [--modules a,b,c] [--out <path>] [--skin-name <name>] [--task-name <name>]` | band.inc 累加拼整板 .ini,回写 `modules.lock.json`(含 `skin_name`/`task_name`,供部署与任务脚本缺省读取)。缺 `--out` 打到 stdout;超预算 → 报错(含"哪个模块可裁")。 |
| 采集 | `python scripts/orchestrator.py --board <board> [--net-only] [--only a,b]` | 跑各模块采集器,写 `data.inc`/`health.json`。`--only` 强制跑指定模块(绕节流)。 |
| 部署 | `powershell -ExecutionPolicy Bypass -File scripts/deploy_skin.ps1 -Board <board> -SkinName Deskdash [-SourceIni <path>] [-RainmeterExe <path>] [-BackupCount 5] [-NoRefresh]` | UTF-8→UTF-16 部署到 `Documents\Rainmeter\Skins\`,轮换 5 份备份,`!RefreshApp`。 |
| 注册常驻 | `powershell -ExecutionPolicy Bypass -File scripts/install_task.ps1 -Board <board> [-TaskName <name>] [-Python <path>]` | 计划任务:登录后 5 分钟 + 每 2 小时跑 orchestrator。幂等(同板重装放行)。`-TaskName` 缺省读 lock 的 `task_name`。**同名任务若指向别的板 → 拒绝覆盖并报错**(防覆盖栏)。 |
| 卸载 | `powershell -ExecutionPolicy Bypass -File scripts/uninstall.ps1 -Board <board> [-SkinName <name>] [-TaskName <name>] [-KeepData] [-Force]` | 反注册任务 + 删皮肤副本 + 删/留数据。`-SkinName`/`-TaskName` 均缺省读 lock。**非交互无 `-Force` 只打印不删**。 |
| 平移 | `python scripts/shift_band.py <ini> <from_y> <dy> [--dry]` | 对成品补偿平移(只动数字字面量 Y=)。 |
| 校验/造件 | `python scripts/validate_module.py <module_dir>` · `python scripts/new_module.py <id>` | VALIDATE 门 / 生成模块骨架(见 §2)。 |

**首次激活新皮肤**:deploy 只写文件 + `!RefreshApp`;**新皮肤第一次上墙必须先 `!ActivateConfig`**(否则文件在但看板不出现):
```
& "<Rainmeter.exe>" !ActivateConfig "Deskdash" "Deskdash.ini"
```
`<Rainmeter.exe>` 取自 doctor 的 `checks.rainmeter.path`(独立字段,直接用;不必从中文 `detail` 里截路径)。已激活过的皮肤后续改动只需 deploy 的 `!RefreshApp`。

---

## §1 工作流①:初装

**原则:先上墙再深聊——绝不让用户对着空白画布答一串问题。**

### 1.1 体检(读高度预算)
```
python scripts/doctor.py
```
读 JSON:`ok=false` 且 `checks.python/platform/rainmeter/screen` 有红 → 按各项 `hint` 处理(缺 Rainmeter 提示 `winget install Rainmeter.Rainmeter`)。**记下 `height_budget`**(逻辑像素,直接喂 assemble 的 `--budget`)。`pillow` 是可选项,缺失只影响日历配图,不挡上墙。

### 1.2 60 秒上墙(Wow #1,失败率设计为零)
先只装 **clock-calendar**(零网络、零密钥;缺 Pillow 也照样显示时钟日期,只是日历图不渲染):
```
# 建板 + 拷时钟模块
New-Item -ItemType Directory -Force <board>
Copy-Item -Recurse modules/clock-calendar <board>/

# 装配(--budget 用 doctor 的 height_budget)+ 先跑一轮生成 data.inc
python scripts/assemble.py --board <board> --size M --budget <height_budget> --modules clock-calendar --out <board>/Deskdash.ini
python scripts/orchestrator.py --board <board> --only clock-calendar

# 部署 + 首次激活
powershell -ExecutionPolicy Bypass -File scripts/deploy_skin.ps1 -Board <board> -SkinName Deskdash
& "<Rainmeter.exe>" !ActivateConfig "Deskdash" "Deskdash.ini"
```
对用户:"看右上角,时钟在了,这是地基。接下来问你几个问题把它填满。"

### 1.3 看货(三起步板)
给三张起步板让用户选起点(引用 `templates/starter-boards/`:`minimal.json`=时钟+天气+待办 / `dev.json` / `life.json`)。用户选了哪张就把对应模块列表作为默认清单带进五问。

### 1.4 批量五问(§1.6),用户已答的跳过,全留空=全默认。

### 1.5 装模块或现场造 → 重装配 → 部署 → 常驻
按五问结果确定模块清单(库里有的直接拷;库里没有的走 §2 现场造)。每个联网/带密钥模块**装前先朗读 privacy 三元组(§6 审阅点一)**。然后:
```
# 把选中的模块逐个拷进板;带密钥/带主机的模块写好 <board>/<id>/config.json(见各模块 README)
python scripts/assemble.py --board <board> --size M --budget <height_budget> --modules clock-calendar,weather,todo --out <board>/Deskdash.ini
python scripts/orchestrator.py --board <board>
powershell -ExecutionPolicy Bypass -File scripts/deploy_skin.ps1 -Board <board> -SkinName Deskdash
# 注册常驻(登录后5分钟 + 每2小时自动刷新)
powershell -ExecutionPolicy Bypass -File scripts/install_task.ps1 -Board <board>
```
超预算报错时:按报错里的"可裁模块"和用户商量删一个,或改 `--size S` 压缩间距重装配。**别手改 .ini 的 Y 值**(§3)。

### 1.6 五问话术(逐字·带默认推荐·带"若答X→倾向Y")

开场白:"给我三十秒答五个问题,或者直接说『全默认』我按最稳的来。留空的我替你选。"

| # | 问题(逐字) | 默认推荐 | 若答 X → 倾向 Y |
|---|---|---|---|
| 1 看什么 | "你最想每天瞥一眼的是什么?天气、待办、服务器、GitHub,还是别的?" | 天气 + 待办 + 日历 | 答"服务器/网站在不在"→server-status;"我的仓/star"→github;"网快不快"→net-latency;库里没有的专有源→进 §2 现场造 |
| 2 数据哪来 | "这些数据从哪取?有些要个密钥——**你只报名字,别贴值**,我告诉你写哪。" | 全走免密公开源(天气=open-meteo) | 答"我有彩云 token"→weather 填 `config.json` 的 `caiyun_token`;"看私有仓"→github 配 gh CLI 或 token;都没有→免密降级 |
| 3 多久更新 | "多久刷一次?桌面挂件一般不用太勤。" | 开机后 5 分钟 + 每 2 小时(计划任务) | 答"实时"→说明桌面挂件无实时、最密每几分钟(net-latency 默认 5 分钟);"一天一次就行"→照默认,重活模块本就每天一次 |
| 4 长什么样 | "三种风格:玻璃暗色 / 纸质浅色 / 极简,选一个?字号要大点吗?" | 玻璃暗色 + M 档字号 | 答"看不清/要大"→`--size L`;"太占地方/紧凑"→`--size S`;风格档随起步板模板 |
| 5 贴哪 | "贴主屏哪边?右侧竖条最不挡活。" | 主屏右侧竖条 | 答"左边/双屏"→部署后在 Rainmeter 拖到位(皮肤位置由 Rainmeter 记忆,不进装配) |

给方案要 **opinionated 单一推荐**,不甩选项菜单(§8 禁术语同理)。

---

## §2 工作流②:加模块 / 现场造

### 2.1 先查库
看 `modules/` 有没有现成的(6 官方:clock-calendar/weather/net-latency/todo/github/server-status)。**有 → 直接装**:拷进板 → 朗读 privacy 三元组(§6)征得同意 → 写 `config.json`(若需)→ 回到 §1.5 重装配部署。

### 2.2 没有 → 现场造:先过探源红绿灯(§2.4),绿灯才动手

```
python scripts/new_module.py <id>          # 生成七件套骨架(拷自 templates/module-skeleton/)
# 编辑 <id>/collector.py 写只读采集逻辑;<id>/band.inc 画带区(§2.5 约束);填 widget.json 的 privacy/output.schema
python scripts/validate_module.py <id目录>  # VALIDATE 门:校验 widget.json + config.example 过 schema + collector dry-run 打印【实际网络目标 + 输出预览】+ 禁止项 AST 扫描
```
**VALIDATE 是审阅点二(§6)**:把代码要点 + 实际会访问的网络目标 + 一次真实输出预览摆给用户,**用户看过点头才接线**(拷进板 → 装配 → 部署)。

### 2.3 回流邀请(装好之后,别省)
"愿意的话我把它脱敏整理成 PR 提到社区仓,其他 <同类用户> 就能直接装。"(流程见 `references/contribution.md`。🟡 黄灯源=仅本地自用,不回流。)

### 2.4 探源红绿灯(写死,SKILL 级判据)

| 灯 | 数据源类型 | 动作 |
|---|---|---|
| 🟢 绿 | 公开 API / 用户自备 key 的 API / 本地文件与局域网设备 | 直接造,可回流公开仓 |
| 🟡 黄 | 需用户自己提供 cookie 的私有服务(自家 NAS/路由器) | 造,但**仅本地自用,不回流**;写清是用户自己的凭据 |
| 🟡 黄 | 用户本人拥有或被明确授权管理的账号的官方网页会话，且同时满足：用户明确要求、任务在用户本机由用户手动触发、独立专用持久化 profile、平台条款未明确禁止该自动化、每个请求的目标 origin 与当前官方页面 origin 相同、操作严格只读、不导出/记录任何会话材料、不绕过登录或风控 | 可做，仅本地自用、不回流；接线前展示域名、本地路径与登录介入点；会话失效时停下来让用户登录 |
| 🔴 红 | 非本人且无可验证明确授权的账号；平台条款明确禁止该自动化；读取/导出浏览器凭据或任何会话材料；代替扫码/验证码/MFA；绕过登录、反爬或风控；伪造签名；或不满足上述黄灯全部条件的社交平台私有接口 | **拒绝** + 降级话术(§2.6) |

### 2.5 本人账号官方网页会话的窄例外

同时满足以下**全部**条件才是黄灯：账号为用户本人拥有或被明确授权管理（非本人且无可验证明确授权即红灯）；用户明确要求；任务在用户本机由用户手动触发；使用独立专用持久化浏览器资料夹；平台条款未明确禁止该自动化；每个请求的目标 origin 必须与当前官方页面 origin 相同；操作严格只读，即不创建、修改、删除数据，不发布内容，不触发业务动作；不读取、复制、导出、打印、记录、上传或跨进程传递任何会话材料（Cookie、Token、Bearer token、sessionStorage、密码、验证码和完整请求头）；不代替扫码/验证码/MFA，不绕过登录、反爬或风控。

符合时仅限本地自用，不回流公共模块；接线前按 §6 展示访问域名、本地路径和登录介入点。会话有效可直接复用；平台结束会话时必须停下来让用户完成登录。

任一条件不满足即红灯：银行/券商；非本人且无可验证明确授权的账号；平台条款明确禁止该自动化；读取日常 Chrome/Edge Cookie 数据库、密码库或凭据目录；读取、复制、导出、打印、记录、上传或跨进程传递 Cookie、Token、Bearer token、sessionStorage、密码、验证码或完整请求头；伪造签名、逆向加密参数、注入反检测脚本；代替扫码、验证码、MFA 或平台风控确认；请求目标 origin 与当前官方页面 origin 不同；创建、修改、删除数据、发布内容或触发业务动作；调用官方页面不会自行发出的接口。

### 2.6 降级话术模板
"这个我不能直接抓,但有两条稳的路:① 用 <X> 的**官方公开 API**(如果有);② 你定期把数据**导出成 CSV/JSON**,我写个读本地文件的模块,一样上墙。你选哪个?"

### 2.7 band.inc 作者约束(现场造模块画带区必须遵守)

带区用**局部坐标**,原点在带区顶(y=0);装配器 `shift_band.shift()` 只做整体下移落位。踩中任一条会静默错位或整板崩:

- **有 `Y=` 定位的 meter**:内部 `Shape` 一律**相对坐标、原点锚定(y ≤ 8)**;平移只动 `Y=` 选项。
- **无定位 meter(默认 0,0)**:内部 `Shape` 带**绝对局部 y**。
- **曲线 / Path meter 的 `Y=` 必须是数字字面量**——`shift()` 只平移数字,`Y=#变量#` / `Y=(公式)` 会**漏移**跑到错位置(todo 输入框即因此改固定 `Y=2`)。
- **段名带模块 prefix**(如 `[WxIcon]`),跨模块唯一;**禁保留段名**:`[Rainmeter]`/`[Metadata]`/`[Variables]`/`[Panel]`/`[BoardTitle]`/`[BandDiv*]`(撞了会覆盖模板段,`[Variables]` 被覆盖=整板崩)。
- **collector 输出扁平标量**:`to_inc` 拒嵌套 dict/list(把 `days[0]['tmax']` 拆成键 `1Tmax`);嵌套会被隔离丢弃并记 bug。
- **中文只走 `#变量#`**(经 `data.inc` UTF-16 注入),**不进 Lua/SetOption**,band 段内绝不内联中文字面量(GBK 乱码,见 `references/encoding.md`)。
- **collector 自包含内联**:模块要能整目录拷走独立跑,**不 import 仓内 `scripts/lib`**;需要的小工具(如温度曲线)内联复制。
- **stdout 只打一行 JSON**,用 `sys.stdout.buffer.write(json...encode("utf-8"))`,**不用 `print`**(避免平台编码把中文打乱)。
- **collector 网络调用须自带超时**(`urlopen(..., timeout=)` 等),**调外部命令须自限**(如 `ping -n/-w` 或 `-c/-W`,别裸调)+ 叠 `subprocess.run(timeout=)` 硬杀——否则留下挂死的孤儿/孙进程拖垮整轮采集(见 `references/data-sources.md §5`)。

细节:`references/rainmeter-drawing.md`(贝塞尔/InlineSetting)、`references/layout.md`(带区/原点锚定/平移)、`references/interaction.md`(InputText 只认 Enter / 双击防抖)。

---

## §3 工作流③:改布局

**铁律:禁止手改成品 .ini 的 Y 值。** 两条正道:

1. **改顺序 / 增删模块** → 改 `modules.lock.json` 的 `modules` 数组(或直接 `assemble --modules a,c,b`)重装配:
   ```
   python scripts/assemble.py --board <board> --size M --budget <height_budget> --modules clock-calendar,todo,weather --out <board>/Deskdash.ini
   ```
2. **对成品整体平移**(极少用) → `python scripts/shift_band.py <board>/Deskdash.ini <from_y> <dy> --dry` 先干看,再去掉 `--dry` 写盘。

改完**必跑四布局不变量**再部署:
```
python -m pytest tests/test_layout.py -q
powershell -ExecutionPolicy Bypass -File scripts/deploy_skin.ps1 -Board <board> -SkinName Deskdash
```
deploy 自动备份 5 份;用户说"恢复昨天的" → 从 `Documents\Rainmeter\Skins\Deskdash\Deskdash.ini.bak1..bak5` 取回。

---

## §4 工作流④:排障(自愈半自动)

模块连挂 ≥ 3 次(`fail_streak≥3`)→ 看板该块自动灰化(`Stale=1`)。用户随口"看板坏了"即触发本流。

### 4.1 读诊断
读 `<board>/health.json`:顶层 `done_date`/`generated_at`,`modules{<id>{last_ok, fail_streak, last_err{kind,retryable,hint_for_agent}, last_run, last_heavy_date}}`;必要时看 `<board>/logs/orchestrator.log`。

### 4.2 按 `err.kind` 分诊(五类)

| kind | 症状(说人话) | 处置 |
|---|---|---|
| `auth` | "钥匙不对,取不回来了" | 引导用户换/补 key,重写 `config.json` 对应字段(只报字段名,不回显值) |
| `rate_limit` | "问得太勤,被限流了" | 拉长 `refresh.interval_s` 或让用户提额;github 无 gh 时提示装 gh CLI 提限流 |
| `network` | "网络没通" | 查代理:**fake-IP 模式会让定位/域名解析漂移**(见 `references/data-sources.md`);测延迟用 **TLS 握手**而非 ping;必要时让用户临时关代理复测 |
| `provider` | "对方服务抽风了" | 多为可重试:手跑一次看是否自愈;超时类查 collector 有无无超时的网络调用 |
| `bug` | "这块的代码有问题" | 改 collector(输出不合 schema / 无法拍平 / 解析失败),改完走 VALIDATE |

### 4.3 手跑取现场 → 改 → VALIDATE → 部署
```
python <board>/<id>/collector.py --config <board>/<id>/config.json   # 拿 stderr/hint,看真实失败
# ...改 collector...
python scripts/validate_module.py <board>/<id>
python scripts/orchestrator.py --board <board> --only <id>            # 单模块重采集验证恢复
powershell -ExecutionPolicy Bypass -File scripts/deploy_skin.ps1 -Board <board> -SkinName Deskdash
```
修好后给用户结论:"<某块>数据取回来了,已经恢复。" 若修的是**社区模块通病**,提议回流 PR(§2.3)。决策树全表见 `references/troubleshoot.md`。

---

## §5 工作流⑤:升级与卸载

### 5.1 升级
开场比对 `<board>/installed.json`(host 版本 + 各模块版本)与仓内版本,有新版**列 changelog 摘要征得同意**再动。
- **模块升级 = 必重走 VALIDATE 再审**(§2.2)——升级不是首装豁免;**owner 变更 / 被摘牌**要明示用户。
- **底座升级**:覆盖 `scripts/`;**用户数据(config/todos/state/health)永不覆盖**;破坏性变更附 `migrate` 脚本,先说清再跑。

### 5.2 卸载
```
# 先干看要删什么(非交互无 -Force 只打印不删,安全)
powershell -ExecutionPolicy Bypass -File scripts/uninstall.ps1 -Board <board> -SkinName Deskdash
# 确认后执行;-KeepData 保留待办/配置等用户数据只删任务与皮肤副本
powershell -ExecutionPolicy Bypass -File scripts/uninstall.ps1 -Board <board> -SkinName Deskdash -Force
```
向用户说清:"会取消开机自动刷新、从桌面移除这块皮肤;你的待办和配置<删掉 / 保留(加了 -KeepData)>。"

---

## §6 三审阅点(半自动的信任闸,不可跳)

1. **装模块前**:朗读该模块 privacy 三元组——**访问哪些域名 / 读写哪些本地路径 / 要哪些密钥名**(取自 `widget.json` 的 `privacy` + `config.secrets`),用户同意才装。速查:

   | 模块 | 网络 | 本地读写 | 密钥名 |
   |---|---|---|---|
   | clock-calendar | 无 | 写自身 `assets/calendar.png` | 无 |
   | weather | open-meteo / caiyunapp / ip-api / geocoding-api | 无 | `caiyun_token`(可选,免密可用) |
   | net-latency | `<用户配置的目标>` | 无 | 无 |
   | todo | 无 | 读写 `todos.json`/`todos.inc`/`.clicks` | 无 |
   | github | `api.github.com` | 无 | 无(可选配 gh/token 提限流) |
   | server-status | `<用户配置的目标>` | 无 | 无 |

本人账号官方网页会话接线前还要展示：实际访问的官方域名、每个请求的目标 origin 与当前页面 origin 相同；专用浏览器资料夹和业务数据的本地读写路径；是否可能需要用户扫码、验证码或确认；并明确声明不读取日常浏览器凭据、不读取或输出任何 Cookie、Token、Bearer token、sessionStorage、密码、验证码或完整请求头。用户确认后才接线。计划任务不得自动启动登录浏览器；只读本地结果的日常刷新可以继续运行。

2. **现场写/改采集器后**:`validate_module.py` 展示**代码要点 + 实际网络目标 + 输出预览**,用户看过才接线(§2.2)。
3. **注册/改计划任务前**:说清"会加一个开机后 5 分钟 + 每 2 小时的后台刷新任务",用户确认再 `install_task.ps1`。

---

## §7 禁止项清单(硬红线,现场造与审模块都据此)

- collector **只读外部、只写自身/board 目录**;禁写系统目录、别人的目录。
- 禁 `eval` / `exec` / `shell=True` / `iwr|iex` / `Invoke-Expression`;`subprocess` 只用 list 参数。
- 禁读取、复制或离线解密日常 Chrome/Edge 的 Cookie 数据库、密码库或凭据目录；禁读取、复制、导出、打印、记录、上传或跨进程传递 Cookie、Token、Bearer token、sessionStorage、密码、验证码和完整请求头。
- 本人账号自动化只走 §2.5：让独立专用浏览器在每个请求目标 origin 与当前官方页面 origin 相同的前提下携带自己的会话执行严格只读操作（不创建、修改、删除数据，不发布内容，不触发业务动作）。会话失效时停下来交给用户完成平台要求的登录步骤。
- 禁访问 `privacy.network` **未声明**的域名(声明与实际必须一致,VALIDATE 会 AST 扫)。
- 皮肤禁 `!Execute` 任意命令、禁远程加载。
- **依赖 `deps ⊆ [requests, Pillow]`,stdlib-only 为默认**;禁 collector 内 `pip install`;白名单外的包一律不许。
- 密钥只进 gitignore 的 `config.json`,**绝不进代码 / 日志 / 错误消息**。

---

## §8 禁术语规则(面向用户的话)

对用户**说人话**,不吐内部术语。翻译对照:

| 别说(内部) | 要说(用户) |
|---|---|
| exit code / 退出码非零 | (直接说结果,不提这个) |
| schema 校验失败 | "这块数据的格式对不上" |
| UTF-16 / 编码 / BOM | (完全不提,自动处理) |
| fail_streak≥3 / Stale=1 | "这块连着几次没取到,先灰掉了" |
| height_budget 超了 | "屏幕装不下这么多,得挑一块拿掉,或者字号调小" |
| collector / orchestrator / assemble | "采集这块的小程序 / 后台刷新 / 拼版" |
| widget.json / privacy 三元组 | "这块的说明书 / 它要连哪、读什么" |

给方案给**单一推荐**,不列 A/B/C 菜单让用户挑技术细节;需要用户拍板的只留"要不要 / 选风格"这类人话选择。

---

## references 索引(细节都在这)

`references/encoding.md`(GBK 桥/UTF-16/中文 bat) · `references/rainmeter-drawing.md`(贝塞尔/InlineSetting/锚点) · `references/layout.md`(带区/原点锚定/平移/高度预算) · `references/interaction.md`(InputText 只认 Enter/双击防抖) · `references/data-sources.md`(彩云 3 天上限/代理 fake-IP 定位漂移/TLS 测延迟) · `references/security.md`(禁止项 + 审阅点全表) · `references/contribution.md`(回流 PR 流程) · `references/troubleshoot.md`(排障决策树) · `references/backends.md`(多后端概念稿)。
