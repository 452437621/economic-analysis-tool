# EPIC screenshots wrapper. All logic lives in scripts/epic.py; this file only maps flags.
param(
  [string]$BaseUrl = "http://127.0.0.1:8765",
  [string]$OutDir = "docs/assets/vue",
  [int]$Width = 1600,
  [int]$Height = 1150,
  [int]$BudgetMs = 12000,
  [string]$Pages = "",
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $py = $venvPy }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $py = "py" }
else { $py = "python" }

$targetArgs = @((Join-Path $root "scripts\epic.py"), "screenshots")
$targetArgs += @("--base-url", $BaseUrl, "--out-dir", $OutDir)
$targetArgs += @("--width", "$Width", "--height", "$Height", "--budget-ms", "$BudgetMs")
if ($Pages) { $targetArgs += @("--pages", $Pages) }
& $py @targetArgs @Rest
exit $LASTEXITCODE
