"""Frankfurter FX daily rate parser tests (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers import frankfurter

pytestmark = pytest.mark.unit


def test_frankfurter_parse_rates():
    payload = {
        "rates": {
            "2026-11-09": {
                "JPY": 158.0,
                "EUR": 0.85,
                "GBP": 0.80,
                "CAD": 1.40,
                "SEK": 9.80,
                "CHF": 0.82,
            }
        }
    }
    bars = frankfurter.parse_rates(payload)
    assert bars["USDJPY"][0].close == 158.0
    assert round(bars["EURUSD"][0].close, 4) == round(1 / 0.85, 4)
    assert round(bars["GBPUSD"][0].close, 4) == round(1 / 0.80, 4)
    assert bars["USDCAD"][0].close == 1.40
