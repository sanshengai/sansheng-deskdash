# security · 安全模型:三审阅点 / 禁止项 / 供应链 / 诚实边界

skill 让 agent **现场写代码**并让它常驻运行——信任从哪来?本篇是安全边界的完整说明,也是审模块(人工或 `validate_module.py`)的判据来源。**核心诚实**:v1 **没有运行时网络沙箱**,边界靠四层叠加,不伪装成沙箱。

## 1. 三审阅点(半自动的信任闸,不可跳)

1. **装模块前**:朗读该模块 **privacy 三元组**——访问哪些**域名** / 读写哪些**本地路径** / 要哪些**密钥名**(取自 `widget.json.runtime.privacy` + `config.secrets`)。用户同意才装。
2. **现场写/改采集器后**:`validate_module.py` 展示**代码要点 + 实际会访问的网络目标 + 一次真实输出预览**,用户看过点头才接线(拷进板→装配→部署)。
3. **注册/改计划任务前**:说清"会加一个开机后 5 分钟 + 每 2 小时的后台刷新任务",确认再 `install_task.ps1`。

**升级模块 = 重走审阅点二**(升级不是首装豁免);owner 变更 / 被摘牌要明示用户。

## 2. 禁止项全表(硬红线)

| 类别 | 禁止 | 为什么 |
|---|---|---|
| 文件 | 只读外部;**只写自身/board 目录**;禁写系统目录、别人的目录 | 越权写 = 破坏面 |
| 执行 | 禁 `eval` / `exec` / `os.system` / `shell=True` / `iwr\|iex` / `Invoke-Expression` | 任意代码执行;杀毒/SmartScreen 误杀之鉴。`subprocess` 只用 **list 参数** |
| 凭据 | 禁读浏览器 cookie / 凭据目录 / 密码库 | 盗号面 |
| 网络 | 禁访问 `privacy.network` **未声明**的域名(声明与实际必须一致) | 声明制的地基;`validate_module` AST 扫 URL 字面量核对 |
| 皮肤 | 皮肤禁 `!Execute` 任意命令、禁远程加载 | .ini 也是攻击面 |
| 依赖 | `deps ⊆ [requests, Pillow]`,**stdlib-only 为默认**;禁 collector 内 `pip install`;白名单外一律不许 | 见 §3 供应链 |
| 密钥 | 只进 gitignore 的 `config.json`;**绝不进代码 / 日志 / 异常消息** | secret-canary 断言;错误 hint 只说"哪个字段错",不回显值 |

## 3. pip 供应链政策

- **collector stdlib-only 是默认硬约束**。现实可行:六个官方采集器全部只用 stdlib(`urllib`/`socket`/`ssl`/`subprocess`/`json`/`calendar`…),没有一个需要第三方。
- **例外白名单仅 `[requests, Pillow]`**:`requests`(个别 HTTP 场景比 urllib 省事)、`Pillow`(画日历图这类本地渲染)。`deps` 数组只允许这两个值(`widget.schema.json` 的 `enum` 硬约束),空数组 = 零依赖。
- 禁 collector 内 `pip install`;白名单扩充走 maintainer 决议,不是模块作者随手加。

## 4. 诚实边界:v1 无运行时网络沙箱

Windows 用户态没有低成本、可靠的"限制某进程只能连某域名"的沙箱方案。所以**不假装有**。边界 = **四层叠加**:

1. **声明制**:`privacy.network` 列出允许的域名,装前朗读、要用户同意。
2. **AST 静态扫描**(`validate_module.py`):扫 collector 里的 URL 字面量,核对**实际请求域 ⊆ 声明**;检测禁用调用(eval/exec/os.system/shell=True)。
3. **VALIDATE 试跑**:真跑一次采集器,把实际网络目标 + 输出摆给用户看。
4. **用户审阅**:三审阅点,人是最后一道闸。

这四层拦不住一个**蓄意恶意**且**绕过静态特征**的采集器(它可以运行时拼字符串域名躲过 AST)。所以 README 安全模型一节**明说这不是沙箱**,并靠社区治理(摘牌 / 用户端比对提示卸载)兜住恶意模块。诚实比伪装安全重要。

## 5. CI 域名盲区:subprocess 调外部二进制,AST 扫不到

- **现象**:`github` 采集器用 `subprocess` 调 `gh` CLI 拿数据。`gh` 到底连了哪些域名,**AST 扫 Python 源码看不出来**(网络行为在 `gh` 二进制内部,不是 Python 里的 URL 字面量)。
- **根因**:静态扫描只能看它能解析的语言;跨进程调外部二进制处,声明与实际的核验链**断了**。
- **解法**:`validate_module.py` 检测到 `subprocess` 调**非 python 外部二进制** → 把该模块标记 **`network-opaque`**(privacy.network 无法静态核验)→ 输出警告 + 查**"已知二进制→域名"白名单**:
  - 内置 `gh → api.github.com`:若模块声明的 `privacy.network` 覆盖了白名单域名 → 通过(有背书);
  - 白名单外的二进制(自定义 CLI、`curl`/`ssh` 等)→ 警告"该模块网络行为无法静态核验,需人工/文档背书",不自动放行也不硬拦(它是**警告不是错误**,官方模块如 `ping` 仍能过绿灯,但会留一条 opaque 记录供审阅)。
- 维护这张白名单是 maintainer 的活;新增"调外部网络二进制"的模块须补白名单条目或在 README 说明其网络面。

## 6. 给审模块者的速查

- 装前:`privacy` 三元组读给用户听了吗?
- 代码里有没有 §2 禁止项?`validate_module.py` 跑绿了吗?
- URL 字面量的域名都在 `privacy.network` 里吗?有没有 `network-opaque` 的外部二进制没背书?
- `config.example.json` 里有没有像真密钥的东西(熵检测)?`secrets` 声明了吗?
- 输出过 `output.schema` 了吗?schema 有没有用**校验器不支持**的关键字(见 `contribution.md` / `validate_module.py` 的"假信心"检查)?
