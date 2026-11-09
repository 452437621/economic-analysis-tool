"""Static checks for the multi-theme dashboard."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")


def test_theme_selector_and_palettes_exist():
    assert 'id="theme-select"' in HTML
    assert 'data-theme="light"' in HTML
    assert 'data-theme="sepia"' in HTML
    assert 'value="auto"' in HTML


def test_theme_persistence_hooks():
    assert "localStorage" in HTML
    assert "THEME_KEY" in HTML
    assert "prefers-color-scheme" in HTML
    assert "?theme=" not in HTML or "URLSearchParams" in HTML
