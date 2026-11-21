"""Release hygiene: single-source version, lint gate, CI workflow present."""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest
import yaml

from tests.helpers import ROOT

pytestmark = [pytest.mark.release, pytest.mark.slow]


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
        encoding="utf-8",
        errors="replace",
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


def test_cross_platform_lifecycle_scripts():
    """Every lifecycle action ships PowerShell, CMD and bash wrappers."""
    scripts = ROOT / "scripts"
    for action in ("start", "stop", "restart", "status", "setup", "build"):
        for extension in (".ps1", ".cmd", ".sh"):
            assert (scripts / f"{action}{extension}").exists(), f"{action}{extension}"
    for name in ("start.ps1", "stop.ps1", "restart.ps1", "status.ps1"):
        path = scripts / name
        assert path.read_bytes().startswith(b"\xef\xbb\xbf"), f"{name} needs a UTF-8 BOM"

    start = (scripts / "start.ps1").read_text(encoding="utf-8-sig")
    assert "Foreground" in start and "NoBrowser" in start
    stop = (scripts / "stop.ps1").read_text(encoding="utf-8-sig")
    assert "Force" in stop

    core = (scripts / "epic.py").read_text(encoding="utf-8")
    assert "app.serve" in core, "background start must launch the detached launcher"
    assert "server_pid" in core, "stop must prefer the real server PID"
    assert (ROOT / "backend" / "app" / "serve.py").exists()


def test_detached_launcher_module_runs():
    result = subprocess.run(
        [sys.executable, "-m", "app.serve", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
        cwd=ROOT / "backend",
        env={**os.environ, "PYTHONPATH": str(ROOT / "backend")},
    )
    assert result.returncode == 0, result.stderr
    assert "--port" in result.stdout
