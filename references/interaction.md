# interaction · InputText / 双击防抖 / 动态定位 / 并发语义

看板不只是只读挂件——todo 模块能就地勾选、编辑、增删。交互靠 band.inc 的鼠标 `Action` 调用同目录的 `todo_action.py`。本篇记做交互模块必踩的四个坑。

## 1. `InputText` 只认 Enter 提交,点框外=静默丢弃

- **现象**:想给输入框做一个"确认按钮",点按钮读输入框的值——读不到,或点框外后值就没了。
- **根因**:Rainmeter 的 `Plugin=InputText` **只有 Enter 触发 `Command1`**(提交);一旦焦点离开输入框(点了别处),`FocusDismiss=1` 会**静默丢弃**当前输入,`$UserInput$` 此时已不可取。它没有"读当前框内文本"的旁路 API——**做不了独立确认按钮**。
- **解法**:提交动作只能绑在输入框的 `Command1`(=用户按 Enter)。UI 上就设计成"弹出输入框 → 打字 → Enter 提交 / Esc 或点别处取消":
  ```
  [TdInput]
  Measure=Plugin
  Plugin=InputText
  FocusDismiss=1
  Command1=["#TdPyw#" "#TdScript#" input "#TdEditRow#" "$UserInput$" "#TdConfig#"]
  DismissAction=[!Refresh]
  ```
  增/改用同一个输入框,靠运行时变量 `#TdEditRow#` 区分(`0`=新增追加,`N`=改写第 N 条);双击某行时 `!SetVariable TdEditRow "N"` 并 `!SetOption TdInput DefaultValue "原文"` 预填。

## 2. 双击防抖:UpAction 会触发两次

- **现象**:给待办文字绑"单击切完成态"(`LeftMouseUpAction=... toggle`),同时想"双击开编辑框"。结果**双击会先误切一次完成态 + `!Refresh` 把刚弹出的编辑框冲掉**。
- **根因**:Windows 双击的消息序列是 **`DOWN / UP / DBLCLK / UP`**——两个 `UP`。Rainmeter 的 `LeftMouseUpAction` 因此在一次双击里**触发两次**(源仓 `Skin.cpp` 实证)。单击直接动作,双击必然多打一下。
- **解法**(`todo_action.click`):单击**不立即动作**,先原子追加一条点击流水,等一个**双击判别窗**(`DBL_WINDOW=0.30s`)让另一次点击(若有)落盘可见,再**只读**统计该行在窗内的点击数:
  - 窗内计数 `< 2` → 确属单击 → `toggle`;
  - 窗内计数 `≥ 2` → 判为双击 → 单击侧**不动作**,交给 `LeftMouseDoubleClickAction` 开编辑框。
  ```python
  def click(n, skin=None):
      my_ts = time.time()
      _log_click(n, my_ts)                 # O_APPEND 追加一行 "行号 时间戳"(非内核级原子,见下)
      time.sleep(DBL_WINDOW + 0.03)        # 等足判别窗
      if _count_clicks(n, my_ts) < 2:      # 只读计数,不 truncate → 无写竞争
          toggle(n, skin)
  ```

### 为什么 `.clicks` 用 `O_APPEND` + 只读计数

- 双击的两个 `UP` 各起**一个进程**,若用"读全文件→改→写回"会互相覆盖(truncate 竞争),计数不准。
- 改成:每次点击 `os.open(..., O_WRONLY|O_CREAT|O_APPEND)` **单次小写**,判别只**读文件计数**(不改),从根上避开 read-modify-write 的 truncate 竞争。
- ⚠ **别把 O_APPEND 当硬原子保证**:CPython 在 Windows 上的 `O_APPEND` 是 CRT 层 **seek-to-end + write 两步**,并非内核级 `FILE_APPEND_DATA` 原子写——高并发下理论上存在丢写(一次 `UP` 覆盖另一次 → 双击被少计成单击、误 toggle,恰是它想防的 bug)。本场景每次点击只追加一行、两次写间隔毫秒级,实测难触发、实践安全;但**高并发模块请另设计**(加锁 / 单写进程 / OS 级原子 API)。
- 旧点击由 `collector.prune_clicks()` **每轮采集顺手剪掉**(留 `CLICKS_TTL=5s` 内)——orchestrator 周期只跑 `collector.py`,band 从不触发 `render`,故回收**必须挂在采集这条必经路**上,否则 `.clicks` 只增不减、计数越来越慢。

## 3. 动态定位 `Y=#var#` 与装配不兼容 → 改固定位置

- **现象**:源仓的行内输入框跟随待办条数落在"下一空行",用 `Y=#TodoInputY#`。搬进本仓装配后,输入框跑到错误位置。
- **根因**:本仓带区要经装配平移器 `shift_band.shift()` 整体落位,而它**只平移数字字面量 `Y=`**,`Y=#变量#` 不会被移到绝对坐标(见 `layout.md §3`)。
- **解法**:交互元素改用**固定数字字面量 Y**。todo 把跟随行号的输入框改成**单个输入框固定 `Y=2`**(表头就地弹出),用 `#TdEditRow#` 区分增/改——行为等价,装配正确。**交互模块里凡是要被装配平移的定位,一律数字字面量,不用动态 Y。**

## 4. 并发语义:两份文件保证不同,别混为一谈

| 文件 | 写法 | 保证 | 不保证 |
|---|---|---|---|
| `todos.json` | 临时文件 + `os.replace` 原子替换 | **不撕裂**:读方要么见旧全本、要么见新全本,永不半截 | **非**并发安全的 read-modify-write:多进程同时改是 **last-writer-wins**(后写者用自己读到的旧快照覆盖,中间别人的改动会丢) |
| `.clicks` | `O_APPEND` 单次小写 + 只读计数 | 避开 read-modify-write 的 truncate 竞争;本场景(每次追加一行、毫秒级间隔)实践安全 | **非**内核级原子写:Win 上 `O_APPEND`=CRT seek-to-end+write 两步,高并发下理论上会丢写(双击被少计成单击)——勿当硬原子保证,高并发另设计 |

- `todos.json` 的 last-writer-wins 在**桌面单人 widget** 场景可接受(不会两个人同时抢改)。若把本模块当范本扩到多写者,需另加锁/CAS,**别默认它"并发安全"**。
- 交互后即时反馈靠 `todo_action` 重渲 `todos.inc`(UTF-16),皮肤 `@Include2` 在 `data.inc` 之后载入 → **覆盖同名变量** → 不必等下一轮采集就上屏。中文只经这条 UTF-16 通道(见 `encoding.md`),**绝不用 `!SetOption ... Text 中文`**。
