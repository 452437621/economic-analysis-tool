param()
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Find-Python312 {
  $managedRoot = Join-Path $root ".python"
  $managed = Get-ChildItem -LiteralPath $managedRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "cpython-3.1*" } | Sort-Object Name -Descending | Select-Object -First 1
  if ($managed) {
    $candidate = Join-Path $managed.FullName "python.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  $pyOutput = & py -3.12 -c "import sys;print(sys.executable)" 2>$null
  if ($LASTEXITCODE -eq 0 -and $pyOutput) { return $pyOutput.Trim() }
  return $null
}

$py = Find-Python312
if (-not $py) {
  Write-Host "[setup] 未找到 Python 3.12，使用 uv 在工作区内引导安装 ..."
  $uv = Join-Path $root ".tools\uv\bin\uv.exe"
  if (-not (Test-Path -LiteralPath $uv)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
      throw "未找到 Python 3.12，也无法用系统 Python 引导。请安装 https://www.python.org/downloads/ 的 Python 3.12+ 后重试。"
    }
    $uvTarget = Join-Path $root ".tools\uv"
    New-Item -ItemType Directory -Force -Path $uvTarget | Out-Null
    Write-Host "[setup] pip install uv -> $uvTarget"
    & python -m pip install --quiet --target $uvTarget uv
    $uv = Join-Path $uvTarget "bin\uv.exe"
  }
  $env:UV_CACHE_DIR = Join-Path $root ".cache\uv"
  $env:UV_PYTHON_INSTALL_DIR = Join-Path $root ".python"
  & $uv python install 3.12
  $py = Find-Python312
}
if (-not $py) { throw "Python 3.12 引导失败，请手动安装后重试。" }
Write-Host "[setup] Python: $py"

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
  Write-Host "[setup] 创建虚拟环境 .venv ..."
  & $py -m venv (Join-Path $root ".venv")
}
Write-Host "[setup] 安装依赖 ..."
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -e "$root" 2>&1 | Select-Object -Last 4
& $venvPy -m pip install pytest pytest-asyncio | Out-Null

$env:PYTHONPATH = Join-Path $root "backend"
Write-Host "[setup] 初始化数据库 ..."
Push-Location (Join-Path $root "backend")
try { & $venvPy -m app.init_db } finally { Pop-Location }

Write-Host ""
Write-Host "[setup] 完成。启动： scripts\start.ps1 ；浏览器打开 http://127.0.0.1:8765"
