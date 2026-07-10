# todo · 待办清单

桌面看板的**交互旗舰**模块:就地勾选完成、单击/双击、行内新增与改写、删除——全部在看板上直接点,不用切窗口。

- **中文名**:待办清单 / **英文名**:Todo
- **prefix**:`Td` / **分类**:tasks / **交互**:有(`band.interactive: true`)

## 用途(what)

最多 6 行待办(第 7 条起不显示,仍存在 `todos.json`),每行:勾选框 + 文字 + 删除 ✕。

| 操作 | 手势 | 效果 |
|---|---|---|
| 完成/取消 | 单击勾选框,或单击文字 | 切换完成态(灰化 + ✓) |
| 编辑 | 双击文字 | 表头弹出输入框(预填原文),Enter 提交改写 |
| 新增 | 点右上「＋ 添加」 | 表头弹出空输入框,Enter 提交追加到末尾 |
| 删除 | 单击行尾 ✕ | 删除该行 |

## 架构:采集器 + 交互脚本(两脚本一模块)

| 脚本 | 谁调用 | 干什么 |
|---|---|---|
| `collector.py` | orchestrator 每轮 | 读 `todos.json` → 扁平变量(`Row1Text`/`Row1Done`/…/`Count`)+ 部署变量(`Config`/`Pyw`/`Script`)→ 写 `data.inc`。保证冷启动/零交互时看板也显示当前待办。 |
| `todo_action.py` | band 的鼠标 Action | `input`/`click`/`toggle`/`del`:改 `todos.json` → 重渲 `todos.inc`(UTF-16)→ `!Refresh`。**即时反馈**,不必等下一轮采集。 |

两条渲染路共用 `collector.render_vars()`(单一真源,输出严格一致)。`todos.inc` 由皮肤 `@Include2` 在 `data.inc` 之后载入 → 覆盖同名变量 → 交互立即上屏。

## 双击防抖(为什么单击/双击不打架)

**根因**:Windows 双击的消息序列是 `DOWN/UP/DBLCLK/UP`,Rainmeter 的 `LeftMouseUpAction` 会因此触发**两次**(源仓 Skin.cpp 实证)。若单击直接 `toggle`,双击就会「先误切完成态 + `!Refresh` 冲掉刚弹出的编辑框」。

**解法**(`todo_action.click`):单击不立即动作——先原子追加一条点击流水(`.clicks`),等一个判别窗(`DBL_WINDOW=0.30s`)让另一次点击(若有)落盘可见,再**只读**统计该行在窗内的点击数:

- 窗内计数 `< 2` → 确属单击 → `toggle`;
- 窗内计数 `≥ 2` → 判为双击 → 单击侧不动作,交给 `LeftMouseDoubleClickAction` 开编辑框。

并发安全:两个 UP 各起一个进程,均**只追加(原子)+ 只读计数**(不 truncate),无文件撕裂。旧点击在 `render` 周期被 `_prune_clicks()` 剪掉(留 5s 内)。

## 为什么输入框不跟随行号(装配约束)

源仓的行内输入框用动态 `Y=#TodoInputY#`(随待办条数落在下一行)。但本仓的带区要经**装配平移器** `shift_band.shift()` 整体落位,而它**只平移数字字面量 `Y=`**,`Y=#变量#` 形式不会被平移到绝对坐标——动态 Y 的输入框装配后会跑到错误位置。

故改为:**单个输入框 `[TdInput]` 固定 `Y=2`(数字字面量,装配正确平移)**,在表头就地弹出;用运行时变量 `#TdEditRow#` 区分增/改(`0`=新增追加,`N`=改写第 N 条)。双击某行会 `!SetVariable TdEditRow "N"` 并预填原文。行为与源仓等价,且装配安全。

## 配置(config)

复制 `config.example.json` 为 `config.json`(两项均可缺省):

```json
{
  "skin_name": "DeskdashDemo",
  "rainmeter_exe": "C:\\Program Files\\Rainmeter\\Rainmeter.exe"
}
```

- `skin_name`:部署后的皮肤 config 名。交互后 `!Refresh` 定向刷新该皮肤;**留空则走 `!RefreshApp` 全刷**(略重但稳)。部署脚本(Task 7)会自动填。
- `rainmeter_exe`:Rainmeter.exe 路径,缺省用标准安装路径。
- 无密钥字段(`secrets: []`)。

## 依赖与安全

- **依赖**:无(纯 stdlib)。
- **网络**:无(`privacy.network: []`)。**读本地**:`todos.json`。**写本地**:`todos.json` / `todos.inc`(board 根)/ `.clicks`——都在自身/board 目录内。
- 无 `eval` / `exec` / `shell=True`;`subprocess` 用 list 参数(仅 `Rainmeter.exe !Refresh`)。
- 🔒 **用户数据**:`todos.json` 是你的待办内容,已 gitignore,永不入仓。

## 自验

```bash
python collector.py --config config.example.json
# → 单行 JSON,含 Count / Row1Text.. / Title / Pyw / Script(无 todos.json 时 Count=0,全行透明)
```

交互逻辑测试见 `tests/test_todo_module.py`(迁自源仓 `tests/test_todo.py` 的 8 项:防抖/settext/toggle/prune 等)。
