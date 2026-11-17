# EPIC 通用脚本函数（由 start/stop/restart 点源引用）
# 约定：文件以 UTF-8 BOM 保存，兼容 Windows PowerShell 5.1 与 pwsh 7。

function Get-EpicPaths {
  $root = Split-Path -Parent $PSScriptRoot
  [pscustomobject]@{
    Root    = $root
    VenvPy  = Join-Path $root ".venv\Scripts\python.exe"
    Backend = Join-Path $root "backend"
    RunDir  = Join-Path $root "data\run"
    PidFile = Join-Path $root "data\run\epic.pid"
    LogDir  = Join-Path $root "data\logs"
    OutLog  = Join-Path $root "data\logs\server.out.log"
    ErrLog  = Join-Path $root "data\logs\server.err.log"
  }
}

function Get-EpicPort {
  param([int]$Default = 8765)
  $paths = Get-EpicPaths
  $envFile = Join-Path $paths.Root ".env"
  if (Test-Path -LiteralPath $envFile) {
    $line = Get-Content -LiteralPath $envFile -ErrorAction SilentlyContinue |
      Where-Object { $_ -match "^\s*EPIC_PORT\s*=" } | Select-Object -First 1
    if ($line -and $line -match "=\s*(\d+)") { return [int]$Matches[1] }
  }
  return $Default
}

