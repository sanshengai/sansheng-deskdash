<#
.SYNOPSIS
  把 assemble.py 产出的皮肤 .ini(UTF-8)部署到 Documents\Rainmeter\Skins,转成 Rainmeter
  要求的 UTF-16 LE + BOM,部署前轮换 5 份备份,最后 !RefreshApp 刷新看板。

.DESCRIPTION
  · 不改系统 ExecutionPolicy、不下载任何东西(应以 `powershell -ExecutionPolicy Bypass -File` 调用)。
  · 源 .ini(仓内一律 UTF-8)读进来后以 UTF-16 LE+BOM 写出——Rainmeter 读中文变量需 UTF-16。
  · 备份轮换 .bak1...bak5:部署前把现有目标文件推入 .bak1,旧档依次后移,支持"恢复昨天的看板"。
  · 全程用 .NET 文件 API(不走 Remove-Item/Move-Item),规避个别机器的 profile 拦截与确认提示。

.PARAMETER Board
  板目录:含 assemble 产出的 <SkinName>.ini(UTF-8 源)与 modules.lock.json。

.PARAMETER SkinName
  皮肤名(= 部署目录名 = 部署文件名)。缺省从 modules.lock.json 的 skin_name 读,再缺省用 "Deskdash"。

.PARAMETER SourceIni
  源 .ini 路径。缺省 <Board>\<SkinName>.ini。

.PARAMETER RainmeterExe
  Rainmeter.exe 路径。缺省自动探测(Program Files / Program Files (x86) / 注册表 App Paths)。

.PARAMETER BackupCount
  保留的备份份数(默认 5)。

.PARAMETER NoRefresh
  只部署不刷新(找不到 Rainmeter 或干跑校验时用)。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\deploy_skin.ps1 -Board C:\boards\my -SkinName Deskdash
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Board,
    [string]$SkinName,
    [string]$SourceIni,
    [string]$RainmeterExe,
    [int]$BackupCount = 5,
    [switch]$NoRefresh
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
        } catch { }   # lock 坏了不致命,退到默认名
    }
    return "Deskdash"
}

function Find-RainmeterExe {
    param([string]$explicit)
    if ($explicit) {
        if (Test-Path -LiteralPath $explicit) { return $explicit }
        throw "指定的 Rainmeter.exe 不存在:$explicit"
    }
    foreach ($env in @($env:ProgramW6432, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($env) {
            $p = Join-Path $env "Rainmeter\Rainmeter.exe"
            if (Test-Path -LiteralPath $p) { return $p }
        }
    }
    # 注册表 App Paths(64/32 视图)
    $keys = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Rainmeter.exe",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Rainmeter.exe"
    )
    foreach ($k in $keys) {
        try {
            $v = (Get-ItemProperty -LiteralPath $k -ErrorAction Stop).'(default)'
            if ($v -and (Test-Path -LiteralPath $v)) { return $v }
        } catch { }
    }
    return $null
}

function Invoke-BackupRotation {
    param([string]$file, [int]$count)
    if (-not (Test-Path -LiteralPath $file)) { return }   # 首次部署无旧档可备
    # 删最旧一份,再自高到低整体后移一格,最后把当前档推入 .bak1
    $oldest = "$file.bak$count"
    if (Test-Path -LiteralPath $oldest) { [System.IO.File]::Delete($oldest) }
    for ($i = $count - 1; $i -ge 1; $i--) {
        $src = "$file.bak$i"
        $dst = "$file.bak$($i + 1)"
        if (Test-Path -LiteralPath $src) {
            if (Test-Path -LiteralPath $dst) { [System.IO.File]::Delete($dst) }
            [System.IO.File]::Move($src, $dst)
        }
    }
    if (Test-Path -LiteralPath "$file.bak1") { [System.IO.File]::Delete("$file.bak1") }
    [System.IO.File]::Move($file, "$file.bak1")
}

# —— 解析路径 ——
$Board = [System.IO.Path]::GetFullPath($Board)
if (-not (Test-Path -LiteralPath $Board -PathType Container)) {
    throw "板目录不存在:$Board"
}
$SkinName = Resolve-SkinName -name $SkinName -board $Board
if (-not $SourceIni) { $SourceIni = Join-Path $Board "$SkinName.ini" }
if (-not (Test-Path -LiteralPath $SourceIni -PathType Leaf)) {
    throw "源 .ini 不存在:$SourceIni`n先跑:python scripts\assemble.py --board `"$Board`" --out `"$SourceIni`""
}

$skinsRoot = Join-Path $env:USERPROFILE "Documents\Rainmeter\Skins"
$targetDir = Join-Path $skinsRoot $SkinName
$targetIni = Join-Path $targetDir "$SkinName.ini"
[void][System.IO.Directory]::CreateDirectory($targetDir)   # 幂等建目录,无提示

# —— 备份轮换 ——
Invoke-BackupRotation -file $targetIni -count $BackupCount

# —— UTF-8 源 → UTF-16 LE+BOM 部署副本 ——
$utf16 = New-Object System.Text.UnicodeEncoding($false, $true)   # LE + BOM
[System.IO.File]::WriteAllText($targetIni,
    [System.IO.File]::ReadAllText($SourceIni, [System.Text.Encoding]::UTF8), $utf16)

Write-Host "[OK] 已部署皮肤:$targetIni"
Write-Host "     皮肤名 : $SkinName"
Write-Host "     源文件 : $SourceIni (UTF-8) -> 部署副本 UTF-16 LE+BOM"
Write-Host "     备份   : 轮换保留最近 $BackupCount 份($targetIni.bak1 .. .bak$BackupCount)"

# —— 刷新 ——
if ($NoRefresh) {
    Write-Host "     刷新   : 已跳过(-NoRefresh);手动刷新可右键皮肤 -> Refresh。"
    return
}
$rm = Find-RainmeterExe -explicit $RainmeterExe
if (-not $rm) {
    Write-Warning ("未找到 Rainmeter.exe,已完成文件部署但无法自动刷新。`n" +
        "  安装:winget install Rainmeter.Rainmeter;或用 -RainmeterExe 指定路径;`n" +
        "  也可手动打开 Rainmeter 管理器右键该皮肤 -> Refresh。")
    return
}
& $rm "!RefreshApp"
Write-Host "     刷新   : 已调 Rainmeter !RefreshApp($rm)"
