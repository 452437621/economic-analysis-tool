#Requires -Version 5.1
<#
.SYNOPSIS
    破坏性 Git 操作前的「工作区快照」。

.DESCRIPTION
    在 git reset --hard / git checkout -- . / git clean -fd 之前先运行本脚本，
    把当前未提交状态完整落盘到 data/backups/snapshot-<时间戳>/：

      head.txt         当前 HEAD 与分支
      status.txt       git status --porcelain=v2 --branch（操作前后可 diff 对照）
      worktree.patch   工作区相对 HEAD 的改动（--binary，可 git apply）
      index.patch      暂存区相对 HEAD 的改动（--binary，可 git apply --cached）
      untracked-files.txt  未跟踪文件清单
      untracked/       未跟踪文件原样副本（保持相对路径）

    恢复：
      git apply "<快照目录>\worktree.patch"
      git apply --cached "<快照目录>\index.patch"
      （未跟踪文件直接从 untracked/ 拷回）

.EXAMPLE
    .\scripts\snapshot.ps1

.NOTES
    2026-11-17 事故（git reset --hard 覆盖 6 个前端源文件）之后新增。
    快照位于 data/（已被 .gitignore 忽略），不会污染版本库。
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $root "data\backups\snapshot-$stamp"

Push-Location $root
try {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    $branch = (& git rev-parse --abbrev-ref HEAD 2>$null) -join ""
    $headSha = (& git rev-parse HEAD 2>$null) -join ""
    Set-Content -LiteralPath (Join-Path $dest "head.txt") -Encoding utf8 -Value @(
        "branch=$branch",
        "head=$headSha"
    )
    & git status --porcelain=v2 --branch | Set-Content -LiteralPath (Join-Path $dest "status.txt") -Encoding utf8

    # --output 直接写原始字节，避免 PowerShell 管道对 UTF-8 补丁的再编码
    & git diff HEAD --binary "--output=$(Join-Path $dest 'worktree.patch')"
    & git diff --cached --binary "--output=$(Join-Path $dest 'index.patch')"

    $untracked = @(& git ls-files --others --exclude-standard)
    Set-Content -LiteralPath (Join-Path $dest "untracked-files.txt") -Encoding utf8 -Value $untracked
    if ($untracked.Count -gt 0) {
        $stage = Join-Path $dest "untracked"
        foreach ($rel in $untracked) {
            $target = Join-Path $stage $rel
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $rel -Destination $target -Force
        }
    }

    $patchBytes = (Get-Item (Join-Path $dest "worktree.patch")).Length
    Write-Host "[snapshot] branch=$branch head=$headSha"
    Write-Host "[snapshot] 未跟踪文件 $($untracked.Count) 个，worktree.patch $patchBytes 字节"
    Write-Host "[snapshot] 已写入 $dest"
    Write-Host "[snapshot] 恢复：git apply `"$dest\worktree.patch`""
} finally {
    Pop-Location
}
