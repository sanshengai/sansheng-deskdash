---
name: sansheng-deskdash
description: Use when 用户在 Windows 或 macOS 上搭建、修改、修复或卸载常驻桌面看板，涉及天气、待办、服务器或 GitHub 模块；Windows 走 Rainmeter 皮肤，macOS 走原生 SwiftUI 面板，采集层两平台共用；触发词：桌面看板、桌面挂件、改布局、看板不更新、卸载看板、Mac 看板。浏览器或 Electron 仪表盘不用此 Skill。
---

# sansheng-deskdash

**一句话**:你说想看什么,我把它变成常驻桌面的一块——原生贴壁纸,不占浏览器,数据自己刷新,坏了自己会喊修。**Windows 和 macOS 都能上墙,采集层同一套。**

**三楔子**(差异化,别当普通 dashboard):
1. **原生贴壁纸常驻**:Rainmeter 皮肤直接钉在壁纸上,不是浏览器标签、不是 Electron 大窗;关机重开自动在。
2. **现场造长尾采集器**:库里没有的数据源(自家 NAS、某个有 API 的小服务),我**当场写一个只读采集器**给你——这是全行业没人做的一层。
3. **自愈闭环**:模块连挂 3 次自动灰化并提示"对我说『修看板』";你一句话触发,我读诊断数据半自动重修。**绝不无人值守自动改码**(安全红线)。

---

## 路由:先认平台,再认意图

### 第 0 步 · 认平台(每次都做,别猜)

```
python scripts/doctor.py     # JSON 里的 checks.platform 就是判据
```

| 平台 | 渲染层 | 部署 | 定时 |
|---|---|---|---|
| **Windows** | Rainmeter 皮肤(`.ini` + band.inc,UTF-16) | `scripts/deploy_skin.ps1` | 计划任务 `install_task.ps1` |
| **macOS** | 原生 SwiftUI 面板(`templates/macos-panel/Panel.swift`) | `scripts/deploy_macos.sh` | `launchd`(**不是 cron**,见下) |

**采集层两平台完全一样**:模块的 `collector.py` 不动、`orchestrator.py` 不动。
orchestrator 每轮同时写 `data.inc`(UTF-16,给 Rainmeter)和 `data.json`(UTF-8,给 macOS 面板),
**两份出自同一份 outputs** —— 不会出现两个平台上的数不一样。

所以「换平台」换的只是渲染与部署两步,§2 现场造模块、§4 排障、§6 三审阅点、§7 禁止项**全部照旧**。

macOS 的形态选择(原生面板 / 系统小组件 / 网页贴壁纸)、平台硬限制与全部踩坑见
`references/macos.md` —— **动手前必读那一篇**,里面每条都是真机实测,不是推演。

> 🔴 **macOS 上最容易白干的三件事**(细节在 `references/macos.md`):
> ① 窗口钉在**桌面层就永远收不到鼠标**(平台硬限制),要可拖可点必须用桌面图标层;
> ② **无边框窗口默认不能成为 key 窗口**,不重写 `canBecomeKey` 照样点不动;
> ③ 只有 Command Line Tools 时**用不了 `@State` 等 SwiftUI 宏**(实现插件只随 Xcode 提供),
>    状态要放进 `ObservableObject`。

### 第 1 步 · 认意图

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
- ps1 一律 `powershell -ExecutionPolicy Bypass -File <ps1> ...` 调用(不改系统策略、不下载);macOS 侧对应的是 `bash scripts/deploy_macos.sh`。
- 🔴 macOS 定时用 **`launchd`,不要 `cron`**:笔记本合盖睡眠时 cron 会**直接跳过**错过的时间点,
  launchd 的 `StartInterval` 会在**唤醒后补跑** —— 这是「醒来就是新数据」和「醒来还是昨晚的数据」的区别。
- 仓内源文件 UTF-8;皮肤部署副本与 `data.inc`/`todos.inc` 的 UTF-16 由脚本自动转,**你不手动碰编码**。

