# scripts/doctor.py — 环境体检:检查 Python/平台/Rainmeter/屏幕高度预算/可选依赖/计划任务,
# 把结果打成 JSON 到 stdout 供 agent 读(SKILL.md 初装工作流第一步)。
#
# 输出契约(顶层):
#   {"ok": <bool 必备项全绿>, "checks": {<name>: {ok, detail, hint, required}}, "height_budget": <int>}
# 每项 check:
#   · ok        本项是否通过。
#   · detail    人话说明(给 agent 转述用户)。
#   · hint      未过时的下一步(装什么/怎么修);过了则空串。
#   · required  是否计入顶层 ok(可选依赖/信息项为 false,不因缺失判整体失败)。
# height_budget = 屏幕逻辑工作区高度 − 上下边距,单位逻辑像素,直接喂 assemble.py --budget。
#
# 退出码恒为 0:JSON 的 ok 字段才是判定源(便于机器消费,不因非零码中断上层工具)。
#
# 安全铁律:纯 stdlib(sys/os/json/ctypes/subprocess/importlib/shutil/winreg);无 eval/exec/
# shell=True;不下载任何东西;只读系统信息,不改系统状态(不设 DPI awareness 全局态、不写注册表)。
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys

MIN_PY = (3, 10)
DEFAULT_TASK_NAME = "SanshengDeskdash"

# 高度预算的上下边距(逻辑像素):看板贴桌面时给屏幕上沿/任务栏上方各留一点余量。
TOP_MARGIN = 24
BOTTOM_MARGIN = 24
# 拿不到屏幕分辨率(非 Windows / ctypes 不可用)时的保守兜底预算,供 assemble 仍能给个约束。
FALLBACK_HEIGHT_BUDGET = 900

# 计入顶层 ok 的必备项;其余为可选依赖/信息项(缺失不判整体失败)。
_REQUIRED = ("python", "platform", "rainmeter", "screen")

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# ============================================================
#  可被测试 monkeypatch 的系统探测接缝(build_report 只调这些函数)
# ============================================================

def _which(exe):
    """PATH 里找可执行文件,返回全路径或 None。"""
    return shutil.which(exe)


def _module_present(name):
    """import 得到该顶层模块则 True(不真 import,只查 spec)。"""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _screen_metrics():
    """读主屏逻辑/物理分辨率、DPI 缩放、逻辑工作区(排除任务栏)。仅 Windows 可用。

    返回 {"logical": (w,h), "physical": (w,h), "work_area": (w,h 逻辑), "scale": float, "dpi": int}。
    非 Windows 或 ctypes 失败 → 抛异常(上层退到 FALLBACK 预算)。

    DPI 归一(关键):进程 DPI 感知状态决定 GetSystemMetrics 返回逻辑还是物理像素——
      · 感知(aware):返回物理像素 → 除以 GetDpiForSystem/96 得逻辑;
      · 不感知(unaware,python.org 解释器默认):返回逻辑像素 → 真实缩放取 DESKTOPVERTRES/VERTRES
        (GetDpiForSystem 对 unaware 进程恒返回 96,不能用它判缩放)。
    本函数只读取、绝不调 SetProcessDpiAware*(那会改全进程状态,是副作用)。
    """
    if sys.platform != "win32":
        raise OSError("屏幕分辨率检测仅支持 Windows")
    import ctypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    # 全屏(随进程感知态:unaware=逻辑 / aware=物理)
    sm_w = int(user32.GetSystemMetrics(0))       # SM_CXSCREEN
    sm_h = int(user32.GetSystemMetrics(1))       # SM_CYSCREEN

    # 工作区(排除任务栏,同样随感知态)
    r = _RECT()
    if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):   # SPI_GETWORKAREA
        work_w, work_h = r.right - r.left, r.bottom - r.top
    else:
        work_w, work_h = sm_w, sm_h

    # GetDeviceCaps:VERTRES=进程相对分辨率;DESKTOPVERTRES=真实物理分辨率
    hdc = user32.GetDC(0)
    try:
        vertres = int(gdi32.GetDeviceCaps(hdc, 10))          # VERTRES
        horzres = int(gdi32.GetDeviceCaps(hdc, 8))           # HORZRES
        desk_v = int(gdi32.GetDeviceCaps(hdc, 117))          # DESKTOPVERTRES
        desk_h = int(gdi32.GetDeviceCaps(hdc, 118))          # DESKTOPHORZRES
    finally:
        user32.ReleaseDC(0, hdc)

    aware = _process_dpi_awareness(ctypes)      # 0=unaware / 1=system / 2=permonitor / None=未知

    if aware in (1, 2):
        # 感知进程:GetSystemMetrics 是物理像素,用系统 DPI 换算回逻辑
        dpi = _system_dpi(ctypes) or 96
        scale = dpi / 96.0 or 1.0
        logical = (int(round(sm_w / scale)), int(round(sm_h / scale)))
        work_logical = (int(round(work_w / scale)), int(round(work_h / scale)))
        physical = (desk_h or sm_w, desk_v or sm_h)
    else:
        # 不感知(或未知):GetSystemMetrics 已是逻辑像素;真实缩放= 物理/进程相对分辨率
        scale = (desk_v / vertres) if vertres else 1.0
        logical = (sm_w, sm_h)
        work_logical = (work_w, work_h)
        physical = (desk_h or sm_w, desk_v or sm_h)
        dpi = int(round(scale * 96))

    return {"logical": logical, "physical": physical, "work_area": work_logical,
            "scale": round(scale, 2), "dpi": int(dpi)}


