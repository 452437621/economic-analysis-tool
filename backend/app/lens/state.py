"""Persisted lens state and forecast helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lens.helpers import METHOD_SYNTHESIS, _ASSET_META
from app.models.v2 import Derivation, Forecast
from app.provenance.engine import aware, new_id

def latest_state(session: Session) -> dict[str, Any] | None:
    """Return the latest persisted lens state without recomputing."""
    synthesis = session.scalar(
        select(Derivation)
        .where(Derivation.code == "lens.synthesis")
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )
    if synthesis is None:
        return None
    fed = session.scalar(
        select(Derivation)
        .where(Derivation.code == "lens.fed.state")
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )
    song = session.scalar(
        select(Derivation)
        .where(Derivation.code == "lens.song.state")
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )
    run = synthesis.run_id
    macro = _latest_derivation(session, "lens.macro.state")
    micro = _latest_derivation(session, "lens.micro.state")
    personas = list(
        session.scalars(
            select(Derivation)
            .where(Derivation.code.like("lens.persona.%.state"))
            .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
            .limit(40)
        ).all()
    )
    seen: dict[str, Derivation] = {}
    for row in personas:
        persona_id = row.code.removeprefix("lens.persona.").removesuffix(".state")
        seen.setdefault(persona_id, row)
    return {
        "run_id": run,
        "asof": aware(synthesis.asof).isoformat() if synthesis.asof else None,
        "fed": fed,
        "song": song,
        "macro": macro,
        "micro": micro,
        "personas": seen,
        "synthesis": synthesis,
    }


def _latest_derivation(session: Session, code: str) -> Derivation | None:
    return session.scalar(
        select(Derivation)
        .where(Derivation.code == code)
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )


def latest_forecasts(session: Session, limit: int = 50, status: str | None = None) -> list[Forecast]:
    stmt = select(Forecast).where(Forecast.subject == "lens")
    if status:
        stmt = stmt.where(Forecast.status == status)
    return list(session.scalars(stmt.order_by(Forecast.made_at.desc()).limit(limit)).all())


def create_forecast(
    session: Session,
    *,
    asset: str,
    direction: str,
    horizon_days: int = 90,
    probability: float | None = None,
    notes: str | None = None,
    baseline_value: float | None = None,
    derivation_id: str | None = None,
    run_id: str | None = None,
) -> Forecast:
    if asset not in _ASSET_META:
        raise ValueError(f"unknown lens asset: {asset}")
    if direction not in {"up", "down", "flat"}:
        raise ValueError(f"invalid direction: {direction}")
    if not 1 <= int(horizon_days) <= 365:
        raise ValueError("horizon_days must be between 1 and 365")
    now = datetime.now(timezone.utc)
    row = Forecast(
        id=new_id(),
        run_id=run_id,
        derivation_id=derivation_id,
        code=f"lens.{asset}",
        subject="lens",
        direction=direction,
        horizon_days=int(horizon_days),
        made_at=now,
        target_date=(now + timedelta(days=int(horizon_days))).date(),
        probability=probability,
        method_id=METHOD_SYNTHESIS,
        status="open",
        baseline_value=baseline_value,
        notes=notes,
    )
    session.add(row)
    session.commit()
    return row


def forecast_payload(row: Forecast) -> dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "asset": row.code.replace("lens.", "", 1),
        "subject": row.subject,
        "direction": row.direction,
        "horizon_days": row.horizon_days,
        "made_at": row.made_at.isoformat() if row.made_at else None,
        "target_date": row.target_date.isoformat() if row.target_date else None,
        "probability": row.probability,
        "point": row.point,
        "status": row.status,
        "baseline_value": row.baseline_value,
        "notes": row.notes,
        "derivation_id": row.derivation_id,
    }
