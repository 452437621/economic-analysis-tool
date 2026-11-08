param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) { throw "尚未初始化，请先运行 scripts\setup.ps1" }
$env:PYTHONPATH = Join-Path $root "backend"
$env:EPIC_ENV = "test"
Set-Location $root

if (-not $SkipTests) {
  Write-Host "[acceptance] 运行测试 ..."
  & $venvPy -m pytest -q
  if ($LASTEXITCODE -ne 0) { exit 1 }
}

Write-Host "[acceptance] 检查 DoD ..."
$result = @'
import json
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    payload = client.get("/api/system/acceptance").json()
print(json.dumps(payload, ensure_ascii=False))
raise SystemExit(0 if payload.get("passed") else 1)
'@ | & $venvPy -
if ($LASTEXITCODE -ne 0) {
  Write-Host $result
  Write-Host "[acceptance] FAILED"
  exit 1
}
Write-Host $result
Write-Host "[acceptance] PASSED"
