# EPIC selfcheck wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [switch]$SkipBuild,
  [switch]$SkipLint,
  [switch]$SkipTests,
  [switch]$SkipFrontendTests,
  [switch]$SkipRuntime,
  [switch]$Coverage,
  [int]$Port = 0,
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "selfcheck")
if ($SkipBuild) { $targetArgs += "--skip-build" }
if ($SkipLint) { $targetArgs += "--skip-lint" }
if ($SkipTests) { $targetArgs += "--skip-tests" }
if ($SkipFrontendTests) { $targetArgs += "--skip-frontend-tests" }
if ($SkipRuntime) { $targetArgs += "--skip-runtime" }
if ($Coverage) { $targetArgs += "--coverage" }
if ($Port -gt 0) { $targetArgs += @("--port", "$Port") }
& $py @targetArgs @Rest
exit $LASTEXITCODE
