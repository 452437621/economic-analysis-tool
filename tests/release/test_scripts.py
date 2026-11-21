"""Cross-platform script entry points: one action, three wrappers, one core."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

from tests.helpers import ROOT

pytestmark = pytest.mark.release

SCRIPTS = ROOT / "scripts"
EPIC = SCRIPTS / "epic.py"


def _load_epic():
    spec = importlib.util.spec_from_file_location("epic_runner", EPIC)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACTIONS = _load_epic().ACTIONS


def test_every_action_has_three_wrappers() -> None:
    for action in ACTIONS:
        for extension in (".ps1", ".cmd", ".sh"):
            path = SCRIPTS / f"{action}{extension}"
            assert path.exists(), f"missing {path.name}"
            assert path.stat().st_size > 0


def test_powershell_wrappers_are_utf8_and_delegate() -> None:
    for action in ACTIONS:
        path = SCRIPTS / f"{action}.ps1"
        data = path.read_bytes()
        assert data.startswith(b"\xef\xbb\xbf"), f"{path.name} must be UTF-8 BOM"
        text = data.decode("utf-8-sig")
        assert "epic.py" in text
        assert f'"{action}"' in text
        assert "$LASTEXITCODE" in text


def test_cmd_wrappers_are_ascii_and_delegate() -> None:
    for action in ACTIONS:
        path = SCRIPTS / f"{action}.cmd"
        data = path.read_bytes()
        assert all(byte < 0x80 for byte in data), f"{path.name} must be ASCII"
        text = data.decode("ascii")
        assert text.startswith("@echo off")
        assert "epic.py" in text
        assert f" {action} " in f" {text} "
        assert "%ERRORLEVEL%" in text


def test_shell_wrappers_use_lf_and_exec() -> None:
    for action in ACTIONS:
        path = SCRIPTS / f"{action}.sh"
        data = path.read_bytes()
        assert b"\r\n" not in data, f"{path.name} must use LF"
        text = data.decode("utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert "epic.py" in text
        assert f" {action} " in f" {text} "
        assert "exec " in text


def test_start_and_stop_wrappers_expose_legacy_flags() -> None:
    start = (SCRIPTS / "start.ps1").read_text(encoding="utf-8-sig")
    for flag in ("Foreground", "Reload", "NoBrowser", "Port"):
        assert flag in start
    stop = (SCRIPTS / "stop.ps1").read_text(encoding="utf-8-sig")
    assert "Force" in stop and "Port" in stop


def test_core_contains_platform_lifecycle_markers() -> None:
    text = EPIC.read_text(encoding="utf-8")
    for marker in ("DETACHED_PROCESS", "start_new_session", "app.serve", "server_pid", "--force"):
        assert marker in text


def test_dead_scripts_are_gone() -> None:
    assert not (SCRIPTS / "_common.ps1").exists(), "old shared PowerShell helper must be removed"
    assert not (ROOT / "backend" / "app" / "jobs" / "catchup.py").exists()


def test_every_action_help_works() -> None:
    for action in ACTIONS:
        result = subprocess.run(
            [sys.executable, str(EPIC), action, "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, f"{action}: {result.stderr}"


def test_status_json_runs_without_server() -> None:
    result = subprocess.run(
        [sys.executable, str(EPIC), "status", "--json", "--port", "63999"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"running"' in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="bash syntax check is POSIX-only")
def test_shell_wrappers_parse_with_bash() -> None:
    bash = shutil_which("bash")
    if not bash:
        pytest.skip("bash not installed")
    for action in ACTIONS:
        result = subprocess.run(
            [bash, "-n", str(SCRIPTS / f"{action}.sh")],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)
