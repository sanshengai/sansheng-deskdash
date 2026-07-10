<#
.SYNOPSIS
  注册「桌面看板采集调度」计划任务(幂等):登录后延迟 5 分钟触发一次 + 之后每 2 小时触发。
  动作 = python <repo>\scripts\orchestrator.py --board <Board>。

.DESCRIPTION
  · 幂等:Register-ScheduledTask -Force 覆盖同名任务,重复运行不堆叠;末尾核验实际已注册。
  · 登录触发加 5 分钟延迟——开机时网络/时区可能未就绪,orchestrator 本有 stale 沿用容错,
    延迟只为把首轮尽量落在网络可用后(设计稿 §6 Windows 真实阻断)。
  · 优先 pythonw.exe(无控制台黑窗后台跑更干净),没有则退 python.exe。
  · 应以 `powershell -ExecutionPolicy Bypass -File` 调用,不改系统 ExecutionPolicy、不下载任何东西。

.PARAMETER Board
  传给 orchestrator 的板目录(其下 modules.lock.json + 各模块子目录)。

.PARAMETER TaskName
  计划任务名(默认 SanshengDeskdash)。

.PARAMETER Python
  python/pythonw 可执行文件路径。缺省自动探测 pythonw.exe -> python.exe。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1 -Board C:\boards\my
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Board,
    [string]$TaskName = "SanshengDeskdash",
    [string]$Python
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    param([string]$explicit)
    if ($explicit) {
        if (Test-Path -LiteralPath $explicit) { return $explicit }
        throw "指定的 Python 不存在:$explicit"
    }
    foreach ($exe in @("pythonw.exe", "python.exe")) {
        $c = Get-Command $exe -ErrorAction SilentlyContinue
        if ($c) { return $c.Source }
    }
    throw "未找到 pythonw/python,请先安装 Python 3.10+ 并加入 PATH。"
}

# —— 解析路径 ——
$Board = [System.IO.Path]::GetFullPath($Board)
if (-not (Test-Path -LiteralPath $Board -PathType Container)) {
    throw "板目录不存在:$Board"
}
$orchestrator = Join-Path $PSScriptRoot "orchestrator.py"
if (-not (Test-Path -LiteralPath $orchestrator -PathType Leaf)) {
    throw "找不到 orchestrator.py:$orchestrator(本脚本须放在 repo\scripts\ 下)"
}
$py = Resolve-Python -explicit $Python

# —— 动作:python orchestrator.py --board <Board> ——
#   注:计划动作直接跑 python(非 powershell),故此处与 ExecutionPolicy 无关;
#   工作目录设为 scripts\,让 orchestrator 的 `from lib.xxx import` 稳妥。
$argline = ('"{0}" --board "{1}"' -f $orchestrator, $Board)
$action = New-ScheduledTaskAction -Execute $py -Argument $argline -WorkingDirectory $PSScriptRoot

# —— 触发器 ①:登录后延迟 5 分钟 ——
$t1 = New-ScheduledTaskTrigger -AtLogOn
$t1.Delay = "PT5M"    # ISO8601;登录触发器只支持固定 Delay

# —— 触发器 ②:每 2 小时 ——
#   用"每天此刻起、每 2 小时重复、持续 1 天"表达持续的每 2 小时(PS5.1 兼容写法,
#   避免 RepetitionDuration 无限值的坑;每日滚动即覆盖全天)。
$t2 = New-ScheduledTaskTrigger -Daily -At (Get-Date)
$rep = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Hours 2) `
        -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
$t2.Repetition = $rep

# —— 设置:错过则可用时补跑(网络未就绪容错);单轮上限 10 分钟防挂死 ——
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger @($t1, $t2) -Settings $settings `
    -Description "sansheng-deskdash 采集调度:登录后5分钟 + 每2小时跑 orchestrator 写 data.inc" `
    -Force | Out-Null

# —— 核验(注册若走非终止错误也不静默) ——
if (-not (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    throw "计划任务注册失败(未查到「$TaskName」),请检查上方报错。"
}

Write-Host "[OK] 计划任务已注册:$TaskName"
Write-Host "     触发   : 登录后延迟5分钟 + 每2小时"
Write-Host "     动作   : $py $argline"
Write-Host "     工作目录: $PSScriptRoot"
Write-Host "-> 立即手动跑一次:Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "-> 卸载:powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -Board `"$Board`" -Force"