def _process_dpi_awareness(ctypes):
    """当前进程 DPI 感知:0/1/2,拿不到返回 None(老系统 / shcore 缺失)。"""
    try:
        val = ctypes.c_int(-1)
        if ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(val)) == 0:
            return val.value
    except Exception:
        pass
    return None


def _system_dpi(ctypes):
    """系统 DPI(1607+ 的 GetDpiForSystem);拿不到返回 None。"""
    try:
        return int(ctypes.windll.user32.GetDpiForSystem())
    except Exception:
        return None


def _rainmeter_info():
    """探测 Rainmeter.exe:Program Files / Program Files (x86) / 注册表 App Paths。

    返回 {"path": <exe 或 None>, "version": <str 或 None>, "source": <命中来源描述>}。
    """
    candidates = []
    for env in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env)
        if base:
            candidates.append((os.path.join(base, "Rainmeter", "Rainmeter.exe"), env))
    for path, src in candidates:
        if os.path.isfile(path):
            return {"path": path, "version": _file_version(path), "source": src}

    reg_path = _rainmeter_from_registry()
    if reg_path and os.path.isfile(reg_path):
        return {"path": reg_path, "version": _file_version(reg_path), "source": "registry(App Paths)"}
    return {"path": None, "version": None, "source": None}


def _rainmeter_from_registry():
    """注册表 App Paths\\Rainmeter.exe 默认值(64/32 视图各试)。非 Windows/缺失返回 None。"""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    sub = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Rainmeter.exe"
    for view in (getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0)):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0,
                                winreg.KEY_READ | view) as k:
                val, _ = winreg.QueryValueEx(k, None)      # 默认值 = 全路径
                if val:
                    return val
        except OSError:
            continue
    return None


