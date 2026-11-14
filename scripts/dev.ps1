param([int]$Port = 5173)
# 前端开发模式：Vite dev server（/api 代理到 127.0.0.1:8765）。
# 若后端未运行，会先用 scripts\start.ps1 -NoBrowser 拉起。
# 约定：文件以 UTF-8 BOM 保存，兼容 Windows PowerShell 5.1 与 pwsh 7。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"

function Test-Backend {
  try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8765/healthz" -UseBasicParsing -TimeoutSec 3
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

if (-not (Test-Backend)) {
  Write-Host "[dev] 后端未运行，先启动（无浏览器）..." -ForegroundColor Cyan
  & (Join-Path $PSScriptRoot "start.ps1") -NoBrowser | Out-Host
  Start-Sleep -Seconds 2
}

Write-Host ("[dev] Vite dev server -> http://127.0.0.1:{0}" -f $Port) -ForegroundColor Green
Write-Host "[dev] API 代理 -> http://127.0.0.1:8765/api" -ForegroundColor DarkGray
Push-Location $frontend
try {
  & npm.cmd run dev -- --port $Port --strictPort
} finally {
  Pop-Location
}
