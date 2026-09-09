# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，所有公开版本面共用同一版本号。

## [未发布]

## [0.4.0] -- 2026-09-09

### 新增

- **macOS 支持（双平台并列，不是替换）**。Rainmeter 只有 Windows 版，macOS 上没有等价物，所以换的是渲染层不是整套：
  - **采集层零改动**：模块的 `collector.py` 不动、调度不动。`orchestrator.py` 每轮在写 `data.inc`（UTF-16，给 Rainmeter）的同时多写一份 `data.json`（UTF-8，给 macOS 面板）；🔴 **两份出自同一份 outputs**，各算各的迟早会「两个平台上的数不一样」，而这种不一致没有任何症状、只能靠肉眼比对发现，所以用例里钉死了同源断言。
  - **原生 SwiftUI 面板模板** `templates/macos-panel/Panel.swift`：按模块 prefix 自动分块渲染，**新装模块不改代码就能上墙**；块的顺序与标题是两张表（`ORDER` / `TITLES`），要给某个模块做专属排版才动 `customBlock()`。
  - **一条命令上墙** `scripts/deploy_macos.sh`：编译 + 本机自签 + 启动。**不需要 Xcode、不需要 Apple 开发者账号**——自己在自己机器上编出来的 App 没有隔离标记，Gatekeeper 不拦。实测常驻内存 18~22 MB、CPU 0.0%。
  - **`references/macos.md`**：形态取舍（原生面板 / WidgetKit 小组件 / 网页贴壁纸）与全部平台硬限制，每条都是真机实测。
- **SKILL 路由改成「先认平台，再认意图」**，并在 §3 改布局、§5 卸载两处分平台给法。macOS 定时明确用 `launchd` 而不是 `cron`：笔记本合盖时 cron 会直接跳过错过的时间点，launchd 会在唤醒后补跑。

### macOS 上最容易白干的几件事（全部实测，细节见 `references/macos.md`）

- 🔴 **窗口钉在桌面层就永远收不到鼠标**——窗口服务器不往那一层投递事件。画得出来，但永远点不了、拖不动。要可拖可点必须用**桌面图标层**（桌面图标本身能点能拖，就是这层收事件的证据）。
- 🔴 **无边框窗口默认不能成为 key 窗口**，不重写 `canBecomeKey` / `canBecomeMain` 照样收不到事件。这条和层级是两件事，缺任一条都表现为「点不动」。
- 🔴 **只装 Command Line Tools 时用不了 `@State` 等 SwiftUI 宏**（实现插件 `SwiftUIMacros` 只随 Xcode 提供，`swiftc` 直接报错）。状态放进 `ObservableObject` 即可绕过，`@Published` / `@ObservedObject` 不是宏、不受影响。
- 🔴 **拖动要交给窗口服务器**（`performDrag(with:)`），别自己逐帧 `setFrameOrigin`——后者每帧过一遍 SwiftUI 布局，手感明显发涩。`isMovableByWindowBackground` 对 SwiftUI 内容不可靠，显式关掉。
- 🔴 **同层里谁在前谁收事件**：系统桌面小组件也在这一层，被它压到后面之后面板会彻底没反应。移动完重排，外加 5 秒心跳兜底。
- 🔴 **可点元素必须自己说明「我能点」**：悬停变手型 + 行尾静态角标。只挂 `onTapGesture` 而没有任何提示，用户不敢点，等于不能点。
- 🔴 **增量为 0 也要显示 `+0`**：只在 >0 时才画的话，「查过了是 0」和「压根没这个字段」在屏幕上一模一样。三态要分得开：`+1` 绿 / `+0` 灰 / `—` 红。
- 🔴 **位置持久化要夹回屏内**：面板高度随内容变，照搬旧坐标会有一截掉出屏幕。
- 🔴 **验收不能靠截图**：SSH 起的进程拿不到「屏幕录制」权限，且不该让别的会话代跑截图（那是绕过权限）。改用 `CGWindowListCopyWindowInfo` 直接问窗口服务器，无需任何权限就能证明「窗口在屏上、在哪一层、多大」。

### 修复

- `scripts/deploy_macos.sh` 里变量名后紧跟中文标点会在某些 locale 下被 bash 当成变量名的一部分，`set -u` 报「未绑定的变量」。全部改为 `${VAR}`，并在原处注明。

## [0.3.0] -- 2026-09-09

