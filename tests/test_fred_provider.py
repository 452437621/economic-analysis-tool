"""FRED CSV backup provider (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers import fred
from app.ingest.providers.errors import ProviderError

CSV = """observation_date,DGS10
2026-11-18,4.12
2026-11-19,.
2026-11-20,4.08
"""

WALCL = """observation_date,WALCL
2026-11-12,6759000
2026-11-19,6765000
"""


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict] = []

    def get(self, url, *, params=None):  # noqa: ANN001, ANN201
        self.calls.append({"url": url, "params": params})
        return FakeResponse(self._text)


def test_parse_csv_skips_missing_values():
    points = fred.parse_series_csv(CSV, "US10Y", fred.FRED_SERIES["US10Y"])
    assert len(points) == 2
    assert points[-1].value == 4.08
    assert points[-1].ts.date().isoformat() == "2026-11-20"


def test_fetch_scales_balance_sheet_millions_to_dollars():
    client = FakeClient(WALCL)
    points = fred.fetch_series(client, "US_FED_ASSETS")
    assert points[-1].value == pytest.approx(6765000 * 1e6)
    assert client.calls[0]["params"]["id"] == "WALCL"


def test_unknown_code_raises_provider_error():
    with pytest.raises(ProviderError):
        fred.fetch_series(FakeClient(CSV), "NOT_MAPPED")


def test_empty_response_raises_provider_error():
    with pytest.raises(ProviderError):
        fred.fetch_series(FakeClient("observation_date,DGS10\n"), "US10Y")
