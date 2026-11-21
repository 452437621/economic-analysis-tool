"""EPIC cross-platform task runner (standard library only).

One implementation for Windows (PowerShell 5.1/7 and cmd.exe) and Linux/macOS
(bash).  The per-platform files in ``scripts/`` are thin wrappers around this
module, so lifecycle behaviour cannot drift between platforms.

Usage:
    python scripts/epic.py --help
    python scripts/epic.py status --json
    python scripts/epic.py start --no-browser
    python scripts/epic.py stop --force
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data"
RUN_DIR = DATA / "run"
LOG_DIR = DATA / "logs"
PID_FILE = RUN_DIR / "epic.pid"
OUT_LOG = LOG_DIR / "server.out.log"
ERR_LOG = LOG_DIR / "server.err.log"
DEFAULT_PORT = 8765
DEFAULT_VITE_PORT = 5173
LOG_TAIL = 20
IS_WINDOWS = os.name == "nt"
# PowerShell is asked to emit UTF-8 explicitly (see _ps_script), so the result
# is decoded the same way whether the caller is PowerShell (cp936 console) or
# cmd.exe (chcp 65001).
PS_ENCODING = "utf-8"

# Captured terminals (CI, cmd.exe pipes) should receive UTF-8 regardless of the
# active code page; PowerShell/cmd wrappers switch to 65001 where they can.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

#: Actions that must have a .ps1/.cmd/.sh wrapper in scripts/.
ACTIONS = (
    "setup",
    "start",
    "stop",
    "restart",
    "status",
    "build",
    "dev",
    "ci",
    "selfcheck",
    "check-acceptance",
    "backup",
    "restore",
    "maintain",
    "snapshot",
    "screenshots",
    "lint",
)
ACTION_NAMES = frozenset(ACTIONS)


class EpicError(RuntimeError):
    """A user-facing failure with a readable hint."""


# ---------------------------------------------------------------------------
# Process / platform helpers
# ---------------------------------------------------------------------------


def venv_python() -> Path:
    return ROOT / (".venv/Scripts/python.exe" if IS_WINDOWS else ".venv/bin/python")


def ensure_venv() -> Path:
    override = os.environ.get("EPIC_PYTHON")
    if override:
        candidate = Path(override)
        if candidate.exists():
            return candidate
        resolved = shutil.which(override)
        if resolved:
            return Path(resolved)
    python = venv_python()
    if not python.exists():
        raise EpicError(
            "虚拟环境尚未初始化。请先运行 setup "
            "(Windows: scripts\\setup.cmd 或 .\\scripts\\setup.ps1；Linux: ./scripts/setup.sh)。"
        )
    return python


def _version_ok(command: list[str]) -> bool:
    try:
        result = subprocess.run(
            [*command, "-c", "import sys;print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    try:
        major, minor = (int(part) for part in result.stdout.strip().split()[:2])
    except (ValueError, IndexError):
        return False
    return (major, minor) >= (3, 11)


def find_python(explicit: str | None = None) -> list[str]:
    """Return a command prefix for a Python >= 3.11 interpreter."""
    candidates: list[list[str]] = []
    for value in (explicit, os.environ.get("EPIC_PYTHON")):
        if value:
            candidates.append([value])
    if explicit or os.environ.get("EPIC_PYTHON"):
        for candidate in candidates:
            if _version_ok(candidate):
                return candidate
        raise EpicError(f"指定的 Python 不可用或低于 3.11: {explicit or os.environ.get('EPIC_PYTHON')}")

    managed_root = ROOT / ".python"
    if managed_root.exists():
        managed = sorted(
            (path for path in managed_root.iterdir() if path.is_dir() and path.name.startswith("cpython-")),
            reverse=True,
        )
        for directory in managed:
            for candidate in (directory / "python.exe", directory / "bin" / "python3"):
                if candidate.exists():
                    candidates.append([str(candidate)])

    if IS_WINDOWS:
        candidates.extend([["py", "-3.12"], ["py", "-3.11"], ["python"]])
    else:
        candidates.extend([["python3.12"], ["python3.11"], ["python3"], ["python"]])

    for command in candidates:
        if _version_ok(command):
            return command
    raise EpicError(
        "未找到 Python 3.11+。请安装 Python 3.12，或设置 EPIC_PYTHON 指向解释器。"
    )


def _bootstrap_python_with_uv() -> None:
    """Install a managed Python 3.12 under ``.python/`` when no usable Python exists.

    Mirrors the old setup script: bootstrap ``uv`` with any system Python, then
    let uv download CPython into the workspace (no system changes).
    """
    uv: Path | None = None
    candidates: list[Path] = [
        ROOT / ".tools" / "uv" / "bin" / "uv.exe",
        ROOT / ".tools" / "uv" / "bin" / "uv",
    ]
    system_uv = shutil.which("uv")
    if system_uv:
        candidates.append(Path(system_uv))
    for candidate in candidates:
        if candidate.exists():
            uv = candidate
            break
    if uv is None:
        base = shutil.which("python") or shutil.which("python3")
        if not base:
            raise EpicError(
                "未找到可用的 Python 或 uv。请安装 Python 3.11+，或先安装 uv 后重试。"
            )
        target = ROOT / ".tools" / "uv"
        target.mkdir(parents=True, exist_ok=True)
        print("[setup] 用系统 Python 引导 uv ...")
        result = run(
            [base, "-m", "pip", "install", "--quiet", "--target", str(target), "uv"],
            check=False,
        )
        if result.returncode != 0:
            raise EpicError("uv 安装失败；请手动安装 Python 3.12 或 uv。")
        uv = target / ("bin/uv.exe" if IS_WINDOWS else "bin/uv")
    if not uv.exists():
        raise EpicError("uv 引导失败；请手动安装 Python 3.12。")
    print("[setup] 用 uv 安装 Python 3.12 到 .python/ ...")
    run(
        [str(uv), "python", "install", "3.12"],
        env={
            "UV_CACHE_DIR": str(ROOT / ".cache" / "uv"),
            "UV_PYTHON_INSTALL_DIR": str(ROOT / ".python"),
        },
        check=True,
    )


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.setdefault("PYTHONIOENCODING", "utf-8")
    if env:
        merged.update(env)
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            env=merged,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise EpicError(f"找不到命令: {command[0]}") from exc
    if check and result.returncode != 0:
        detail = ""
        if capture:
            detail = (result.stdout or "") + (result.stderr or "")
        raise EpicError(f"命令失败 ({result.returncode}): {' '.join(command)}\n{detail}".strip())
    return result


def backend_env(**extra: str) -> dict[str, str]:
    env = {"PYTHONPATH": str(BACKEND), "PYTHONIOENCODING": "utf-8", **extra}
    return env


def read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if not env_file.exists():
        return values
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_port(value: int | None) -> int:
    if value and value > 0:
        return value
    env_value = os.environ.get("EPIC_PORT") or read_env_file().get("EPIC_PORT")
    try:
        return int(env_value) if env_value else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WINDOWS:
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(ok) and exit_code.value == 259  # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _ps_script(body: str) -> str:
    """Force UTF-8 stdout so ownership checks are independent of the console code page."""
    return "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + body


def process_cmdline(pid: int) -> str:
    if pid <= 0:
        return ""
    if IS_WINDOWS:
        script = _ps_script(
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                encoding=PS_ENCODING,
                errors="replace",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return (result.stdout or "").strip()
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        pass
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        return (result.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def process_exe(pid: int) -> str:
    if pid <= 0:
        return ""
    if IS_WINDOWS:
        script = _ps_script(
            f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').ExecutablePath"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                encoding=PS_ENCODING,
                errors="replace",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return (result.stdout or "").strip()
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return ""


def is_our_process(pid: int) -> bool:
    if not is_pid_alive(pid):
        return False
    cmdline = process_cmdline(pid)
    if not cmdline:
        return False
    if "app.main:app" not in cmdline and "app.serve" not in cmdline:
        return False
    root = str(ROOT)
    exe = process_exe(pid)
    return root.lower() in cmdline.lower() or (bool(exe) and root.lower() in exe.lower())


def children_of(pid: int) -> list[int]:
    if pid <= 0:
        return []
    if IS_WINDOWS:
        script = _ps_script(
            f"Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}' "
            "| Select-Object -ExpandProperty ProcessId"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                encoding=PS_ENCODING,
                errors="replace",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        found: list[int] = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                found.append(int(line))
        return found
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        return [int(line) for line in result.stdout.split() if line.isdigit()]
    except (OSError, subprocess.SubprocessError):
        return []


def process_tree(pid: int, depth: int = 4) -> list[int]:
    seen = [pid]
    frontier = [pid]
    for _ in range(depth):
        next_frontier: list[int] = []
        for parent in frontier:
            for child in children_of(parent):
                if child not in seen:
                    seen.append(child)
                    next_frontier.append(child)
        if not next_frontier:
            break
        frontier = next_frontier
    return seen


def stop_process_tree(pid: int) -> bool:
    if not is_pid_alive(pid):
        return False
    if IS_WINDOWS:
        run(["taskkill", "/PID", str(pid), "/T", "/F"], capture=True)
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                return True
        for _ in range(20):
            time.sleep(0.15)
            if not is_pid_alive(pid):
                return True
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    for _ in range(20):
        time.sleep(0.15)
        if not is_pid_alive(pid):
            return True
    return not is_pid_alive(pid)


def port_listeners(port: int) -> list[int]:
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        found: set[int] = set()
        for line in (result.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0].upper() == "TCP" and f":{port}" in parts[1]:
                if parts[3].upper().startswith("LISTEN"):
                    try:
                        found.add(int(parts[4]))
                    except ValueError:
                        continue
        return sorted(found)

    for command in (
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        ["fuser", f"{port}/tcp"],
    ):
        if not shutil.which(command[0]):
            continue
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        pids = {int(token) for token in result.stdout.split() if token.isdigit()}
        if pids:
            return sorted(pids)
    if shutil.which("ss"):
        try:
            result = subprocess.run(
                ["ss", "-ltnp", f"sport = :{port}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        pids = set()
        import re

        for match in re.finditer(r"pid=(\d+)", result.stdout or ""):
            pids.add(int(match.group(1)))
        return sorted(pids)
    return []


def port_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def health_ok(port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            request = (
                f"GET /healthz HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
            ).encode("ascii")
            sock.sendall(request)
            data = b""
            while len(data) < 256:
                chunk = sock.recv(256)
                if not chunk:
                    break
                data += chunk
            status = data.split(b"\r\n", 1)[0]
            return b" 200" in status
    except OSError:
        return False


def wait_health(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if health_ok(port):
            return True
        time.sleep(0.5)
    return False


def wait_port_free(port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not port_listening(port) and not port_listeners(port):
            return True
        time.sleep(0.3)
    return not port_listening(port) and not port_listeners(port)


def read_pid_file() -> dict | None:
    if not PID_FILE.exists():
        return None
    try:
        return json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_pid_file(record: dict) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    temporary = PID_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(PID_FILE)


def remove_pid_file() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


def tail_logs() -> None:
    for path in (ERR_LOG, OUT_LOG):
        if not path.exists():
            continue
        print(f"--- {path} ---")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-LOG_TAIL:]:
            print(line)


def http_json(port: int, path: str, timeout: float = 15.0):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}{path}", timeout=timeout) as response:
        return json.load(response)


def detached_spawn(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    options = {
        "cwd": str(cwd),
        "env": {**os.environ.copy(), **env},
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if IS_WINDOWS:
        options["creationflags"] = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def npm_command() -> str:
    return "npm.cmd" if IS_WINDOWS else "npm"


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def action_setup(args: argparse.Namespace) -> int:
    try:
        python = find_python(args.python)
    except EpicError:
        if args.no_uv or args.python:
            raise
        _bootstrap_python_with_uv()
        python = find_python(None)
    print(f"[setup] Python: {' '.join(python)}")

    venv = ROOT / ".venv"
    if not venv.exists():
        print("[setup] 创建虚拟环境 .venv ...")
        run([*python, "-m", "venv", str(venv)], check=True)

    venv_py = ensure_venv()
    print("[setup] 安装依赖 ...")
    run([str(venv_py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    run([str(venv_py), "-m", "pip", "install", "-e", f"{ROOT}[dev]"], check=True)

    if not args.skip_db:
        print("[setup] 初始化数据库 ...")
        run([str(venv_py), "-m", "app.init_db"], cwd=BACKEND, env=backend_env(), check=True)

    if not args.skip_build:
        print("[setup] 构建前端 ...")
        build_args = argparse.Namespace(skip_install=False)
        if action_build(build_args) != 0:
            raise EpicError("前端构建失败，请检查 Node.js 与 npm（需要 v22+）")

    print("[setup] 完成。启动：start（PowerShell/cmd/bash）或 python scripts/epic.py start")
    return 0


def action_start(args: argparse.Namespace) -> int:
    venv_py = ensure_venv()
    port = resolve_port(args.port)
    url = f"http://127.0.0.1:{port}"

    record = read_pid_file()
    if record:
        recorded = int(record.get("pid") or 0)
        if recorded and is_pid_alive(recorded) and health_ok(int(record.get("port") or port)):
            print(f"[start] 已在运行 (PID {recorded}) -> {url}")
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        print("[start] 清理失效的 PID 文件 ...")
        remove_pid_file()

    listeners = port_listeners(port)
    if listeners:
        ours = [pid for pid in listeners if is_our_process(pid)]
        if ours:
            print(f"[start] 端口 {port} 上已有本项目的服务在运行 (PID {', '.join(map(str, ours))})。")
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        raise EpicError(
            f"端口 {port} 已被进程 {', '.join(map(str, listeners))} 占用。"
            "请先结束该进程，或用 --port 指定其他端口。"
        )

    env = backend_env()
    if args.foreground or args.reload:
        print(f"[start] 前台运行 {url} （Ctrl+C 停止）")
        command = [
            str(venv_py),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ]
        if args.reload:
            command.append("--reload")
        return run(command, cwd=BACKEND, env=env).returncode

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        str(venv_py),
        "-m",
        "app.serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "info",
    ]
    print(f"[start] 后台启动 {url} ...")
    process = detached_spawn(command, cwd=BACKEND, env=env)
    write_pid_file(
        {
            "pid": process.pid,
            "server_pid": 0,
            "port": port,
            "started_at": _now(),
            "arguments": " ".join(command),
            "python": str(venv_py),
            "root": str(ROOT),
            "cwd": str(BACKEND),
        }
    )

    deadline = time.monotonic() + args.timeout
    ready = False
    server_pid = 0
    while time.monotonic() < deadline:
        if not is_pid_alive(process.pid):
            break
        if health_ok(port):
            listeners = port_listeners(port)
            tree = process_tree(process.pid)
            for listener in listeners:
                if listener in tree or is_our_process(listener):
                    server_pid = listener
                    break
            ready = True
            break
        time.sleep(0.5)

    if not ready:
        print("[start] 启动失败，最近日志：")
        tail_logs()
        stop_process_tree(process.pid)
        remove_pid_file()
        if port_listening(port):
            raise EpicError(
                f"服务未就绪，且端口 {port} 仍被占用（可能被其他进程抢占）。请运行 stop 或换端口。"
            )
        raise EpicError(f"服务未在 {args.timeout:g} 秒内就绪，已终止进程。请检查 {ERR_LOG}。")

    write_pid_file(
        {
            "pid": process.pid,
            "server_pid": server_pid,
            "port": port,
            "started_at": _now(),
            "arguments": " ".join(command),
            "python": str(venv_py),
            "root": str(ROOT),
            "cwd": str(BACKEND),
        }
    )
    if server_pid:
        print(f"[start] 已启动 (启动器 PID {process.pid}，服务 PID {server_pid}) -> {url}")
    else:
        print(f"[start] 已启动 (PID {process.pid}) -> {url}")
    print(f"[start] 日志： {OUT_LOG} / {ERR_LOG}")
    if not args.no_browser:
        webbrowser.open(url)
    return 0


def _stop_candidates(port: int, force: bool) -> bool:
    stopped = False
    record = read_pid_file()
    if record:
        candidates = []
        if int(record.get("server_pid") or 0) > 0:
            candidates.append(int(record["server_pid"]))
        if int(record.get("pid") or 0) > 0:
            candidates.append(int(record["pid"]))
        for candidate in dict.fromkeys(candidates):
            if not is_pid_alive(candidate):
                continue
            if is_our_process(candidate) or force:
                print(f"[stop] 停止进程 {candidate}（PID 文件）...")
                stopped = stop_process_tree(candidate) or stopped
            else:
                print(f"[stop] PID {candidate} 不是本项目的服务，跳过（确认后可加 --force）。")
    remove_pid_file()

    for listener in port_listeners(port):
        if not is_pid_alive(listener):
            continue
        if is_our_process(listener) or force:
            print(f"[stop] 停止进程 {listener}（端口 {port}）...")
            stopped = stop_process_tree(listener) or stopped
        else:
            print(f"[stop] 端口 {port} 被进程 {listener} 占用，但不是本项目服务；未停止。")
            print("[stop] 若确认可停止，执行：stop --force")
    return stopped


def action_stop(args: argparse.Namespace) -> int:
    port = resolve_port(args.port)
    stopped = _stop_candidates(port, args.force)
    time.sleep(0.4)
    if health_ok(port):
        print(f"[stop] 服务仍在响应 {port}。请检查是否为手动启动的 uvicorn（可加 --force）。")
        return 1
    if port_listening(port):
        print(f"[stop] 端口 {port} 仍被占用（进程可能正在退出），请稍后重试或检查子进程。")
        return 1
    if stopped:
        print(f"[stop] 已停止 {port}")
    else:
        print(f"[stop] 未发现运行中的服务（端口 {port} 空闲）")
    return 0


def action_restart(args: argparse.Namespace) -> int:
    port = resolve_port(args.port)
    stop_args = argparse.Namespace(port=port, force=args.force)
    code = action_stop(stop_args)
    if code != 0:
        return code
    if not wait_port_free(port, 15):
        raise EpicError(f"端口 {port} 在 15 秒内未释放，重启中止")
    start_args = argparse.Namespace(
        port=port,
        no_browser=args.no_browser,
        foreground=False,
        reload=False,
        timeout=60,
    )
    return action_start(start_args)


def action_status(args: argparse.Namespace) -> int:
    port = resolve_port(args.port)
    record = read_pid_file() or {}
    alive = bool(record.get("pid")) and is_pid_alive(int(record["pid"]))
    health = health_ok(port)
    listeners = port_listeners(port)
    payload = {
        "running": health,
        "port": port,
        "url": f"http://127.0.0.1:{port}",
        "pid": record.get("pid", 0),
        "server_pid": record.get("server_pid", 0),
        "pid_alive": alive,
        "listeners": listeners,
        "started_at": record.get("started_at", ""),
        "log_out": str(OUT_LOG),
        "log_err": str(ERR_LOG),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        state = "running" if health else "stopped"
        print(f"[status] {state} -> {payload['url']}")
        if record:
            print(
                f"[status] PID {payload['pid']} / server PID {payload['server_pid']} "
                f"/ alive {alive} / listeners {listeners or '[]'}"
            )
            print(f"[status] started_at {payload['started_at']}")
    return 0


def action_build(args: argparse.Namespace) -> int:
    if not (FRONTEND / "package.json").exists():
        raise EpicError("未找到 frontend/package.json")
    npm = npm_command()
    if not (FRONTEND / "node_modules").exists():
        if args.skip_install:
            raise EpicError("frontend/node_modules 缺失，已指定 --skip-install")
        print("[build] 安装前端依赖（首次）...")
        result = run([npm, "install", "--no-audit", "--no-fund"], cwd=FRONTEND)
        if result.returncode != 0:
            raise EpicError(f"npm install 失败 (exit {result.returncode})")

    temporary = FRONTEND / ".tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    env = {"TEMP": str(temporary), "TMP": str(temporary), "TMPDIR": str(temporary)}
    print("[build] 构建前端（vue-tsc + vite build）...")
    result = run([npm, "run", "build"], cwd=FRONTEND, env=env)
    if result.returncode != 0:
        raise EpicError(f"前端构建失败 (exit {result.returncode})")

    index_file = ROOT / "web" / "index.html"
    assets_dir = ROOT / "web" / "assets"
    if not index_file.exists():
        raise EpicError("构建产物缺失：web/index.html")
    if not assets_dir.exists():
        raise EpicError("构建产物缺失：web/assets")
    html = index_file.read_text(encoding="utf-8", errors="replace")
    if "/assets/" not in html:
        raise EpicError("web/index.html 未引用 /assets，构建产物异常")
    if "http://" in html or "https://" in html:
        external = [
            url
            for url in html.replace('"', " ").replace("'", " ").split()
            if url.startswith(("http://", "https://")) and "127.0.0.1" not in url
        ]
        if external:
            print(f"[build] WARN 构建产物包含外部 URL: {external[:3]}")
    files = [path for path in assets_dir.iterdir() if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    print(f"[build] 完成 -> web/index.html（{len(files)} 个资源，{total / 1024:,.0f} KB）")
    return 0


def action_dev(args: argparse.Namespace) -> int:
    ensure_venv()
    backend_port = resolve_port(args.backend_port)
    if not health_ok(backend_port):
        print("[dev] 后端未运行，先启动（无浏览器）...")
        start_args = argparse.Namespace(
            port=backend_port,
            no_browser=True,
            foreground=False,
            reload=False,
            timeout=60,
        )
        code = action_start(start_args)
        if code != 0:
            return code
    print(f"[dev] Vite dev server -> http://127.0.0.1:{args.port}")
    print(f"[dev] API 代理 -> http://127.0.0.1:{backend_port}/api")
    env = {"EPIC_PORT": str(backend_port)}
    return run(
        [npm_command(), "run", "dev", "--", "--port", str(args.port), "--strictPort"],
        cwd=FRONTEND,
        env=env,
    ).returncode


def _runtime_checks(port: int) -> int:
    try:
        health = http_json(port, "/api/system/health")
        acceptance = http_json(port, "/api/system/acceptance")
        quality = http_json(port, "/api/system/data-quality")
    except Exception as exc:  # noqa: BLE001 - runtime probe must not crash the gate
        print(f"[ci] 服务未运行，跳过运行时检查（{exc}）")
        return 2
    print(f"status: {health.get('status')}")
    print(f"version: {health.get('version')} llm: {health.get('llm_enabled')}")
    checks = acceptance.get("checks", [])
    failed = [check["name"] for check in checks if not check.get("passed")]
    print(
        f"acceptance: {acceptance.get('passed')} "
        f"{sum(1 for check in checks if check.get('passed'))}/{len(checks)}"
    )
    print(f"quality: {quality.get('summary')}")
    if failed:
        print(f"failed checks: {failed}")
    summary = quality.get("summary") or {}
    ok = health.get("status") == "ok" and bool(acceptance.get("passed")) and summary.get("failed") == 0
    return 0 if ok else 1


def action_ci(args: argparse.Namespace) -> int:
    venv_py = ensure_venv()
    env = backend_env(EPIC_ENV="test")
    failed = False

    if not args.skip_build:
        print("[ci] 前端构建 ...")
        if action_build(argparse.Namespace(skip_install=False)) != 0:
            failed = True

    if not args.skip_frontend_tests and (FRONTEND / "node_modules").exists():
        print("[ci] 前端测试 (vitest) ...")
        result = run([npm_command(), "run", "test"], cwd=FRONTEND)
        if result.returncode != 0:
            failed = True

    if not args.skip_lint:
        print("[ci] 静态检查 (scripts/lint.py) ...")
        result = run([str(venv_py), str(SCRIPTS / "lint.py")], cwd=ROOT, env=env)
        if result.returncode != 0:
            failed = True

    if not args.skip_tests:
        print("[ci] 单元/集成测试 ...")
        command = [str(venv_py), "-m", "pytest", "-q"]
        if args.coverage:
            command.extend(["--cov=app", "--cov-report=term-missing"])
        result = run(command, cwd=ROOT, env=env)
        if result.returncode != 0:
            failed = True

    if not args.skip_runtime:
        print("[ci] 运行时检查 (health / acceptance / quality) ...")
        port = resolve_port(args.port)
        code = _runtime_checks(port)
        if code not in (0, 2):
            failed = True

    print("[ci] FAILED" if failed else "[ci] PASSED")
    return 1 if failed else 0


def action_selfcheck(args: argparse.Namespace) -> int:
    return action_ci(args)


def action_check_acceptance(args: argparse.Namespace) -> int:
    venv_py = ensure_venv()
    env = backend_env(EPIC_ENV="test")
    if not args.skip_tests:
        print("[acceptance] 运行测试 ...")
        result = run([str(venv_py), "-m", "pytest", "-q"], cwd=ROOT, env=env)
        if result.returncode != 0:
            return 1
    print("[acceptance] 检查 DoD ...")
    code = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "with TestClient(app) as client:\n"
        "    client.post('/api/system/schedule-check', json={'wait': True, 'run_data': False, "
        "'run_downstream': False})\n"
        "    payload = client.get('/api/system/acceptance').json()\n"
        "print(json.dumps(payload, ensure_ascii=False))\n"
        "raise SystemExit(0 if payload.get('passed') else 1)\n"
    )
    result = run([str(venv_py), "-c", code], cwd=ROOT, env=env)
    print((result.stdout or "").strip())
    if result.returncode != 0:
        print("[acceptance] FAILED")
        return 1
    print("[acceptance] PASSED")
    return 0


def action_backup(args: argparse.Namespace) -> int:
    venv_py = ensure_venv()
    command = [str(venv_py), "-m", "app.backup"]
    if args.keep:
        command.extend(["--keep", str(args.keep)])
    return run(command, cwd=BACKEND, env=backend_env()).returncode


def _integrity_check(database: Path) -> str:
    connection = sqlite3.connect(str(database))
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "unknown"
    finally:
        connection.close()


def action_restore(args: argparse.Namespace) -> int:
    backup_root = DATA / "backup"
    if args.backup_dir:
        backup_dir = Path(args.backup_dir)
    else:
        candidates = sorted(
            (path for path in backup_root.iterdir() if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        ) if backup_root.exists() else []
        if not candidates:
            raise EpicError("未找到备份。请先运行 backup。")
        backup_dir = candidates[0]
    if not backup_dir.exists():
        raise EpicError(f"备份目录不存在: {backup_dir}")
    source_db = backup_dir / "epic.db"
    if not source_db.exists():
        raise EpicError(f"备份中缺少 epic.db: {backup_dir}")

    integrity = _integrity_check(source_db)
    print(f"source integrity_check: {integrity}")
    if integrity != "ok":
        raise EpicError(f"备份完整性检查失败: {source_db}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safety_dir = backup_root / f"pre-restore-{stamp}"
    target_db = DATA / "epic.db"
    target_config = ROOT / "config" / "default.yaml"
    print(f"[restore] backup dir: {backup_dir}")
    print(f"[restore] target db: {target_db}")
    print(f"[restore] safety copy: {safety_dir}")
    if args.dry_run:
        print("[restore] DryRun: validation only, nothing written.")
        return 0
    if not args.force:
        answer = input("Restore will overwrite the current database. Type YES to continue: ")
        if answer.strip() != "YES":
            print("Cancelled")
            return 1

    safety_dir.mkdir(parents=True, exist_ok=True)
    if target_db.exists():
        shutil.copy2(target_db, safety_dir / "epic.db")
    if target_config.exists():
        shutil.copy2(target_config, safety_dir / "default.yaml")

    shutil.copy2(source_db, target_db)
    source_config = backup_dir / "default.yaml"
    if source_config.exists():
        answer = "YES" if args.force else input(
            "Also restore config/default.yaml? Type YES to confirm: "
        )
        if answer.strip() == "YES":
            shutil.copy2(source_config, target_config)

    print("[restore] done. Restart the server and run selfcheck.")
    print(f"[restore] rollback copy: {safety_dir}")
    return 0


def _directory_size(path: Path) -> tuple[int, int]:
    files = 0
    total = 0
    if not path.exists():
        return files, total
    if path.is_file():
        return 1, path.stat().st_size
    for item in path.rglob("*"):
        if item.is_file():
            files += 1
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return files, total


def _format_size(size: int) -> str:
    if size >= 1024**3:
        return f"{size / 1024**3:.2f} GB"
    if size >= 1024**2:
        return f"{size / 1024**2:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


def _collect_maintenance_targets(include_raw: bool, include_logs: bool) -> list[tuple[str, Path, str]]:
    targets: list[tuple[str, Path, str]] = []
    for directory in sorted(DATA.glob("chrome-*")):
        if directory.is_dir():
            targets.append(("截图浏览器配置", directory, "删除（可重建）"))
    for png in sorted(DATA.glob("*.png")):
        if png.is_file():
            targets.append(("临时调试截图", png, "删除（docs/assets 有成品）"))
    for name, action in (("test", "删除（测试再生）"), ("scratch", "删除")):
        path = DATA / name
        if path.exists():
            targets.append(("调试残留", path, action))
    if PID_FILE.exists() and not port_listeners(resolve_port(None)):
        targets.append(("过期 PID 文件", PID_FILE, "删除（端口未监听）"))
    else:
        print(f"[skip] {PID_FILE}：端口仍有服务在监听，保留")
    for base in (BACKEND, ROOT / "tests", SCRIPTS):
        if base.exists():
            for cache in base.rglob("__pycache__"):
                targets.append(("Python 缓存", cache, "删除"))
    if include_raw:
        cutoff = datetime.now().date() - timedelta(days=30)
        raw_root = DATA / "raw"
        if raw_root.exists():
            for source in raw_root.iterdir():
                if not source.is_dir():
                    continue
                for day_dir in source.iterdir():
                    if not day_dir.is_dir():
                        continue
                    try:
                        parsed = datetime.strptime(day_dir.name, "%Y%m%d").date()
                    except ValueError:
                        continue
                    if parsed < cutoff:
                        targets.append(("原始快照（超期）", day_dir, "删除（早于 30 天）"))
    if include_logs:
        cutoff = datetime.now() - timedelta(days=7)
        for log in (DATA / "logs").glob("*.log") if (DATA / "logs").exists() else []:
            try:
                if datetime.fromtimestamp(log.stat().st_mtime) < cutoff:
                    targets.append(("过期日志", log, "删除（早于 7 天）"))
            except OSError:
                continue
    return targets


def action_maintain(args: argparse.Namespace) -> int:
    if args.dry_run and args.apply:
        raise EpicError("参数冲突：--dry-run 与 --apply 只能二选一")
    mode = "verify" if args.verify else ("apply" if args.apply else "dry-run")
    targets = _collect_maintenance_targets(args.include_raw, args.include_logs)
    rows = []
    for category, path, action in targets:
        files, size = _directory_size(path)
        if files == 0 and size == 0:
            continue
        rows.append((category, path, files, size, action))
    rows.sort(key=lambda row: row[3], reverse=True)
    for category, path, files, size, action in rows:
        print(f"[plan] {category}: {path} ({files} files, {_format_size(size)}) -> {action}")
    print(
        f"\n模式：{mode}    待清理：{len(rows)} 项 / {sum(row[2] for row in rows)} 个文件 / "
        f"{_format_size(sum(row[3] for row in rows))}"
    )

    if mode == "verify":
        data_files, data_size = _directory_size(DATA)
        print(f"data/ 当前体积：{_format_size(data_size)} / {data_files} 个文件")
        for keep in (DATA / "epic.db", DATA / "backup", DATA / "raw", DATA / "logs"):
            print(f"保留检查 {keep}：{'存在' if keep.exists() else '缺失！'}")
        return 0
    if mode == "dry-run":
        print("DryRun 未删除任何文件。确认后执行：maintain --apply")
        return 0

    failures = 0
    freed = 0
    for category, path, files, size, action in rows:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            freed += size
            print(f"[ok] {path}  {_format_size(size)}  {action}")
        except OSError as exc:
            failures += 1
            print(f"[fail] {path}: {exc}")
    print(f"\n完成：释放 {_format_size(freed)}")
    return 1 if failures else 0


def action_snapshot(args: argparse.Namespace) -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = DATA / "backups" / f"snapshot-{stamp}"
    destination.mkdir(parents=True, exist_ok=True)

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True).stdout.strip()
    head = run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip()
    (destination / "head.txt").write_text(f"branch={branch}\nhead={head}\n", encoding="utf-8")
    status = run(["git", "status", "--porcelain=v2", "--branch"], capture=True).stdout
    (destination / "status.txt").write_text(status, encoding="utf-8")
    run(["git", "diff", "HEAD", "--binary", f"--output={destination / 'worktree.patch'}"])
    run(["git", "diff", "--cached", "--binary", f"--output={destination / 'index.patch'}"])
    untracked_result = run(["git", "ls-files", "--others", "--exclude-standard"], capture=True)
    untracked = [line for line in untracked_result.stdout.splitlines() if line.strip()]
    (destination / "untracked-files.txt").write_text("\n".join(untracked), encoding="utf-8")
    for relative in untracked:
        source = ROOT / relative
        target = destination / "untracked" / relative
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source, target)
            except OSError as exc:
                print(f"[snapshot] WARN 无法复制 {relative}: {exc}")

    patch_size = (destination / "worktree.patch").stat().st_size if (destination / "worktree.patch").exists() else 0
    print(f"[snapshot] branch={branch} head={head}")
    print(f"[snapshot] 未跟踪文件 {len(untracked)} 个，worktree.patch {patch_size} 字节")
    print(f"[snapshot] 已写入 {destination}")
    print(f'[snapshot] 恢复：git apply "{destination / "worktree.patch"}"')
    return 0


SCREENSHOT_PAGES = (
    ("vue-overview", "/"),
    ("vue-overview-light", "/?theme=light"),
    ("vue-market", "/market"),
    ("vue-rates", "/rates"),
    ("vue-analysis", "/analysis"),
    ("vue-signals", "/signals"),
    ("vue-lenses", "/lenses"),
    ("vue-gold", "/gold"),
    ("vue-theses", "/theses"),
    ("vue-briefs", "/briefs"),
    ("vue-system", "/system"),
    ("vue-cycle", "/cycle"),
    ("vue-alerts", "/alerts"),
    ("vue-pipeline", "/pipeline"),
    ("vue-history", "/history"),
    ("vue-ledger", "/ledger"),
    ("vue-principles", "/principles"),
    ("vue-trades", "/trades"),
    ("vue-docs", "/docs"),
)


def find_browser() -> Path:
    candidates: list[Path] = []
    if IS_WINDOWS:
        roots = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        for root in filter(None, roots):
            base = Path(root)
            candidates.extend(
                [
                    base / "Google/Chrome/Application/chrome.exe",
                    base / "Microsoft/Edge/Application/msedge.exe",
                ]
            )
    else:
        for name in (
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
            "msedge",
        ):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise EpicError("未找到 Chrome/Edge，无法截图")


def action_screenshots(args: argparse.Namespace) -> int:
    browser = find_browser()
    out_dir = (ROOT / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = DATA / "test" / "tmp" / "chrome-profile"
    profile.mkdir(parents=True, exist_ok=True)
    err_log = DATA / "test" / "tmp" / "chrome.err.txt"
    pages = SCREENSHOT_PAGES
    if args.pages:
        wanted = {name.strip() for name in args.pages.split(",") if name.strip()}
        pages = tuple(page for page in SCREENSHOT_PAGES if page[0] in wanted)
    ok = 0
    for name, path in pages:
        shot = out_dir / f"{name}.png"
        url = f"{args.base_url}{path}"
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--no-first-run",
            "--disable-extensions",
            f"--user-data-dir={profile}",
            f"--window-size={args.width},{args.height}",
            f"--virtual-time-budget={args.budget_ms}",
            f"--screenshot={shot}",
            url,
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=args.budget_ms / 1000 + 30,
                check=False,
            )
            if shot.exists():
                print(f"[ok] {name} <- {path} ({shot.stat().st_size} bytes)")
                ok += 1
                continue
            err_log.write_text((result.stderr or "")[-4000:], encoding="utf-8")
            print(f"[fail] {name} <- {path} (exit {result.returncode})")
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"[fail] {name}: {exc}")
    print(f"[done] {ok}/{len(pages)} 张已写入 {out_dir}")
    return 0 if ok == len(pages) else 1


def action_lint(args: argparse.Namespace) -> int:
    python = sys.executable
    command = [python, str(SCRIPTS / "lint.py")]
    if args.quiet:
        command.append("--quiet")
    if args.json:
        command.append("--json")
    return run(command, cwd=ROOT, env=backend_env()).returncode


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--verbose", action="store_true", help="print extra detail")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="epic.py",
        description="EPIC cross-platform task runner (Windows PowerShell/cmd + Linux bash).",
    )
    parser.add_argument("--version", action="store_true", help="print the EPIC version and exit")
    subparsers = parser.add_subparsers(dest="action")

    setup = subparsers.add_parser("setup", help="bootstrap Python, venv, dependencies, DB and frontend")
    setup.add_argument("--python", default=None, help="explicit Python 3.11+ interpreter")
    setup.add_argument("--skip-build", action="store_true")
    setup.add_argument("--skip-db", action="store_true")
    setup.add_argument("--no-uv", action="store_true", help="disable the managed-Python bootstrap")
    setup.set_defaults(handler=action_setup)

    start = subparsers.add_parser("start", help="start the server (background by default)")
    start.add_argument("--foreground", action="store_true")
    start.add_argument("--reload", action="store_true")
    start.add_argument("--no-browser", action="store_true")
    start.add_argument("--port", type=int, default=0)
    start.add_argument("--timeout", type=float, default=60.0)
    start.set_defaults(handler=action_start)

    stop = subparsers.add_parser("stop", help="stop the server and free the port")
    stop.add_argument("--port", type=int, default=0)
    stop.add_argument("--force", action="store_true")
    stop.set_defaults(handler=action_stop)

    restart = subparsers.add_parser("restart", help="stop then start")
    restart.add_argument("--port", type=int, default=0)
    restart.add_argument("--no-browser", action="store_true")
    restart.add_argument("--force", action="store_true")
    restart.set_defaults(handler=action_restart)

    status = subparsers.add_parser("status", help="show PID/port/health status")
    status.add_argument("--port", type=int, default=0)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=action_status)

    build = subparsers.add_parser("build", help="build the Vue frontend into web/")
    build.add_argument("--skip-install", action="store_true")
    build.set_defaults(handler=action_build)

    dev = subparsers.add_parser("dev", help="run the Vite dev server (starts the backend if needed)")
    dev.add_argument("--port", type=int, default=DEFAULT_VITE_PORT)
    dev.add_argument("--backend-port", type=int, default=0)
    dev.add_argument("--no-browser", action="store_true", help="accepted for wrapper parity")
    dev.add_argument("--no-backend", action="store_true", help="accepted for wrapper parity")
    dev.set_defaults(handler=action_dev)

    ci = subparsers.add_parser("ci", help="frontend build + tests + lint + pytest + runtime checks")
    ci.add_argument("--skip-build", action="store_true")
    ci.add_argument("--skip-lint", action="store_true")
    ci.add_argument("--skip-tests", action="store_true")
    ci.add_argument("--skip-frontend-tests", action="store_true")
    ci.add_argument("--skip-runtime", action="store_true")
    ci.add_argument("--coverage", action="store_true")
    ci.add_argument("--port", type=int, default=0)
    ci.set_defaults(handler=action_ci)

    selfcheck = subparsers.add_parser("selfcheck", help="alias of ci")
    selfcheck.add_argument("--skip-build", action="store_true")
    selfcheck.add_argument("--skip-lint", action="store_true")
    selfcheck.add_argument("--skip-tests", action="store_true")
    selfcheck.add_argument("--skip-frontend-tests", action="store_true")
    selfcheck.add_argument("--skip-runtime", action="store_true")
    selfcheck.add_argument("--coverage", action="store_true")
    selfcheck.add_argument("--port", type=int, default=0)
    selfcheck.set_defaults(handler=action_selfcheck)

    acceptance = subparsers.add_parser("check-acceptance", help="run tests then the DoD acceptance endpoint")
    acceptance.add_argument("--skip-tests", action="store_true")
    acceptance.set_defaults(handler=action_check_acceptance)

    backup = subparsers.add_parser("backup", help="back up the database and config")
    backup.add_argument("--keep", type=int, default=0, help="retention count passed to app.backup")
    backup.set_defaults(handler=action_backup)

    restore = subparsers.add_parser("restore", help="restore the database/config from a backup")
    restore.add_argument("--backup-dir", default="")
    restore.add_argument("--force", action="store_true")
    restore.add_argument("--dry-run", action="store_true")
    restore.set_defaults(handler=action_restore)

    maintain = subparsers.add_parser("maintain", help="clean regenerable workspace artifacts")
    maintain.add_argument("--dry-run", action="store_true")
    maintain.add_argument("--apply", action="store_true")
    maintain.add_argument("--verify", action="store_true")
    maintain.add_argument("--include-raw", action="store_true")
    maintain.add_argument("--include-logs", action="store_true")
    maintain.set_defaults(handler=action_maintain)

    snapshot = subparsers.add_parser("snapshot", help="snapshot the git worktree before destructive operations")
    snapshot.set_defaults(handler=action_snapshot)

    screenshots = subparsers.add_parser("screenshots", help="capture headless Chrome/Edge screenshots")
    screenshots.add_argument("--base-url", default=f"http://127.0.0.1:{DEFAULT_PORT}")
    screenshots.add_argument("--out-dir", default="docs/assets/vue")
    screenshots.add_argument("--width", type=int, default=1600)
    screenshots.add_argument("--height", type=int, default=1150)
    screenshots.add_argument("--budget-ms", type=int, default=12000)
    screenshots.add_argument("--pages", default="", help="comma-separated page names")
    screenshots.set_defaults(handler=action_screenshots)

    lint = subparsers.add_parser("lint", help="run scripts/lint.py")
    lint.add_argument("--quiet", action="store_true")
    lint.add_argument("--json", action="store_true")
    lint.set_defaults(handler=action_lint)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        version_file = BACKEND / "app" / "__init__.py"
        for line in version_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                print(line.split("=", 1)[1].strip().strip('"'))
                return 0
        print("unknown")
        return 1
    if not getattr(args, "action", None):
        parser.print_help()
        return 2
    try:
        return int(args.handler(args))
    except EpicError as exc:
        print(f"[epic] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("[epic] interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
