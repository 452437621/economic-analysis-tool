"""US Treasury curve CSV and breakeven parser tests (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers import treasury

pytestmark = pytest.mark.unit

TREASURY_NOMINAL = (
    'Date,"1 Mo","2 Mo","3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"\n'
    "11/06/2026,4.02,4.15,4.19,4.23,4.33,4.50,4.55,4.60,4.70,4.84,5.10,5.20\n"
    "11/05/2026,4.01,4.14,4.18,4.22,4.32,4.49,4.54,4.59,4.69,4.83,5.09,5.19\n"
)
TREASURY_REAL = (
    'Date,"5 YR","7 YR","10 YR","20 YR","30 YR"\n'
    "11/06/2026,2.35,2.48,2.63,2.91,3.07\n"
    "11/05/2026,2.33,2.46,2.60,2.90,3.05\n"
)


def test_treasury_curves_and_breakevens():
    nominal = treasury.parse_curve_csv(TREASURY_NOMINAL, treasury.NOMINAL_COLUMNS)
    real = treasury.parse_curve_csv(TREASURY_REAL, treasury.REAL_COLUMNS)
    assert nominal["US10Y"][-1].value == 4.84
    assert real["US10Y_REAL"][-1].value == 2.63
    merged = {**nominal, **real}
    treasury.add_breakevens(merged)
    assert merged["US10Y_BE"][-1].value == 2.21
    assert merged["US5Y_BE"][-1].value == 2.25
