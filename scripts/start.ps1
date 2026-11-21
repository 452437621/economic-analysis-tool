# EPIC start wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [switch]$Foreground,
  [switch]$Reload,
  [switch]$NoBrowser,
  [int]$Port = 0,
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "start")
if ($Foreground) { $targetArgs += "--foreground" }
if ($Reload) { $targetArgs += "--reload" }
if ($NoBrowser) { $targetArgs += "--no-browser" }
if ($Port -gt 0) { $targetArgs += @("--port", "$Port") }
& $py @targetArgs @Rest
exit $LASTEXITCODE
