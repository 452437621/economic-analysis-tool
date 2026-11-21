# EPIC lint wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [switch]$Quiet,
  [switch]$Json,
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "lint")
if ($Quiet) { $targetArgs += "--quiet" }
if ($Json) { $targetArgs += "--json" }
& $py @targetArgs @Rest
exit $LASTEXITCODE