| 命令 | 签名 | 干什么 |
|---|---|---|
| 体检 | `python scripts/doctor.py [--board <board>] [--task-name <name>]` | 输出 JSON(`ok`/`height_budget`/`checks{python,platform,rainmeter,screen,gh,pillow,tzdata,scheduled_task,board}`)。退出码恒 0,**判定看 JSON 的 `ok`**。 |
| 装配 | `python scripts/assemble.py --board <board> --size M [--budget <N>] [--modules a,b,c] [--out <path>] [--skin-name <name>] [--task-name <name>]` | band.inc 累加拼整板 .ini,回写 `modules.lock.json`(含 `skin_name`/`task_name`,供部署与任务脚本缺省读取)。缺 `--out` 打到 stdout;超预算 → 报错(含"哪个模块可裁")。 |
| 采集 | `python scripts/orchestrator.py --board <board> [--net-only] [--only a,b]` | 跑各模块采集器,写 `data.inc`/`health.json`。`--only` 强制跑指定模块(绕节流)。 |
| 部署 | `powershell -ExecutionPolicy Bypass -File scripts/deploy_skin.ps1 -Board <board> -SkinName Deskdash [-SourceIni <path>] [-RainmeterExe <path>] [-BackupCount 5] [-NoRefresh]` | UTF-8→UTF-16 部署到 `Documents\Rainmeter\Skins\`,轮换 5 份备份,`!RefreshApp`。 |
| 注册常驻 | `powershell -ExecutionPolicy Bypass -File scripts/install_task.ps1 -Board <board> [-TaskName <name>] [-Python <path>]` | 计划任务:登录后 5 分钟 + 每 2 小时跑 orchestrator。幂等(同板重装放行)。`-TaskName` 缺省读 lock 的 `task_name`。**同名任务若指向别的板 → 拒绝覆盖并报错**(防覆盖栏)。 |
| 卸载 | `powershell -ExecutionPolicy Bypass -File scripts/uninstall.ps1 -Board <board> [-SkinName <name>] [-TaskName <name>] [-KeepData] [-Force]` | 反注册任务 + 删皮肤副本 + 删/留数据。`-SkinName`/`-TaskName` 均缺省读 lock。**非交互无 `-Force` 只打印不删**。 |
| 平移 | `python scripts/shift_band.py <ini> <from_y> <dy> [--dry]` | 对成品补偿平移(只动数字字面量 Y=)。**Windows 专用**。 |
| 上墙(macOS) | `bash scripts/deploy_macos.sh --board <board> [--level icon\|desktop\|back] [--source <Panel.swift>]` | 编译 + 本机自签 + 上墙。**不需要 Xcode、不需要 Apple 账号**。拖不动就换 `--level back`。停掉:`--stop`。 |
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
- **线形 `Shape` 必须显式 `| StrokeWidth 0`**:Rainmeter 的 Shape 默认描边是「1px 纯黑」,一条 1px 高的分隔线会渲染成 3px、正中间 `#000000` 的黑带。判据是取像素,不是肉眼(见 `references/rainmeter-drawing.md §7.1`)。
- **宽度会变的文本用 `StringAlign=CenterCenter`**:Rainmeter 量不到文字实宽,左对齐时文本一长就会压住旁边按估算摆的元素(见 `§7.3`)。
- **collector 网络调用须自带超时**(`urlopen(..., timeout=)` 等),**调外部命令须自限**(如 `ping -n/-w` 或 `-c/-W`,别裸调)+ 叠 `subprocess.run(timeout=)` 硬杀——否则留下挂死的孤儿/孙进程拖垮整轮采集(见 `references/data-sources.md §5`)。

### 2.8 可选:二级弹层(点开看详情)——默认不做

看板的默认形态是**纯展示**:数据画在带区上,用户只看不点。"点某一块弹出小窗看明细"是可选的进阶形态。

**先问一句、给单一推荐,别默认给上。** 对用户的话:"要不要点开看详情?不点开的话这块就只显示前 4 条,更省事也更不容易坏。"

| 情形 | 结论 |
|---|---|
| 每块 3~4 行以内、一屏看得完 | **不做**。信息全摆在带区上,点都不用点 |
| 用户只早上瞥一眼、不操作 | **不做** |
| 只是想"更像个 app" | **不做**。这是形态偏好不是需求,代价见下 |
| 某块条目天然多于能显示的行数(20 条待办只显示 4 条) | 可做:弹层给完整列表 |
| 需要看某条详情(留言全文、报错堆栈) | 可做:弹层给这一条的明细 |
| 需要就地操作(标记已读、勾完成) | 可做,但先想想带区上的单击热区够不够 |

代价不是"多一个功能",是多一套 Rainmeter **会持久化**的状态(哪个开着、盖在谁上面、什么时候关),出问题的方式很隐蔽。真要做,四条硬规则一条都不能省(全文与证据见 `references/popups.md`):

