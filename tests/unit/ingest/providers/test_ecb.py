"""European Central Bank rate parser tests (offline)."""

from __future__ import annotations

from datetime import date

import pytest

from app.ingest.providers.ecb import fetch_rates as fetch_ecb

pytestmark = pytest.mark.unit


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        return None


class FakeECBClient:
    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        series = "SR_2Y" if "SR_2Y" in url else "SR_10Y"
        value = "2.10" if series == "SR_2Y" else "2.65"
        csv_text = f"KEY,TIME_PERIOD,OBS_VALUE\nX,2026-11-05,{value}\nX,2026-11-06,{value}\n"
        return FakeResponse(csv_text)


def test_ecb_parser_extracts_de2y_de10y():
    rates = fetch_ecb(FakeECBClient(), start_year=2026)  # type: ignore[arg-type]
    assert rates["DE10Y"][-1].value == 2.65
    assert rates["DE10Y"][-1].ts.date() == date(2026, 11, 6)
    assert rates["DE2Y"][-1].value == 2.10
