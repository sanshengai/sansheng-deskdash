# macos · macOS 上的看板：形态选择、平台硬限制与踩坑

Rainmeter 只有 Windows 版，macOS 上**没有等价物**——所以这不是移植，是换一层渲染。
好消息是本 skill 的分层恰好经得起换：**采集层完全平台无关**（collector 输出扁平 JSON，
orchestrator 汇总），只有渲染层绑平台。Windows 拿 `data.inc`（UTF-16），macOS 拿
`data.json`（UTF-8），**两份出自同一份 outputs**，不会出现两个平台数字不一样。

本篇所有数字与结论都来自 2026-09-09 在 macOS 27.0 / M5 Pro 上的真机实测，不是推演。

## 0. 先选形态：三条路，默认走第一条

| 形态 | 内存 | 排版自由度 | 交互 | 要 Xcode | 要 $99 |
|---|---|---|---|---|---|
| **原生面板**（本篇主线） | **约 20 MB** | 完全自由 | 可拖、可点、可跳链接 | ❌ 不要 | ❌ 不要 |
| WidgetKit 系统小组件 | 更低（系统托管） | 🔴 固定尺寸档 | 🔴 只有按钮/开关，不能滚动、不能打字 | ✅ 必须 | 多半要 |
| 网页贴壁纸（Plash 等第三方） | 100~250 MB | 完全自由 | 看宿主 App | ❌ | ❌ |

**默认推荐原生面板**：零账号、零 Xcode、内存最低档之一，而且**大部分工作在有 Mac 之前就能写**。

**什么时候才值得上 WidgetKit**：用户明确想要「系统原生小组件那种观感」，且愿意装 Xcode。
它的致命限制是不能滚动、不能文本输入——凡是需要输入的功能都得跳回 App。

**不推荐第三方网页方案**：内存是原生的 6~15 倍（同机 Chrome 渲染进程实测 142~372 MB），
而且把渲染押在别人的闭源 App 上。唯一的优势是复用 HTML 排版能力——但采集层本来就要自己维护，
这点优势不成立。

## 1. 🔴 不装 Xcode 能做什么、不能做什么

只装 **Command Line Tools**（`xcode-select --install`）就能：
- `swiftc` 编译 **SwiftUI + AppKit** 的完整原生界面
- `codesign --force --deep --sign -` **本机自签**，直接运行

不能：
- **用不了 SwiftUI 的属性宏** `@State` / `@Binding` / `@StateObject`。它们是**宏**，实现插件
  `SwiftUIMacros` 只随 Xcode 提供，`swiftc` 会报：

  ```
  error: external macro implementation type 'SwiftUIMacros.StateMacro' could not be found
         for macro 'State()'; plugin for module 'SwiftUIMacros' not found
  ```

  **绕法**：状态放进 `ObservableObject`（`@Published` / `@ObservedObject` 是普通属性包装器，
  不是宏，不受影响），视图用 `@ObservedObject` 读。模板 `templates/macos-panel/` 就是这么写的。
- 做 WidgetKit 小组件（必须 Xcode）

**要不要建议用户装 Xcode**：先别。它免费但十几 GB，而绕开宏的代价落在你身上、不落在用户身上。
只有用户明确要做 WidgetKit 时才值得。

## 2. 🔴 窗口层级：桌面层收不到鼠标，这是平台硬限制

三档取舍，**默认用 `desktopIconWindow`**：

| 层级 | 常量 | 在窗口之下 | 能收鼠标 | 说明 |
|---|---|---|---|---|
| 桌面层 | `CGWindowLevelForKey(.desktopWindow)` | ✅ | 🔴 **不能** | 窗口服务器**不往这一层投递鼠标事件**。面板画得出来，但永远点不了、拖不动 |
| 桌面图标层 | `CGWindowLevelForKey(.desktopIconWindow)` | ✅ | ✅ | 桌面图标本身能点能拖，就是这一层收事件的证据。**默认用它** |
| 普通层压底 | `.normal` + `orderBack` | ⚠️ 会被抬起 | ✅ | 兜底档。代价是它成了一个真窗口，会进 Mission Control、可能被误点到前面 |

配套两条，**缺一条都表现为「点不动」**：

1. **无边框窗口默认不能成为 key 窗口**，必须子类化重写：
   ```swift
   final class PanelWindow: NSWindow {
       override var canBecomeKey: Bool { true }
       override var canBecomeMain: Bool { true }
   }
   ```
   不重写的话，就算层级对了照样收不到事件。
2. **同层里谁在前谁收事件**。系统的桌面小组件也在这一层——面板被它压到后面之后会
   **彻底没反应**（不响应悬停、不能拖，看上去像死了）。实测把面板拖到系统日历小组件附近
   必然触发。修法是移动完 `orderFrontRegardless()`，再挂一个 5 秒心跳兜底
   （系统小组件增删都会重排这一层）。

## 3. 🔴 拖动交给窗口服务器，别自己搬窗口

SwiftUI 的 `DragGesture` 里逐帧 `setFrameOrigin` 能拖，但**手感明显发涩**——每一帧都要过
一遍 SwiftUI 布局。用户的原话是「拖动的时候感觉很卡」。

