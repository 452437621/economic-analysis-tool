"""Eastmoney quote/kline parsers and quote-provider fallbacks (offline)."""

from __future__ import annotations

import httpx
import pytest

from app.ingest.providers import eastmoney

pytestmark = pytest.mark.unit

EM_QUOTE = {
    "rc": 0,
    "data": {
        "f43": 1329,
        "f44": 1372,
        "f45": 1318,
        "f46": 1350,
        "f47": 2279676,
        "f48": 3059247286.0,
        "f57": "603993",
        "f58": "洛阳钼业",
        "f60": 1401,
        "f170": -514,
    },
}

EM_KLINE = {
    "data": {
        "klines": [
            "2026-11-05,13.90,14.01,14.05,13.80,1900000,2650000000.0,1.8",
            "2026-11-06,13.50,13.29,13.72,13.18,2279676,3059247286.0,4.0",
        ]
    }
}

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


def test_eastmoney_quote_and_kline():
    quote = eastmoney.parse_quote(EM_QUOTE, "603993")
    assert quote is not None
    assert quote.price == 13.29
    assert quote.prev_close == 14.01
    assert round(quote.change_pct, 2) == -5.14
    bars = eastmoney.parse_kline(EM_KLINE)
    assert len(bars) == 2
    assert bars[-1].close == 13.29
    assert bars[-1].volume == 2279676.0


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
