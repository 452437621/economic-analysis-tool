"""Decision runner: generate signals, plans, checks, predictions and backtest stats."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.analytics.data import aligned, load_frames
from app.decision.backtest import backtest_all
from app.decision.plans import build_plan
from app.decision.signals import generate_all
from app.models.core import (
    AnalyticsResult,
    Instrument,
    PlanCheck,
    PlanDetail,
    Prediction,
    Signal,
    TradePlan,
    WatchItem,
)
from app.platform.config import settings
from app.platform.db import SessionLocal
from app.platform.quality_gate import assess as assess_quality

logger = logging.getLogger(__name__)

MAX_PLANS = 6
MIN_STRENGTH = 0.5


def _asof(closes) -> datetime:  # noqa: ANN001
    latest = closes.index[-1].to_pydatetime()
    if latest.tzinfo is None:
        return latest.replace(tzinfo=timezone.utc)
    return latest


def run_decision() -> dict:
    frames = load_frames()
    closes, _ = aligned(frames)
    if closes.empty:
        raise RuntimeError("no daily bars for decision engine")

    with SessionLocal() as quality_session:
        quality = assess_quality(quality_session)
    if quality["status"] in {"blocked", "unknown"}:
        return {
            "status": "blocked" if quality["status"] == "blocked" else "degraded",
            "skipped": "quality_gate",
            "quality": quality,
            "reason": quality.get("caveat"),
            "signals": 0,
            "plans": 0,
        }

    asof = _asof(closes)
    if settings.watchlist_only:
        with SessionLocal() as watch_session:
            watch_symbols = {
                row.symbol
                for row in watch_session.scalars(
                    select(Instrument)
                    .join(WatchItem, WatchItem.instrument_id == Instrument.id)
                ).all()
            }
        keep = [symbol for symbol in closes.columns if symbol in watch_symbols]
        if keep:
            closes = closes[keep]
    signals = generate_all(closes)
    backtests = backtest_all(closes)
    counts = {"signals": 0, "plans": 0, "checks": 0, "predictions": 0, "backtests": 0}

    with SessionLocal() as session:
        session.execute(delete(Signal).where(Signal.ts >= asof))
        draft_ids = session.scalars(
            select(TradePlan.id).where(TradePlan.status == "draft")
        ).all()
        if draft_ids:
            session.execute(delete(Prediction).where(Prediction.plan_id.in_(draft_ids)))
        session.execute(delete(TradePlan).where(TradePlan.status == "draft"))
        session.execute(
            delete(AnalyticsResult).where(
                AnalyticsResult.kind == "signal_backtest", AnalyticsResult.asof == asof
            )
        )
        instrument_ids = {row.symbol: row.id for row in session.scalars(select(Instrument)).all()}
        instruments = {row.symbol: row for row in session.scalars(select(Instrument)).all()}

        saved: list[dict] = []
        for item in signals:
            instrument_id = instrument_ids.get(item["symbol"])
            if instrument_id is None:
                continue
            row = Signal(
                type=item["type"],
                instrument_id=instrument_id,
                ts=asof,
                direction=item["direction"],
                strength=item["strength"],
                params={
                    "price": item["price"],
                    "atr": item["atr"],
                    "note": item["note"],
                    **item.get("params", {}),
                },
                note=item["note"],
            )
            session.add(row)
            session.flush()
            item["signal_id"] = row.id
            saved.append(item)
            counts["signals"] += 1

        for item in saved[:MAX_PLANS]:
            if item["strength"] < MIN_STRENGTH:
                continue
            instrument = instruments[item["symbol"]]
            spec = {
                "contract_size": instrument.contract_size,
                "margin_pct": instrument.margin_pct,
                **(instrument.extra or {}),
            }
            plan = build_plan(item, spec=spec)
            plan["checks"].append(
                {
                    "rule": "数据质量门",
                    "passed": quality["status"] in {"ok", "degraded"},
                    "detail": quality.get("caveat") or f"status={quality['status']}",
                }
            )
            trade_plan = TradePlan(
                signal_id=item["signal_id"],
                instrument_id=instrument.id,
                side=plan["side"],
                entry_low=plan["entry_low"],
                entry_high=plan["entry_high"],
                stop=plan["stop"],
                targets=plan["targets"],
                size=plan["size"],
                risk_pct=plan["risk_pct"],
                time_stop_days=plan["time_stop_days"],
                invalidation=plan["invalidation"],
                status="draft",
            )
            session.add(trade_plan)
            session.flush()
            counts["plans"] += 1

            session.add(
                PlanDetail(
                    plan_id=trade_plan.id,
                    payload={
                        "lots": plan["size"],
                        "lots_int": plan["lots_int"],
                        "raw_lots": plan["raw_lots"],
                        "contract_size": plan["contract_size"],
                        "margin_pct": plan["margin_pct"],
                        "notional": plan["notional"],
                        "margin": plan["margin"],
                        "fee": plan["fee"],
                        "risk_amount": plan["risk_amount"],
                        "stop_distance_pct": plan["stop_distance_pct"],
                        "weight_pct": plan["weight_pct"],
                        "leverage": plan["leverage"],
                        "risk_reward": plan["risk_reward"],
                        "sizing_note": plan["sizing_note"],
                        "base_equity": plan["base_equity"],
                        "equity": plan["equity"],
                        "checks": plan["checks"],
                        "quality_gate": quality,
                    },
                )
            )

            for check in plan["checks"]:
                session.add(
                    PlanCheck(
                        plan_id=trade_plan.id,
                        rule=check["rule"],
                        passed=check["passed"],
                        detail=check["detail"],
                    )
                )
                counts["checks"] += 1

            session.add(
                Prediction(
                    plan_id=trade_plan.id,
                    probability=0.55,
                    horizon_days=plan["time_stop_days"],
                    status="open",
                )
            )
            counts["predictions"] += 1

        for rule, payload in backtests.items():
            session.add(
                AnalyticsResult(
                    kind="signal_backtest",
                    subject=rule,
                    asof=asof,
                    payload=payload,
                    code_version="m4.0",
                )
            )
            counts["backtests"] += 1

        session.commit()

    logger.info("run_decision: %s", counts)
    counts["asof"] = asof.date().isoformat()
    counts["quality"] = quality
    if quality["status"] != "ok":
        counts["status"] = "degraded"
    return counts
