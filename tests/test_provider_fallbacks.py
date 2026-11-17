"""Offline tests for quote-provider fallbacks (Eastmoney trends, Tencent)."""

from __future__ import annotations

import httpx
import pytest

from app.ingest.providers import eastmoney, tencent

TREND_PAYLOAD = {
    "rc": 0,
    "data": {
        "preClose": 4016.29,
        "trends": [
            "2026-11-16 09:30,4017.00",
            "2026-11-16 14:59,3979.90",
            "2026-11-16 15:00,3979.80",
        ],
    },
}


class FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=httpx.Request("GET", "https://example.invalid"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        assert self._payload is not None
        return self._payload


class FakeClient:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict | None, int | None]] = []

    def get(self, url, *, headers=None, params=None, retries=None):  # noqa: ANN001, ANN201
        self.calls.append((url, params, retries))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _reset_breaker():
    eastmoney.reset_quote_breaker()
    yield
    eastmoney.reset_quote_breaker()


def test_parse_trend_quote_uses_last_point_and_preclose() -> None:
    quote = eastmoney.parse_trend_quote(TREND_PAYLOAD, "000300")
    assert quote is not None
    assert quote.price == pytest.approx(3979.80)
    assert quote.prev_close == pytest.approx(4016.29)
    assert quote.delay_sec == 60


def test_parse_trend_quote_handles_empty_payload() -> None:
    assert eastmoney.parse_trend_quote({"data": {}}, "000300") is None
    assert eastmoney.parse_trend_quote({"rc": 0, "data": None}, "000300") is None


def test_fetch_quote_falls_back_to_trends_when_snapshot_breaks() -> None:
    client = FakeClient(
        [
            httpx.RemoteProtocolError("Server disconnected without sending a response."),
            FakeResponse(TREND_PAYLOAD),
        ]
    )
    quote = eastmoney.fetch_quote(client, "1.000300", "000300")

    assert quote is not None
    assert quote.price == pytest.approx(3979.80)
    assert client.calls[0][0] == eastmoney.QUOTE_URL
    assert client.calls[0][2] == 1  # 主接口只试一次，快速失败
    assert client.calls[1][0] == eastmoney.TRENDS_URL


def test_fetch_quote_skips_snapshot_while_breaker_open() -> None:
    assert eastmoney.fetch_quote(
        FakeClient([httpx.RemoteProtocolError("boom"), FakeResponse(TREND_PAYLOAD)]),
        "1.000300",
        "000300",
    )
    assert eastmoney.quote_api_blocked() is True

    client = FakeClient([FakeResponse(TREND_PAYLOAD)])
    quote = eastmoney.fetch_quote(client, "1.000300", "000300")

    assert quote is not None
    assert [call[0] for call in client.calls] == [eastmoney.TRENDS_URL]


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
