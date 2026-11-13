param()
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) { throw "尚未初始化，请先运行 scripts\setup.ps1" }
$env:PYTHONPATH = Join-Path $root "backend"
Push-Location (Join-Path $root "backend")
try { & $venvPy -m app.backup } finally { Pop-Location }
