<#
.SYNOPSIS
  卸载桌面看板:反注册计划任务 -> 删 Documents 里的皮肤部署副本 -> 按 -KeepData 决定删/留板内用户数据。

.DESCRIPTION
  破坏性动作,带防误删栏:先列出"将要删除的全部内容",然后:
    · 传了 -Force        → 直接执行;
    · 交互式终端         → 提示确认(输入 y);
    · 非交互且无 -Force  → 拒绝执行(打印清单后退出,避免自动化环境误删)。
  文件/目录删除一律走 .NET API(不走 Remove-Item),规避个别机器 profile 拦截与确认提示。
  应以 `powershell -ExecutionPolicy Bypass -File` 调用,不改系统 ExecutionPolicy、不下载任何东西。

.PARAMETER Board
  板目录(用户数据所在;含各模块子目录、health.json、state\ 等)。

.PARAMETER SkinName
  皮肤名(= Documents\Rainmeter\Skins\<SkinName> 部署副本目录名)。缺省从 modules.lock.json
  的 skin_name 读,再缺省 "Deskdash"。

.PARAMETER TaskName
  要反注册的计划任务名(默认 SanshengDeskdash)。

.PARAMETER KeepData
  保留板内用户数据(config.json / todos.json / state\ / health.json / data.inc 等);只删任务与皮肤副本。

.PARAMETER Force
  跳过确认直接执行(自动化/agent 用)。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -Board C:\boards\my -Force
  powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -Board C:\boards\my -KeepData -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Board,
    [string]$SkinName,
    [string]$TaskName = "SanshengDeskdash",
    [switch]$KeepData,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Resolve-SkinName {
    param([string]$name, [string]$board)
    if ($name) { return $name }
    $lock = Join-Path $board "modules.lock.json"
    if (Test-Path -LiteralPath $lock) {
        try {
            $j = Get-Content -LiteralPath $lock -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($j.skin_name) { return [string]$j.skin_name }
        } catch { }
    }
    return "Deskdash"
}

function Get-DataTargets {
    # 板内"用户数据"路径:板根固定档 + 每个直属子目录(模块目录)的用户档。
    param([string]$board)
    $targets = @()
    foreach ($n in @("health.json", "data.inc", "todos.inc", "config.json")) {
        $p = Join-Path $board $n
        if (Test-Path -LiteralPath $p -PathType Leaf) { $targets += $p }
    }
    foreach ($n in @("state", "logs")) {
        $p = Join-Path $board $n
        if (Test-Path -LiteralPath $p -PathType Container) { $targets += $p }
    }
    # 模块子目录里的用户数据(采集器/交互脚本读写,非模块源文件)
    Get-ChildItem -LiteralPath $board -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        foreach ($n in @("config.json", "todos.json", ".clicks")) {
            $p = Join-Path $_.FullName $n
            if (Test-Path -LiteralPath $p -PathType Leaf) { $targets += $p }
        }
    }
    return $targets
}

function Remove-PathSafe {
    param([string]$path)
    if (-not (Test-Path -LiteralPath $path)) { return }
    if (Test-Path -LiteralPath $path -PathType Container) {
        [System.IO.Directory]::Delete($path, $true)     # 递归删目录
    } else {
        [System.IO.File]::Delete($path)
    }
}

# —— 解析 ——
$Board = [System.IO.Path]::GetFullPath($Board)
$SkinName = Resolve-SkinName -name $SkinName -board $Board
$skinDir = Join-Path (Join-Path $env:USERPROFILE "Documents\Rainmeter\Skins") $SkinName

$taskExists = [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
$skinExists = Test-Path -LiteralPath $skinDir -PathType Container
$dataTargets = if ($KeepData) { @() } else { Get-DataTargets -board $Board }

# —— 列出将删内容(防误删栏)——
Write-Host "== 卸载将执行以下操作 =="
Write-Host ("  [{0}] 反注册计划任务:{1}" -f $(if ($taskExists) { "有" } else { "无/跳过" }), $TaskName)
Write-Host ("  [{0}] 删除皮肤部署副本:{1}" -f $(if ($skinExists) { "有" } else { "无/跳过" }), $skinDir)
if ($KeepData) {
    Write-Host "  [保留] 板内用户数据(-KeepData):$Board"
} elseif ($dataTargets.Count -gt 0) {
    Write-Host "  [删除] 板内用户数据($($dataTargets.Count) 项):"
    $dataTargets | ForEach-Object { Write-Host "         - $_" }
} else {
    Write-Host "  [删除] 板内用户数据:无匹配项"
}
Write-Host ""

# —— 防误删闸 ——
#   交互判定:UserInteractive 在 -NonInteractive 下仍为真,故叠加 stdin 是否被重定向
#   (自动化/管道场景 IsInputRedirected=true)——两者皆真才提示确认,否则拒绝执行防挂死/误删。
if (-not $Force) {
    $interactive = [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
    if ($interactive) {
        $ans = Read-Host "确认执行以上删除?输入 y 继续,其他任意键取消"
        if ($ans -ne "y") { Write-Host "已取消。"; return }
    } else {
        Write-Warning "非交互环境且未传 -Force:仅打印清单,未执行任何删除。加 -Force 以确认执行。"
        return
    }
}

# —— 执行 ——
if ($taskExists) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[OK] 已反注册计划任务:$TaskName"
}
if ($skinExists) {
    Remove-PathSafe -path $skinDir
    Write-Host "[OK] 已删除皮肤部署副本:$skinDir"
}
if (-not $KeepData) {
    foreach ($t in $dataTargets) {
        Remove-PathSafe -path $t
    }
    if ($dataTargets.Count -gt 0) { Write-Host "[OK] 已删除板内用户数据($($dataTargets.Count) 项)" }
} else {
    Write-Host "[OK] 已保留板内用户数据(-KeepData)"
}
Write-Host "卸载完成。"
