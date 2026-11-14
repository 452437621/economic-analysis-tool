# EPIC 一键重启：先停止（若在运行），再后台启动
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\restart.ps1
#   .\scripts\restart.ps1 -NoBrowser
param(
  [switch]$NoBrowser,
  [int]$Port = 0
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_common.ps1")

$paths = Get-EpicPaths
if ($Port -le 0) { $Port = Get-EpicPort }

# stop.ps1 在"服务未运行"时返回 0，可安全调用
& (Join-Path $PSScriptRoot "stop.ps1") -Port $Port | Out-Host

# 等待端口真正释放（避免旧进程尚未退出时 start 误判"端口被占用"）
$deadline = (Get-Date).AddSeconds(15)
while (@(Get-PortListeners -Port $Port).Count -gt 0) {
  if ((Get-Date) -gt $deadline) { throw "端口 $Port 在 15 秒内未释放，重启中止" }
  Start-Sleep -Milliseconds 300
}

$startArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "start.ps1"), "-Port", "$Port")
if ($NoBrowser) { $startArgs += "-NoBrowser" }
& powershell.exe @startArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
