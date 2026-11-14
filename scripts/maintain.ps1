# EPIC 工作区维护脚本：清理可再生临时产物 + 保留核心数据
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\scripts\maintain.ps1                # 默认 DryRun，只列清单不删除
#   powershell -ExecutionPolicy Bypass -File .\scripts\maintain.ps1 -DryRun        # 显式 DryRun
#   powershell -ExecutionPolicy Bypass -File .\scripts\maintain.ps1 -Apply         # 执行安全清理
#   powershell -ExecutionPolicy Bypass -File .\scripts\maintain.ps1 -Apply -IncludeRaw   # 额外清理 30 天前原始快照
#   powershell -ExecutionPolicy Bypass -File .\scripts\maintain.ps1 -Verify        # 清理后复查
#
# 安全边界（默认永不删除）：
#   data\epic.db*、data\backup\、data\raw\（除非 -IncludeRaw）、data\logs\、config\、代码与文档
#
# 约定：文件以 UTF-8 BOM 保存，兼容 Windows PowerShell 5.1 与 pwsh 7。

param(
  [switch]$DryRun,
  [switch]$Apply,
  [switch]$Verify,
  [switch]$IncludeRaw,
  [switch]$IncludeLogs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
. (Join-Path $PSScriptRoot "_common.ps1")

if ($DryRun -and $Apply) { throw "参数冲突：-DryRun 与 -Apply 只能二选一" }
if (-not $Apply -and -not $Verify) { $DryRun = $true }
$rawDays = 30
$logDays = 7
$freeBytes = 0
$freeFiles = 0
$failures = New-Object System.Collections.ArrayList

function Format-Size {
  param([double]$Bytes)
  if ($Bytes -ge 1GB) { return ("{0:N2} GB" -f ($Bytes / 1GB)) }
  if ($Bytes -ge 1MB) { return ("{0:N1} MB" -f ($Bytes / 1MB)) }
  if ($Bytes -ge 1KB) { return ("{0:N0} KB" -f ($Bytes / 1KB)) }
  return ("{0:N0} B" -f $Bytes)
}

function Get-Stats {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    return [pscustomobject]@{ Files = 0; Bytes = [int64]0 }
  }
  $items = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue)
  $sum = [int64]0
  foreach ($item in $items) { $sum += $item.Length }
  return [pscustomobject]@{ Files = $items.Count; Bytes = $sum }
}

function Add-Target {
  param(
    [string]$Category,
    [string]$Path,
    [string]$Action,
    [bool]$Delete
  )
  $full = Join-Path $root $Path
  if (-not (Test-Path -LiteralPath $full)) { return }
  $stats = Get-Stats -Path $full
  if ($stats.Files -eq 0 -and $stats.Bytes -eq 0) { return }
  $script:row = [pscustomobject]@{
    Category = $Category
    Path     = $Path
    Files    = $stats.Files
    Size     = Format-Size $stats.Bytes
    Bytes    = $stats.Bytes
    Action   = $Action
  }
  $script:plan += $script:row
}

# ---------- 收集清理目标 ----------
$script:plan = New-Object System.Collections.ArrayList

