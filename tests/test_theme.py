"""Static checks for the multi-theme dashboard."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")


def test_settings_button_and_palettes_exist():
    assert 'id="settings-btn"' in HTML
    assert 'id="settings-modal"' in HTML
    assert 'data-theme-mode="dark"' in HTML
    assert 'data-theme-mode="light"' in HTML
    assert 'data-theme-mode="sepia"' in HTML
    assert 'data-theme-mode="auto"' in HTML
    assert 'data-updown-mode="red"' in HTML
    assert 'data-updown-mode="green"' in HTML
    assert 'data-updown="red"' in HTML


def test_theme_and_updown_persistence_hooks():
    assert "localStorage" in HTML
    assert "THEME_KEY" in HTML
    assert "UPDOWN_KEY" in HTML
    assert "prefers-color-scheme" in HTML
    assert "--up-color" in HTML
    assert "--down-color" in HTML
