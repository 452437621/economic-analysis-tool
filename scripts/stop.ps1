# EPIC 一键停止
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
#   .\scripts\stop.ps1 -Port 8766     # 按端口停止（无 PID 文件时）
#   .\scripts\stop.ps1 -Force         # 停止占用端口的任意进程（仅在确认是本项目时使用）
param(
  [int]$Port = 0,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_common.ps1")

$paths = Get-EpicPaths
if ($Port -le 0) { $Port = Get-EpicPort }

function Stop-EpicProcess {
  param([int]$ProcessId, [string]$Reason)
  if (-not (Test-EpicPidAlive -ProcessId $ProcessId)) { return $false }
  Write-Host "[stop] 停止进程 $ProcessId（$Reason）..."
  try {
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
  } catch {
    & taskkill /PID $ProcessId /T /F 2>$null | Out-Null
  }
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 250
    if (-not (Test-EpicPidAlive -ProcessId $ProcessId)) { return $true }
  }
  & taskkill /PID $ProcessId /T /F 2>$null | Out-Null
  Start-Sleep -Milliseconds 500
  return -not (Test-EpicPidAlive -ProcessId $ProcessId)
}

$stopped = $false

# 1) 优先用 PID 文件；优先停真实服务进程（server_pid），再兜底启动器
$record = Read-EpicPidFile -PidFile $paths.PidFile
if ($record) {
  $candidates = @()
  if ($record.server_pid -and [int]$record.server_pid -gt 0) { $candidates += [int]$record.server_pid }
  if ($record.pid -and [int]$record.pid -gt 0) { $candidates += [int]$record.pid }
  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if (-not (Test-EpicPidAlive -ProcessId $candidate)) { continue }
    if ((Test-EpicProcessIsOurs -ProcessId $candidate) -or $Force) {
      if (Stop-EpicProcess -ProcessId $candidate -Reason "PID 文件") { $stopped = $true }
    } else {
      Write-Host "[stop] PID $candidate 不是本项目的服务，跳过（确认后可加 -Force）。"
    }
  }
}
Remove-EpicPidFile -PidFile $paths.PidFile

# 2) 按端口兜底（PID 文件缺失、或服务由其他方式启动）
$listeners = @(Get-PortListeners -Port $Port)
if ($listeners.Count -gt 0) {
  foreach ($listener in $listeners) {
    $owner = [int]$listener.OwningProcess
    $info = Get-EpicProcessInfo -ProcessId $owner
    $name = if ($info) { $info.Name } else { "unknown" }
    $isOurs = Test-EpicProcessIsOurs -ProcessId $owner
    if ($isOurs -or $Force) {
      if (Stop-EpicProcess -ProcessId $owner -Reason "端口 $Port") { $stopped = $true }
    } else {
      Write-Host "[stop] 端口 $Port 被进程 $owner ($name) 占用，但不是本项目服务；未停止。"
      if ($info -and $info.CommandLine) { Write-Host "[stop] 命令行： $($info.CommandLine)" }
      Write-Host "[stop] 若确认可停止，执行： .\scripts\stop.ps1 -Force"
    }
  }
}

# 3) 结果判定：以端口是否仍健康为准
Start-Sleep -Milliseconds 400
if (Get-EpicHealth -Port $Port) {
  Write-Host "[stop] 服务仍在响应 $Port。请检查是否为手动启动的 uvicorn（可加 -Force）。"
  exit 1
}
if (Test-PortListening -Port $Port) {
  Write-Host "[stop] 端口 $Port 仍被占用（进程可能正在退出），请稍后重试或检查子进程。"
  exit 1
}
if ($stopped) {
  Write-Host "[stop] 已停止 $Port"
} else {
  Write-Host "[stop] 未发现运行中的服务（端口 $Port 空闲）"
}