### 新增

- **可选的「二级弹层」形态,以及它的四条硬规则**(`references/popups.md`,SKILL §2.8)。看板默认仍是纯展示——弹层是**可选项,不是升级**:每块三四行、一屏看得完、用户只瞥一眼不操作的板,做弹层只会多一套会持久化的状态。新增判据表帮你先判断需不需要,以及对用户怎么问(给单一推荐,不甩菜单)。真要做时四条不能省:
  - 🔴 **「产出文件」和「打开界面」必须是两条命令**。Rainmeter 把「哪些 config 开着」写进 `Rainmeter.ini` 的 `Active=1`,而部署必发的 `!RefreshApp` 会重新加载每一个 `Active=1` 的 config —— 任何一次「顺手激活」都会在之后**每一次部署里复活,用户关掉也没用**。真实事故:部署脚本为生成弹层的数据文件调了一条名叫「显示这一类内容」的命令,于是每部署一次用户桌面上就多一个窗,连着几天都以为是「关不掉」。
  - 🔴 **部署收尾对每个弹层显式 `!DeactivateConfig`**,把遗留的 `Active=1` 一并清掉。
  - 🔴 **弹层 `ZPos` 用 `0`**:`-2` 会把它按到看板底下,`1`/`2` 是霸屏。刷过看板后隔约 0.45s 再补层级收尾,否则被刷新本身盖掉。附:同层内 `!ZPos` 发相同值是空操作,要抬窗得 `!Refresh` 它自己。
  - 🔴 **测试不许替用户点**:被测软件装在本机时,「发命令」这层没打桩就是真的发出去了(曾经跑一次测试就在用户桌面上弹一个窗,而测试全绿——副作用不在任何断言里)。给出 autouse 全局桩写法,并写明**要换掉模块里那个 `subprocess` 名字、不是改 `subprocess.run` 属性**。
- **排障新增一条判据**:用户说「关不掉 / 又回来了」是**持久化状态**的特征,不是手滑的特征 —— 先去 `Rainmeter.ini` 看 `Active`,别在触发点上找谁点了它。
- **绘制默认值三坑**(`references/rainmeter-drawing.md §7`,并收进 §2.7 带区作者约束):
  - `Shape` 的默认描边是 **1px 纯黑** —— 一条 1px 高的分隔线会渲染成 3px、正中间 `#000000` 的黑带。每条线形 Shape 必须显式 `| StrokeWidth 0`;判据是取像素,不是肉眼。
  - **字形墨迹 ≠ 字号**:`‹ ›` 这类标点在雅黑里墨迹只有字号的约三分之一(`FontSize=8` 时 4×4px,`28` 时才 10×13px);而 `◀ ❮ ⟨ ˂` 在雅黑里根本没有字形,会掉进兜底字体。附换字形前的验字脚本。
  - **Rainmeter 量不到文字实宽**:宽度会变的文本要用 `StringAlign=CenterCenter` 让变化对称吃掉,否则文本一长就会压住旁边按估算摆的元素(实测两位数月份把翻页箭头整个盖住,看起来像「那个按钮没画」)。

### 变更

- `§7 禁止项`新增一条硬红线:**部署与测试链路不许替用户操作界面**。这条一破,用户桌面上会多出一个他关不掉的窗。

## [0.2.1] -- 2026-07-30

### 修复

- 安装命令、插件元数据与代理下载链接已统一到当前公开仓地址，避免继续跳转到失效地址。

## [0.2.0] -- 2026-07-22

### 新增

- **本人账号的官方网页只读会话窄例外**：用户每次手动触发后，可在专用持久化浏览器 profile 中读取本人账号、官方域名、同源页面的数据；严格禁止导出或暴露 Cookie、token、密码和 MFA，禁止写操作、跨域跳转与后台自动运行。例外边界经过规则压力测试并进一步收紧。

### 修复

