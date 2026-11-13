"""Release hygiene: single-source version, lint gate, CI workflow present."""

from __future__ import annotations

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
