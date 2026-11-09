"""Analytics runner: compute all M3 results and persist snapshots."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.analytics.analogs import build_state, find_analogs
from app.analytics.attribution import build_drivers, decompose
from app.analytics.calendar_study import build_calendar_study
from app.analytics.correlation import correlation_snapshot
from app.analytics.data import aligned, load_frames
from app.analytics.events import build_event_study
from app.analytics.indicators import compute_indicators
from app.analytics.leadlag import leadlag_pairs
from app.analytics.regime import compute_regimes
from app.analytics.wind import compute_wind
from app.models.core import AnalyticsResult
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

ATTRIBUTION_SYMBOLS = ["AU", "AG", "CU", "SC", "603993", "000300"]


def _asof(closes) -> datetime:  # noqa: ANN001
    latest = closes.index[-1].to_pydatetime()
    if latest.tzinfo is None:
        return latest.replace(tzinfo=timezone.utc)
    return latest


def _save(session, kind: str, subject: str, asof: datetime, payload: dict) -> None:  # noqa: ANN001
    # 每类结果只保留最新快照，避免旧的 asof 覆盖新计算结果
    session.execute(
        delete(AnalyticsResult).where(
            AnalyticsResult.kind == kind, AnalyticsResult.subject == subject
        )
    )
    session.add(
        AnalyticsResult(kind=kind, subject=subject, asof=asof, payload=payload, code_version="m3.0")
    )


def run_analytics() -> dict:
    frames = load_frames()
    closes, macro = aligned(frames)
    if closes.empty or macro.empty:
        raise RuntimeError("no daily bars or macro data available for analytics")

    asof = _asof(closes)
    counts = {
        "indicators": 0,
        "regimes": 0,
        "attribution": 0,
        "correlation": 0,
        "wind": 0,
        "analogs": 0,
        "leadlag": 0,
        "events": 0,
    }
    with SessionLocal() as session:
        for symbol in closes.columns:
            oi = frames.open_interest[symbol] if symbol in frames.open_interest.columns else None
            payload = compute_indicators(symbol, closes[symbol], oi)
            if payload:
                _save(session, "indicator", symbol, asof, payload)
                counts["indicators"] += 1

        for country, payload in compute_regimes(closes, macro).items():
            _save(session, "regime", country, asof, payload)
            counts["regimes"] += 1

        wind = compute_wind(closes, macro)
        if wind:
            _save(session, "wind", "market", asof, wind)
            counts["wind"] = 1

        correlation = correlation_snapshot(closes)
        if correlation:
            _save(session, "correlation", "matrix", asof, correlation)
            counts["correlation"] = 1

        drivers = build_drivers(macro)
        if "DXY" in closes.columns:
            drivers["dxy_chg"] = closes["DXY"].pct_change()
        if not drivers.empty:
            for symbol in ATTRIBUTION_SYMBOLS:
                if symbol not in closes.columns:
                    continue
                payload = decompose(closes[symbol].pct_change(), drivers)
                if payload:
                    _save(session, "attribution", symbol, asof, payload)
                    counts["attribution"] += 1

        state = build_state(closes, macro)
        analogs = find_analogs(state, closes)
        if analogs:
            _save(session, "analogs", "current", asof, analogs)
            counts["analogs"] = 1

        leadlag = leadlag_pairs(closes)
        if leadlag:
            _save(session, "leadlag", "pairs", asof, leadlag)
            counts["leadlag"] = 1

        events = build_event_study(closes)
        if events:
            _save(session, "event_study", "library", asof, events)
            counts["events"] = 1

        from app.models.core import EconomicEvent

        calendar_rows = session.scalars(
            select(EconomicEvent)
            .where(
                EconomicEvent.ts_utc >= asof - timedelta(days=365),
                EconomicEvent.ts_utc <= asof,
                EconomicEvent.importance >= 3,
            )
            .order_by(EconomicEvent.ts_utc.asc())
        ).all()
        calendar_payload = build_calendar_study(
            closes,
            [
                {
                    "ts": row.ts_utc,
                    "name": row.name,
                    "country": row.country,
                    "importance": row.importance,
                }
                for row in calendar_rows
            ],
        )
        if calendar_payload.get("groups"):
            _save(session, "calendar_study", "market", asof, calendar_payload)
            counts["calendar_study"] = 1

        session.commit()

    logger.info("run_analytics: %s", counts)
    counts["asof"] = asof.date().isoformat()
    return counts
