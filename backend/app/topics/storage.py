"""Persistence helpers for topic datasets (idempotent upserts, health, settings)."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.topics import TopicDataset, TopicDatasetRow, TopicSetting, TopicSourceRun
from app.platform.config import settings

CHUNK = 200
RUN_RETENTION_DAYS = 90


def today_local() -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def jsonable(value: Any) -> Any:
    """Recursively convert numpy/pandas/date/NaN values into JSON-safe ones."""
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    if hasattr(value, "item"):  # numpy scalar fallback
        try:
            return jsonable(value.item())
        except Exception:  # noqa: BLE001 - defensive
            return str(value)
    return str(value)


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value)[:19]).date()
    except ValueError:
        return None


def ensure_dataset(
    session: Session,
    *,
    topic_id: str,
    dataset: str,
    name: str = "",
    source: str | None = None,
    freq: str | None = None,
    unit: str | None = None,
    primary_key: str | None = None,
    fields: dict | None = None,
) -> TopicDataset:
    row = session.scalar(
        select(TopicDataset).where(TopicDataset.topic_id == topic_id, TopicDataset.dataset == dataset)
    )
    if row is None:
        row = TopicDataset(
            topic_id=topic_id,
            dataset=dataset,
            name=name or dataset,
            source=source,
            freq=freq,
            unit=unit,
            primary_key=primary_key,
        )
        session.add(row)
        session.flush()
    changed = False
    for attr, value in (
        ("name", name or row.name),
        ("source", source or row.source),
        ("freq", freq or row.freq),
        ("unit", unit or row.unit),
        ("primary_key", primary_key or row.primary_key),
    ):
        if value and getattr(row, attr) != value:
            setattr(row, attr, value)
            changed = True
    if fields:
        merged = {**(row.fields or {}), **jsonable(fields)}
        if merged != row.fields:
            row.fields = merged
            changed = True
    if changed:
        session.flush()
    return row


def upsert_rows(
    session: Session,
    dataset_row: TopicDataset,
    rows: Iterable[dict[str, Any]],
    *,
    prune_before: date | None = None,
) -> int:
    """Upsert normalized rows. Each row: ``{as_of, row_key?, payload}``."""
    cutoff = today_local()
    # Deduplicate by (as_of, row_key): SQLite refuses a batch that touches the
    # same conflict key twice.  Later rows win, matching upsert semantics.
    deduped: dict[tuple[date, str], dict[str, Any]] = {}
    for item in rows:
        as_of = _as_date(item.get("as_of"))
        if as_of is None or as_of > cutoff:
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        row_key = str(item.get("row_key") or "default")[:120]
        deduped[(as_of, row_key)] = {
            "dataset_id": dataset_row.id,
            "as_of": as_of,
            "row_key": row_key,
            "payload": jsonable(payload),
            "created_at": datetime.now(timezone.utc),
        }
    prepared = list(deduped.values())
    if not prepared:
        return 0

    for start in range(0, len(prepared), CHUNK):
        chunk = prepared[start : start + CHUNK]
        stmt = sqlite_insert(TopicDatasetRow).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["dataset_id", "as_of", "row_key"],
            set_={
                "payload": stmt.excluded.payload,
                # Keep ``created_at`` as the last-write timestamp so
                # ``data_version`` advances when existing rows are refreshed.
                "created_at": stmt.excluded.created_at,
            },
        )
        session.execute(stmt)

    if prune_before is not None:
        session.execute(
            delete(TopicDatasetRow).where(
                TopicDatasetRow.dataset_id == dataset_row.id,
                TopicDatasetRow.as_of < prune_before,
            )
        )
    session.flush()
    refresh_dataset_stats(session, dataset_row)
    return len(prepared)


def refresh_dataset_stats(session: Session, dataset_row: TopicDataset) -> None:
    latest = session.scalar(
        select(func.max(TopicDatasetRow.as_of)).where(TopicDatasetRow.dataset_id == dataset_row.id)
    )
    count = session.scalar(
        select(func.count(TopicDatasetRow.id)).where(TopicDatasetRow.dataset_id == dataset_row.id)
    )
    dataset_row.latest_as_of = latest
    dataset_row.row_count = int(count or 0)
    session.flush()


def load_rows(
    session: Session,
    topic_id: str,
    dataset: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    dataset_row = session.scalar(
        select(TopicDataset).where(TopicDataset.topic_id == topic_id, TopicDataset.dataset == dataset)
    )
    if dataset_row is None:
        return []
    stmt = select(TopicDatasetRow).where(TopicDatasetRow.dataset_id == dataset_row.id)
    if limit:
        # ``limit`` means "the latest N", not the oldest N.
        stmt = stmt.order_by(TopicDatasetRow.as_of.desc(), TopicDatasetRow.row_key.desc()).limit(limit)
        rows = list(reversed(session.scalars(stmt).all()))
    else:
        rows = session.scalars(
            stmt.order_by(TopicDatasetRow.as_of.asc(), TopicDatasetRow.row_key.asc())
        ).all()
    return [
        {"as_of": row.as_of, "row_key": row.row_key, "payload": row.payload or {}}
        for row in rows
    ]


def load_dataset_catalog(session: Session, topic_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(TopicDataset).where(TopicDataset.topic_id == topic_id).order_by(TopicDataset.dataset)
    ).all()
    return [
        {
            "dataset": row.dataset,
            "name": row.name,
            "source": row.source,
            "freq": row.freq,
            "unit": row.unit,
            "primary_key": row.primary_key,
            "latest_as_of": row.latest_as_of.isoformat() if row.latest_as_of else None,
            "row_count": row.row_count,
            "fields": row.fields or {},
        }
        for row in rows
    ]


def record_source_run(
    session: Session,
    *,
    topic_id: str,
    dataset: str,
    provider: str,
    ok: bool,
    records: int,
    error: str | None = None,
) -> None:
    session.add(
        TopicSourceRun(
            topic_id=topic_id,
            dataset=dataset,
            provider=provider,
            ok=ok,
            records=records,
            error=(error[:1000] if error else None),
        )
    )
    session.flush()


def latest_source_runs(session: Session, topic_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(TopicSourceRun)
        .where(TopicSourceRun.topic_id == topic_id)
        .order_by(TopicSourceRun.checked_at.desc())
        .limit(300)
    ).all()
    latest: dict[str, TopicSourceRun] = {}
    for row in rows:
        latest.setdefault(row.dataset, row)
    return [
        {
            "dataset": row.dataset,
            "provider": row.provider,
            "ok": row.ok,
            "records": row.records,
            "error": row.error,
            "checked_at": row.checked_at.isoformat() if row.checked_at else None,
        }
        for row in latest.values()
    ]


def prune_source_runs(session: Session, *, days: int = RUN_RETENTION_DAYS) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = session.execute(delete(TopicSourceRun).where(TopicSourceRun.checked_at < cutoff))
    return int(result.rowcount or 0)


def get_setting(session: Session, topic_id: str) -> tuple[dict[str, Any], datetime | None]:
    row = session.scalar(select(TopicSetting).where(TopicSetting.topic_id == topic_id))
    if row is None:
        return {}, None
    return dict(row.payload or {}), row.updated_at


def save_setting(session: Session, topic_id: str, payload: dict[str, Any]) -> datetime:
    row = session.scalar(select(TopicSetting).where(TopicSetting.topic_id == topic_id))
    if row is None:
        row = TopicSetting(topic_id=topic_id, payload=jsonable(payload))
        session.add(row)
    else:
        row.payload = jsonable(payload)
    session.flush()
    return row.updated_at


def clear_setting(session: Session, topic_id: str) -> None:
    session.execute(delete(TopicSetting).where(TopicSetting.topic_id == topic_id))
    session.flush()


def data_version(session: Session, topic_id: str) -> str:
    """Cheap cache key: latest dataset write + settings update."""
    latest = session.scalar(
        select(func.max(TopicDatasetRow.created_at))
        .join(TopicDataset, TopicDataset.id == TopicDatasetRow.dataset_id)
        .where(TopicDataset.topic_id == topic_id)
    )
    setting_updated = session.scalar(
        select(func.max(TopicSetting.updated_at)).where(TopicSetting.topic_id == topic_id)
    )
    return f"{latest or '-'}:{setting_updated or '-'}"
