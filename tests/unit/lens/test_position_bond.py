"""Long-bond stop placement must follow the position side."""

from __future__ import annotations

import pytest

from app.lens.position import build_asset_plan

pytestmark = pytest.mark.unit


def _row(consensus: float, direction: str) -> dict:
    return {
        "id": "long_bond",
        "label": "长债",
        "symbol": "US30Y",
        "last": 4.50,
        "consensus": consensus,
        "direction": direction,
        "agreement": "共振",
    }


def test_long_bond_long_stops_on_yield_up() -> None:
    plan = build_asset_plan(_row(0.8, "up"), panel=None)
    assert plan["side"] == "long"
    assert plan["stop_level"] > 4.50
    assert "上行" in plan["stop_note"]


def test_long_bond_short_stops_on_yield_down() -> None:
    plan = build_asset_plan(_row(-0.8, "down"), panel=None)
    assert plan["side"] == "short"
    assert plan["stop_level"] < 4.50
    assert "下行" in plan["stop_note"]