def _file_version(path):
    """读 PE 文件版本(如 4.5.18.3727);读不到返回 None。纯 ctypes(version.dll)。"""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(path, 0, size, buf):
            return None
        lp = ctypes.c_void_p()
        ln = ctypes.c_uint()
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(lp), ctypes.byref(ln)):
            return None

        class _FFI(ctypes.Structure):
            _fields_ = [("dwSignature", ctypes.c_uint32), ("dwStrucVersion", ctypes.c_uint32),
                        ("dwFileVersionMS", ctypes.c_uint32), ("dwFileVersionLS", ctypes.c_uint32),
                        ("dwProductVersionMS", ctypes.c_uint32), ("dwProductVersionLS", ctypes.c_uint32),
                        ("dwFileFlagsMask", ctypes.c_uint32), ("dwFileFlags", ctypes.c_uint32),
                        ("dwFileOS", ctypes.c_uint32), ("dwFileType", ctypes.c_uint32),
                        ("dwFileSubtype", ctypes.c_uint32), ("dwFileDateMS", ctypes.c_uint32),
                        ("dwFileDateLS", ctypes.c_uint32)]

        ffi = ctypes.cast(lp, ctypes.POINTER(_FFI)).contents
        ms, ls = ffi.dwFileVersionMS, ffi.dwFileVersionLS
        return "%d.%d.%d.%d" % ((ms >> 16) & 0xFFFF, ms & 0xFFFF,
                                (ls >> 16) & 0xFFFF, ls & 0xFFFF)
    except Exception:
        return None


def _task_registered(task_name):
    """计划任务是否已注册(schtasks /Query)。非 Windows / 查询失败 → False。"""
    if sys.platform != "win32":
        return False
    try:
        p = subprocess.run(["schtasks", "/Query", "/TN", task_name],
                           capture_output=True, timeout=10,
                           creationflags=_CREATE_NO_WINDOW)
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ============================================================
#  各检查项
# ============================================================

def _check_python():
    ok = sys.version_info >= MIN_PY
    v = "%d.%d.%d" % sys.version_info[:3]
    return {
        "ok": ok, "required": True,
        "detail": "Python %s(要求 ≥ %d.%d)" % (v, MIN_PY[0], MIN_PY[1]),
        "hint": "" if ok else "升级到 Python 3.10 或更高版本(python.org 下载,勾选 Add to PATH)。",
    }


def _check_platform():
    ok = sys.platform == "win32"
    return {
        "ok": ok, "required": True,
        "detail": "平台 %s" % sys.platform,
        "hint": "" if ok else "本 skill 目标是 Windows(原生贴桌面);当前平台不支持皮肤部署与计划任务。",
    }


def _check_rainmeter():
    info = _rainmeter_info()
    if info["path"]:
        ver = (" v%s" % info["version"]) if info["version"] else ""
        return {
            "ok": True, "required": True,
            "detail": "Rainmeter%s 已安装:%s(来源 %s)" % (ver, info["path"], info["source"]),
            "hint": "",
        }
    return {
        "ok": False, "required": True,
        "detail": "未检测到 Rainmeter(Program Files 与注册表都没找到 Rainmeter.exe)。",
        "hint": "安装 Rainmeter:winget install Rainmeter.Rainmeter(或到 rainmeter.net 下载)。",
    }


def _check_screen():
    """返回 (check_dict, height_budget)。"""
    try:
        m = _screen_metrics()
    except Exception as e:
        return ({
            "ok": False, "required": True,
            "detail": "无法读取屏幕分辨率/DPI:%s" % e,
            "hint": "非 Windows 或 ctypes 不可用;height_budget 退回保守默认 %d 逻辑像素。"
                    % FALLBACK_HEIGHT_BUDGET,
        }, FALLBACK_HEIGHT_BUDGET)

    lw, lh = m["logical"]
    pw, ph = m["physical"]
    ww, wh = m["work_area"]
    budget = wh - TOP_MARGIN - BOTTOM_MARGIN
    if budget <= 0:
        budget = wh
    detail = ("逻辑分辨率 %dx%d,DPI 缩放 %d%%(物理 %dx%d);逻辑工作区 %dx%d;"
              "高度预算=%d(工作区高 %d - 上边距 %d - 下边距 %d)"
              % (lw, lh, int(round(m["scale"] * 100)), pw, ph, ww, wh,
                 budget, wh, TOP_MARGIN, BOTTOM_MARGIN))
    return ({"ok": True, "required": True, "detail": detail, "hint": ""}, budget)


