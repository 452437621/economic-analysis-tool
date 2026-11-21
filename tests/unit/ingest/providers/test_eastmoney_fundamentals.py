"""Eastmoney fundamentals provider: parsing, pagination and normalization."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.ingest.providers import eastmoney_fundamentals as em

pytestmark = pytest.mark.unit


class _Response:
    def __init__(self, payload, *, jsonp_text: str | None = None):
        self._payload = payload
        self.text = jsonp_text or ""

    def raise_for_status(self):
        return None

    def json(self):
        if self.text:
            raise json.JSONDecodeError("expecting value", self.text, 0)
        return self._payload


class _Client:
    def __init__(self, pages):
        self.pages = pages
        self.requested: list[int] = []

    def get(self, _url, params=None, **_kwargs):
        page = int((params or {}).get("pageNumber", 1))
        self.requested.append(page)
        return _Response(self.pages(page))


def test_fetch_kline_parses_fields():
    def pages(_page):
        return {
            "data": {
                "klines": [
                    "2026-01-02,10.0,10.5,10.8,9.8,12345,120000000,10.0,5.0,0.5,2.0",
                ]
            }
        }

    rows = em.fetch_kline(_Client(pages), "1.603993")
    assert len(rows) == 1
    payload = rows[0]["payload"]
    assert rows[0]["as_of"] == date(2026, 1, 2)
    assert payload["open"] == 10.0
    assert payload["close"] == 10.5
    assert payload["high"] == 10.8
    assert payload["pct_chg"] == 5.0


def test_fetch_datacenter_paginates_until_last_page():
    def pages(number):
        return {"result": {"data": [{"REPORT_DATE": f"2025-0{number}-01"}], "pages": 2}}

    client = _Client(pages)
    rows = em.fetch_datacenter(client, "RPT_TEST", max_pages=5)
    assert len(rows) == 2
    assert client.requested == [1, 2]


def test_fetch_datacenter_accepts_jsonp_payload():
    class JsonpClient:
        def get(self, _url, params=None, **_kwargs):
            return _Response(None, jsonp_text='cb({"result":{"data":[{"A":1}],"pages":1}})')

    rows = em.fetch_datacenter(JsonpClient(), "RPT_TEST")
    assert rows == [{"A": 1}]


def test_merge_raw_close_keeps_unadjusted_prices():
    adjusted = [{"as_of": date(2026, 1, 2), "row_key": "default", "payload": {"close": 10.5, "open": 10.0}}]
    raw = [{"as_of": date(2026, 1, 2), "row_key": "default", "payload": {"close": 11.0, "open": 10.6}}]
    merged = em.merge_raw_close(adjusted, raw)
    assert merged[0]["payload"]["close"] == 10.5
    assert merged[0]["payload"]["close_raw"] == 11.0
    assert merged[0]["payload"]["open_raw"] == 10.6


def test_normalize_valuation_and_dividends():
    valuation = em.normalize_valuation(
        [
            {
                "TRADE_DATE": "2026-01-02 00:00:00",
                "CLOSE_PRICE": "10.5",
                "TOTAL_MARKET_CAP": "220000000000",
                "TOTAL_SHARES": "21400000000",
                "PE_TTM": "12.5",
                "PB_MRQ": "2.1",
                "PS_TTM": "1.2",
            }
        ]
    )
    assert valuation[0]["as_of"] == date(2026, 1, 2)
    assert valuation[0]["payload"]["pe_ttm"] == 12.5
    assert valuation[0]["payload"]["pb_mrq"] == 2.1

    dividends = em.normalize_dividends(
        [
            {
                "REPORT_DATE": "2026-03-01",
                "EX_DIVIDEND_DATE": "2026-05-27",
                "PRETAX_BONUS_RMB": "2.86",
            }
        ]
    )
    assert dividends[0]["row_key"] == "2026-05-27"
    assert dividends[0]["payload"]["pretax_bonus_rmb"] == 2.86


def test_normalize_helpers_tolerate_missing_and_dirty_values():
    assert em._num("-") is None
    assert em._num("abc") is None
    assert em._date("not-a-date") is None
    assert em.normalize_valuation([{"TRADE_DATE": None}]) == []
    assert em.normalize_financials([{"REPORT_DATE": None}]) == []
