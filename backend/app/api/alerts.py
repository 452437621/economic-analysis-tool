"""Alert APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.core import Alert
from app.platform.db import get_session

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    limit: int = Query(30, ge=1, le=200),
    include_acked: bool = Query(False),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if not include_acked:
        stmt = stmt.where(Alert.acknowledged.is_(False))
    rows = session.scalars(stmt).all()
    return {
        "data": [
            {
                "id": row.id,
                "level": row.level,
                "kind": row.kind,
                "title": row.title,
                "message": row.message,
                "acknowledged": row.acknowledged,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/{alert_id}/ack")
def ack(alert_id: str, session: Session = Depends(get_session)) -> dict:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    alert.acknowledged = True
    session.commit()
    return {"id": alert.id, "acknowledged": True, "at": utcnow().isoformat()}
