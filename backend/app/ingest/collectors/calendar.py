"""Economic calendar collection."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.ingest import store
from app.ingest.http import HttpClient
from app.ingest.providers import eastmoney_calendar
from app.ingest.sources import SOURCE_EM
from app.models.core import EconomicEvent
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def collect_calendar(days_ahead: int = 14, days_back: int = 180) -> dict:
    started = time.perf_counter()
    stats: dict = {"events": 0, "new": 0, "errors": []}
    now = datetime.now(timezone.utc)
    today = now.astimezone(timezone(timedelta(hours=8))).date()
    start = today - timedelta(days=days_back)
    end = today + timedelta(days=days_ahead)

    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        source = store.get_source(session, **SOURCE_EM)
        try:
            events = eastmoney_calendar.fetch_calendar(client, start, end)
            existing = {
                (ts.replace(tzinfo=None) if ts.tzinfo else ts, name)
                for ts, name in session.execute(
                    select(EconomicEvent.ts_utc, EconomicEvent.name)
                ).all()
            }
            for event in events:
                naive_ts = event["ts_utc"].replace(tzinfo=None)
                if (naive_ts, event["name"]) in existing:
                    continue
                session.add(
                    EconomicEvent(
                        ts_utc=naive_ts,
                        name=event["name"],
                        category=event["category"],
                        country=event["country"],
                        importance=event["importance"],
                        source_code=event["source_code"],
                    )
                )
                existing.add((naive_ts, event["name"]))
                stats["new"] += 1
            cutoff = now.replace(tzinfo=None) - timedelta(days=365)
            session.execute(delete(EconomicEvent).where(EconomicEvent.ts_utc < cutoff))
            session.execute(delete(EconomicEvent).where(EconomicEvent.name.like("%累计同比%")))
            session.commit()
            stats["events"] = len(events)
            store.record_health(session, source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("calendar failed")
            store.record_health(session, source.id, ok=False, error=str(exc))
            stats["errors"].append(str(exc))
    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_calendar: %s", stats)
    return stats