- **每日重活测试不再受运行时刻影响**：测试时钟固定在当天中午，避免夜间运行时“加 2 小时”跨日造成假失败。
- **多板互撞(静默数据丢失)**:第二块板执行 `install_task.ps1` 时,若不显式传 `-TaskName`,会因默认值硬编码为 `SanshengDeskdash` + `Register-ScheduledTask -Force` 而**直接覆盖第一块板的计划任务,且不报错** —— 第一块板从此永不刷新,看板停在旧数据上,用户无从察觉。`uninstall.ps1` 同款硬编码默认值(且不像 `-SkinName` 那样回落读 lock),导致**卸载 B 板会反注册掉 A 板的任务**。三处根治:
  - `assemble.py` 新增 `task_name`,与既有 `skin_name` 同规格写进 `modules.lock.json`(lock 仍是单一真值);缺省按皮肤名推导 —— 默认皮肤保持 `SanshengDeskdash`(向后兼容,既有安装的任务名不漂移),其余皮肤为 `SanshengDeskdash-<皮肤名>`,使多板天然不撞。新增 `--task-name`。
  - `install_task.ps1` / `uninstall.ps1` 各加 `Resolve-TaskName`(显式 > lock > 默认),与 `Resolve-SkinName` 同款模式。
  - `install_task.ps1` 新增**防覆盖栏**:同名任务若指向别的板则拒绝执行并给出三条解法,不再静默 `-Force` 顶掉(幂等边界收紧为「同一块板重装」)。
- **`doctor.py` 多板假阴性**:`--task-name` 缺省硬编码 `SanshengDeskdash`,多板时会对着不存在的默认名报「计划任务未注册」。改为缺省从 `--board` 的 lock 读 `task_name`(lock 缺失/坏 JSON/无该字段均安全退默认名,体检器不自崩)。

## [0.1.0] -- 2026-07-11

首个公开版本(P0「施工队可用」)。陌生用户装上 skill 说一句「帮我搭个桌面看板」,即可走完 体检 → 60 秒上墙 → 五问 → 装模块 / 现场造 → 常驻桌面 的完整链路。

### 新增

- **五工作流 SKILL.md**:初装 / 加模块(含现场造)/ 改布局 / 排障(半自动自愈)/ 升级与卸载;批量五问话术、探源红绿灯、不接清单、三审阅点、禁术语规则。
- **带区装配器 `assemble.py`**:模块 `band.inc`(局部 Y)按顺序累加拼整板 Rainmeter 皮肤,高度预算校验,`modules.lock.json` 单源;四布局不变量测试兜底。
- **调度器 `orchestrator.py`**:subprocess 隔离 + 强制超时跑各模块采集器,`health.json` 记账,`fail_streak≥3` 灰化,汇总写 `data.inc`(UTF-16);done_date 秒退 / daily_heavy / net-only / interval 四套节流。
- **契约层**:`widget.json` 双段(display + runtime)+ stdlib JSON Schema 子集校验器;结构化错误约定 + secret-canary 防泄漏。
- **官方 6 模块**:clock-calendar / weather / todo(交互旗舰)/ github / net-latency / server-status,均自包含 stdlib、真机截图。
- **部署三件 + 体检**:`deploy_skin.ps1`(UTF-8→UTF-16 + 备份轮换)/ `install_task.ps1`(计划任务,幂等)/ `uninstall.ps1`(防误删栏)/ `doctor.py`(环境体检 + 高度预算)。
- **造件工具**:`new_module.py` 骨架生成 + `validate_module.py`(契约校验 + config.example 过 schema + collector dry-run + 禁止项 AST 扫描)。
- **references 9 篇**:encoding / rainmeter-drawing / layout / interaction / data-sources / security / contribution / troubleshoot / backends。
- **模板与起步板**:`templates/module-skeleton/`(七件套骨架)+ `starter-boards/`(minimal / dev / life)。
- **registry 单源 + 双语 README**:`registry/registry.json` 驱动 `gen_readme_gallery.py` 幂等生成模块画廊;中文为主 README + 英文 README_EN;安全模型诚实声明(v1 无运行时沙箱,四层纵深边界)。

### 安全

- 采集器 stdlib-only 为默认,依赖白名单仅 `requests` / `Pillow`;禁 `eval`/`exec`/`shell=True`/`iwr|iex`。
- 密钥只进 gitignore 的 `config.json`,绝不进代码 / 日志 / 错误消息。
- PowerShell 一律 `-ExecutionPolicy Bypass -File` 调用,不改系统策略、全程无网络下载执行。

### 已知边界

- 仅 Windows。v1 无运行时网络沙箱(边界为声明制 + AST 静态扫描 + VALIDATE + 用户审阅四层)。
- 社区管线(module-ci 11 项 / 机器人自动合并 / 质量评级)属 P1,本版未含。
