"""宏观序列频率元数据：月频序列不能被当成停更的日频序列告警。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.ingest import store
from app.ingest.contracts import MacroPoint
from app.ingest.pipeline import MACRO_SERIES_META
from app.models.core import MacroSeries
from app.platform.db import SessionLocal, init_db


def _point(day: int = 1, value: float = 3.4) -> MacroPoint:
    return MacroPoint(code="FR10Y", ts=datetime(2026, 10, day, tzinfo=timezone.utc), value=value)


def test_france_10y_is_declared_monthly():
    assert MACRO_SERIES_META["FR10Y"]["freq"] == "m"


def test_upsert_macro_sets_and_repairs_freq():
    init_db()
    with SessionLocal() as session:
        # 1) 首次写入时按声明频率建序列
        store.upsert_macro(session, "FR10Y", [_point()], name="法国国债10年（月度）", freq="m")
        series = session.scalar(select(MacroSeries).where(MacroSeries.code == "FR10Y"))
        assert series is not None and series.freq == "m"

        # 2) 历史遗留的 freq='d' 会被下一次采集纠正
        series.freq = "d"
        session.flush()
        store.upsert_macro(session, "FR10Y", [_point(value=3.5)], freq="m")
        session.refresh(series)
        assert series.freq == "m"

        # 3) 不传 freq 时保持原值，避免把没声明频率的序列改坏
        store.upsert_macro(session, "FR10Y", [_point(value=3.6)])
        session.refresh(series)
        assert series.freq == "m"
