"""Topic research API: registry, overview, refresh and per-topic settings."""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.platform.db import get_session
from app.topics import TopicAdapterMissing, build_overview
from app.topics import config as topic_config
from app.topics import storage

router = APIRouter(prefix="/api/topics", tags=["topics"])

_CACHE_TTL_SECONDS = 25
_overview_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _require_topic(topic_id: str):
    try:
        spec = topic_config.get_topic(topic_id)
    except topic_config.TopicConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if spec is None:
        raise HTTPException(status_code=404, detail=f"unknown topic: {topic_id}")
    if not spec.enabled:
        raise HTTPException(status_code=404, detail=f"topic disabled: {topic_id}")
    return spec


@router.get("")
def list_topics() -> dict:
    try:
        return topic_config.topic_list_payload()
    except topic_config.TopicConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{topic_id}/overview")
def overview(
    topic_id: str,
    series_limit: int = Query(2500, ge=60, le=6000),
    session: Session = Depends(get_session),
) -> dict:
    spec = _require_topic(topic_id)
    try:
        version = topic_config.config_version()
    except topic_config.TopicConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    data_version = storage.data_version(session, topic_id)
    key = f"{topic_id}:{version}:{data_version}:{series_limit}"
    cached = _overview_cache.get(key)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    try:
        payload = build_overview(spec, session, series_limit=series_limit, config_version=version)
    except TopicAdapterMissing as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except topic_config.TopicConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _overview_cache[key] = (time.monotonic(), payload)
    if len(_overview_cache) > 24:
        for stale in sorted(_overview_cache, key=lambda item: _overview_cache[item][0])[:8]:
            _overview_cache.pop(stale, None)
    return payload


@router.post("/{topic_id}/refresh")
def refresh(topic_id: str, background: BackgroundTasks) -> dict:
    spec = _require_topic(topic_id)
    job = spec.refresh_job
    if not job:
        raise HTTPException(status_code=400, detail=f"{topic_id} 未配置 refresh_job")

    def _run() -> None:
        from app.jobs.runner import run_job_locked

        run_job_locked(job)
        _overview_cache.clear()

    background.add_task(_run)
    return {"accepted": True, "job": job, "message": f"{spec.label} 采集已开始"}


class DividendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    per_share: float = Field(ge=0)


class PositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buy_price: float | None = Field(default=None, gt=0)
    buy_date: str | None = None
    shares_lots: float | None = Field(default=None, ge=0)
    dividends: list[DividendIn] | None = None
    add_prices: list[float] | None = None
    add_ratios: list[float] | None = None

    @field_validator("buy_date")
    @classmethod
    def _check_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            date.fromisoformat(value if len(value) > 7 else f"{value}-01")
        except ValueError as exc:
            raise ValueError("buy_date 需为 YYYY-MM 或 YYYY-MM-DD") from exc
        return value

    @field_validator("dividends")
    @classmethod
    def _check_dividends(cls, value: list[DividendIn] | None) -> list[DividendIn] | None:
        if value is None:
            return None
        for item in value:
            try:
                date.fromisoformat(item.date)
            except ValueError as exc:
                raise ValueError(f"分红日期非法：{item.date}") from exc
        return value

    @field_validator("add_prices")
    @classmethod
    def _check_add_prices(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if any(item <= 0 for item in value):
            raise ValueError("add_prices 必须全部大于 0")
        return value

    @field_validator("add_ratios")
    @classmethod
    def _check_add_ratios(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if any(item < 0 for item in value):
            raise ValueError("add_ratios 必须全部大于等于 0")
        return value


def _position_defaults(spec) -> dict[str, Any]:
    raw = (spec.params or {}).get("position_defaults") or {}
    dividends = raw.get("dividends") or []
    return {
        "buy_price": raw.get("buy_price"),
        "buy_date": raw.get("buy_date"),
        "shares_lots": raw.get("shares_lots"),
        "dividends": [
            {"date": str(item.get("date")), "per_share": float(item.get("per_share") or 0)}
            for item in dividends
            if isinstance(item, dict)
        ],
        "add_prices": [float(item) for item in raw.get("add_prices") or []],
        "add_ratios": [float(item) for item in raw.get("add_ratios") or []],
    }


def _position_payload(session: Session, spec) -> dict[str, Any]:
    defaults = _position_defaults(spec)
    overrides, updated_at = storage.get_setting(session, spec.id)
    effective = {**defaults, **{key: value for key, value in overrides.items() if value is not None}}
    return {
        "topic_id": spec.id,
        "defaults": defaults,
        "overrides": overrides,
        "effective": effective,
        "editable": ["buy_price", "buy_date", "shares_lots", "dividends", "add_prices", "add_ratios"],
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


@router.get("/{topic_id}/position")
def get_position(topic_id: str, session: Session = Depends(get_session)) -> dict:
    spec = _require_topic(topic_id)
    if not _position_defaults(spec).get("buy_price"):
        raise HTTPException(status_code=404, detail=f"{topic_id} 未配置持仓参数")
    return _position_payload(session, spec)


@router.put("/{topic_id}/position")
def put_position(
    topic_id: str,
    payload: PositionIn,
    session: Session = Depends(get_session),
) -> dict:
    spec = _require_topic(topic_id)
    if not _position_defaults(spec).get("buy_price"):
        raise HTTPException(status_code=404, detail=f"{topic_id} 未配置持仓参数")
    overrides, _ = storage.get_setting(session, spec.id)
    patch = payload.model_dump(exclude_unset=True)
    if patch.get("dividends") is not None:
        patch["dividends"] = [
            {"date": item["date"], "per_share": float(item["per_share"])} for item in patch["dividends"]
        ]
    merged = {**overrides, **{key: value for key, value in patch.items() if value is not None}}
    storage.save_setting(session, spec.id, merged)
    session.commit()
    _overview_cache.clear()
    return _position_payload(session, spec)
