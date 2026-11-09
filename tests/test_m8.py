"""M8 tests: JGB and ECB rate parsers."""

from __future__ import annotations

from datetime import date

from app.ingest.providers.ecb import fetch_rates as fetch_ecb
from app.ingest.providers.jgb import fetch_rates as fetch_jgb

JGB_CSV = """Interest Rate,,,,,,,,,,,,,,,(Unit : %)
Date,1Y,2Y,3Y,4Y,5Y,6Y,7Y,8Y,9Y,10Y,15Y,20Y,25Y,30Y,40Y
2026/11/2,1.671,1.88,1.982,2.136,2.243,2.326,2.429,2.569,2.692,2.817,3.362,3.669,3.972,3.94,3.96
2026/11/4,1.680,1.90,2.000,2.150,2.260,2.340,2.440,2.580,2.700,2.830,3.380,3.680,3.980,3.95,3.97
"""


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        return None


class FakeJGBClient:
    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        return FakeResponse(JGB_CSV)


class FakeECBClient:
    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        series = "SR_2Y" if "SR_2Y" in url else "SR_10Y"
        value = "2.10" if series == "SR_2Y" else "2.65"
        csv_text = f"KEY,TIME_PERIOD,OBS_VALUE\nX,2026-11-05,{value}\nX,2026-11-06,{value}\n"
        return FakeResponse(csv_text)


def test_jgb_parser_extracts_2y_10y_30y():
    rates = fetch_jgb(FakeJGBClient(), start_year=2026)  # type: ignore[arg-type]
    assert rates["JP10Y"][-1].value == 2.83
    assert rates["JP10Y"][-1].ts.date() == date(2026, 11, 4)
    assert rates["JP2Y"][-1].value == 1.90
    assert rates["JP30Y"][-1].value == 3.95


def test_ecb_parser_extracts_de2y_de10y():
    rates = fetch_ecb(FakeECBClient(), start_year=2026)  # type: ignore[arg-type]
    assert rates["DE10Y"][-1].value == 2.65
    assert rates["DE10Y"][-1].ts.date() == date(2026, 11, 6)
    assert rates["DE2Y"][-1].value == 2.10
