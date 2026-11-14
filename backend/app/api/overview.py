"""Composite overview API.

One request for the dashboard: health, latest brief, enriched snapshot,
watchlist with sparklines, macro rates + mini trends, alerts, upcoming calendar
and job health. Keeps the frontend from fanning out ~20 requests on first paint.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import (
    DAILY_KINDS,
    brief_payload,
    latest_quotes,
    macro_latest_rows,
    macro_sparks,
    snapshot_payload,
    watchlist_payload,
)
from app.api.system import health as health_payload
from app.models.core import Alert, Brief, EconomicEvent, Job
from app.platform.db import get_session

router = APIRouter(prefix="/api", tags=["overview"])

#: 总览利率卡需要迷你走势的序列（与前端 MACRO_ORDER 前 10 项一致）
MACRO_SPARK_CODES = [
    "SOFR",
    "EFFR",
    "SOFR_EFFR",
    "US2Y",
    "US10Y",
    "US30Y",
    "US10Y_REAL",
    "CN10Y",
    "JP10Y",
    "DE10Y",
]


@router.get("/overview")
def overview(
    calendar_limit: int = Query(6, ge=1, le=20),
    alerts_limit: int = Query(5, ge=1, le=20),
    session: Session = Depends(get_session),
) -> dict:
    """总览页聚合数据（单请求）。各分区都可独立缺失，前端按区块降级。"""
    instruments, latest = latest_quotes(session)
    snapshot = snapshot_payload(session, instruments, latest)
    watchlist = watchlist_payload(session, with_spark=True, latest=latest)
    latest_brief = session.scalar(
        select(Brief)
        .where(Brief.kind.in_(DAILY_KINDS))
        .order_by(Brief.created_at.desc(), Brief.trade_date.desc())
        .limit(1)
    )
    unread_alerts = int(
        session.scalar(
            select(func.count()).select_from(Alert).where(Alert.acknowledged.is_(False))
        )
        or 0
    )
    alert_rows = session.scalars(
        select(Alert)
        .where(Alert.acknowledged.is_(False))
        .order_by(Alert.created_at.desc())
        .limit(alerts_limit)
    ).all()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    calendar_rows = session.scalars(
        select(EconomicEvent)
        .where(
            EconomicEvent.ts_utc >= now - timedelta(hours=6),
            EconomicEvent.ts_utc <= now + timedelta(days=14),
        )
        .order_by(EconomicEvent.ts_utc.asc())
        .limit(calendar_limit)
    ).all()
    job_total = int(session.scalar(select(func.count()).select_from(Job)) or 0)
    job_errors = int(
        session.scalar(
            select(func.count()).select_from(Job).where(Job.last_status == "error")
        )
        or 0
    )

    health = health_payload(session=session)
    return {
        "asof": snapshot.get("meta", {}).get("asof"),
        "health": {
            "status": health["status"],
            "version": health["version"],
            "env": health["env"],
            "llm_enabled": health["llm_enabled"],
            "time_local": health["time_local"],
            "database": health["database"],
            "scheduler": health["scheduler"],
            "counts": health["counts"],
        },
        "brief": brief_payload(latest_brief) if latest_brief else None,
        "snapshot": snapshot,
        "watchlist": watchlist,
        "macro": {
            "latest": macro_latest_rows(session),
            "sparks": macro_sparks(session, MACRO_SPARK_CODES),
        },
        "alerts": {
            "unread": unread_alerts,
            "items": [
                {
                    "id": row.id,
                    "level": row.level,
                    "kind": row.kind,
                    "title": row.title,
                    "message": row.message,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in alert_rows
            ],
        },
        "calendar": [
            {
                "id": row.id,
                "ts": row.ts_utc.isoformat() if row.ts_utc else None,
                "name": row.name,
                "category": row.category,
                "country": row.country,
                "importance": row.importance,
            }
            for row in calendar_rows
        ],
        "jobs": {
            "total": job_total,
            "failed": job_errors,
            "scheduler_running": bool(health["scheduler"].get("running")),
            "next_run": (
                health["scheduler"].get("jobs", [{}])[0].get("next_run")
                if health["scheduler"].get("jobs")
                else None
            ),
        },
    }
