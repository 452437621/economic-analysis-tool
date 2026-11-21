"""Quote collection cadence: one-minute polling with unchanged-value dedupe and bounded retention.

Regression guard for 「总览的美元指数好几分钟不动」: the collector used to run every
5 minutes while the UI polled every 15 seconds, so the price looked frozen.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.init_db import JOBS_DEFAULT, seed_jobs
from app.ingest import store
from app.ingest.contracts import Quote
from app.models.core import Instrument, Job, Quote as QuoteRow
from app.platform.config import settings
from app.platform.db import SessionLocal, init_db

pytestmark = [pytest.mark.unit, pytest.mark.db]


def _instrument_id(symbol: str = "CADENCE") -> str:
    """Probe instrument, with its quote rows cleared so reruns start from zero."""
    init_db()
    seed_jobs()
    with SessionLocal() as session:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
        if instrument is None:
            instrument = Instrument(
                symbol=symbol,
                name="quote cadence probe",
                asset_class="fx",
                currency="USD",
                active=False,
            )
            session.add(instrument)
            session.commit()
        session.execute(delete(QuoteRow).where(QuoteRow.instrument_id == instrument.id))
        session.commit()
        return instrument.id


def _store(
    symbols: dict[str, str], quotes: list[Quote], dedupe_sec: int = store.QUOTE_DEDUPE_SEC
) -> int:
    with SessionLocal() as session:
        written = store.upsert_quotes(session, quotes, symbols, None, dedupe_sec=dedupe_sec)
        session.commit()
        return written


def _quote(symbol: str, ts: datetime, price: float, prev_close: float = 99.0) -> Quote:
    return Quote(symbol=symbol, ts=ts, price=price, prev_close=prev_close)


def test_unchanged_quote_is_deduped_within_window():
    instrument_id = _instrument_id()
    symbols = {"CADENCE": instrument_id}
    now = datetime.now(timezone.utc)

    assert _store(symbols, [_quote("CADENCE", now, 100.0)]) == 1
    # Same numbers one minute later: the reader only needs the newest row.
    assert _store(symbols, [_quote("CADENCE", now + timedelta(seconds=60), 100.0)]) == 0
    # A real move is always stored.
    assert _store(symbols, [_quote("CADENCE", now + timedelta(seconds=120), 100.5)]) == 1
    # dedupe_sec=0 disables the optimisation (used by tests/debugging).
    assert _store(symbols, [_quote("CADENCE", now + timedelta(seconds=180), 100.5)], dedupe_sec=0) == 1


def test_unchanged_quote_is_stored_again_after_the_window():
    symbol = "CADENCE_STALE"
    instrument_id = _instrument_id(symbol)
    symbols = {symbol: instrument_id}
    now = datetime.now(timezone.utc)

    assert _store(symbols, [_quote(symbol, now - timedelta(minutes=10), 50.0)]) == 1
    # Same price, but the stored row is older than QUOTE_DEDUPE_SEC: refresh it so
    # the snapshot does not age out into 「旧数据」 while a market is merely quiet.
    assert _store(symbols, [_quote(symbol, now, 50.0)]) == 1


def test_prune_quotes_drops_rows_past_retention():
    symbol = "CADENCE_PRUNE"
    instrument_id = _instrument_id(symbol)
    symbols = {symbol: instrument_id}
    now = datetime.now(timezone.utc)

    assert _store(symbols, [_quote(symbol, now - timedelta(days=45), 1.0)]) == 1
    assert _store(symbols, [_quote(symbol, now - timedelta(minutes=5), 2.0)]) == 1

    with SessionLocal() as session:
        assert store.prune_quotes(session, keep_days=30) >= 1
        kept = session.scalars(
            select(QuoteRow).where(QuoteRow.instrument_id == instrument_id)
        ).all()
        assert [row.price for row in kept] == [2.0]
        # 0 disables pruning (operator opt-out via EPIC_QUOTES_RETENTION_DAYS).
        assert store.prune_quotes(session, keep_days=0) == 0


def test_quotes_retention_default_keeps_intraday_history_bounded():
    assert settings.quotes_retention_days == 30


def test_seed_jobs_refreshes_stale_quote_cadence_label():
    init_db()
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "collect_quotes"))
        job.cron = "every 60s (trading hours)"
        job.enabled = False
        session.commit()

    seed_jobs()
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "collect_quotes"))
        assert JOBS_DEFAULT["collect_quotes"] == "every 60s"
        assert job.cron == "every 60s"  # the 系统状态 page must not lie about the trigger
        assert job.enabled is False  # operator switch is preserved
        job.enabled = True
        session.commit()


def test_collect_quotes_is_scheduled_every_minute():
    from app.platform.scheduler import _register_collectors, scheduler

    _register_collectors()
    try:
        job = scheduler.get_job("collect_quotes")
        assert job is not None
        assert job.trigger.interval.total_seconds() == 60
    finally:
        scheduler.remove_all_jobs()
