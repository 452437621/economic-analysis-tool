param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) { throw "尚未初始化，请先运行 scripts\setup.ps1" }
$env:PYTHONPATH = Join-Path $root "backend"
$env:EPIC_ENV = "test"
Set-Location $root

if (-not $SkipTests) {
  Write-Host "[selfcheck] 运行测试 ..."
  & $venvPy -m pytest -q
  if ($LASTEXITCODE -ne 0) { exit 1 }
}

Write-Host "[selfcheck] 检查 API / 数据 / 验收 ..."
$result = @'
import json
import urllib.request

base = "http://127.0.0.1:8765"
def get(path):
    with urllib.request.urlopen(base + path, timeout=15) as resp:
        return json.load(resp)

health = get("/api/system/health")
acceptance = get("/api/system/acceptance")
quality = get("/api/system/data-quality")
print("status:", health.get("status"))
print("counts:", {k: health["counts"].get(k) for k in ("instruments", "market_bars", "macro", "documents", "claims", "trade_plans", "theses")})
print("acceptance:", acceptance.get("passed"), f"{sum(1 for c in acceptance['checks'] if c['passed'])}/{len(acceptance['checks'])}")
print("quality:", quality.get("summary"))
failed = [c["name"] for c in acceptance["checks"] if not c["passed"]]
if failed:
    print("failed checks:", failed)
ok = health.get("status") == "ok" and acceptance.get("passed") and quality["summary"]["failed"] == 0
raise SystemExit(0 if ok else 1)
'@ | & $venvPy -
if ($LASTEXITCODE -ne 0) {
  Write-Host $result
  Write-Host "[selfcheck] FAILED"
  exit 1
}
Write-Host $result
Write-Host "[selfcheck] PASSED"
