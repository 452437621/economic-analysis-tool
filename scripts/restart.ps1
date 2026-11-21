# EPIC restart wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [int]$Port = 0,
  [switch]$NoBrowser,
  [switch]$Force,
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "restart")
if ($Port -gt 0) { $targetArgs += @("--port", "$Port") }
if ($NoBrowser) { $targetArgs += "--no-browser" }
if ($Force) { $targetArgs += "--force" }
& $py @targetArgs @Rest
exit $LASTEXITCODE
