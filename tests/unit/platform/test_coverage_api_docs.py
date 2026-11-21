"""Data-coverage metrics and the self-hosted API docs renderer."""

from __future__ import annotations

import pytest

from datetime import datetime, timedelta, timezone

from app.models.core import Job, MacroObs, MacroSeries
from app.platform.api_docs import render_html
from app.platform.coverage import (
    data_quality_pct,
    job_health,
    latest_sync,
    series_coverage,
)
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_empty_database_reports_zero_not_error(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            assert series_coverage(session) == (0, 0)
            assert job_health(session) == (0, 0)
            assert latest_sync(session) is None
        assert data_quality_pct(0, 0, 0, 0) == 0.0
    finally:
        engine.dispose()


def test_series_coverage_respects_frequency_window(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        now = _now()
        with factory() as session:
            daily = MacroSeries(code="US10Y", name="daily", freq="d")
            annual = MacroSeries(code="US_DEBT_GDP", name="annual", freq="y")
            stale = MacroSeries(code="OLD", name="stale", freq="d")
            session.add_all([daily, annual, stale])
            session.flush()
            session.add_all(
                [
                    MacroObs(series_id=daily.id, ts_utc=now - timedelta(days=1), value=4.0),
                    MacroObs(series_id=annual.id, ts_utc=now - timedelta(days=400), value=100.0),
                    MacroObs(series_id=stale.id, ts_utc=now - timedelta(days=30), value=1.0),
                ]
            )
            session.add_all(
                [
                    Job(name="a", last_status="ok"),
                    Job(name="b", last_status="failed"),
                ]
            )
            session.commit()
            assert series_coverage(session, now=now) == (2, 3)
            assert job_health(session) == (1, 2)
            assert latest_sync(session) is not None
        assert data_quality_pct(2, 3, 1, 2) == 60.0
    finally:
        engine.dispose()


def test_api_docs_html_is_self_hosted_and_escapes_title() -> None:
    html = render_html("<script>alert(1)</script>", "3.0.0")
    assert "3.0.0" in html
    assert "&lt;script&gt;" in html
    assert "cdn.jsdelivr" not in html
    assert "/openapi.json" in html
