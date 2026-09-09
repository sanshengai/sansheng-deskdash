// macOS 原生桌面面板 · 通用模板
//
// 契约：读 `<board>/data.json`（orchestrator 每轮和 data.inc 一起写，同一份 outputs），
// 按模块 prefix 分块渲染。**新增模块不用改这个文件** —— 模块进了板，data.json 里就多一段，
// 面板自动多一块。要给某个模块做专属排版时，再在 CUSTOM 区加一个分支。
//
// 本文件所有平台相关的坑都在 references/macos.md 里有完整解释，改之前先读那一篇。
// 三条最容易翻车的，这里也各留了行内注释：窗口层级 / 拖动移交 / 缺数据标红。
//
// 编译（只需 Command Line Tools，不需要 Xcode、不需要 Apple 账号）：
//    bash scripts/deploy_macos.sh --board ~/Deskdash
import AppKit
import SwiftUI

// MARK: - 宽松取值
//
// 🔴 一律「取不到就画红色的 —」，绝不静默留白。
// Swift 的可选链一路 `?? ""` 下来，字段名写错的表现是一片空白，看着像「设计如此」。
// 实测一次接真数据错了四个字段名，全靠这条当场暴露。

struct J {
    let raw: Any?
    init(_ r: Any?) { raw = r }
    subscript(_ k: String) -> J { J((raw as? [String: Any])?[k]) }
    var dict: [String: Any] { (raw as? [String: Any]) ?? [:] }
    var arr: [J] { (raw as? [Any])?.map(J.init) ?? [] }
    var str: String? { raw as? String }
    var int: Int? { (raw as? NSNumber)?.intValue }
    var bool: Bool { (raw as? NSNumber)?.boolValue ?? false }
    var missing: Bool { raw == nil }
    /// 标量转展示串。nil → 「—」，由调用方配红色。
    var show: String { str ?? int.map(String.init) ?? (raw == nil ? "—" : "\(raw!)") }
}

final class Store: ObservableObject {
    @Published var root = J(nil)
    @Published var loadedAt = ""
    @Published var error = ""
    private let url: URL
    private var timer: Timer?
    init(path: String, everySeconds: TimeInterval = 60) {
        url = URL(fileURLWithPath: path)
        load()
        timer = Timer.scheduledTimer(withTimeInterval: everySeconds, repeats: true) { [weak self] _ in
            self?.load()
        }
    }
    func load() {
        do {
            root = J(try JSONSerialization.jsonObject(with: try Data(contentsOf: url)))
            let f = DateFormatter(); f.dateFormat = "HH:mm"
            loadedAt = f.string(from: Date()); error = ""
        } catch { self.error = String("\(error)".prefix(50)) }
    }
    var modules: [String: Any] { root["modules"].dict }
    var health: J { root["health"] }
}

/// 交互态。🔴 这里本该用 @State，但 @State 是**宏**，实现插件只随 Xcode 提供；
/// 只有 Command Line Tools 时 swiftc 会报 "could not be found for macro 'State()'"。
/// @Published / @ObservedObject 是普通属性包装器，不受影响 —— 所以状态外置到这里。
final class UIState: ObservableObject {
    @Published var hovering = false
    var dragging = false
}

// MARK: - 视觉（改配色改这里；颜色只表状态，不作装饰）

let cBG     = Color(red: 18/255, green: 24/255, blue: 34/255)
let cText   = Color(red: 228/255, green: 235/255, blue: 243/255)
let cSub    = Color(red: 148/255, green: 158/255, blue: 173/255)
let cMuted  = Color(red: 108/255, green: 118/255, blue: 134/255)
let cAccent = Color(red: 52/255, green: 199/255, blue: 120/255)
let cRed    = Color(red: 235/255, green: 82/255, blue: 82/255)
let cAmber  = Color(red: 232/255, green: 176/255, blue: 68/255)
let cLine   = Color.white.opacity(0.10)

