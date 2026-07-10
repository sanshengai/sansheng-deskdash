# tests/test_todo_module.py — todo 交互逻辑测试(迁自私有仓 tests/test_todo.py 的 8 项)。
#   防抖(单击/双击判别)、settext、toggle、prune、add、行内输入(do_input)、del、render_inc。
# 数据层在 collector.py,交互层在 todo_action.py(同模块共享);测试通过 patch 两处模块级路径隔离到 tmp。
import os
import sys
import time

_TODO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "modules", "todo")
sys.path.insert(0, _TODO_DIR)
import todo_action as ta          # noqa: E402  (import 时会 import 同目录 collector)
co = ta.collector                  # 数据层单一真源(load/save/render_vars/路径常量)


def _setup(tmp_path, items):
    """把用户数据/点击流水/todos.inc 全隔离到 tmp;RAINMETER 指不存在路径 → refresh 静默跳过。"""
    co.TODOS = str(tmp_path / "todos.json")
    co.CLICKS = str(tmp_path / ".clicks")
    ta.INC = str(tmp_path / "todos.inc")
    ta.RAINMETER = r"Z:\nope\Rainmeter.exe"
    co.save_todos([{"t": t, "done": d} for t, d in items])


# —— settext(改写第 N 条)——

def test_set_text_edits_row(tmp_path):
    _setup(tmp_path, [("原文一", False), ("原文二", True)])
    ta.set_text(1, "改后一")
    todos = co.load_todos()
    assert todos[0]["t"] == "改后一" and todos[0]["done"] is False   # 只改文字不动完成态
    assert todos[1]["t"] == "原文二"


def test_set_text_empty_is_cancel(tmp_path):
    _setup(tmp_path, [("原文", False)])
    ta.set_text(1, "   ")
    assert co.load_todos()[0]["t"] == "原文"          # 空输入=取消,不改


def test_set_text_out_of_range_noop(tmp_path):
    _setup(tmp_path, [("原文", False)])
    ta.set_text(9, "x")
    assert co.load_todos()[0]["t"] == "原文"


# —— toggle(切完成态)——

def test_toggle_flips_done(tmp_path):
    _setup(tmp_path, [("a", False)])
    ta.toggle(1, None)
    assert co.load_todos()[0]["done"] is True
    ta.toggle(1, None)
    assert co.load_todos()[0]["done"] is False


# —— 双击防抖 ——

def test_count_clicks_window(tmp_path):
    _setup(tmp_path, [("a", False)])
    base = 1000.0
    ta._log_click(1, base)
    ta._log_click(1, base + 0.1)         # 窗内(双击)
    ta._log_click(1, base + 5)           # 窗外
    ta._log_click(2, base)               # 别的行
    assert ta._count_clicks(1, base) == 2        # 只数行1窗内两次
    assert ta._count_clicks(2, base) == 1


def test_click_single_toggles(tmp_path):
    _setup(tmp_path, [("a", False)])
    ta.DBL_WINDOW = 0.05                 # 缩短窗加速测试
    ta.click(1, None)                    # 单次点击
    assert co.load_todos()[0]["done"] is True


def test_click_double_does_not_toggle(tmp_path):
    _setup(tmp_path, [("a", False)])
    ta.DBL_WINDOW = 0.15
    # 预置同窗第二次点击(模拟双击的另一次 UP),click 内自己再记一次 → 计数=2 → 跳过 toggle
    ta._log_click(1, time.time())
    ta.click(1, None)
    assert co.load_todos()[0]["done"] is False        # 判为双击,不 toggle(留给编辑)


def test_prune_clicks_drops_old(tmp_path):
    _setup(tmp_path, [("a", False)])
    ta._log_click(1, time.time() - 10)   # 旧
    ta._log_click(1, time.time())        # 新
    co.prune_clicks()                    # 剪枝已下沉数据层(collector);render 与 collect 共用同一份
    with open(co.CLICKS, encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert len(lines) == 1                 # 只留 CLICKS_TTL(5s)内的


def test_collect_prunes_clicks(tmp_path):
    """孤儿剪枝路径补齐:collector 每轮 collect() 顺手剪 .clicks——旧行剪掉、窗内新行保留。
    (orchestrator 周期只跑 collector.py;band.inc 从不触发 todo_action render,不能靠它回收。)"""
    _setup(tmp_path, [("a", False)])
    ta._log_click(1, time.time() - 100)  # 旧点击(远超 CLICKS_TTL)
    ta._log_click(1, time.time())        # 窗内新点击
    co.collect({"skin_name": ""})        # 跑一轮采集(内部顺手 prune_clicks)
    with open(co.CLICKS, encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert len(lines) == 1                 # 只留窗内新行,旧行被剪


# —— add / 行内输入 / del(模块新增覆盖)——

def test_add_item_appends(tmp_path):
    _setup(tmp_path, [("a", False)])
    assert ta.add_item("新任务") is True
    todos = co.load_todos()
    assert len(todos) == 2 and todos[1]["t"] == "新任务" and todos[1]["done"] is False


def test_add_item_empty_rejected(tmp_path):
    _setup(tmp_path, [])
    assert ta.add_item("   ") is False
    assert co.load_todos() == []


def test_add_item_rejects_when_full(tmp_path):
    _setup(tmp_path, [("t%d" % i, False) for i in range(co.MAX_ROWS)])
    assert ta.add_item("溢出") is False               # 满 MAX_ROWS 条 → 拒绝
    assert len(co.load_todos()) == co.MAX_ROWS


def test_do_input_zero_adds(tmp_path):
    _setup(tmp_path, [("a", False)])
    ta.do_input(0, "行内新增", None)                  # row=0 → 新增
    todos = co.load_todos()
    assert len(todos) == 2 and todos[1]["t"] == "行内新增"


def test_do_input_n_edits(tmp_path):
    _setup(tmp_path, [("a", False)])
    ta.do_input(1, "行内改写", None)                  # row=N → 改写
    assert co.load_todos()[0]["t"] == "行内改写"


def test_delete_removes_row(tmp_path):
    _setup(tmp_path, [("a", False), ("b", True), ("c", False)])
    ta.delete(2, None)
    todos = co.load_todos()
    assert [t["t"] for t in todos] == ["a", "c"]


def test_render_inc_writes_utf16_prefixed(tmp_path):
    _setup(tmp_path, [("买菜", False), ("写周报", True)])
    ta.render_inc(co.load_todos())
    with open(ta.INC, encoding="utf-16") as f:
        txt = f.read()
    assert "[Variables]" in txt
    assert "TdRow1Text=买菜" in txt                   # 带 Td 前缀,与 data.inc 同名
    assert "TdRow2Mark=✓" in txt                      # 完成态勾
    assert "TdCount=2" in txt