$chromeDirs = @(Get-ChildItem -LiteralPath (Join-Path $root "data") -Directory -Filter "chrome-*" -Force -ErrorAction SilentlyContinue)
foreach ($dir in $chromeDirs) {
  Add-Target -Category "截图浏览器配置" -Path ("data\" + $dir.Name) -Action "删除（可重建）" -Delete $true
}

$pngs = @(Get-ChildItem -LiteralPath (Join-Path $root "data") -File -Filter "*.png" -Force -ErrorAction SilentlyContinue)
foreach ($png in $pngs) {
  Add-Target -Category "临时调试截图" -Path ("data\" + $png.Name) -Action "删除（docs/assets 有成品）" -Delete $true
}

Add-Target -Category "pytest 临时目录" -Path "data\test" -Action "删除（测试再生）" -Delete $true
Add-Target -Category "调试残留" -Path "data\scratch" -Action "删除" -Delete $true

$pidFile = Join-Path $root "data\run\epic.pid"
if (Test-Path -LiteralPath $pidFile) {
  $port = Get-EpicPort
  $listeners = @(Get-PortListeners -Port $port)
  if ($listeners.Count -eq 0) {
    Add-Target -Category "过期 PID 文件" -Path "data\run\epic.pid" -Action "删除（端口未监听）" -Delete $true
  } else {
    Write-Host ("[skip] data\run\epic.pid：端口 {0} 仍有服务在监听，保留" -f $port) -ForegroundColor DarkYellow
  }
}

$pycacheRoots = @("backend", "tests", "scripts")
$pycacheDirs = @()
foreach ($base in $pycacheRoots) {
  $basePath = Join-Path $root $base
  if (Test-Path -LiteralPath $basePath) {
    $pycacheDirs += @(Get-ChildItem -LiteralPath $basePath -Recurse -Directory -Filter "__pycache__" -Force -ErrorAction SilentlyContinue)
  }
}
foreach ($dir in $pycacheDirs) {
  Add-Target -Category "Python 缓存" -Path $dir.FullName.Substring($root.Length + 1) -Action "删除" -Delete $true
}

if ($IncludeRaw) {
  $rawRoot = Join-Path $root "data\raw"
  if (Test-Path -LiteralPath $rawRoot) {
    $cutoff = (Get-Date).Date.AddDays(-$rawDays)
    foreach ($source in @(Get-ChildItem -LiteralPath $rawRoot -Directory -Force -ErrorAction SilentlyContinue)) {
      foreach ($dayDir in @(Get-ChildItem -LiteralPath $source.FullName -Directory -Force -ErrorAction SilentlyContinue)) {
        $parsed = [datetime]::MinValue
        if ([datetime]::TryParseExact($dayDir.Name, "yyyyMMdd", $null, [System.Globalization.DateTimeStyles]::None, [ref]$parsed)) {
          if ($parsed -lt $cutoff) {
            Add-Target -Category "原始快照（超期）" -Path ("data\raw\" + $source.Name + "\" + $dayDir.Name) -Action ("删除（早于 " + $rawDays + " 天）") -Delete $true
          }
        }
      }
    }
  }
}

if ($IncludeLogs) {
  $logDir = Join-Path $root "data\logs"
  if (Test-Path -LiteralPath $logDir) {
    $cutoff = (Get-Date).AddDays(-$logDays)
    foreach ($log in @(Get-ChildItem -LiteralPath $logDir -File -Filter "*.log" -Force -ErrorAction SilentlyContinue)) {
      if ($log.LastWriteTime -lt $cutoff) {
        Add-Target -Category "过期日志" -Path ("data\logs\" + $log.Name) -Action ("删除（早于 " + $logDays + " 天）") -Delete $true
      }
    }
  }
}

# ---------- 输出清单 ----------
$totalBytes = [int64]0
$totalFiles = 0
foreach ($row in $script:plan) { $totalBytes += $row.Bytes; $totalFiles += $row.Files }

if ($script:plan.Count -gt 0) {
  $script:plan | Sort-Object Bytes -Descending |
    Format-Table -AutoSize Category, Path, Files, Size, Action
}

$mode = "DryRun"
if ($Apply) { $mode = "Apply" }
if ($Verify) { $mode = "Verify" }
Write-Host ""
Write-Host ("模式：{0}    待清理：{1} 项 / {2} 个文件 / {3}" -f $mode, $script:plan.Count, $totalFiles, (Format-Size $totalBytes)) -ForegroundColor Cyan

if ($Verify) {
  $dataStats = Get-Stats -Path (Join-Path $root "data")
  Write-Host ("data\ 当前体积：{0} / {1} 个文件" -f (Format-Size $dataStats.Bytes), $dataStats.Files) -ForegroundColor Green
  $leftChrome = @(Get-ChildItem -LiteralPath (Join-Path $root "data") -Directory -Filter "chrome-*" -Force -ErrorAction SilentlyContinue).Count
  $leftPng = @(Get-ChildItem -LiteralPath (Join-Path $root "data") -File -Filter "*.png" -Force -ErrorAction SilentlyContinue).Count
  Write-Host ("残留 chrome-* 目录：{0}    data\*.png：{1}" -f $leftChrome, $leftPng)
  foreach ($keep in @("data\epic.db", "data\backup", "data\raw", "data\logs")) {
    $ok = Test-Path -LiteralPath (Join-Path $root $keep)
    Write-Host ("保留检查 {0}：{1}" -f $keep, $(if ($ok) { "存在" } else { "缺失！" }))
  }
  Write-Host "提醒：data\raw 保留策略需 -Apply -IncludeRaw 才会执行；默认不动原始快照。" -ForegroundColor DarkYellow
  exit 0
}

if ($DryRun) {
  Write-Host "DryRun 未删除任何文件。确认后执行：powershell -ExecutionPolicy Bypass -File .\scripts\maintain.ps1 -Apply" -ForegroundColor Yellow
  exit 0
}

# ---------- 执行删除 ----------
foreach ($row in ($script:plan | Sort-Object Bytes -Descending)) {
  $full = Join-Path $root $row.Path
  try {
    if (Test-Path -LiteralPath $full) {
      Remove-Item -LiteralPath $full -Recurse -Force
      $freeBytes += $row.Bytes
      $freeFiles += $row.Files
      Write-Host ("[ok] {0}  {1}  {2}" -f $row.Path, $row.Size, $row.Action)
    }
  } catch {
    $failures += ("{0}: {1}" -f $row.Path, $_.Exception.Message) | Out-Null
    Write-Host ("[fail] {0}: {1}" -f $row.Path, $_.Exception.Message) -ForegroundColor Red
  }
}

Write-Host ""
Write-Host ("完成：释放 {0} / {1} 个文件" -f (Format-Size $freeBytes), $freeFiles) -ForegroundColor Green
if ($failures.Count -gt 0) {
  Write-Host ("有 {0} 项删除失败，见上方 [fail] 行。" -f $failures.Count) -ForegroundColor Red
  exit 1
}
Write-Host "建议随后运行：scripts\start.ps1 -NoBrowser，确认 /healthz 与看板正常。" -ForegroundColor Yellow
exit 0
