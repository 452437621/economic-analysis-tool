"""V2.0 玻璃盒读接口：运行、步骤、推导、方法、观测。

设计依据 docs/20-功能与接口设计.md（F19/F20/F31），路径前缀 /api/v2。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.serializers import iso, run_payload
from app.models.v2 import (
    AnalysisRun,
    AnalysisStep,
    Derivation,
    DerivationLink,
    MethodRegistry,
    Observation,
    RuleHit,
)
from app.platform.db import get_session

router = APIRouter(prefix="/api/v2", tags=["glassbox"])


def _iso(value) -> str | None:  # noqa: ANN001
    return iso(value)


def _run_dict(row: AnalysisRun) -> dict:
    return run_payload(row)


def _step_dict(row: AnalysisStep) -> dict:
    return {
        "id": row.id,
        "seq": row.seq,
        "name": row.name,
        "kind": row.kind,
        "status": row.status,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "duration_ms": row.duration_ms,
        "inputs": row.inputs,
        "outputs": row.outputs,
        "params": row.params,
        "error": row.error,
    }


def _derivation_dict(row: Derivation) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "code": row.code,
        "subject": row.subject,
        "claim": row.claim,
        "value": row.value,
        "confidence": row.confidence,
        "evidence_grade": row.evidence_grade,
        "method_id": row.method_id,
        "inputs": row.inputs or [],
        "steps": row.steps or [],
        "rules_hit": row.rules_hit or [],
        "caveats": row.caveats or [],
        "falsifiers": row.falsifiers or [],
        "opposing": row.opposing or [],
        "asof": _iso(row.asof),
        "created_at": _iso(row.created_at),
    }


def _method_dict(row: MethodRegistry) -> dict:
    return {
        "method_id": row.method_id,
        "name": row.name,
        "version": row.version,
        "kind": row.kind,
        "description": row.description,
        "code_sha": row.code_sha,
        "params_schema": row.params_schema,
    }


@router.get("/runs")
def list_runs(
    kind: str | None = Query(default=None, max_length=40),
    subject: str | None = Query(default=None, max_length=60),
    status: str | None = Query(default=None, max_length=16),
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(AnalysisRun).order_by(AnalysisRun.started_at.desc())
    if kind:
        stmt = stmt.where(AnalysisRun.kind == kind)
    if subject:
        stmt = stmt.where(AnalysisRun.subject == subject)
    if status:
        stmt = stmt.where(AnalysisRun.status == status)
    rows = session.scalars(stmt.limit(limit)).all()
    total = session.scalar(select(func.count()).select_from(AnalysisRun)) or 0
    return {
        "items": [_run_dict(row) for row in rows],
        "total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(AnalysisRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    steps = session.scalars(
        select(AnalysisStep).where(AnalysisStep.run_id == run_id).order_by(AnalysisStep.seq.asc())
    ).all()
    rules = session.scalars(
        select(RuleHit).where(RuleHit.run_id == run_id).order_by(RuleHit.created_at.asc())
    ).all()
    derivations = session.scalars(
        select(Derivation).where(Derivation.run_id == run_id).order_by(Derivation.created_at.asc())
    ).all()
    return {
        "run": _run_dict(row),
        "steps": [_step_dict(step) for step in steps],
        "rules": [
            {
                "rule_id": item.rule_id,
                "severity": item.severity,
                "fired": bool(item.fired),
                "message": item.message,
                "inputs": item.inputs,
                "created_at": _iso(item.created_at),
            }
            for item in rules
        ],
        "derivations": [_derivation_dict(item) for item in derivations],
    }


@router.get("/derivations")
def list_derivations(
    code: str | None = Query(default=None, max_length=80),
    subject: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(Derivation).order_by(Derivation.asof.desc(), Derivation.created_at.desc())
    if code:
        stmt = stmt.where(Derivation.code == code)
    if subject:
        stmt = stmt.where(Derivation.subject == subject)
    rows = session.scalars(stmt.limit(limit)).all()
    return {"items": [_derivation_dict(row) for row in rows], "total": len(rows)}


@router.get("/derivations/{derivation_id}")
def get_derivation(derivation_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(Derivation, derivation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="derivation not found")
    parents = session.scalars(
        select(Derivation).join(DerivationLink, DerivationLink.parent_id == Derivation.id).where(
            DerivationLink.child_id == derivation_id
        )
    ).all()
    children = session.scalars(
        select(Derivation).join(DerivationLink, DerivationLink.child_id == Derivation.id).where(
            DerivationLink.parent_id == derivation_id
        )
    ).all()
    method = session.get(MethodRegistry, row.method_id) if row.method_id else None
    return {
        "derivation": _derivation_dict(row),
        "method": _method_dict(method) if method else None,
        "parents": [_derivation_dict(item) for item in parents],
        "children": [_derivation_dict(item) for item in children],
    }


@router.get("/methods")
def list_methods(session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(select(MethodRegistry).order_by(MethodRegistry.method_id.asc())).all()
    return {"items": [_method_dict(row) for row in rows], "total": len(rows)}


@router.get("/observations")
def list_observations(
    code: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(Observation).order_by(Observation.asof.desc())
    if code:
        stmt = stmt.where(Observation.code == code)
    rows = session.scalars(stmt.limit(limit)).all()
    return {
        "items": [
            {
                "id": row.id,
                "code": row.code,
                "asof": _iso(row.asof),
                "vintage_date": _iso(row.vintage_date),
                "value": row.value,
                "unit": row.unit,
                "source": row.source,
                "evidence_grade": row.evidence_grade,
                "extra": row.extra,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    """玻璃盒首页摘要：最近一次运行、失败/降级计数、推导与观测规模。"""
    last = session.scalar(select(AnalysisRun).order_by(AnalysisRun.started_at.desc()).limit(1))
    counts = {
        "runs": session.scalar(select(func.count()).select_from(AnalysisRun)) or 0,
        "degraded": session.scalar(
            select(func.count()).select_from(AnalysisRun).where(AnalysisRun.degraded.is_(True))
        )
        or 0,
        "failed": session.scalar(
            select(func.count()).select_from(AnalysisRun).where(AnalysisRun.status == "failed")
        )
        or 0,
        "derivations": session.scalar(select(func.count()).select_from(Derivation)) or 0,
        "observations": session.scalar(select(func.count()).select_from(Observation)) or 0,
        "methods": session.scalar(select(func.count()).select_from(MethodRegistry)) or 0,
    }
    return {
        "last_run": _run_dict(last) if last else None,
        "counts": counts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
