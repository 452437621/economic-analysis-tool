"""Analytics runner: compute all M3 results and persist snapshots."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.analytics.analogs import build_state, find_analogs
from app.analytics.attribution import build_drivers, decompose
from app.analytics.correlation import correlation_snapshot
from app.analytics.data import aligned, load_frames
from app.analytics.indicators import compute_indicators
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
    row = session.scalar(
        select(AnalyticsResult).where(
            AnalyticsResult.kind == kind,
            AnalyticsResult.subject == subject,
            AnalyticsResult.asof == asof,
        )
    )
    if row is None:
        session.add(
            AnalyticsResult(kind=kind, subject=subject, asof=asof, payload=payload, code_version="m3.0")
        )
    else:
        row.payload = payload
        row.created_at = datetime.now(timezone.utc)


def run_analytics() -> dict:
    frames = load_frames()
    closes, macro = aligned(frames)
    if closes.empty or macro.empty:
        raise RuntimeError("no daily bars or macro data available for analytics")

    asof = _asof(closes)
    counts = {"indicators": 0, "regimes": 0, "attribution": 0, "correlation": 0, "wind": 0, "analogs": 0}

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

        session.commit()

    logger.info("run_analytics: %s", counts)
    counts["asof"] = asof.date().isoformat()
    return counts
