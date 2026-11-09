"""Thesis & scenario APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Claim, Scenario, Thesis, ThesisEvidence
from app.platform.db import get_session

router = APIRouter(prefix="/api/theses", tags=["theses"])

STATUSES = {"active", "watch", "closed", "invalidated"}


class ThesisStatus(BaseModel):
    status: str


@router.get("")
def list_theses(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    rows = session.scalars(select(Thesis).order_by(Thesis.created_at.desc()).limit(limit)).all()
    evidence_counts = dict(
        session.execute(
            select(ThesisEvidence.thesis_id, func.count()).group_by(ThesisEvidence.thesis_id)
        ).all()
    )
    scenarios = {}
    for row in session.scalars(select(Scenario)).all():
        scenarios.setdefault(row.thesis_id, []).append(
            {
                "name": row.name,
                "probability": row.probability,
                "triggers": row.triggers,
                "impacts": row.impacts,
            }
        )
    return {
        "data": [
            {
                "id": row.id,
                "title": row.title,
                "direction": row.direction,
                "prior": row.prior,
                "posterior": row.posterior,
                "horizon_days": row.horizon_days,
                "status": row.status,
                "invalidation": row.invalidation,
                "main_driver": row.main_driver,
                "evidence_count": int(evidence_counts.get(row.id, 0)),
                "scenarios": scenarios.get(row.id, []),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.patch("/{thesis_id}")
def update_status(
    thesis_id: str,
    payload: ThesisStatus,
    session: Session = Depends(get_session),
) -> dict:
    if payload.status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"invalid status: {payload.status}")
    thesis = session.get(Thesis, thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="thesis not found")
    thesis.status = payload.status
    session.commit()
    return {"id": thesis.id, "status": thesis.status}


@router.get("/{thesis_id}")
def thesis_detail(thesis_id: str, session: Session = Depends(get_session)) -> dict:
    thesis = session.get(Thesis, thesis_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail="thesis not found")
    evidence = session.execute(
        select(ThesisEvidence, Claim)
        .join(Claim, Claim.id == ThesisEvidence.claim_id)
        .where(ThesisEvidence.thesis_id == thesis_id)
    ).all()
    scenarios = session.scalars(select(Scenario).where(Scenario.thesis_id == thesis_id)).all()
    return {
        "id": thesis.id,
        "title": thesis.title,
        "direction": thesis.direction,
        "prior": thesis.prior,
        "posterior": thesis.posterior,
        "status": thesis.status,
        "invalidation": thesis.invalidation,
        "main_driver": thesis.main_driver,
        "evidence": [
            {
                "claim_id": claim.id,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "value": claim.value,
                "unit": claim.unit,
                "weight": link.weight,
                "note": link.note,
            }
            for link, claim in evidence
        ],
        "scenarios": [
            {
                "name": row.name,
                "probability": row.probability,
                "triggers": row.triggers,
                "impacts": row.impacts,
            }
            for row in scenarios
        ],
    }
