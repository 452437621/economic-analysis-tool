"""Gold monitoring API: composite score, indicators, series, providers, manual input."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gold.registry import CATEGORY_LABELS, INDICATORS, SERIES_CODES, manual_codes
from app.gold.runner import collect_gold, latest_provider_runs
from app.gold.scoring import compute_gold_score, history
from app.models.core import GoldMetric
from app.platform.db import get_session

router = APIRouter(prefix="/api/gold", tags=["gold"])


class ManualMetricIn(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    value: float
    as_of: date | None = None
    source: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=500)


@router.get("/overview")
def overview(
    series_limit: int = Query(160, ge=10, le=3000),
    session: Session = Depends(get_session),
) -> dict:
    """Gold dashboard payload: score + factors + series + provider health."""
    score = compute_gold_score(session)
    series: dict[str, list[dict]] = {}
    for code in SERIES_CODES:
        series[code] = [
            {"t": as_of.isoformat(), "v": round(value, 4)}
            for as_of, value in history(session, code, limit=series_limit)
        ]
    manual = []
    for code in manual_codes():
        item = INDICATORS[code]
        obs = history(session, code, limit=2)
        manual.append(
            {
                "code": code,
                "name": item.name,
                "category": item.category,
                "unit": item.unit,
                "freq": item.freq,
                "source": item.source,
                "weight": item.weight,
                "available": bool(obs),
                "value": round(obs[-1][1], 4) if obs else None,
                "as_of": obs[-1][0].isoformat() if obs else None,
                "note": item.note,
            }
        )
    return {
        "score": score,
        "series": series,
        "providers": latest_provider_runs(session),
        "manual": manual,
        "indicators": [
            {
                "code": code,
                "name": item.name,
                "category": item.category,
                "unit": item.unit,
                "freq": item.freq,
                "source": item.source,
                "weight": item.weight,
                "direction": item.direction,
                "manual": item.manual,
                "note": item.note,
            }
            for code, item in INDICATORS.items()
        ],
        "categories": [{"key": key, "label": label} for key, label in CATEGORY_LABELS.items()],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/series")
def series(
    code: str = Query(..., min_length=1, max_length=48),
    limit: int = Query(240, ge=2, le=2000),
    session: Session = Depends(get_session),
) -> dict:
    if code not in INDICATORS:
        raise HTTPException(status_code=404, detail=f"unknown gold indicator: {code}")
    item = INDICATORS[code]
    return {
        "code": code,
        "name": item.name,
        "unit": item.unit,
        "freq": item.freq,
        "source": item.source,
        "data": [{"t": as_of.isoformat(), "v": round(value, 4)} for as_of, value in history(session, code, limit)],
    }


@router.get("/providers")
def providers(session: Session = Depends(get_session)) -> dict:
    return {"data": latest_provider_runs(session)}


@router.post("/metrics")
def save_manual_metric(
    payload: ManualMetricIn,
    session: Session = Depends(get_session),
) -> dict:
    """手动录入无法自动采集的指标（BIS 租赁/掉期、COMEX/SGE 库存、银行净合约等）。"""
    code = payload.code
    if code not in INDICATORS:
        raise HTTPException(status_code=404, detail=f"unknown gold indicator: {code}")
    if not INDICATORS[code].manual:
        raise HTTPException(status_code=400, detail=f"{code} 由自动采集维护，不支持手动写入")
    as_of = datetime.combine(payload.as_of or date.today(), time.min, tzinfo=timezone.utc)
    row = session.scalar(
        select(GoldMetric).where(GoldMetric.code == code, GoldMetric.as_of == as_of)
    )
    if row is None:
        row = GoldMetric(code=code, as_of=as_of, value=payload.value, source=payload.source or "manual")
        session.add(row)
    else:
        row.value = payload.value
        row.source = payload.source or "manual"
    if payload.note:
        row.extra = {**(row.extra or {}), "note": payload.note}
    session.commit()
    return {"code": code, "as_of": as_of.isoformat(), "value": payload.value, "saved": True}


@router.post("/refresh")
def refresh(background: BackgroundTasks) -> dict:
    """异步执行一次 gold 采集（下载 WGC/CFTC/LBMA 等，耗时约 20-60s）。"""
    background.add_task(collect_gold)
    return {"accepted": True, "message": "gold collection started in background"}
