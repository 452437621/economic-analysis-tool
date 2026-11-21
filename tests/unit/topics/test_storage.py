"""Topic dataset storage: idempotent upsert, latest-N reads and data version."""

from __future__ import annotations

import time
from datetime import date

import pytest

from app.topics import storage
from tests.helpers import memory_db

pytestmark = [pytest.mark.unit, pytest.mark.db]


def _rows(count: int, *, prefix: int = 1) -> list[dict]:
    return [
        {
            "as_of": date(2026, 1, index + 1),
            "row_key": "default",
            "payload": {"close": float(prefix + index)},
        }
        for index in range(count)
    ]


def test_upsert_is_idempotent_and_dedupes_in_batch():
    _, factory = memory_db()
    with factory() as session:
        dataset = storage.ensure_dataset(session, topic_id="t", dataset="price")
        duplicated = _rows(2) + [{"as_of": date(2026, 1, 2), "row_key": "default", "payload": {"close": 99.0}}]
        written = storage.upsert_rows(session, dataset, duplicated)
        assert written == 2
        rows = storage.load_rows(session, "t", "price")
        assert len(rows) == 2
        assert rows[1]["payload"]["close"] == 99.0

        # Upserting the same keys again must not duplicate or raise.
        written = storage.upsert_rows(session, dataset, duplicated)
        assert written == 2
        assert len(storage.load_rows(session, "t", "price")) == 2


def test_load_rows_limit_returns_latest_rows_in_ascending_order():
    _, factory = memory_db()
    with factory() as session:
        dataset = storage.ensure_dataset(session, topic_id="t", dataset="price")
        storage.upsert_rows(session, dataset, _rows(6))
        rows = storage.load_rows(session, "t", "price", limit=2)
        assert [item["as_of"] for item in rows] == [date(2026, 1, 5), date(2026, 1, 6)]


def test_future_rows_are_skipped():
    _, factory = memory_db()
    with factory() as session:
        dataset = storage.ensure_dataset(session, topic_id="t", dataset="price")
        rows = _rows(1) + [{"as_of": date(2099, 1, 1), "row_key": "default", "payload": {"close": 1.0}}]
        assert storage.upsert_rows(session, dataset, rows) == 1
        assert len(storage.load_rows(session, "t", "price")) == 1


def test_data_version_advances_when_existing_rows_are_refreshed():
    _, factory = memory_db()
    with factory() as session:
        dataset = storage.ensure_dataset(session, topic_id="t", dataset="price")
        storage.upsert_rows(session, dataset, _rows(1))
        session.commit()
        first = storage.data_version(session, "t")
        time.sleep(0.01)
        storage.upsert_rows(session, dataset, [{"as_of": date(2026, 1, 1), "row_key": "default", "payload": {"close": 2.0}}])
        session.commit()
        assert storage.data_version(session, "t") != first


def test_settings_roundtrip():
    _, factory = memory_db()
    with factory() as session:
        assert storage.get_setting(session, "t") == ({}, None)
        storage.save_setting(session, "t", {"buy_price": 12.5})
        session.commit()
        payload, updated = storage.get_setting(session, "t")
        assert payload["buy_price"] == 12.5
        assert updated is not None
        storage.clear_setting(session, "t")
        session.commit()
        assert storage.get_setting(session, "t") == ({}, None)
