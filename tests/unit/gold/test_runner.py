"""Gold metric persistence helpers."""

from __future__ import annotations

import pytest

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.gold.runner import _key, _upsert_metrics
from app.models.core import GoldMetric
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def _at(offset_days: int = 0) -> datetime:
    return datetime(2026, 1, 2, 12, 30, 45, tzinfo=timezone.utc) + timedelta(days=offset_days)


def test_upsert_inserts_then_updates_same_code_and_asof(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            inserted, updated = _upsert_metrics(
                session,
                [{"code": "GOLD_PRICE_USD", "as_of": _at(), "value": 2000.0, "source": "test"}],
            )
            assert (inserted, updated) == (1, 0)
            inserted, updated = _upsert_metrics(
                session,
                [{"code": "GOLD_PRICE_USD", "as_of": _at(), "value": 2001.5, "source": "test2"}],
            )
            assert (inserted, updated) == (0, 1)
            rows = session.scalars(select(GoldMetric)).all()
            assert len(rows) == 1
            assert rows[0].value == 2001.5
            assert rows[0].source == "test2"
    finally:
        engine.dispose()


def test_upsert_ignores_unknown_indicator(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            assert _upsert_metrics(
                session, [{"code": "NOT_AN_INDICATOR", "as_of": _at(), "value": 1.0}]
            ) == (0, 0)
            assert session.scalars(select(GoldMetric)).all() == []
    finally:
        engine.dispose()


def test_key_normalises_naive_and_seconds() -> None:
    aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    naive = datetime(2026, 1, 2, 3, 4, 5)
    assert _key(aware) == _key(naive)
    assert _key(aware).endswith(":04:00+00:00")
