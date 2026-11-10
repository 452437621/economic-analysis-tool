"""Static UI checks for section navigation and drag-to-order watchlist."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")


def test_section_navigation_present():
    assert 'id="section-nav"' in HTML
    assert "initSectionNav" in HTML
    assert "scroll-margin-top" in HTML


def test_watchlist_drag_mode_present():
    assert 'id="watch-edit-btn"' in HTML
    assert 'id="watch-save-btn"' in HTML
    assert "attachWatchDnD" in HTML
    assert "/api/watchlist/reorder" in HTML
    assert "draggable=" in HTML


def test_history_modal_and_sofr_cards_present():
    assert 'id="history-modal"' in HTML
    assert "openHistory" in HTML
    assert "SOFR_EFFR" in HTML
    assert "initHistoryRanges" in HTML

