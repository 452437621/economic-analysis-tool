# 内部辅助：校验 .ps1 文件语法（供 scripts/lint.py 调用，不直接给用户使用）
# 用法：powershell -File scripts\_lint_ps.ps1 -Files "a.ps1,b.ps1"
param([Parameter(Mandatory = $true)][string]$Files)

$bad = 0
foreach ($file in ($Files -split ",")) {
  $path = $file.Trim()
  if (-not $path) { continue }
  $parseErrors = $null
  [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath $path), [ref]$parseErrors) | Out-Null
  if ($parseErrors.Count -gt 0) {
    $bad++
    Write-Output ("FAIL " + (Split-Path -Leaf $path))
    foreach ($e in $parseErrors) { Write-Output ("  line " + $e.Token.StartLine + ": " + $e.Message) }
  } else {
    Write-Output ("OK " + (Split-Path -Leaf $path))
  }
}
exit $bad
