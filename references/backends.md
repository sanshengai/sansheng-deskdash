# backends · 多后端概念稿(留门,不实现)

v1 只做 Windows + Rainmeter。但契约设计时**特意把后端相关的部分收窄到一层**,好让未来接别的桌面挂件引擎(macOS 的 Übersicht、Linux 的 Conky 等)时**只补适配层、不重写模块**。本篇是概念稿——**留门,不留实现债**;P0/P1 不写任何后端代码。

## 1. 契约三层:只有 band 是 Rainmeter 专有

`widget.json` 的 `runtime` 段可按"是否绑定后端"切成三类:

| 契约部分 | 后端相关? | 说明 |
|---|---|---|
| `output`(prefix + schema) | **无关** | 采集器吐**扁平标量键值**,任何后端都能消费 |
| `config`(schema + example + secrets) | **无关** | 配置与密钥语义与渲染引擎无关 |
| `privacy`(network/local_read/local_write) | **无关** | 安全声明与后端无关 |
| `refresh`(mode / interval_s / net_only_ok)| **无关** | 调度语义与后端无关 |
| `entry`(collector.py) | **无关** | 采集器是纯 Python,产出 JSON,不碰渲染 |
| **`band`(file / height / interactive)** | **✅ Rainmeter 专有** | `band.inc` 是 Rainmeter 皮肤语法;`height` 是像素堆叠语义 |

**关键设计**:采集器 → 扁平 outputs 这一段**完全后端无关**。换后端 = 换"把 outputs 渲染成挂件"的那一层(band + 装配 + 部署),采集器与契约的其余部分原样复用。

## 2. 接 Übersicht(macOS)需要实现的适配点

[Übersicht](http://tracesof.net/uebersicht/) 是 macOS 上的桌面挂件引擎,widget = 一段 **JSX + CSS**,自带 `refreshFrequency`(毫秒)与 `command`(shell 取数据)。假如未来要接:

1. **band 的对等物**:新增 `widget.jsx`(或 `band.jsx`)替代 `band.inc`——同样用局部布局、绑 outputs 变量,但语法是 JSX/CSS 而非 Rainmeter INI。契约里 `band` 段泛化成 `render`,按后端选 `band.inc` 或 `widget.jsx`。
2. **装配器对等物**:Rainmeter 靠 `assemble.py` 堆叠 band + UTF-16 data.inc;Übersicht 可让每个模块是独立 widget(它原生支持多 widget),或拼一个大 widget。堆叠/高度预算语义要按 JSX 布局重写一层。
3. **调度对接**:Übersicht 的 `refreshFrequency` 对应 `refresh.interval_s`;但本 skill 的调度器(subprocess 跑 collector + 强制 timeout + health 记账)更强,可保留 orchestrator 只出 JSON,让 widget 读 JSON 文件(而非 Übersicht 自己的 `command`)。
4. **编码/部署**:UTF-16 是 Rainmeter 特有;macOS/JSX 用 UTF-8。部署路径、刷新命令(`osascript` 调 Übersicht 刷新)各不同,进后端适配层。
5. **交互**:Übersicht 的交互走 JSX 事件,与 Rainmeter 的鼠标 `Action`+`InputText` 完全不同——交互模块(如 todo)的交互层要按后端重写,但**数据层(collector / todos.json 原子写 / 防抖语义)可复用**。

## 3. 留门原则

- **不为未实现的后端写抽象**:v1 不引入"后端接口基类"之类的空泛抽象层(那是实现债)。只保证**契约里后端无关的部分确实无关**(采集器纯出 JSON、privacy/output/config/refresh 不含 Rainmeter 词汇),门就留住了。
- 真要接新后端时,照 §2 列的五个适配点补一层即可,采集器与六个模块的取数逻辑一行不用改。
- Mac 用户:v1 契约留了概念空间,**不做实现**;README 明说"仅 Windows",不给 Mac 用户虚假承诺。
