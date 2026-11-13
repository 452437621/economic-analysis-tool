param([switch]$SkipTests)
$ci = Join-Path $PSScriptRoot "ci.ps1"
if ($SkipTests) {
  & $ci -SkipTests
} else {
  & $ci
}
