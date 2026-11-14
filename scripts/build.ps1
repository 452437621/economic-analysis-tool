param([switch]$SkipInstall)
# 构建 Vue 前端到仓库根 web/（由 FastAPI 托管）。
# 约定：文件以 UTF-8 BOM 保存，兼容 Windows PowerShell 5.1 与 pwsh 7。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$npm = "npm.cmd"

if (-not (Test-Path -LiteralPath (Join-Path $frontend "package.json"))) {
  throw "未找到 frontend/package.json"
}

if (-not (Test-Path -LiteralPath (Join-Path $frontend "node_modules"))) {
  if ($SkipInstall) { throw "frontend/node_modules 缺失，已指定 -SkipInstall" }
  Write-Host "[build] 安装前端依赖（首次）..." -ForegroundColor Cyan
  Push-Location $frontend
  try { & $npm install --no-audit --no-fund } finally { Pop-Location }
  if ($LASTEXITCODE -ne 0) { throw "npm install 失败 (exit $LASTEXITCODE)" }
}

# 本机 esbuild 偶发无法删除系统 TEMP 中的临时文件：把 TEMP 指到工作区
$tmp = Join-Path $frontend ".tmp"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$env:TEMP = $tmp
$env:TMP = $tmp

Write-Host "[build] 构建前端（vue-tsc + vite build）..." -ForegroundColor Cyan
Push-Location $frontend
try {
  & $npm run build
  if ($LASTEXITCODE -ne 0) { throw "前端构建失败 (exit $LASTEXITCODE)" }
} finally {
  Pop-Location
}

$indexFile = Join-Path $root "web\index.html"
if (-not (Test-Path -LiteralPath $indexFile)) { throw "构建产物缺失：web\index.html" }
$assetsDir = Join-Path $root "web\assets"
if (-not (Test-Path -LiteralPath $assetsDir)) { throw "构建产物缺失：web\assets" }

$html = Get-Content -LiteralPath $indexFile -Raw -Encoding UTF8
if ($html -notmatch "/assets/") { throw "web\index.html 未引用 /assets，构建产物异常" }
if ($html -match "https?://(?!127\.0\.0\.1)") {
  Write-Warning "构建产物包含外部 URL，请确认没有引入 CDN / 外部字体"
}

$files = @(Get-ChildItem -LiteralPath $assetsDir -File)
$total = ($files | Measure-Object -Sum Length).Sum
Write-Host ("[build] 完成 -> web\index.html（{0} 个资源，{1:N0} KB）" -f $files.Count, ($total / 1KB)) -ForegroundColor Green
