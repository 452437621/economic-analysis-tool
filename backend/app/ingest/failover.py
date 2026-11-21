"""Generic ordered source chains with health-based circuit breakers.

Every candidate records its own ``SourceHealth`` row. A source that failed
``source_failover_failures`` times in a row is skipped for a short cooldown so
the next cycle can use a backup immediately instead of waiting for the primary
to time out again.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import store
from app.models.core import Source, SourceHealth
from app.platform.config import settings

logger = logging.getLogger(__name__)

CHAIN_STATS: dict[str, dict] = {}


@dataclass(frozen=True)
class Candidate:
    source_conf: dict
    fetch: Callable[[Any], Any]
    role: str = "primary"


@dataclass
class ChainResult:
    value: Any | None
    provider: str | None = None
    source_id: str | None = None
    attempts: list[dict] = field(default_factory=list)
    degraded: bool = False
    stale: bool = False
    used_last_known_good: bool = False
    as_of: datetime | None = None
    reconciliation: list[dict] = field(default_factory=list)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def breaker_state(
    session: Session,
    source_id: str,
    now: datetime | None = None,
    *,
    cooldown_minutes: int | None = None,
    failures: int | None = None,
) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current - timedelta(hours=24)
    rows = session.scalars(
        select(SourceHealth)
        .where(SourceHealth.source_id == source_id, SourceHealth.ts >= cutoff)
        .order_by(SourceHealth.ts.desc())
        .limit(200)
    ).all()
    consecutive = 0
    for row in rows:
        if row.ok:
            break
        consecutive += 1
    last_failure = next((_aware(row.ts) for row in rows if not row.ok), None)
    last_success = next((_aware(row.ts) for row in rows if row.ok), None)
    checks = len(rows)
    ok_count = sum(1 for row in rows if row.ok)
    threshold = failures or settings.source_failover_failures
    cooldown = cooldown_minutes or settings.source_failover_cooldown_minutes
    cooldown_until = None
    if consecutive >= threshold and last_failure is not None:
        until = last_failure + timedelta(minutes=cooldown)
        if until > current:
            cooldown_until = until
    return {
        "source_id": source_id,
        "checks_24h": checks,
        "success_rate_24h": round(ok_count / checks, 3) if checks else None,
        "consecutive_failures": consecutive,
        "last_failure": last_failure,
        "last_success": last_success,
        "cooldown_until": cooldown_until,
        "open": cooldown_until is not None,
    }


def _record(
    session: Session,
    source_id: str,
    *,
    ok: bool,
    latency_ms: int | None,
    error: str | None,
) -> None:
    store.record_health(session, source_id, ok=ok, latency_ms=latency_ms, error=error)
    session.flush()


def run_chain(
    session: Session,
    chain_id: str,
    candidates: list[Candidate],
    client: Any,
    *,
    validator: Callable[[Any], bool] | None = None,
    cache_loader: Callable[[], Any] | None = None,
    now: datetime | None = None,
) -> ChainResult:
    """Try candidates in order, recording health and honoring open breakers."""
    current = now or datetime.now(timezone.utc)
    result = ChainResult(value=None)
    resolved: list[tuple[Candidate, Source, dict]] = []
    for candidate in candidates:
        source = store.get_source(session, **candidate.source_conf)
        state = breaker_state(session, source.id, current)
        resolved.append((candidate, source, state))
        result.attempts.append(
            {
                "source": source.name,
                "role": candidate.role,
                "skipped": False,
                "cooldown": bool(state["open"]),
                "ok": None,
                "latency_ms": None,
                "error": None,
            }
        )
    all_open = all(state["open"] for _candidate, _source, state in resolved) if resolved else False
    for index, (candidate, source, state) in enumerate(resolved):
        if state["open"] and not all_open:
            result.attempts[index]["skipped"] = True
            result.attempts[index]["error"] = "source in cooldown"
            continue
        started = time.perf_counter()
        try:
            value = candidate.fetch(client)
            if validator is not None and not validator(value):
                raise ValueError("validator rejected provider response")
            latency = int((time.perf_counter() - started) * 1000)
            _record(session, source.id, ok=True, latency_ms=latency, error=None)
            result.attempts[index]["ok"] = True
            result.attempts[index]["latency_ms"] = latency
            result.value = value
            result.provider = source.name
            result.source_id = source.id
            CHAIN_STATS[chain_id] = {
                "last_used": current.isoformat(),
                "last_success": current.isoformat(),
                "last_provider": source.name,
                "last_error": None,
            }
            return result
        except Exception as exc:  # noqa: BLE001 - fallback chain must try the next source
            latency = int((time.perf_counter() - started) * 1000)
            _record(session, source.id, ok=False, latency_ms=latency, error=str(exc)[:1000])
            result.attempts[index]["ok"] = False
            result.attempts[index]["latency_ms"] = latency
            result.attempts[index]["error"] = str(exc)[:500]
            logger.warning("chain %s source %s failed: %s", chain_id, source.name, exc)
    result.degraded = True
    CHAIN_STATS[chain_id] = {
        "last_used": current.isoformat(),
        "last_success": (CHAIN_STATS.get(chain_id) or {}).get("last_success"),
        "last_provider": None,
        "last_error": "; ".join(
            f"{item['source']}: {item['error']}" for item in result.attempts if item.get("error")
        )[:500],
    }
    if cache_loader is not None:
        try:
            cached = cache_loader()
        except Exception:  # noqa: BLE001
            cached = None
        if cached is not None:
            result.value = cached
            result.stale = True
            result.used_last_known_good = True
    return result


def chain_stats(chain_id: str) -> dict:
    return CHAIN_STATS.get(chain_id) or {}
