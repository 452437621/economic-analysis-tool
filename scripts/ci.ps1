param(
  [switch]$SkipTests,
  [switch]$SkipLint,
  [switch]$SkipRuntime
)
# Single release gate: static lint -> unit/integration tests -> live runtime checks.
# Used locally (selfcheck.ps1) and by CI (.github/workflows/ci.yml).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) { throw "尚未初始化，请先运行 scripts\setup.ps1" }
$env:PYTHONPATH = Join-Path $root "backend"
$env:PYTHONIOENCODING = "utf-8"
$env:EPIC_ENV = "test"
Set-Location $root
$failed = $false

if (-not $SkipLint) {
  Write-Host "[ci] 静态检查 (scripts/lint.py) ..."
  & $venvPy scripts\lint.py
  if ($LASTEXITCODE -ne 0) { $failed = $true }
}

if (-not $SkipTests) {
  Write-Host "[ci] 单元/集成测试 ..."
  & $venvPy -m pytest -q
  if ($LASTEXITCODE -ne 0) { $failed = $true }
}

if (-not $SkipRuntime) {
  Write-Host "[ci] 运行时检查 (health / acceptance / quality) ..."
  $result = @'
import json
import urllib.request

base = "http://127.0.0.1:8765"


def get(path):
    with urllib.request.urlopen(base + path, timeout=15) as resp:
        return json.load(resp)


try:
    health = get("/api/system/health")
    acceptance = get("/api/system/acceptance")
    quality = get("/api/system/data-quality")
except Exception as exc:  # noqa: BLE001
    print("runtime unavailable:", exc)
    raise SystemExit(2)

print("status:", health.get("status"))
print("version:", health.get("version"), "llm:", health.get("llm_enabled"))
print("counts:", {k: health["counts"].get(k) for k in ("instruments", "market_bars", "macro_observations", "documents", "claims", "trade_plans", "theses")})
print("acceptance:", acceptance.get("passed"), f"{sum(1 for c in acceptance['checks'] if c['passed'])}/{len(acceptance['checks'])}")
print("quality:", quality.get("summary"))
failed = [c["name"] for c in acceptance["checks"] if not c["passed"]]
if failed:
    print("failed checks:", failed)
ok = health.get("status") == "ok" and acceptance.get("passed") and quality["summary"]["failed"] == 0
raise SystemExit(0 if ok else 1)
'@ | & $venvPy -
  if ($LASTEXITCODE -eq 2) {
    Write-Host "[ci] 服务未运行，跳过运行时检查（可用 scripts\start.ps1 启动后再跑）"
  } elseif ($LASTEXITCODE -ne 0) {
    Write-Host $result
    $failed = $true
  } else {
    Write-Host $result
  }
}

if ($failed) {
  Write-Host "[ci] FAILED"
  exit 1
}
Write-Host "[ci] PASSED"
