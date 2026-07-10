# tests/test_ps1_syntax.py — 三个部署 ps1 的语法冒烟测试。
#
# 用 PSParser::Tokenize 做解析级校验(不执行脚本,零副作用:不注册计划任务、不碰 Documents)。
# 本机无 powershell/pwsh 则整体 skip(非 Windows CI 上不阻塞)。
import os
import shutil
import subprocess

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
_PS1_FILES = ["deploy_skin.ps1", "install_task.ps1", "uninstall.ps1"]

# 优先 Windows PowerShell(部署脚本的主要运行时,对 UTF-8 BOM 敏感,最能暴露编码问题),
# 没有再退 pwsh 7。两者都没有 → skip。
_PS = shutil.which("powershell") or shutil.which("pwsh")

# Tokenize 源文本,把解析错误写 stderr 并以退出码 1 报告;无错退出 0。
_TOKENIZE = (
    "$ErrorActionPreference='Stop';"
    "$p=$env:PS1_TARGET;"
    "$errs=$null;"
    "$null=[System.Management.Automation.PSParser]::Tokenize("
    "(Get-Content -Raw -LiteralPath $p),[ref]$errs);"
    "if($errs -and $errs.Count -gt 0){"
    "$errs|ForEach-Object{[Console]::Error.WriteLine("
    "('L{0}: {1}' -f $_.Token.StartLine,$_.Message))};exit 1}"
    "exit 0"
)


@pytest.mark.skipif(_PS is None, reason="本机无 powershell/pwsh,跳过 ps1 语法校验")
@pytest.mark.parametrize("name", _PS1_FILES)
def test_ps1_parses_clean(name):
    path = os.path.join(_SCRIPTS, name)
    assert os.path.isfile(path), "缺少部署脚本:%s" % path
    env = dict(os.environ)
    env["PS1_TARGET"] = path
    proc = subprocess.run(
        [_PS, "-NoProfile", "-NonInteractive", "-Command", _TOKENIZE],
        capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, (
        "%s 解析出错:\n%s\n%s" % (name, proc.stdout, proc.stderr))


@pytest.mark.skipif(_PS is None, reason="本机无 powershell/pwsh,跳过 ps1 语法校验")
@pytest.mark.parametrize("name", _PS1_FILES)
def test_ps1_has_utf8_bom(name):
    """含中文的 .ps1 必须带 UTF-8 BOM,否则 Windows PowerShell 5.1 按 ANSII/GBK 误解码致乱码崩溃。"""
    path = os.path.join(_SCRIPTS, name)
    with open(path, "rb") as f:
        head = f.read(3)
    assert head == b"\xef\xbb\xbf", "%s 应以 UTF-8 BOM(EF BB BF)开头,实际 %r" % (name, head)
