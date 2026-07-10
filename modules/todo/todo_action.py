# modules/todo/todo_action.py — 待办交互脚本(被 band.inc 的鼠标 Action 调用)。
#
# 用法(band.inc 的 LeftMouseUpAction / 输入框 Command1 调它;参数从 band 变量取):
#   todo_action.py input <row> "<文字>" [skin]   行内输入提交:row=0 新增到末尾 / row=N 改写第 N 条
#   todo_action.py click  <row> [skin]           待办文字单击:等一个双击窗口,确属单击才切完成态
#   todo_action.py toggle <row> [skin]           立即切换第 row 条完成态(勾选框走这个)
#   todo_action.py del    <row> [skin]           删除第 row 条
#   todo_action.py render [skin]                 重渲 todos.inc + 剪旧点击(供手动/维护触发)
#
# 交互后即时反馈:改 todos.json → 重渲 todos.inc(UTF-16)→ Rainmeter !Refresh。todos.inc 由皮肤
#   @Include2 载入(在 data.inc 之后 → 覆盖 collector 写的同名变量),故无需等下一轮采集就能上屏。
#
# 双击防抖(faithful 迁自私有仓 todo.py,见 click() 注释):Windows 双击序列 DOWN/UP/DBLCLK/UP 会让
#   Rainmeter 的 UpAction 触发两次;单击侧用"判别窗内点击计数"区分单击/双击,双击不误 toggle。
#
# 数据层(load/save/render_vars/路径常量)复用同目录 collector.py(同模块共享,非跨模块 import;
#   保证两条渲染路输出严格一致)。安全铁律:无 eval/exec/shell=True;subprocess 用 list 参数。
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)                      # 让 `import collector`(同目录)在 Rainmeter 启动下可用
import collector                                    # noqa: E402  数据层单一真源

# todos.inc 写到 board 根(= 模块目录的上一级),与模板 @Include2={{TODOS_INC}} 指向一致。
INC = os.path.join(os.path.dirname(_HERE), "todos.inc")
# Rainmeter.exe 默认安装路径(config.rainmeter_exe 可覆盖);仅用于 !Refresh 定向刷新。
RAINMETER = r"C:\Program Files\Rainmeter\Rainmeter.exe"

DBL_WINDOW = 0.30                                   # 双击判别窗(秒);两次点击间隔小于它即判双击


def _row(v):
    """CLI 参数 → 行号 int;非数字视为 0。"""
    s = str(v) if v is not None else ""
    return int(s) if s.lstrip("-").isdigit() else 0


def render_inc(todos):
    """待办 → todos.inc(UTF-16,Rainmeter 中文不乱码)。变量名带 collector.PREFIX,与 data.inc 同名。"""
    varmap = collector.render_vars(todos)
    lines = ["[Variables]", "; 自动生成 勿手改 — todo_action.py"]
    for k, v in varmap.items():
        if isinstance(v, bool):
            v = 1 if v else 0
        lines.append("%s%s=%s" % (collector.PREFIX, k, collector._san(v)))
    tmp = INC + ".tmp"
    with open(tmp, "w", encoding="utf-16") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, INC)


def _rainmeter_exe():
    """Rainmeter.exe 路径:config.json 的 rainmeter_exe 覆盖 > 标准安装路径默认。"""
    try:
        import json
        with open(os.path.join(_HERE, "config.json"), "r", encoding="utf-8") as f:
            v = (json.load(f) or {}).get("rainmeter_exe") or ""
        if v:
            return v
    except (OSError, ValueError):
        pass
    return RAINMETER


def refresh(skin):
    """交互后刷新皮肤:给了 skin 名 → !Refresh 定向;否则 → !RefreshApp 全刷(略重但稳)。
    Rainmeter 未安装/路径不对 → 静默跳过(交互仍已落盘,下一轮采集兜底)。"""
    exe = _rainmeter_exe()
    if not os.path.isfile(exe):
        return
    skin = (skin or "").strip()
    cmd = [exe, "!Refresh", skin] if skin else [exe, "!RefreshApp"]
    try:
        subprocess.Popen(cmd)                      # noqa: S603 (list 参数,非 shell)
    except OSError:
        pass


# —— 变更操作 ——

def add_item(text):
    """追加一条待办(尾部)并重渲。→ True 成功 / False(空文本或已满 MAX_ROWS 条)。"""
    text = (text or "").strip()
    if not text:
        return False
    todos = collector.load_todos()
    if len(todos) >= collector.MAX_ROWS:
        return False
    todos.append({"t": text, "done": False})
    collector.save_todos(todos)
    render_inc(todos)
    return True


