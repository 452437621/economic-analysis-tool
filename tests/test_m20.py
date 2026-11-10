"""M20: overseas/FX daily-bar coverage and Sina global parser."""

from __future__ import annotations

from app.ingest.providers import frankfurter
from app.ingest.providers.sina import parse_global_daily_jsonp
from app.ingest.symbols import SINA_GLOBAL_FUTURES


def test_parse_global_daily_jsonp():
    text = (
        'var _GC=([{"date":"2026-11-09","open":"4100.0","high":"4150.0",'
        '"low":"4090.0","close":"4133.1","volume":"0","position":"0"},'
        '{"date":"2026-11-10","open":"4133.0","high":"4156.2",'
        '"low":"4130.8","close":"4140.5","volume":"12","position":"34"}]);'
    )
    bars = parse_global_daily_jsonp(text)
    assert len(bars) == 2
    assert bars[-1].close == 4140.5
    assert bars[-1].volume == 12
    assert str(bars[-1].ts.date()) == "2026-11-10"


def test_foreign_futures_and_fx_are_mapped_for_daily_bars():
    assert {"GC", "SI", "CL", "BZ", "XAUUSD", "HG"} <= set(SINA_GLOBAL_FUTURES)
    assert {"USDJPY", "EURUSD", "GBPUSD", "USDCAD", "USDSEK", "USDCHF"} <= set(frankfurter.SYMBOLS)


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

