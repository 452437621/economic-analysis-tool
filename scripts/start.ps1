param([switch]$Reload)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
  throw "尚未初始化，请先运行 scripts\setup.ps1"
}
$env:PYTHONPATH = Join-Path $root "backend"
$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765")
if ($Reload) { $uvicornArgs += "--reload" }
Write-Host "[start] EPIC -> http://127.0.0.1:8765  (Ctrl+C 停止)"
Set-Location (Join-Path $root "backend")
& $venvPy @uvicornArgs