let PANEL_W: CGFloat = 340, PANEL_PAD: CGFloat = 14

weak var gWindow: NSWindow?

func openURL(_ s: String?) {
    guard let s = s, let u = URL(string: s) else { return }
    NSWorkspace.shared.open(u)
}

// MARK: - 元件

/// 🔴 可点元素必须自己说明「我能点」：悬停变手型（动态）+ 行尾淡「›」（静态）。
/// 只挂 onTapGesture 而没有任何提示 = 用户不敢点 = 等于不能点。
extension View {
    func clickable(_ action: @escaping () -> Void) -> some View {
        self.contentShape(Rectangle())
            .onHover { $0 ? NSCursor.pointingHand.push() : NSCursor.pop() }
            .onTapGesture(perform: action)
    }
}

struct Chev: View {
    var body: some View { Text("›").font(.system(size: 11)).foregroundStyle(cMuted.opacity(0.7)) }
}

struct KV: View {
    let k: String
    let v: String
    var vc: Color = cText
    var note: String? = nil
    var body: some View {
        HStack(spacing: 6) {
            Text(k).font(.system(size: 11)).foregroundStyle(cSub)
            Spacer(minLength: 6)
            if let n = note { Text(n).font(.system(size: 10)).foregroundStyle(cMuted) }
            Text(v).font(.system(size: 11, weight: .medium)).foregroundStyle(vc)
        }
    }
}

struct Head: View {
    let t: String
    var right: String? = nil
    var rc: Color = cMuted
    var action: (() -> Void)? = nil
    var body: some View {
        HStack {
            Text(t).font(.system(size: 11, weight: .semibold)).foregroundStyle(cText)
            Spacer()
            if let r = right {
                if let a = action { Text(r).font(.system(size: 10)).foregroundStyle(rc).clickable(a) }
                else { Text(r).font(.system(size: 10)).foregroundStyle(rc) }
            }
        }
    }
}

struct Div: View {
    var body: some View { Rectangle().fill(cLine).frame(height: 1).padding(.vertical, 8) }
}

/// 增量文本。🔴 +0 也要显示：把「查过了是 0」和「压根没这个字段」区分开。
/// 只在 >0 时才画的话，两种情况在屏幕上一模一样。
func deltaText(_ n: Int?) -> (String, Color) {
    guard let n = n else { return ("—", cRed) }
    if n > 0 { return ("+\(n)", cAccent) }
    if n < 0 { return ("\(n)", cRed) }
    return ("+0", cMuted)
}

/// 环形占比。比柱状条更容易一眼读出「满没满」。
struct Ring: View {
    let pct: Int?
    let label: String
    var note: String? = nil
    var color: Color {
        guard let p = pct else { return cRed }
        return p > 85 ? cRed : (p > 70 ? cAmber : cAccent)
    }
    var body: some View {
        HStack(spacing: 8) {
            ZStack {
                Circle().stroke(Color.white.opacity(0.09), lineWidth: 4)
                Circle().trim(from: 0, to: CGFloat(min(Double(pct ?? 0) / 100.0, 1)))
                    .stroke(color, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text(pct.map { "\($0)%" } ?? "—")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(pct == nil ? cRed : cText)
            }.frame(width: 38, height: 38)
            VStack(alignment: .leading, spacing: 1) {
                Text(label).font(.system(size: 11)).foregroundStyle(cSub)
                if let n = note { Text(n).font(.system(size: 9)).foregroundStyle(cMuted) }
            }
        }
    }
}

// MARK: - 默认渲染：任何模块都能显示

/// 兜底块：把一个模块的扁平 outputs 逐行画出来。
/// 新装的模块**不用改代码**就能上墙 —— 先能看见，再谈好不好看。
struct GenericBlock: View {
    let title: String
    let kv: [String: Any]
    let stale: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Head(t: title, right: stale ? "数据陈旧" : nil, rc: cAmber)
            ForEach(kv.keys.sorted(), id: \.self) { k in
                KV(k: k, v: J(kv[k]).show, vc: kv[k] == nil ? cRed : cText)
            }
        }
    }
}

