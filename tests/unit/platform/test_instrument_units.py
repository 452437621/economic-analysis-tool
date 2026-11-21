"""Instrument display-unit resolution."""

from __future__ import annotations

import pytest

from app.platform.instrument_units import UNIT_BY_SYMBOL, resolve_unit

pytestmark = pytest.mark.unit


def test_static_map_is_used_without_override() -> None:
    assert resolve_unit("AU", None) == "元/克"
    assert resolve_unit("XAUUSD", {}) == "美元/盎司"


def test_database_override_wins() -> None:
    assert resolve_unit("AU", {"unit": "自定义单位"}) == "自定义单位"


def test_unknown_symbol_returns_none() -> None:
    assert resolve_unit("NOT_A_SYMBOL", None) is None
    assert "NOT_A_SYMBOL" not in UNIT_BY_SYMBOL
