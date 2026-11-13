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

$startArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "start.ps1"), "-Port", "$Port")
if ($NoBrowser) { $startArgs += "-NoBrowser" }
& powershell.exe @startArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
