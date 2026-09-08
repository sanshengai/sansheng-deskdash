# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)，所有公开版本面共用同一版本号。

## [未发布]

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
