# EPIC dev wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [int]$Port = 5173,
  [int]$BackendPort = 0,
  [switch]$NoBrowser,
  [switch]$NoBackend,
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "dev")
$targetArgs += @("--port", "$Port")
if ($BackendPort -gt 0) { $targetArgs += @("--backend-port", "$BackendPort") }
if ($NoBrowser) { $targetArgs += "--no-browser" }
if ($NoBackend) { $targetArgs += "--no-backend" }
& $py @targetArgs @Rest
exit $LASTEXITCODE