// MARK: - ▼▼▼ CUSTOM：给某个模块做专属排版就加在这里 ▼▼▼
//
// 约定：函数返回 nil 表示「这个模块没有专属排版」，交回 GenericBlock 兜底。
// 加专属块时优先复用上面的元件（KV / Ring / Head / deltaText），排版才统一。
//
// 例：给 server-status 模块画环形占比而不是一行行数字。
@ViewBuilder
func customBlock(prefix: String, kv: [String: Any], stale: Bool) -> some View {
    let j = J(kv)
    switch prefix {
    case "Sv":                                  // server-status 模块的 output prefix
        VStack(alignment: .leading, spacing: 8) {
            Head(t: "服务器", right: stale ? "数据陈旧" : nil, rc: cAmber)
            HStack(spacing: 0) {
                Ring(pct: j["MemPct"].int, label: "内存").frame(maxWidth: .infinity, alignment: .leading)
                Ring(pct: j["DiskPct"].int, label: "硬盘").frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    default:
        EmptyView()
    }
}

func hasCustom(_ prefix: String) -> Bool { ["Sv"].contains(prefix) }

// MARK: - 面板

/// 模块显示名。key 是 output prefix；没登记的直接显示 prefix。
/// 想调块的**顺序**改 ORDER，想调**标题**改 TITLES —— 都不用动渲染代码。
let TITLES: [String: String] = ["Cc": "时钟日历", "Wx": "天气", "Td": "待办",
                                "Gh": "GitHub", "Nl": "网络延迟", "Sv": "服务器"]
let ORDER: [String] = ["Cc", "Wx", "Td", "Nl", "Sv", "Gh"]

struct PanelView: View {
    @ObservedObject var store: Store
    @ObservedObject var ui: UIState
    let levelName: String

    /// 🔴 拖动一律交给窗口服务器接管。自己逐帧 setFrameOrigin 也能拖，但每帧过一遍
    /// SwiftUI 布局，手感明显发涩（用户原话「拖动的时候感觉很卡」）。
    var dragGesture: some Gesture {
        DragGesture(minimumDistance: 2, coordinateSpace: .global)
            .onChanged { _ in
                guard !ui.dragging, let w = gWindow, let e = NSApp.currentEvent else { return }
                ui.dragging = true
                w.performDrag(with: e)
            }
            .onEnded { _ in
                ui.dragging = false
                if let d = NSApp.delegate as? Delegate { d.savePosition(); d.reassertOrder() }
            }
    }

    var orderedPrefixes: [String] {
        let present = Array(store.modules.keys)
        let known = ORDER.filter { present.contains($0) }
        return known + present.filter { !ORDER.contains($0) }.sorted()   // 没登记的排在后面
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text("桌面看板").font(.system(size: 13, weight: .bold)).foregroundStyle(cText)
                Spacer()
                Text(store.error.isEmpty ? "读于 \(store.loadedAt) · \(levelName)" : "读不到数据")
                    .font(.system(size: 9))
                    .foregroundStyle(store.error.isEmpty ? cMuted : cRed)
            }
            Div()
            if store.modules.isEmpty {
                Text("data.json 里没有模块输出 — 先跑一次 orchestrator")
                    .font(.system(size: 11)).foregroundStyle(cRed)
            } else {
                ForEach(Array(orderedPrefixes.enumerated()), id: \.element) { i, p in
                    let kv = (store.modules[p] as? [String: Any]) ?? [:]
                    let stale = J(kv)["Stale"].bool
                    if hasCustom(p) { customBlock(prefix: p, kv: kv, stale: stale) }
                    else { GenericBlock(title: TITLES[p] ?? p, kv: kv, stale: stale) }
                    if i < orderedPrefixes.count - 1 { Div() }
                }
            }
        }
        .padding(PANEL_PAD)
        .frame(width: PANEL_W, alignment: .topLeading)
        .background(cBG)
        .clipShape(RoundedRectangle(cornerRadius: 13))
        .overlay(RoundedRectangle(cornerRadius: 13)
            .stroke(ui.hovering ? cAccent : Color.white.opacity(0.14), lineWidth: ui.hovering ? 2 : 1))
        .contentShape(Rectangle())
        .onHover { ui.hovering = $0 }
        .gesture(dragGesture)
    }
}

