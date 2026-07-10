# encoding · 编码地雷:GBK 桥 / UTF-16 / stdout

看板要显示中文,而 Rainmeter + Windows 控制台 + PowerShell 各有一套默认编码。踩错任何一处,中文就变问号或整块乱码。本篇把三处坑的**根因 → 现象 → 解法**说清。

## 0. 一句话根治

**Python 端算好一切,写成 UTF-16 的 `data.inc`,皮肤只用 `#变量#` 绑值。** 皮肤段(`.inc`/`.ini`)里**绝不内联中文字面量**,中文也**绝不进 Lua / `!SetOption` / `!SetVariable`**——只走 `data.inc` 这一条 UTF-16 通道。守住这条,下面三坑全部消失。

## 1. GBK 桥:中文经 Lua/SetOption 会退化成问号

- **现象**:用 `!SetOption`/`!SetVariable`/Lua 脚本给 meter 传中文文本,emoji 与生僻字变 `?`,常用字有时也乱。
- **根因**:Rainmeter 的这几条命令通道按 **ANSI(简体中文机上即 GBK/cp936)** 处理传入文本,不是 UTF-16。凡是超出 GBK 编码范围的字符(emoji、少数生僻字)在这一步被替换为 `?`,且这是**不可逆**的——等它到 meter 已经丢了。
- **解法**:任何要上屏的中文**不经命令通道**。采集器把中文文本写进 `data.inc`(UTF-16),meter 用 `Text=#WxNowDesc#` 直接绑变量。交互模块(todo)同理:改 `todos.json` 后由 `todo_action.py` **重渲 `todos.inc`(UTF-16)**再 `!Refresh`,而不是用 `!SetOption ... Text 中文`。

## 2. data.inc / todos.inc 必须 UTF-16 LE

- **现象**:`data.inc` 存成 UTF-8,Rainmeter 读出的中文全是乱码方块。
- **根因**:Rainmeter 读 `@Include` 的变量文件按 **UTF-16** 解析中文;喂 UTF-8 会被逐字节误读。
- **解法**:
  - `orchestrator.py` 写 `data.inc` 用 `atomic_write(path, text, encoding="utf-16")`;`todo_action.py` 写 `todos.inc` 用 `open(..., encoding="utf-16")`。Python 的 `utf-16` 会自动带 BOM 并按本机字节序(LE)写出。
  - **仓内源文件**(band.inc / widget.json / *.py / 模板)一律 **UTF-8**;只有**运行时生成的** `data.inc`/`todos.inc` 与 **部署副本 `.ini`** 是 UTF-16。二者不要混。
  - 皮肤部署副本:`assemble.py` 产出的 `.ini` 是 UTF-8,**由 `deploy_skin.ps1` 转成 UTF-16 LE+BOM** 落到 `Documents\Rainmeter\Skins\`。你不手动碰这一步的编码。

## 3. collector stdout:必须 `sys.stdout.buffer.write(...encode("utf-8"))`,不用 print

- **现象**:采集器里 `print(json.dumps(..., ensure_ascii=False))`,orchestrator 按 UTF-8 解 stdout 时中文乱码 / 偶发 `UnicodeEncodeError`。
- **根因**:Windows 控制台默认代码页 **cp936(GBK)**;`print` 走 `sys.stdout` 的文本层,按控制台代码页编码,与 orchestrator 约定的 UTF-8 解码不一致。计划任务用 `pythonw` 起进程时更不可控。
- **解法**(六个官方采集器统一写法):
  ```python
  def _emit(obj):
      b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
      sys.stdout.buffer.write(b + b"\n")     # 绕过文本层,直接写 UTF-8 字节
      try:
          sys.stdout.buffer.flush()
      except OSError:
          pass                                # 下游管道提前关闭时不炸
  ```
  orchestrator 侧固定 `proc.stdout.decode("utf-8", "replace")`,两端对齐。**任何新模块的 collector 都照抄这个 `_emit`**。

## 4. 中文 stderr / 子进程输出:按来源定编码

- Windows 的 `ping` 中文输出是 **GBK**;`net-latency`/`server-status` 解析时用 `r.stdout.decode("gbk" if 是Windows else "utf-8", errors="replace")`。别统一按 UTF-8 解外部命令输出。

## 5. PowerShell 脚本(.ps1)自身编码

- **现象**:含中文注释/字符串的 `.ps1` 在 **Windows PowerShell 5.1** 下报解析错或中文乱码。
- **根因**:PS 5.1 对**无 BOM** 的脚本按系统 ANSI(GBK)解码;UTF-8 无 BOM 的中文被错读,可能连累语法。(PowerShell 7+ 默认 UTF-8,无此问题,但发布面向 5.1 兜底。)
- **解法**:仓内 `.ps1` 存 **UTF-8 with BOM**;或脚本内尽量少放中文字面量、用 ASCII 标识符 + 英文提示,把中文说明留给 README。本仓 `deploy_skin.ps1` 等即走"关键提示英文/ASCII、详解进 README"的稳妥路线。

## 速记

| 文件 | 编码 | 谁写 |
|---|---|---|
| band.inc / widget.json / *.py / *.tpl(仓内源) | UTF-8 | 人/agent |
| data.inc / todos.inc(运行时) | UTF-16 LE+BOM | orchestrator / todo_action |
| 部署副本 `<Skin>.ini` | UTF-16 LE+BOM | deploy_skin.ps1(从 UTF-8 转) |
| collector stdout | UTF-8 字节 | `_emit` 直写 buffer |
| .ps1 自身 | UTF-8 **with BOM**(兼容 PS 5.1) | 人/agent |
