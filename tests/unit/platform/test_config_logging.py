"""Runtime settings and logging bootstrap."""

from __future__ import annotations

import pytest

import logging

from app import __version__
from app.platform.config import ROOT_DIR, Settings, settings
from app.platform.logging import setup_logging

pytestmark = pytest.mark.unit


def test_settings_version_matches_package() -> None:
    assert settings.app_version == __version__
    assert ROOT_DIR.name == "economic-analysis-tool"


def test_settings_paths_live_inside_workspace() -> None:
    assert settings.data_dir.is_absolute()
    assert settings.log_path.is_absolute()
    assert str(settings.data_dir).startswith(str(ROOT_DIR))


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("EPIC_PORT", "8899")
    monkeypatch.setenv("EPIC_ACCOUNT_EQUITY", "250000")
    custom = Settings()
    assert custom.port == 8899
    assert custom.account_equity == 250000


def test_setup_logging_creates_file(tmp_path) -> None:
    log_dir = tmp_path / "logs"
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    if hasattr(root, "_epic_configured"):
        delattr(root, "_epic_configured")
    setup_logging(log_dir, level=logging.DEBUG)
    logger = logging.getLogger("epic.test")
    logger.info("hello")
    for handler in logging.getLogger().handlers:
        handler.flush()
    files = list(log_dir.glob("*.log"))
    assert files
    assert any("hello" in path.read_text(encoding="utf-8", errors="replace") for path in files)