def set_text(n, text):
    """改写第 n 条文字(空文本视为取消,不动)。→ True 改了 / False 没动。"""
    text = (text or "").strip()
    todos = collector.load_todos()
    i = n - 1
    if text and 0 <= i < len(todos):
        todos[i]["t"] = text
        collector.save_todos(todos)
        render_inc(todos)
        return True
    return False


def toggle(n, skin=None):
    """立即切换第 n 条完成态(1-based)并重渲 + 刷新。"""
    todos = collector.load_todos()
    i = n - 1
    if 0 <= i < len(todos):
        todos[i]["done"] = not todos[i].get("done")
        collector.save_todos(todos)
        render_inc(todos)
    refresh(skin)


def delete(n, skin=None):
    """删除第 n 条并重渲 + 刷新。"""
    todos = collector.load_todos()
    i = n - 1
    if 0 <= i < len(todos):
        todos.pop(i)
        collector.save_todos(todos)
        render_inc(todos)
    refresh(skin)


def do_input(n, text, skin=None):
    """行内输入框提交:n=0 → 新增;n≥1 → 改写第 n 条。写盘后刷新。"""
    if n <= 0:
        add_item(text)
    else:
        set_text(n, text)
    refresh(skin)


# —— 双击防抖(faithful 迁自私有仓 todo.py)——

def _log_click(n, ts):
    """原子追加一条点击(O_APPEND 单次小写在 Windows 上原子,多进程并发不撕裂)。"""
    line = ("%d %.3f\n" % (n, ts)).encode()
    try:
        fd = os.open(collector.CLICKS, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError:
        pass


def _count_clicks(n, center):
    """只读统计:行 n 在 [center±DBL_WINDOW] 内的点击数。只读不改文件 → 无并发写竞争。"""
    cnt = 0
    try:
        with open(collector.CLICKS, "r", encoding="utf-8") as f:
            for ln in f:
                p = ln.split()
                if len(p) == 2 and int(p[0]) == n and abs(float(p[1]) - center) <= DBL_WINDOW:
                    cnt += 1
    except (OSError, ValueError):
        pass
    return cnt


def click(n, skin=None):
    """待办文字单击:防抖判别单击/双击。判别窗内仅此一次点击 → 切完成态;≥2 次 → 判为双击,
    交 LeftMouseDoubleClickAction 开编辑框,单击侧不动作(否则双击会误 toggle + 刷新冲掉编辑框)。
    根因:Windows 双击序列 DOWN/UP/DBLCLK/UP,Rainmeter UpAction 触发两次(Skin.cpp 实证)。
    并发安全:两个 UP 各起一进程,均只追加(原子)+ 只读计数(不 truncate),无文件撕裂。"""
    my_ts = time.time()
    _log_click(n, my_ts)
    time.sleep(DBL_WINDOW + 0.03)                  # 等足判别窗,让另一次点击(若有)落盘可见
    if _count_clicks(n, my_ts) < 2:               # 确属单击 → 切完成态
        toggle(n, skin)


def _prune_clicks():
    """render 周期调用:剪掉 5s 前的旧点击(单线程路径,无并发)。文件不存在则跳过。"""
    if not os.path.exists(collector.CLICKS):
        return
    cutoff = time.time() - 5
    try:
        with open(collector.CLICKS, "r", encoding="utf-8") as f:
            keep = [ln for ln in f
                    if len(ln.split()) == 2 and float(ln.split()[1]) >= cutoff]
        with open(collector.CLICKS, "w", encoding="utf-8") as f:
            f.writelines(keep)
    except (OSError, ValueError):
        pass


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        a = ["render"]
    cmd = a[0]
    if cmd == "input":
        do_input(_row(a[1] if len(a) > 1 else 0),
                 a[2] if len(a) > 2 else "", a[3] if len(a) > 3 else None)
    elif cmd == "click":
        click(_row(a[1] if len(a) > 1 else None), a[2] if len(a) > 2 else None)
    elif cmd == "toggle":
        toggle(_row(a[1] if len(a) > 1 else None), a[2] if len(a) > 2 else None)
    elif cmd == "del":
        delete(_row(a[1] if len(a) > 1 else None), a[2] if len(a) > 2 else None)
    elif cmd == "render":
        render_inc(collector.load_todos())
        _prune_clicks()
        refresh(a[1] if len(a) > 1 else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
