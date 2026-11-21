"""Generic source fallback chains and circuit breakers (offline)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingest import store
from app.ingest.failover import Candidate, breaker_state, run_chain
from app.models.base import Base
from app.models.core import SourceHealth

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test" / "m0" / "failover.db"
PRIMARY = dict(name="test-primary", kind="market", tier="S2", reliability=0.9)
BACKUP = dict(name="test-backup", kind="market", tier="S2", reliability=0.8)


@pytest.fixture()
def session():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        yield db
    engine.dispose()


def _ok(_client):
    return {"value": 1}


def _fail(_client):
    raise RuntimeError("provider down")


def test_primary_failure_uses_backup_and_records_health(session):
    result = run_chain(
        session,
        "test.chain",
        [Candidate(PRIMARY, _fail, "primary"), Candidate(BACKUP, _ok, "backup")],
        client=None,
    )
    assert result.value == {"value": 1}
    assert result.provider == "test-backup"
    assert result.attempts[0]["ok"] is False
    assert result.attempts[1]["ok"] is True
    rows = session.scalars(select(SourceHealth)).all()
    assert len(rows) == 2
    assert {row.ok for row in rows} == {True, False}


def test_breaker_skips_primary_after_three_failures(session):
    now = datetime.now(timezone.utc)
    primary = store.get_source(session, **PRIMARY)
    session.add_all(
        [
            SourceHealth(source_id=primary.id, ts=now - timedelta(minutes=i), ok=False, error="boom")
            for i in range(3)
        ]
    )
    session.commit()
    state = breaker_state(session, primary.id, now)
    assert state["open"] is True
    assert state["consecutive_failures"] >= 3

    result = run_chain(
        session,
        "test.chain",
        [Candidate(PRIMARY, _ok, "primary"), Candidate(BACKUP, _ok, "backup")],
        client=None,
        now=now,
    )
    assert result.provider == "test-backup"
    assert result.attempts[0]["skipped"] is True


def test_all_sources_fail_returns_last_known_good_without_writing(session):
    result = run_chain(
        session,
        "test.chain",
        [Candidate(PRIMARY, _fail, "primary"), Candidate(BACKUP, _fail, "backup")],
        client=None,
        cache_loader=lambda: {"cached": True},
    )
    assert result.value == {"cached": True}
    assert result.stale is True
    assert result.used_last_known_good is True
    assert result.provider is None


def test_single_source_chain_is_marked_when_unavailable(session):
    result = run_chain(
        session,
        "test.single",
        [Candidate(PRIMARY, _fail, "primary")],
        client=None,
    )
    assert result.value is None
    assert result.attempts[0]["ok"] is False
