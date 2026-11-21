"""V2.0 世界长河接口：事件、霸权周期、实力/储备份额、当下坐标。

读接口只读最近一次运行的持久化结果；库为空时 GET /overview 会懒触发一次
``run_timeline``，保证首次打开页面就有内容。写操作只有 POST /run。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import iso
from app.models.v2 import AnalysisRun, Derivation, PowerIndex, TimelineEvent
from app.platform.db import get_session
from app.timeline import dataset
from app.timeline.engine import run_timeline

router = APIRouter(prefix="/api/v2/timeline", tags=["timeline"])


_iso = iso


def _event_payload(row: TimelineEvent) -> dict:
    return {
        "id": row.id,
        "year": row.year,
        "month": row.month,
        "title": row.title,
        "category": row.category,
        "category_label": dataset.CATEGORY_LABELS.get(row.category, row.category),
        "layer": row.layer,
        "layer_label": dataset.LAYER_LABELS.get(row.layer, row.layer),
        "evidence_grade": row.evidence_grade,
        "power": row.related_power,
        "power_label": dataset.POWER_LABELS.get(row.related_power or "", row.related_power),
        "summary": row.summary,
        "source_url": row.source_url,
    }


def _latest(session: Session, code: str) -> Derivation | None:
    return session.scalar(
        select(Derivation).where(Derivation.code == code).order_by(Derivation.asof.desc()).limit(1)
    )


def _position_payload(session: Session) -> dict | None:
    row = _latest(session, "timeline.position")
    if row is None:
        return None
    return {
        "code": row.code,
        "claim": row.claim,
        "value": row.value,
        "confidence": row.confidence,
        "evidence_grade": row.evidence_grade,
        "asof": _iso(row.asof),
        "run_id": row.run_id,
        "caveats": row.caveats or [],
        "falsifiers": row.falsifiers or [],
        "opposing": row.opposing or [],
    }


def _power_rows(session: Session, indicator: str) -> list[dict]:
    rows = session.scalars(
        select(PowerIndex)
        .where(PowerIndex.indicator == indicator)
        .order_by(PowerIndex.power, PowerIndex.year)
    ).all()
    return [
        {
            "power": row.power,
            "power_label": dataset.POWER_LABELS.get(row.power, row.power.upper()),
            "year": row.year,
            "value": row.value,
            "unit": row.unit,
            "evidence_grade": row.evidence_grade,
            "source_url": row.source_url,
        }
        for row in rows
    ]


def _counts(session: Session) -> dict:
    events = session.scalars(select(TimelineEvent)).all()
    grades: dict[str, int] = {}
    layers: dict[str, int] = {}
    for row in events:
        grades[row.evidence_grade] = grades.get(row.evidence_grade, 0) + 1
        layers[row.layer] = layers.get(row.layer, 0) + 1
    return {
        "events": len(events),
        "eras": len(dataset.ERAS),
        "lessons": len(dataset.LESSONS),
        "grades": grades,
        "layers": layers,
    }


def _last_run(session: Session) -> AnalysisRun | None:
    return session.scalar(
        select(AnalysisRun).where(AnalysisRun.kind == "timeline").order_by(AnalysisRun.started_at.desc()).limit(1)
    )


def _ensure(session: Session) -> None:
    if session.scalar(select(TimelineEvent).limit(1)) is None:
        run_timeline(session)


def _era_payload(era: dict) -> dict:
    """A8: merge stage fields with defaults so the API contract is stable."""
    return {
        **era,
        "golden_age": era.get("golden_age"),
        "turning": era.get("turning"),
        "current_stage": era.get("current_stage") or "",
    }


@router.get("/overview")
def overview(session: Session = Depends(get_session)) -> dict:
    _ensure(session)
    run = _last_run(session)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asof": _iso(run.asof) if run else None,
        "run_id": run.id if run else None,
        "status": run.status if run else None,
        "degraded": bool(run.degraded) if run else False,
        "degraded_reasons": (run.degraded_reasons or []) if run else [],
        "counts": _counts(session),
        "eras": [_era_payload(era) for era in dataset.ERAS],
        "events": [_event_payload(row) for row in session.scalars(select(TimelineEvent).order_by(TimelineEvent.year, TimelineEvent.title)).all()],
        "powers": {
            "gdp": _power_rows(session, "gdp_share"),
            "reserve": _power_rows(session, "reserve_share"),
        },
        "position": _position_payload(session),
        "lessons": dataset.LESSONS,
        "labels": {
            "categories": dataset.CATEGORY_LABELS,
            "layers": dataset.LAYER_LABELS,
            "powers": dataset.POWER_LABELS,
        },
    }


@router.get("/events")
def events(
    era: str | None = Query(None, description="时期 id，如 netherlands / uk"),
    layer: str | None = Query(None, pattern="^[LBS]$"),
    power: str | None = None,
    grade: str | None = Query(None, pattern="^[ABC]$"),
    year_from: int | None = Query(None, ge=1400, le=2030),
    year_to: int | None = Query(None, ge=1400, le=2030),
    q: str | None = Query(None, max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    _ensure(session)
    stmt = select(TimelineEvent).order_by(TimelineEvent.year)
    if layer:
        stmt = stmt.where(TimelineEvent.layer == layer)
    if power:
        stmt = stmt.where(TimelineEvent.related_power == power)
    if grade:
        stmt = stmt.where(TimelineEvent.evidence_grade == grade)
    if year_from is not None:
        stmt = stmt.where(TimelineEvent.year >= year_from)
    if year_to is not None:
        stmt = stmt.where(TimelineEvent.year <= year_to)
    if q:
        stmt = stmt.where(TimelineEvent.title.contains(q))
    if era:
        era_row = next((item for item in dataset.ERAS if item["id"] == era), None)
        if era_row is None:
            raise HTTPException(status_code=404, detail=f"unknown era: {era}")
        stmt = stmt.where(
            TimelineEvent.year >= int(era_row["rise"]),
            TimelineEvent.year <= int(era_row["decline"]) + 10,
        )
    rows = session.scalars(stmt).all()
    return {"items": [_event_payload(row) for row in rows], "total": len(rows)}


@router.get("/eras")
def eras() -> dict:
    items = [_era_payload(era) for era in dataset.ERAS]
    return {"items": items, "total": len(items)}


@router.get("/powers")
def powers(session: Session = Depends(get_session)) -> dict:
    _ensure(session)
    return {
        "gdp": _power_rows(session, "gdp_share"),
        "reserve": _power_rows(session, "reserve_share"),
    }


@router.get("/position")
def position(session: Session = Depends(get_session)) -> dict:
    _ensure(session)
    payload = _position_payload(session)
    if payload is None:
        raise HTTPException(status_code=503, detail="timeline position not generated yet")
    return payload


@router.post("/run")
def run(session: Session = Depends(get_session)) -> dict:
    result = run_timeline(session)
    return {
        "ok": True,
        "run_id": result["run_id"],
        "status": result["status"],
        "events": result["events"],
        "eras": result["eras"],
        "lessons": result["lessons"],
        "cycle_found": result["cycle"] is not None,
    }
