"""Gold monitoring collector + composite score persistence."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.gold.providers import PROVIDERS, ProviderResult
from app.gold.registry import INDICATORS
from app.gold.scoring import compute_gold_score
from app.models.core import AnalyticsResult, GoldMetric, GoldProviderRun
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def _upsert_metrics(session, records: list[dict]) -> tuple[int, int]:
    if not records:
        return 0, 0
    codes = {record["code"] for record in records}
    existing_rows = session.scalars(select(GoldMetric).where(GoldMetric.code.in_(codes))).all()
    existing = {(row.code, _key(row.as_of)): row for row in existing_rows}
    inserted = updated = 0
    for record in records:
        code = record["code"]
        if code not in INDICATORS:
            continue
        key = (code, _key(record["as_of"]))
        row = existing.get(key)
        if row is None:
            row = GoldMetric(
                code=code,
                as_of=record["as_of"],
                value=record["value"],
                source=record.get("source"),
                extra=record.get("extra"),
                created_at=datetime.now(timezone.utc),
            )
            session.add(row)
            existing[key] = row
            inserted += 1
        else:
            row.value = record["value"]
            row.source = record.get("source")
            if record.get("extra"):
                row.extra = record["extra"]
            updated += 1
    session.commit()
    return inserted, updated


def _key(value: datetime) -> str:
    # SQLite returns naive datetimes: treat them as UTC instead of local time.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()


def _record_provider_run(session, result: ProviderResult) -> None:
    session.add(
        GoldProviderRun(
            provider=result.name,
            ok=result.ok,
            records=len(result.records),
            error=(result.error or "")[:2000] or None,
            checked_at=datetime.now(timezone.utc),
        )
    )
    session.commit()


def _store_score(session, score: dict) -> None:
    asof = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    row = session.scalar(
        select(AnalyticsResult).where(
            AnalyticsResult.kind == "gold",
            AnalyticsResult.subject == "GOLD",
            AnalyticsResult.asof == asof,
        )
    )
    if row is None:
        row = AnalyticsResult(kind="gold", subject="GOLD", asof=asof)
        session.add(row)
    row.payload = score
    session.commit()


def collect_gold() -> dict:
    """Run all gold providers, persist observations and refresh the composite score."""
    summary = {"providers": {}, "records": 0}
    with SessionLocal() as session:
        for name, fetcher in PROVIDERS:
            try:
                result = fetcher()
            except Exception as exc:  # noqa: BLE001 - provider isolation
                logger.exception("gold provider %s crashed", name)
                result = ProviderResult(name, False, error=str(exc))
            inserted, updated = _upsert_metrics(session, result.records)
            _record_provider_run(session, result)
            summary["providers"][name] = {
                "ok": result.ok,
                "records": len(result.records),
                "inserted": inserted,
                "updated": updated,
                "error": result.error,
            }
            summary["records"] += len(result.records)
        score = compute_gold_score(session)
        _store_score(session, score)
        summary["score"] = score["score"]
        summary["label"] = score["label"]
        summary["coverage"] = score["coverage"]
        logger.info("collect_gold: %s", summary)
    return summary


def latest_provider_runs(session) -> list[dict]:
    rows = session.scalars(
        select(GoldProviderRun).order_by(GoldProviderRun.checked_at.desc()).limit(100)
    ).all()
    latest: dict[str, GoldProviderRun] = {}
    for row in rows:
        latest.setdefault(row.provider, row)
    return [
        {
            "provider": row.provider,
            "ok": row.ok,
            "records": row.records,
            "error": row.error,
            "checked_at": row.checked_at.isoformat() if row.checked_at else None,
        }
        for row in latest.values()
    ]
