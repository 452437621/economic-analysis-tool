# EPIC restore wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [string]$BackupDir = "",
  [switch]$Force,
  [switch]$DryRun,
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "restore")
if ($BackupDir) { $targetArgs += @("--backup-dir", $BackupDir) }
if ($Force) { $targetArgs += "--force" }
if ($DryRun) { $targetArgs += "--dry-run" }
& $py @targetArgs @Rest
exit $LASTEXITCODE
