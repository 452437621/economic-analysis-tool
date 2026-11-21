"""System daily-bar fallback keeps real OHLC and volume."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingest.collectors.topics import _seed_from_system
from app.models.core import Instrument, MarketBar
from app.topics import bars
from app.topics.config import get_topic
from tests.helpers import memory_db

pytestmark = [pytest.mark.unit, pytest.mark.db]


def _seed_bars(session) -> None:
    instrument = Instrument(symbol="603993", name="洛阳钼业", asset_class="equity", active=True)
    session.add(instrument)
    session.flush()
    session.add_all(
        [
            MarketBar(
                instrument_id=instrument.id,
                timeframe="1d",
                ts_utc=datetime(2026, 11, day, tzinfo=timezone.utc),
                open=10.0 + day,
                high=12.0 + day,
                low=9.0 + day,
                close=11.0 + day,
                volume=1000.0 * day,
            )
            for day in (18, 19, 20)
        ]
    )
    session.commit()


def test_load_bar_rows_returns_ohlc_and_volume():
    _, factory = memory_db()
    with factory() as session:
        _seed_bars(session)
        rows = bars.load_bar_rows(session, "603993")

    assert [row["as_of"].day for row in rows] == [18, 19, 20]
    payload = rows[0]["payload"]
    assert payload["open"] == 28.0
    assert payload["high"] == 30.0
    assert payload["low"] == 27.0
    assert payload["close"] == 29.0
    assert payload["volume"] == 18_000.0
    assert payload["close_raw"] == payload["close"]


def test_load_bar_frame_is_date_indexed():
    _, factory = memory_db()
    with factory() as session:
        _seed_bars(session)
        frame = bars.load_bar_frame(session, "603993")

    assert {"open", "high", "low", "close", "volume"} <= set(frame.columns)
    assert frame.index.is_monotonic_increasing
    assert (frame["high"] > frame["low"]).all()


def test_seed_from_system_no_longer_flattens_ohlc():
    _, factory = memory_db()
    spec = get_topic("luoyang")
    with factory() as session:
        _seed_bars(session)
        rows = _seed_from_system(session, spec, "price_daily")

    assert len(rows) == 3
    for row in rows:
        payload = row["payload"]
        assert payload["high"] > payload["low"]
        assert payload["open"] != payload["high"] or payload["close"] != payload["low"]
        assert payload["volume"] is not None
        assert row["row_key"] == "default"
