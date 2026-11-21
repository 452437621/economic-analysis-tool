"""Eastmoney calendar parser tests (offline)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingest.providers.eastmoney_calendar import classify_importance, fetch_calendar

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeCalendarClient:
    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        return FakeResponse(
            {
                "result": {
                    "data": [
                        {
                            "START_DATE": "2026-11-09 09:30:00",
                            "FE_NAME": "中国:CPI:同比(报告期:2026年10月)",
                            "FE_TYPE": "经济数据",
                            "CITY": "中国",
                            "FE_CODE": "1",
                        },
                        {
                            "START_DATE": "2026-11-10 21:30:00",
                            "FE_NAME": "美国:初请失业金人数",
                            "FE_TYPE": "经济数据",
                            "CITY": "美国",
                            "FE_CODE": "2",
                        },
                    ]
                }
            }
        )


def test_calendar_parser_converts_cst_to_utc_and_scores_importance():
    events = fetch_calendar(FakeCalendarClient(), start=datetime(2026, 11, 9).date(), end=datetime(2026, 11, 20).date())
    assert len(events) == 2
    first = events[0]
    assert first["country"] == "中国"
    assert first["importance"] == 3  # CPI is high-impact
    assert first["ts_utc"].astimezone(timezone.utc).hour == 1  # 09:30 CST -> 01:30 UTC
    assert classify_importance("美国:非农就业人口") == 3
    assert classify_importance("某行业会议") == 2
