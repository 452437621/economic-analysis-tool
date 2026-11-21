"""Tencent quote and kline parser tests (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers import tencent

pytestmark = pytest.mark.unit


def _tencent_quote_line(code: str = "sh600000") -> str:
    parts = [""] * 40
    parts[0] = "1"
    parts[1] = "浦发银行"
    parts[2] = "600000"
    parts[3] = "10.78"
    parts[4] = "10.40"
    parts[5] = "10.45"
    parts[6] = "964157"
    parts[30] = "20261116161500"
    parts[31] = "0.38"
    parts[32] = "3.65"
    parts[33] = "10.78"
    parts[34] = "10.39"
    return f'v_{code}="' + "~".join(parts) + '";'


def test_parse_quotes_from_tencent_payload() -> None:
    text = _tencent_quote_line() + "\n" + _tencent_quote_line("usINX")
    quotes = tencent.parse_quotes(text, {"sh600000": "603993", "usINX": "SPX"})

    assert set(quotes) == {"603993", "SPX"}
    quote = quotes["603993"]
    assert quote.price == pytest.approx(10.78)
    assert quote.prev_close == pytest.approx(10.40)
    assert quote.open == pytest.approx(10.45)
    assert quote.high == pytest.approx(10.78)
    assert quote.low == pytest.approx(10.39)
    assert quote.volume == pytest.approx(964157)


def test_parse_quotes_skips_unknown_and_short_lines() -> None:
    text = 'v_sz000001="1~平安银行~000001~10.00";' + _tencent_quote_line()
    quotes = tencent.parse_quotes(text, {"sh600000": "603993"})
    assert set(quotes) == {"603993"}


TENCENT_KLINE_PAYLOAD = {
    "code": 0,
    "data": {
        "sh000300": {
            "day": [
                ["2026-11-13", "3984.77", "4000.10", "4010.00", "3970.55", "123456"],
                ["2026-11-16", "3984.77", "3979.80", "3997.40", "3959.93", "0"],
            ]
        }
    },
}


def test_parse_tencent_kline_bars() -> None:
    bars = tencent.parse_kline(TENCENT_KLINE_PAYLOAD, "sh000300")

    assert len(bars) == 2
    last = bars[-1]
    assert last.ts.day == 16
    assert last.open == pytest.approx(3984.77)
    assert last.close == pytest.approx(3979.80)
    assert last.high == pytest.approx(3997.40)
    assert last.low == pytest.approx(3959.93)


def test_parse_tencent_kline_prefers_qfq() -> None:
    payload = {
        "data": {
            "sh600000": {
                "day": [["2026-11-16", "1.00", "2.00", "2.10", "0.90", "1"]],
                "qfqday": [["2026-11-16", "1.00", "3.00", "3.10", "0.90", "1"]],
            }
        }
    }
    bars = tencent.parse_kline(payload, "sh600000")
    assert [bar.close for bar in bars] == [3.0]