// MARK: - 窗口

/// 🔴 无边框窗口默认 canBecomeKey = false，不重写就收不到任何鼠标事件。
/// 这一条和「层级」是两件事，缺任一条都表现为「点不动」。
final class PanelWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

final class Delegate: NSObject, NSApplicationDelegate {
    var window: PanelWindow!
    var store: Store!
    var posFile: URL!

    func applicationDidFinishLaunching(_ n: Notification) {
        var dir = NSHomeDirectory() + "/Deskdash"
        var levelArg = "icon"
        var it = CommandLine.arguments.dropFirst().makeIterator()
        while let a = it.next() {
            switch a {
            case "--board": if let v = it.next() { dir = v }
            case "--level": if let v = it.next() { levelArg = v }
            default: break
            }
        }
        posFile = URL(fileURLWithPath: dir + "/panel-window.json")
        store = Store(path: dir + "/data.json")

        let ui = UIState()
        let host = NSHostingView(rootView: PanelView(store: store, ui: ui, levelName: levelArg))
        host.frame = NSRect(x: 0, y: 0, width: PANEL_W, height: host.fittingSize.height)

        window = PanelWindow(contentRect: host.frame, styleMask: [.borderless],
                             backing: .buffered, defer: false)
        window.contentView = host
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = false
        window.ignoresMouseEvents = false
        window.isMovableByWindowBackground = false   // 对 SwiftUI 内容不可靠，且会跟手势打架
        window.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]

        // 层级三档，取舍见 references/macos.md §2
        switch levelArg {
        case "desktop":                              // 永不打扰，但**收不到鼠标**（平台硬限制）
            window.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.desktopWindow)))
        case "back":                                 // 兜底：一定可交互，但成了真窗口
            window.level = .normal
        default:                                     // icon：默认。桌面图标能点，说明这层收事件
            window.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.desktopIconWindow)))
        }

        window.setFrame(NSRect(origin: savedOrigin(size: host.frame.size), size: host.frame.size),
                        display: true)
        if levelArg == "back" { window.orderBack(nil) } else { window.orderFrontRegardless() }
        gWindow = window

        // 🔴 心跳：同层里谁在前谁收事件。系统桌面小组件也在这一层，被它压到后面之后面板会
        // 彻底没反应（不响应悬停、拖不动）。5 秒抬一次，位置没变时是空操作。
        Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.reassertOrder() }
    }

    func reassertOrder() {
        guard let w = window, w.level != .normal else { return }
        w.orderFrontRegardless()
    }

    func savePosition() {
        guard let f = window?.frame else { return }
        try? JSONSerialization.data(withJSONObject: ["x": f.origin.x, "y": f.origin.y]).write(to: posFile)
    }

    func savedOrigin(size: NSSize) -> NSPoint {
        let v = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1512, height: 859)
        if let d = try? Data(contentsOf: posFile),
           let o = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any],
           let x = (o["x"] as? NSNumber)?.doubleValue, let y = (o["y"] as? NSNumber)?.doubleValue {
            // 🔴 夹回屏内：面板高度随内容变，照搬旧坐标会有一截掉出屏幕。
            return NSPoint(x: min(max(x, v.minX), v.maxX - size.width),
                           y: min(max(y, v.minY), v.maxY - size.height))
        }
        return NSPoint(x: v.maxX - size.width - 24, y: v.maxY - size.height - 24)
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)          // 不占 Dock、不抢焦点
let delegate = Delegate()
app.delegate = delegate
app.run()