1. 🔴 **"产出文件"和"打开界面"必须是两条命令。** Rainmeter 把"哪些 config 开着"写进 `Rainmeter.ini` 的 `Active=1`,而部署必发的 `!RefreshApp` 会**重新加载每一个 Active=1 的 config**。所以任何一次"顺手激活"都会在之后**每一次部署里复活,用户关掉也没用**。给弹层的数据文件一个只落盘、零 bang 的生成形态,部署链路只准调它。
2. 🔴 **部署收尾对每个弹层显式 `!DeactivateConfig`。** 只做到"不主动打开"不够——上一次遗留的 `Active=1` 会被这一轮 `!RefreshApp` 拉回来。部署是后台维护,跑完桌面上不该多出任何一个窗。
3. 🔴 **弹层的 `ZPos` 是 `0`。** 不是 `-2`(那会把它按到看板底下,用户点开的窗直接沉下去),也不是 `1`/`2`(那是霸屏,一直压在用户正在用的软件前面)。弹层只需要比看板高,而看板在桌面层,普通窗口天然就在它上面。刷过看板后隔约 0.45s 再补一次层级收尾,否则会被刷新本身盖掉。
4. 🔴 **测试不许替用户点。** 被测软件装在本机时,"发命令"这层没打桩就是真的发出去了——曾经跑一次测试就在用户桌面上弹一个窗,而测试全绿,因为副作用不在任何断言里。在测试根 `conftest.py` 放 autouse 全局桩,**换掉模块里那个 `subprocess` 名字,不是改 `subprocess.run` 属性**(后者改的是全局模块对象,别的用例会当场炸)。

排障时记一条:**用户说"关不掉 / 又回来了",那是持久化状态的特征,不是手滑的特征**——先去 `Rainmeter.ini` 看 `Active`,别在触发点上找谁点了它。

细节:`references/rainmeter-drawing.md`(贝塞尔/InlineSetting/三个默认值坑)、`references/layout.md`(带区/原点锚定/平移)、`references/interaction.md`(InputText 只认 Enter / 双击防抖)、`references/popups.md`(可选弹层:激活态持久化/层级/关闭终点)。

---

## §3 工作流③:改布局

### macOS(原生面板)

改 `templates/macos-panel/Panel.swift`,然后 `bash scripts/deploy_macos.sh --board <board>` 重新上墙。
不需要平移工具 —— SwiftUI 自己算布局,没有 Y 值要补偿。三个常改的地方:

- **块的顺序 / 标题** → 文件顶部的 `ORDER` 和 `TITLES` 两张表,不用动渲染代码。
- **某个模块要专属排版** → `customBlock()` 里加一个 `case <prefix>`,并把 prefix 加进 `hasCustom`;
  没有专属分支的模块自动走 `GenericBlock` 兜底(新装模块**不改代码就能上墙**)。
- **配色 / 宽度** → 文件上方的 `c*` 常量与 `PANEL_W`。

🔴 改完必须真机看一眼排版 —— 窗口在不在、在哪一层可以用 `CGWindowListCopyWindowInfo` 程序化验,
但**好不好看只能人眼判断**,别拿「进程在跑」当验收通过。

### Windows(Rainmeter 皮肤)

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

macOS 侧:`bash scripts/deploy_macos.sh --board <board> --stop` 停掉面板,再删 `<board>/<名>.app`
与 `~/Library/LaunchAgents/` 下的 plist(`launchctl bootout gui/$(id -u)/<label>` 先卸载)。
用户数据(config/todos/state/health/data.json)同样默认保留,删之前问一句。

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
- **部署与测试不许替用户操作界面**:装配/采集/部署链路上的任何一步都不许 `!ActivateConfig` 一个弹层;测试根必须有 autouse 全局桩挡住向 Rainmeter 发命令。理由与写法见 `references/popups.md §1 / §4`——这条一破,用户桌面上会多出一个**他关不掉**的窗。

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

`references/encoding.md`(GBK 桥/UTF-16/中文 bat) · `references/rainmeter-drawing.md`(贝塞尔/InlineSetting/锚点) · `references/layout.md`(带区/原点锚定/平移/高度预算) · `references/interaction.md`(InputText 只认 Enter/双击防抖) · `references/data-sources.md`(彩云 3 天上限/代理 fake-IP 定位漂移/TLS 测延迟) · `references/security.md`(禁止项 + 审阅点全表) · `references/contribution.md`(回流 PR 流程) · `references/troubleshoot.md`(排障决策树) · `references/backends.md`(多后端概念稿) · `references/popups.md`(可选二级弹层:要不要做的判据、激活态持久化、层级三条、测试不碰真机) · `references/macos.md`(**macOS 必读**:三种形态取舍、不装 Xcode 的能力边界、窗口层级与鼠标事件、拖动移交、可点提示、launchd、实测内存)。