# 返回监听指定端口的 PID 列表。三层兜底：Get-NetTCPConnection -> CIM -> netstat。
function Get-PortListeners {
  param([int]$Port)
  $found = @()

  try {
    foreach ($conn in @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue)) {
      if ($null -eq $conn) { continue }
      if ("$($conn.State)" -eq "Listen" -or "$($conn.State)" -eq "2") {
        $found += [pscustomobject]@{ OwningProcess = [int]$conn.OwningProcess }
      }
    }
  } catch { }

  if ($found.Count -eq 0) {
    try {
      $cim = Get-CimInstance -Namespace "root/StandardCimv2" -ClassName MSFT_NetTCPConnection `
        -Filter "LocalPort=$Port AND State='Listen'" -ErrorAction SilentlyContinue
      foreach ($row in @($cim)) {
        if ($null -ne $row) { $found += [pscustomobject]@{ OwningProcess = [int]$row.OwningProcess } }
      }
    } catch { }
  }

  if ($found.Count -eq 0) {
    try {
      $lines = @(& netstat -ano -p tcp 2>$null)
      foreach ($line in $lines) {
        if ("$line" -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
          $found += [pscustomobject]@{ OwningProcess = [int]$Matches[1] }
        }
      }
    } catch { }
  }

  $unique = @{}
  foreach ($item in $found) {
    if ($item.OwningProcess -gt 0) { $unique[$item.OwningProcess] = $item }
  }
  return @($unique.Values)
}

function Test-PortListening {
  param([int]$Port)
  try {
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    foreach ($endpoint in $listeners) {
      if ($endpoint.Port -eq $Port) { return $true }
    }
  } catch { }
  return ((Get-PortListeners -Port $Port).Count -gt 0)
}

function Get-EpicProcessInfo {
  param([int]$ProcessId)
  try {
    Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop |
      Select-Object ProcessId, Name, ExecutablePath, CommandLine
  } catch { $null }
}

function Test-EpicPidAlive {
  param([int]$ProcessId)
  if ($ProcessId -le 0) { return $false }
  return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Test-EpicProcessIsOurs {
  param([int]$ProcessId)
  $info = Get-EpicProcessInfo -ProcessId $ProcessId
  if (-not $info) { return $false }
  $cmd = "$($info.CommandLine)"
  # 前台模式是 uvicorn app.main:app；后台模式是 -m app.serve。两种都算本项目。
  if ($cmd -notmatch "app\.main:app|app\.serve") { return $false }
  $paths = Get-EpicPaths
  $exe = "$($info.ExecutablePath)"
  if ($exe -and $exe.StartsWith($paths.Root, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
  return $cmd.Contains($paths.Root)
}

# venv 的 Scripts\python.exe 是启动器，真正监听端口的是它的子进程（基础解释器）。
# 返回根进程 + 其后代 PID 列表，用于健康检查时判断端口归属。
function Get-EpicProcessTree {
  param([int]$RootId)
  $ids = @([int]$RootId)
  try {
    $procs = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
      Select-Object ProcessId, ParentProcessId)
    for ($depth = 0; $depth -lt 3; $depth++) {
      $added = $false
      foreach ($proc in $procs) {
        if ($null -eq $proc) { continue }
        $procId = [int]$proc.ProcessId
        $parentId = [int]$proc.ParentProcessId
        if (($ids -contains $parentId) -and -not ($ids -contains $procId)) {
          $ids += $procId
          $added = $true
        }
      }
      if (-not $added) { break }
    }
  } catch { }
  return $ids
}

function Get-EpicListenerPids {
  param([int]$Port)
  return @(Get-PortListeners -Port $Port | ForEach-Object { [int]$_.OwningProcess })
}

function Get-EpicHealth {
  param([int]$Port, [int]$TimeoutMs = 2000)
  # 直接用 TcpClient 发一个最小 HTTP 请求。
  # 不依赖 System.Net.Http（5.1 默认未加载），也不走 IE 系统代理，
  # 避免本地 127.0.0.1 被代理拦截导致"误判未就绪"。
  $client = $null
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) { return $false }
    $client.EndConnect($connect)
    $stream = $client.GetStream()
    $stream.ReadTimeout = $TimeoutMs
    $stream.WriteTimeout = $TimeoutMs
    $request = "GET /healthz HTTP/1.1`r`nHost: 127.0.0.1:$Port`r`nConnection: close`r`n`r`n"
    $payload = [System.Text.Encoding]::ASCII.GetBytes($request)
    $stream.Write($payload, 0, $payload.Length)
    $buffer = New-Object byte[] 128
    $read = $stream.Read($buffer, 0, $buffer.Length)
    if ($read -le 0) { return $false }
    $statusLine = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $read)
    return ($statusLine -match "HTTP/1\.[01] 200")
  } catch {
    return $false
  } finally {
    if ($client) { $client.Close() }
  }
}

function Wait-EpicHealth {
  param([int]$Port, [int]$TimeoutSeconds = 60)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Get-EpicHealth -Port $Port) { return $true }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

function Read-EpicPidFile {
  param([string]$PidFile)
  if (-not (Test-Path -LiteralPath $PidFile)) { return $null }
  try { Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json } catch { $null }
}

function Write-EpicPidFile {
  param(
    [string]$PidFile,
    [int]$ProcessId,
    [int]$Port,
    [string[]]$Arguments,
    [int]$ServerPid = 0
  )
  $dir = Split-Path -Parent $PidFile
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  [pscustomobject]@{
    pid        = $ProcessId
    server_pid = $ServerPid
    port       = $Port
    started_at = (Get-Date).ToString("o")
    arguments  = ($Arguments -join " ")
  } | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding utf8
}

function Remove-EpicPidFile {
  param([string]$PidFile)
  if (Test-Path -LiteralPath $PidFile) { Remove-Item -LiteralPath $PidFile -Force }
}

function Open-EpicBrowser {
  param([int]$Port)
  Start-Process "http://127.0.0.1:$Port" | Out-Null
}

function Show-EpicLogTail {
  param([string]$OutLog, [string]$ErrLog, [int]$Lines = 20)
  foreach ($log in @($ErrLog, $OutLog)) {
    if (Test-Path -LiteralPath $log) {
      Write-Host "--- $log ---"
      Get-Content -LiteralPath $log -Tail $Lines | ForEach-Object { Write-Host $_ }
    }
  }
}
