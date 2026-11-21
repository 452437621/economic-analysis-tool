"""Regression: the FRED fallback inside ``collect_macro`` must open a client.

The fallback used to reference the ``client`` name even though ``collect_macro``
never opened an ``HttpClient`` context, so every fallback attempt degraded with
``NameError`` and never fetched anything.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ingest import pipeline
from app.ingest.collectors import macro as macro_collector
from app.ingest.contracts import MacroPoint
from app.ingest.providers import fed_h6, fed_h41, fred, imf_datamapper, treasury_fiscal, worldbank
from app.models.base import Base

pytestmark = [pytest.mark.unit, pytest.mark.db]


class _FakeHttpClient:
    instances: list[_FakeHttpClient] = []

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.entered = False
        _FakeHttpClient.instances.append(self)

    def __enter__(self) -> _FakeHttpClient:
        self.entered = True
        return self

    def __exit__(self, *args) -> bool:  # noqa: ANN002
        return False


def test_collect_macro_fred_fallback_opens_http_client(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'macro-fred.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    _FakeHttpClient.instances.clear()

    monkeypatch.setattr(macro_collector, "SessionLocal", factory)
    monkeypatch.setattr(
        macro_collector,
        "settings",
        SimpleNamespace(fred_enabled=True, env="local"),
    )
    monkeypatch.setattr(macro_collector, "HttpClient", _FakeHttpClient)

    # Keep every other provider offline; the H.4.1/H.6 snapshots return nothing so
    # all FX/balance-sheet fallback codes are considered missing.
    monkeypatch.setattr(imf_datamapper, "fetch", lambda *args, **kwargs: {})
    monkeypatch.setattr(treasury_fiscal, "fetch_debt_to_penny", lambda *args, **kwargs: [])
    monkeypatch.setattr(treasury_fiscal, "fetch_mts", lambda *args, **kwargs: [])
    monkeypatch.setattr(worldbank, "fetch", lambda *args, **kwargs: {})
    monkeypatch.setattr(fed_h41, "fetch_current", lambda *args, **kwargs: {"asof": date(2026, 11, 11), "values": {}})
    monkeypatch.setattr(fed_h41, "fetch_history", lambda *args, **kwargs: {})
    monkeypatch.setattr(fed_h6, "fetch_current", lambda *args, **kwargs: {})
    monkeypatch.setattr(fed_h6, "fetch_history", lambda *args, **kwargs: {})

    calls: list[tuple[object, list[str]]] = []

    def fake_fetch_many(client, codes, *, start_date=None):  # noqa: ANN001, ANN202
        calls.append((client, list(codes)))
        return {
            "US_M2": [
                MacroPoint(
                    code="US_M2",
                    ts=datetime(2026, 9, 1, tzinfo=timezone.utc),
                    value=23.4e12,
                )
            ]
        }

    monkeypatch.setattr(fred, "fetch_many", fake_fetch_many)

    stats = pipeline.collect_macro()

    assert calls, "FRED fallback was never attempted"
    assert len(calls) == 1
    client, codes = calls[0]
    assert isinstance(client, _FakeHttpClient)
    assert client.entered
    assert "US_M2" in codes
    assert stats["fred_fallback"] == 1
    assert stats["fred_codes"] == ["US_M2"]
    assert not any(reason.startswith("fred: ") for reason in stats["degraded_reasons"])
    assert not any("name 'client'" in reason for reason in stats["degraded_reasons"])

    engine.dispose()
