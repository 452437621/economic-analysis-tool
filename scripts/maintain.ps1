# EPIC maintain wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [switch]$DryRun,
  [switch]$Apply,
  [switch]$Verify,
  [switch]$IncludeRaw,
  [switch]$IncludeLogs,
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "maintain")
if ($DryRun) { $targetArgs += "--dry-run" }
if ($Apply) { $targetArgs += "--apply" }
if ($Verify) { $targetArgs += "--verify" }
if ($IncludeRaw) { $targetArgs += "--include-raw" }
if ($IncludeLogs) { $targetArgs += "--include-logs" }
& $py @targetArgs @Rest
exit $LASTEXITCODE
