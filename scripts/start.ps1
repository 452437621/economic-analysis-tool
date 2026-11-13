# EPIC 一键启动（默认后台运行）
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
#   .\scripts\start.ps1 -Foreground      # 前台运行，Ctrl+C 停止
#   .\scripts\start.ps1 -Reload          # 前台调试，改代码自动重载
#   .\scripts\start.ps1 -NoBrowser       # 不自动打开浏览器
#   .\scripts\start.ps1 -Port 8766       # 指定端口（默认读 .env 的 EPIC_PORT，否则 8765）
param(
  [switch]$Foreground,
  [switch]$Reload,
  [switch]$NoBrowser,
  [int]$Port = 0
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_common.ps1")

$paths = Get-EpicPaths
if (-not (Test-Path -LiteralPath $paths.VenvPy)) {
  throw "尚未初始化，请先运行 scripts\setup.ps1"
}
if ($Port -le 0) { $Port = Get-EpicPort }
$url = "http://127.0.0.1:$Port"

# 1) 已有本脚本启动的实例？
$existing = Read-EpicPidFile -PidFile $paths.PidFile
if ($existing -and (Test-EpicPidAlive -ProcessId ([int]$existing.pid))) {
  if (Get-EpicHealth -Port ([int]$existing.port)) {
    Write-Host "[start] 已在运行 (PID $($existing.pid)) -> http://127.0.0.1:$($existing.port)"
    Write-Host "[start] 停止： scripts\stop.ps1 ；重启： scripts\restart.ps1"
    if (-not $NoBrowser) { Open-EpicBrowser -Port ([int]$existing.port) }
    exit 0
  }
  Write-Host "[start] 发现残留 PID 文件（进程无响应），清理后继续 ..."
  Remove-EpicPidFile -PidFile $paths.PidFile
} elseif ($existing) {
  Write-Host "[start] 清理失效的 PID 文件 ..."
  Remove-EpicPidFile -PidFile $paths.PidFile
}

# 2) 端口占用检查（必须真实拿到 PID，避免"假启动"）
$listeners = @(Get-PortListeners -Port $Port)
if ($listeners.Count -gt 0) {
  $owner = [int]$listeners[0].OwningProcess
  $info = Get-EpicProcessInfo -ProcessId $owner
  $name = if ($info) { $info.Name } else { "unknown" }
  $isOurs = Test-EpicProcessIsOurs -ProcessId $owner
  if ($isOurs) {
    Write-Host "[start] 端口 $Port 上已有本项目的服务在运行 (PID $owner)。"
    Write-Host "[start] 如需重启： scripts\restart.ps1"
    if (-not $NoBrowser) { Open-EpicBrowser -Port $Port }
    exit 0
  }
  throw "端口 $Port 已被进程 $owner ($name) 占用，无法启动。请先结束该进程，或用 -Port 指定其他端口。"
}

$env:PYTHONPATH = $paths.Backend
$uvicornArgs = @(
  "-m", "uvicorn", "app.main:app",
  "--host", "127.0.0.1", "--port", "$Port",
  "--log-level", "info"
)
if ($Reload) { $uvicornArgs += "--reload" }

# 3) 前台模式（保留原有行为）
if ($Foreground -or $Reload) {
  Write-Host "[start] 前台运行 $url （Ctrl+C 停止）"
  Push-Location $paths.Backend
  try { & $paths.VenvPy @uvicornArgs } finally { Pop-Location }
  exit 0
}

# 4) 后台模式：通过 WMI 创建进程，彻底脱离当前控制台/管道（否则服务会占用父进程 stdout，
#    在 CI 或捕获输出的终端里表现为"启动脚本永不返回"）。日志由 app.serve 写入 data\logs。
#    用 "-m app.serve" 而不是脚本路径：避免把 backend\app 加入 sys.path 造成标准库被
#    同名包（app\platform）遮蔽。
New-Item -ItemType Directory -Force -Path $paths.RunDir, $paths.LogDir | Out-Null
$cmdLine = '"{0}" -m app.serve --host 127.0.0.1 --port {1} --log-level info' -f $paths.VenvPy, $Port
Write-Host "[start] 后台启动 $url ..."
$created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine      = $cmdLine
  CurrentDirectory = $paths.Backend
} -ErrorAction Stop
if (-not $created -or [int]$created.ReturnValue -ne 0) {
  throw "无法创建后台进程（WMI ReturnValue=$($created.ReturnValue)）。可在前台运行： scripts\start.ps1 -Foreground"
}
$procId = [int]$created.ProcessId
Start-Sleep -Milliseconds 600

Write-EpicPidFile -PidFile $paths.PidFile -ProcessId $procId -Port $Port -Arguments @($cmdLine)

# 5) 就绪校验：健康响应 + 端口归属必须在新进程树内（venv 的 python.exe 是启动器，
#    真正监听的是它的子进程，因此用进程树判断，避免"假失败/假成功"）。
$deadline = (Get-Date).AddSeconds(60)
$ready = $false
$serverPid = 0
while ((Get-Date) -lt $deadline) {
  if (-not (Test-EpicPidAlive -ProcessId $procId)) { break }
  if (Get-EpicHealth -Port $Port) {
    $listenerPids = Get-EpicListenerPids -Port $Port
    if ($listenerPids.Count -eq 0) {
      # 无法解析端口归属时退化为"健康即可"
      $ready = $true
      break
    }
    $tree = Get-EpicProcessTree -RootId $procId
    foreach ($listenerPid in $listenerPids) {
      if ($tree -contains $listenerPid) {
        $ready = $true
        $serverPid = $listenerPid
        break
      }
    }
    if ($ready) { break }
  }
  Start-Sleep -Milliseconds 500
}

if (-not $ready) {
  Write-Host "[start] 启动失败，最近日志："
  Show-EpicLogTail -OutLog $paths.OutLog -ErrLog $paths.ErrLog
  if (Test-EpicPidAlive -ProcessId $procId) {
    & taskkill /PID $procId /T /F 2>$null | Out-Null
  }
  Remove-EpicPidFile -PidFile $paths.PidFile
  if (Test-PortListening -Port $Port) {
    throw "服务未就绪，且端口 $Port 仍被占用（可能被其他进程抢占）。请运行 scripts\stop.ps1 或换端口。"
  }
  throw "服务未在 60 秒内就绪，已终止进程。请检查 data\logs\server.err.log。"
}

Write-EpicPidFile -PidFile $paths.PidFile -ProcessId $procId -Port $Port -Arguments @($cmdLine) -ServerPid $serverPid
if ($serverPid -gt 0) {
  Write-Host "[start] 已启动 (启动器 PID $procId，服务 PID $serverPid) -> $url"
} else {
  Write-Host "[start] 已启动 (PID $procId) -> $url"
}
Write-Host "[start] 日志： $($paths.OutLog) / $($paths.ErrLog)"
Write-Host "[start] 停止： scripts\stop.ps1 ；重启： scripts\restart.ps1"
if (-not $NoBrowser) { Open-EpicBrowser -Port $Port }
