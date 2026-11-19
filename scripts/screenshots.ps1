# 用本机 Chrome 无头模式把当前运行的 EPIC 页面逐页截图到 docs/assets/vue/。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\screenshots.ps1
param(
    [string]$BaseUrl = "http://127.0.0.1:8765",
    [string]$OutDir = "docs/assets/vue",
    [int]$Width = 1600,
    [int]$Height = 1150,
    [int]$BudgetMs = 12000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$chrome = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "未找到 Chrome/Edge，无法截图" }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$profile = Join-Path $root "data\test\tmp\chrome-profile"
New-Item -ItemType Directory -Force -Path $profile | Out-Null
$errLog = Join-Path $root "data\test\tmp\chrome.err.txt"

$pages = @(
    @{ name = "vue-overview";       path = "/" },
    @{ name = "vue-overview-light"; path = "/?theme=light" },
    @{ name = "vue-market";         path = "/market" },
    @{ name = "vue-rates";          path = "/rates" },
    @{ name = "vue-analysis";       path = "/analysis" },
    @{ name = "vue-signals";        path = "/signals" },
    @{ name = "vue-lenses";         path = "/lenses" },
    @{ name = "vue-gold";           path = "/gold" },
    @{ name = "vue-theses";         path = "/theses" },
    @{ name = "vue-briefs";         path = "/briefs" },
    @{ name = "vue-system";         path = "/system" },
    @{ name = "vue-cycle";          path = "/cycle" },
    @{ name = "vue-alerts";         path = "/alerts" },
    @{ name = "vue-pipeline";       path = "/pipeline" },
    @{ name = "vue-history";        path = "/history" },
    @{ name = "vue-ledger";         path = "/ledger" },
    @{ name = "vue-principles";     path = "/principles" },
    @{ name = "vue-trades";         path = "/trades" },
    @{ name = "vue-docs";           path = "/docs" }
)

$ok = 0
foreach ($page in $pages) {
    $shot = Join-Path $OutDir "$($page.name).png"
    $url = "$BaseUrl$($page.path)"
    $args = @(
        "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--no-first-run", "--disable-extensions", "--user-data-dir=$profile",
        "--window-size=$Width,$Height", "--virtual-time-budget=$BudgetMs",
        "--screenshot=$shot", $url
    )
    $proc = Start-Process -FilePath $chrome -ArgumentList $args -Wait -PassThru `
        -RedirectStandardError $errLog -RedirectStandardOutput (Join-Path $root "data\test\tmp\chrome.out.txt")
    if (Test-Path $shot) {
        $size = (Get-Item $shot).Length
        Write-Host "[ok] $($page.name) <- $($page.path) ($size bytes)"
        $ok++
    }
    else {
        Write-Warning "[fail] $($page.name) <- $($page.path) (exit $($proc.ExitCode))：$(Get-Content $errLog -Tail 3)"
    }
}
Write-Host "[done] $ok/$($pages.Count) 张已写入 $OutDir"
