"""Release hygiene: single-source version, lint gate, CI workflow present."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert match, "pyproject.toml has no version"
    return match.group(1)


def test_version_is_single_sourced():
    from app import __version__

    from app.platform.config import settings

    assert _pyproject_version() == __version__
    assert settings.app_version == __version__


def test_lint_gate_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lint.py"), "--quiet"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ci_workflow_is_valid_yaml():
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.exists()
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    assert data["jobs"]["quality"]["steps"]
    step_names = [step.get("name", "") for step in data["jobs"]["quality"]["steps"]]
    assert any("lint" in name.lower() for name in step_names)
    assert any("test" in name.lower() for name in step_names)


def test_scripts_expose_ci_entrypoints():
    for name in ("ci.ps1", "selfcheck.ps1", "lint.py", "backup.ps1", "restore.ps1"):
        assert (ROOT / "scripts" / name).exists(), name


def test_windows_lifecycle_scripts():
    """One-click start/stop/restart must exist, share helpers and document usage."""
    scripts = ROOT / "scripts"
    for name in ("start.ps1", "stop.ps1", "restart.ps1", "_common.ps1"):
        path = scripts / name
        assert path.exists(), name
        assert path.read_bytes().startswith(b"\xef\xbb\xbf"), f"{name} needs a UTF-8 BOM for PowerShell 5.1"

    start = (scripts / "start.ps1").read_text(encoding="utf-8-sig")
    assert "Foreground" in start and "NoBrowser" in start
    assert "app.serve" in start, "background start must launch the detached launcher"
    assert "Win32_Process" in start, "background start must detach via WMI"

    stop = (scripts / "stop.ps1").read_text(encoding="utf-8-sig")
    assert "server_pid" in stop, "stop must prefer the real server PID"
    assert "Force" in stop

    assert (ROOT / "backend" / "app" / "serve.py").exists()


def test_detached_launcher_module_runs():
    result = subprocess.run(
        [sys.executable, "-m", "app.serve", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=ROOT / "backend",
        env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
    )
    assert result.returncode == 0, result.stderr
    assert "--port" in result.stdout
