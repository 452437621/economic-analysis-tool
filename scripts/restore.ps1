param(
  [string]$BackupDir = "",
  [switch]$Force,
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root "data"
$backupRoot = Join-Path $dataDir "backup"

if ([string]::IsNullOrWhiteSpace($BackupDir)) {
  $latest = Get-ChildItem -LiteralPath $backupRoot -Directory -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
  if (-not $latest) { throw "No backup found. Run scripts\backup.ps1 first." }
  $BackupDir = $latest.FullName
}
if (-not (Test-Path -LiteralPath $BackupDir)) { throw "Backup directory not found: $BackupDir" }

$sourceDb = Join-Path $BackupDir "epic.db"
if (-not (Test-Path -LiteralPath $sourceDb)) { throw "epic.db missing in backup: $BackupDir" }

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $root "backend"
$env:EPIC_ENV = "test"
$check = @"
import sqlite3, sys
path = sys.argv[1]
conn = sqlite3.connect(path)
try:
    result = conn.execute('PRAGMA integrity_check').fetchone()
    print('source integrity_check:', result[0] if result else 'unknown')
    sys.exit(0 if result and result[0] == 'ok' else 1)
finally:
    conn.close()
"@ | & $venvPy - $sourceDb
if ($LASTEXITCODE -ne 0) { throw "Backup integrity check failed: $sourceDb" }
Write-Host $check

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$safetyDir = Join-Path $backupRoot "pre-restore-$stamp"
$targetDb = Join-Path $dataDir "epic.db"
$targetConfig = Join-Path $root "config\default.yaml"

Write-Host "[restore] backup dir: $BackupDir"
Write-Host "[restore] target db: $targetDb"
Write-Host "[restore] safety copy: $safetyDir"
if ($DryRun) {
  Write-Host "[restore] DryRun: validation only, nothing written."
  exit 0
}

if (-not $Force) {
  $answer = Read-Host "Restore will overwrite the current database. Type YES to continue"
  if ($answer -ne "YES") { Write-Host "Cancelled"; exit 1 }
}

New-Item -ItemType Directory -Path $safetyDir -Force | Out-Null
if (Test-Path -LiteralPath $targetDb) { Copy-Item -LiteralPath $targetDb -Destination (Join-Path $safetyDir "epic.db") }
if (Test-Path -LiteralPath $targetConfig) { Copy-Item -LiteralPath $targetConfig -Destination (Join-Path $safetyDir "default.yaml") }

Copy-Item -LiteralPath $sourceDb -Destination $targetDb -Force
$sourceConfig = Join-Path $BackupDir "default.yaml"
if (Test-Path -LiteralPath $sourceConfig) {
  if (-not $Force) {
    $answer = Read-Host "Also restore config/default.yaml? Type YES to confirm"
  } else {
    $answer = "YES"
  }
  if ($answer -eq "YES") { Copy-Item -LiteralPath $sourceConfig -Destination $targetConfig -Force }
}

Write-Host "[restore] done. Restart the server and run scripts\selfcheck.ps1."
Write-Host "[restore] rollback copy: $safetyDir"
