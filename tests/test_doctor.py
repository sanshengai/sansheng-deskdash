# tests/test_doctor.py — doctor.py 单测:mock 掉系统探测接缝,验 JSON 结构、缺 Rainmeter
# 判定、height_budget 计算、屏幕失败兜底、可选依赖不拖垮整体 ok。
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "scripts"))
import doctor  # noqa: E402


# —— 通用:让必备项(除被测项外)恒绿,方便单独验某一项 ——

def _all_green(monkeypatch):
    monkeypatch.setattr(doctor.sys, "platform", "win32", raising=False)
    monkeypatch.setattr(doctor, "_rainmeter_info",
                        lambda: {"path": r"C:\PF\Rainmeter\Rainmeter.exe",
                                 "version": "4.5.0.0", "source": "ProgramFiles"})
    monkeypatch.setattr(doctor, "_screen_metrics",
                        lambda: {"logical": (1707, 1067), "physical": (2560, 1600),
                                 "work_area": (1707, 1027), "scale": 1.5, "dpi": 144})
    monkeypatch.setattr(doctor, "_task_registered", lambda name: False)
    monkeypatch.setattr(doctor, "_which", lambda exe: None)
    monkeypatch.setattr(doctor, "_module_present", lambda mod: False)


# —— 顶层结构 ——

def test_report_shape(monkeypatch):
    _all_green(monkeypatch)
    rep = doctor.build_report(board=None)
    assert set(rep) == {"ok", "checks", "height_budget"}
    assert isinstance(rep["ok"], bool)
    assert isinstance(rep["height_budget"], int)
    # 必备 + 可选各项都在
    for name in ("python", "platform", "rainmeter", "screen",
                 "gh", "pillow", "tzdata", "scheduled_task", "board"):
        assert name in rep["checks"], name
        c = rep["checks"][name]
        assert set(("ok", "detail", "hint", "required")) <= set(c)
        assert isinstance(c["ok"], bool)
        assert isinstance(c["detail"], str)
        assert isinstance(c["hint"], str)


def test_overall_ok_when_required_green(monkeypatch):
    _all_green(monkeypatch)
    rep = doctor.build_report(board=None)
    # 可选依赖(gh/pillow/tzdata/task)全缺,整体仍应 ok=true(只看必备四项)
    assert rep["ok"] is True
    assert rep["checks"]["gh"]["ok"] is False
    assert rep["checks"]["pillow"]["ok"] is False
    assert rep["checks"]["scheduled_task"]["ok"] is False


# —— Rainmeter 缺失 ——

def test_missing_rainmeter_fails_and_hints_winget(monkeypatch):
    _all_green(monkeypatch)
    monkeypatch.setattr(doctor, "_rainmeter_info",
                        lambda: {"path": None, "version": None, "source": None})
    rep = doctor.build_report(board=None)
    rm = rep["checks"]["rainmeter"]
    assert rm["ok"] is False
    assert "winget" in rm["hint"]
    assert rm["path"] is None         # 缺失时独立 path 字段为 None
    assert rep["ok"] is False        # 必备项失败 → 整体失败


def test_rainmeter_exposes_independent_path(monkeypatch):
    """rainmeter 检查项带独立 path 字段(= exe 全路径),上层不必从中文 detail 截路径。"""
    _all_green(monkeypatch)
    exe = r"C:\PF\Rainmeter\Rainmeter.exe"
    monkeypatch.setattr(doctor, "_rainmeter_info",
                        lambda: {"path": exe, "version": "4.5.0.0", "source": "ProgramFiles"})
    rep = doctor.build_report(board=None)
    rm = rep["checks"]["rainmeter"]
    assert rm["ok"] is True
    assert rm["path"] == exe          # 独立字段直接可用,不依赖解析 detail


# —— height_budget 计算 ——

def test_height_budget_computed_from_work_area(monkeypatch):
    _all_green(monkeypatch)
    monkeypatch.setattr(doctor, "_screen_metrics",
                        lambda: {"logical": (1920, 1080), "physical": (1920, 1080),
                                 "work_area": (1920, 1040), "scale": 1.0, "dpi": 96})
    rep = doctor.build_report(board=None)
    expected = 1040 - doctor.TOP_MARGIN - doctor.BOTTOM_MARGIN
    assert rep["height_budget"] == expected
    assert rep["checks"]["screen"]["ok"] is True
    assert str(expected) in rep["checks"]["screen"]["detail"]


def test_screen_failure_falls_back(monkeypatch):
    _all_green(monkeypatch)

    def _boom():
        raise OSError("no ctypes")

    monkeypatch.setattr(doctor, "_screen_metrics", _boom)
    rep = doctor.build_report(board=None)
    assert rep["checks"]["screen"]["ok"] is False
    assert rep["height_budget"] == doctor.FALLBACK_HEIGHT_BUDGET
    assert rep["ok"] is False        # screen 是必备项


# —— python / platform 必备项 ——

def test_python_check_passes_on_current(monkeypatch):
    _all_green(monkeypatch)
    rep = doctor.build_report(board=None)
    assert rep["checks"]["python"]["ok"] is True    # 跑测试的解释器 ≥ 3.10