正确做法是一次性移交：

```swift
DragGesture(minimumDistance: 2, coordinateSpace: .global)
    .onChanged { _ in
        guard !ui.dragging, let w = gWindow, let e = NSApp.currentEvent else { return }
        ui.dragging = true
        w.performDrag(with: e)      // 交出去，之后由系统跑完整个拖动循环
    }
    .onEnded { _ in ui.dragging = false; savePosition(); reassertOrder() }
```

`performDrag` 之后走的是和拖系统窗口完全相同的代码路径，跟手。注意用 `ui.dragging` 挡住
重复调用——`onChanged` 每帧都触发，只该在一次拖动里移交一次。

**不要用 `isMovableByWindowBackground`**：它对 SwiftUI 内容经常失效（`NSHostingView` 把
事件消费掉了），而且开着会跟自己的手势打架。显式关掉。

## 4. 可点元素必须自己说明「我能点」

只挂 `onTapGesture` 是不够的：光标不变、也没有任何静态标记，用户的原话是
「我又不确定哪里可以点击，我就怕乱点」。**能点但看不出来等于不能点。**

两重提示，一动一静：

```swift
extension View {
    func clickable(_ action: @escaping () -> Void) -> some View {
        self.contentShape(Rectangle())
            .onHover { $0 ? NSCursor.pointingHand.push() : NSCursor.pop() }
            .onTapGesture(perform: action)
    }
}
```

再给可点行尾加一个淡「›」——它不是装饰，是「这一行能点」的唯一常驻提示（不悬停也看得见）。
外链另加「↗」。

## 5. 位置持久化要夹回屏内

拖完把坐标落盘、启动时恢复。**恢复时必须夹进 `visibleFrame`**：面板高度会随内容变
（实测一次改版 640 → 699），照搬旧坐标就会有一截掉出屏幕。

```swift
let v = NSScreen.main?.visibleFrame ?? .zero
return NSPoint(x: min(max(x, v.minX), v.maxX - size.width),
               y: min(max(y, v.minY), v.maxY - size.height))
```

顺带：系统小组件拖动时会吸附网格，自绘面板不会。**这是差异不是缺陷**，用户可能反而更喜欢
自由摆放；要吸附得自己算，先问再做。

## 6. 定时采集用 `launchd`，不要 `cron`

笔记本会合盖睡眠。`cron` 错过的时间点**直接跳过**，`launchd` 的 `StartInterval` 会在
**唤醒后补跑**——对每两小时刷一次的看板，这是「醒来就是新数据」和「醒来还是昨晚的数据」的区别。

```xml
<key>StartInterval</key><integer>7200</integer>
<key>RunAtLoad</key><true/>
```

装到 `~/Library/LaunchAgents/`，`launchctl bootstrap gui/$(id -u) <plist>` 生效。

## 7. 缺数据要显式标红，不许静默留白

跟 Windows 侧同一条纪律，但在 macOS 上更容易犯：Swift 的可选链一路 `?? ""` 下来，
字段名写错的表现是**一片空白**，看着像「设计如此」。

实测教训：一次接真数据，四个字段名凭印象写错（净增叫 `net` 不叫 `delta`、订阅数叫
`subscriptions` 不叫 `subscription`、百分比已经算好不用再除、网络延迟是三个具名字段
不是数组）。**全靠「取不到就画红色的 —」当场暴露**，否则就是四块空白蒙混过去。

还有一条同源的：**增量为 0 也要显示 `+0`**。只在 `>0` 时才画的话，「查过了是 0」和
「压根没这个字段」在屏幕上一模一样，用户会反馈「看不到新增」。三态要分得开：
`+1` 绿 / `+0` 灰 / `—` 红。

## 8. 实测数字（macOS 27.0 · M5 Pro · 24 GB）

| 项 | 值 |
|---|---|
| 面板常驻内存（`phys_footprint`，即活动监视器「内存」列） | **20~22 MB** |
| CPU（静置） | 0.0% |
| 编译产物 | 约 230 KB |
| 编译耗时 | 数秒 |
| 同机对照 | 罗技驱动 218 MB · Chrome 单个渲染进程 142~372 MB |

注意 `ps` 报的 RSS（约 47 MB）会明显偏大——里面大部分是与系统共享的框架。
**看 `footprint -p <pid>` 的 `phys_footprint`**，那才是用户在活动监视器里看到的数。

## 9. 验收：不能靠截图，靠窗口服务器

SSH 起的进程拿不到「屏幕录制」权限，`screencapture` 直接报
`could not create image from display`。**不要让另一个会话代跑截图**——那是绕过权限。

改成直接问窗口服务器，无需任何权限：

```swift
let list = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as? [[String: Any]] ?? []
// 逐个看 kCGWindowOwnerName / kCGWindowLayer / kCGWindowBounds / kCGWindowIsOnscreen
```

它能证明「窗口在屏上、在哪一层、多大、在哪」，这几项就够判定上墙成功。
**真正需要人眼的只有排版好不好看**，那一项老老实实交给用户看。
