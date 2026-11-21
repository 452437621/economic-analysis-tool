"""Symbol registry coverage and symbol mapping helpers."""

from __future__ import annotations

import pytest

from app.ingest.providers import frankfurter
from app.ingest.symbols import EM_DAILY_SECID, SINA_GLOBAL_FUTURES, compute_dxy

pytestmark = pytest.mark.unit


def test_dxy_daily_coverage_configured():
    assert EM_DAILY_SECID.get("DXY") == "100.UDI"
    assert EM_DAILY_SECID.get("USDCNH") == "133.USDCNH"
    assert EM_DAILY_SECID.get("SPX") == "100.SPX"
    from app.ingest.symbols import SINA_HF

    assert SINA_HF.get("AL_LME") == "hf_AHD"


def test_dxy_proxy():
    prices = {
        "EURUSD": 1.1139,
        "USDJPY": 158.41,
        "GBPUSD": 1.3355,
        "USDCAD": 1.4125,
        "USDSEK": 9.8842,
        "USDCHF": 0.8194,
    }
    dxy = compute_dxy(prices)
    assert dxy is not None
    assert 95 < dxy < 110
    prices.pop("USDCHF")
    assert compute_dxy(prices) is None


def test_foreign_futures_and_fx_are_mapped_for_daily_bars():
    assert {"GC", "SI", "CL", "BZ", "XAUUSD", "HG"} <= set(SINA_GLOBAL_FUTURES)
    assert {"USDJPY", "EURUSD", "GBPUSD", "USDCAD", "USDSEK", "USDCHF"} <= set(frankfurter.SYMBOLS)