def test_non_windows_platform_fails(monkeypatch):
    _all_green(monkeypatch)
    monkeypatch.setattr(doctor.sys, "platform", "linux", raising=False)
    rep = doctor.build_report(board=None)
    assert rep["checks"]["platform"]["ok"] is False
    assert rep["ok"] is False


# —— 可选依赖存在时标 ok ——

def test_optional_present(monkeypatch):
    _all_green(monkeypatch)
    monkeypatch.setattr(doctor, "_which", lambda exe: r"C:\PF\gh\gh.exe")
    monkeypatch.setattr(doctor, "_module_present", lambda mod: True)
    monkeypatch.setattr(doctor, "_task_registered", lambda name: True)
    rep = doctor.build_report(board=None, task_name="SomeTask")
    assert rep["checks"]["gh"]["ok"] is True
    assert rep["checks"]["pillow"]["ok"] is True
    assert rep["checks"]["tzdata"]["ok"] is True
    assert rep["checks"]["scheduled_task"]["ok"] is True
    assert "SomeTask" in rep["checks"]["scheduled_task"]["detail"]


# —— 任务名从 lock 读(多板时别去查默认名报假阴性)——

def _lock(tmp_path, **kv):
    b = tmp_path / "brd"
    b.mkdir(exist_ok=True)
    (b / "modules.lock.json").write_text(json.dumps(kv), encoding="utf-8")
    return str(b)


def test_task_name_read_from_lock(monkeypatch, tmp_path):
    """doctor 缺省应查 lock 里的 task_name,而非硬编默认名 ——
    否则多板时会对着「SanshengDeskdash」报「未注册」,而真任务叫别的名字。"""
    _all_green(monkeypatch)
    seen = []
    monkeypatch.setattr(doctor, "_task_registered", lambda name: seen.append(name) or True)
    board = _lock(tmp_path, task_name="SanshengDeskdash-MyBoard", skin_name="MyBoard")
    rep = doctor.build_report(board=board)
    assert seen == ["SanshengDeskdash-MyBoard"]
    assert "SanshengDeskdash-MyBoard" in rep["checks"]["scheduled_task"]["detail"]


def test_explicit_task_name_beats_lock(monkeypatch, tmp_path):
    _all_green(monkeypatch)
    seen = []
    monkeypatch.setattr(doctor, "_task_registered", lambda name: seen.append(name) or True)
    board = _lock(tmp_path, task_name="FromLock")
    doctor.build_report(board=board, task_name="Explicit")
    assert seen == ["Explicit"]


def test_task_name_falls_back_when_lock_missing_or_broken(monkeypatch, tmp_path):
    """lock 缺失 / 坏 JSON / 无 task_name 字段 → 退默认名,不抛异常(体检器不能自己崩)。"""
    _all_green(monkeypatch)
    assert doctor.task_name_from_lock(None) is None
    assert doctor.task_name_from_lock(str(tmp_path / "nope")) is None
    b = tmp_path / "broken"
    b.mkdir()
    (b / "modules.lock.json").write_text("{ not json", encoding="utf-8")
    assert doctor.task_name_from_lock(str(b)) is None
    assert doctor.task_name_from_lock(_lock(tmp_path, skin_name="X")) is None   # 无 task_name 字段
    seen = []
    monkeypatch.setattr(doctor, "_task_registered", lambda name: seen.append(name) or True)
    doctor.build_report(board=str(b))
    assert seen == [doctor.DEFAULT_TASK_NAME]


# —— board 检查 ——

def test_board_check(monkeypatch, tmp_path):
    _all_green(monkeypatch)
    # 不存在
    rep = doctor.build_report(board=str(tmp_path / "nope"))
    assert rep["checks"]["board"]["ok"] is False
    # 存在但无 lock
    board = tmp_path / "b"
    board.mkdir()
    rep = doctor.build_report(board=str(board))
    assert rep["checks"]["board"]["ok"] is True
    assert "尚未生成" in rep["checks"]["board"]["detail"]
    # 存在且有 lock
    (board / "modules.lock.json").write_text("{}", encoding="utf-8")
    rep = doctor.build_report(board=str(board))
    assert rep["checks"]["board"]["ok"] is True
    assert "已生成" in rep["checks"]["board"]["detail"]


# —— main 打印合法 JSON ——

def test_main_prints_valid_json(monkeypatch, capsys):
    import json
    _all_green(monkeypatch)
    rc = doctor.main(["--board", "."])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "ok" in parsed and "checks" in parsed and "height_budget" in parsed


# —— 真机烟测:win32 上 _screen_metrics 应能给出合理结构(非 win 跳过)——

@pytest.mark.skipif(sys.platform != "win32", reason="屏幕分辨率检测仅 Windows")
def test_screen_metrics_live_shape():
    m = doctor._screen_metrics()
    assert set(("logical", "physical", "work_area", "scale", "dpi")) <= set(m)
    assert m["work_area"][1] > 0
    assert m["scale"] >= 1.0