def _check_optional_exe(exe, purpose, install_hint):
    path = _which(exe)
    if path:
        return {"ok": True, "required": False,
                "detail": "%s 已安装:%s" % (exe, path), "hint": ""}
    return {"ok": False, "required": False,
            "detail": "%s 未安装(%s)" % (exe, purpose), "hint": install_hint}


def _check_optional_module(mod, pkg, purpose):
    if _module_present(mod):
        return {"ok": True, "required": False,
                "detail": "%s 已安装" % pkg, "hint": ""}
    return {"ok": False, "required": False,
            "detail": "%s 未安装(%s)" % (pkg, purpose),
            "hint": "按需安装:pip install %s" % pkg}


def _check_task(task_name):
    if _task_registered(task_name):
        return {"ok": True, "required": False,
                "detail": "计划任务「%s」已注册" % task_name, "hint": ""}
    return {"ok": False, "required": False,
            "detail": "计划任务「%s」未注册(尚未安装采集调度,或用了别的任务名)" % task_name,
            "hint": "初装完成后跑 scripts/install_task.ps1 注册;若已装请用 --task-name 传实际任务名。"}


def _check_board(board):
    if not board:
        return {"ok": False, "required": False,
                "detail": "未指定板目录(--board),跳过板检查", "hint": ""}
    board = os.path.abspath(board)
    if os.path.isdir(board):
        has_lock = os.path.isfile(os.path.join(board, "modules.lock.json"))
        return {"ok": True, "required": False,
                "detail": "板目录存在:%s(modules.lock.json %s)"
                          % (board, "已生成" if has_lock else "尚未生成,需先 assemble"),
                "hint": "" if has_lock else "跑 scripts/assemble.py 生成 modules.lock.json 与 .ini。"}
    return {"ok": False, "required": False,
            "detail": "板目录不存在:%s" % board,
            "hint": "确认路径,或先创建板目录并放入模块子目录。"}


# ============================================================
#  组装报告
# ============================================================

def build_report(board=None, task_name=DEFAULT_TASK_NAME):
    """跑全部检查,返回 {"ok", "checks", "height_budget"}。"""
    checks = {}
    checks["python"] = _check_python()
    checks["platform"] = _check_platform()
    checks["rainmeter"] = _check_rainmeter()
    screen_check, height_budget = _check_screen()
    checks["screen"] = screen_check
    checks["gh"] = _check_optional_exe(
        "gh", "github 模块用它读私有仓/提高限流;没有则降级匿名 REST",
        "安装 GitHub CLI:winget install GitHub.cli(github 模块可选)。")
    checks["pillow"] = _check_optional_module(
        "PIL", "Pillow", "clock-calendar 模块用 PIL 画日历图")
    checks["tzdata"] = _check_optional_module(
        "tzdata", "tzdata", "仅当 DESKDASH_TZ 用 IANA 时区名(如 Asia/Shanghai)时需要")
    checks["scheduled_task"] = _check_task(task_name)
    checks["board"] = _check_board(board)

    overall = all(checks[k]["ok"] for k in _REQUIRED)
    return {"ok": overall, "checks": checks, "height_budget": height_budget}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="sansheng-deskdash 环境体检:输出 JSON 到 stdout(ok 字段为判定源)。")
    ap.add_argument("--board", default=None, help="板目录(检查是否存在 + 是否已 assemble)")
    ap.add_argument("--task-name", default=DEFAULT_TASK_NAME,
                    help="计划任务名(默认 %s)" % DEFAULT_TASK_NAME)
    args = ap.parse_args(argv)

    report = build_report(board=args.board, task_name=args.task_name)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0        # 退出码恒 0;判定看 JSON 的 ok 字段


if __name__ == "__main__":
    sys.exit(main())
