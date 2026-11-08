"""Prediction ledger scoring: resolve open predictions against daily bars."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.core import MarketBar, Outcome, Prediction, TradePlan
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def score_predictions() -> dict:
    resolved = 0
    skipped = 0
    with SessionLocal() as session:
        predictions = session.scalars(
            select(Prediction).where(Prediction.status == "open")
        ).all()
        for prediction in predictions:
            plan = session.get(TradePlan, prediction.plan_id) if prediction.plan_id else None
            if plan is None:
                skipped += 1
                continue
            horizon = prediction.horizon_days or 10
            bars = session.scalars(
                select(MarketBar)
                .where(
                    MarketBar.instrument_id == plan.instrument_id,
                    MarketBar.timeframe == "1d",
                    MarketBar.ts_utc >= prediction.made_at,
                )
                .order_by(MarketBar.ts_utc)
                .limit(horizon + 1)
            ).all()
            if len(bars) <= horizon:
                skipped += 1
                continue
            entry = (
                (plan.entry_low + plan.entry_high) / 2
                if plan.entry_low and plan.entry_high
                else bars[0].open
            )
            stop = plan.stop
            target = (plan.targets or {}).get("T1")
            is_long = plan.side == "long"
            outcome: int | None = None
            reason = None
            for bar in bars[:horizon]:
                if is_long:
                    if stop and bar.low <= stop:
                        outcome, reason = 0, f"止损触发 @{stop:.4f}"
                        break
                    if target and bar.high >= target:
                        outcome, reason = 1, f"目标达成 @{target:.4f}"
                        break
                else:
                    if stop and bar.high >= stop:
                        outcome, reason = 0, f"止损触发 @{stop:.4f}"
                        break
                    if target and bar.low <= target:
                        outcome, reason = 1, f"目标达成 @{target:.4f}"
                        break
            if outcome is None:
                final = bars[horizon - 1].close
                signed = (final / entry - 1) * (1 if is_long else -1)
                outcome = 1 if signed > 0 else 0
                reason = f"到期结算 {signed * 100:.2f}%"

            brier = (prediction.probability - outcome) ** 2
            session.add(
                Outcome(
                    prediction_id=prediction.id,
                    actual=float(outcome),
                    score=brier,
                    notes=reason,
                )
            )
            prediction.status = "resolved"
            prediction.resolved_at = datetime.now(timezone.utc)
            prediction.brier = brier
            resolved += 1
        session.commit()

    logger.info("score_predictions: resolved=%s skipped=%s", resolved, skipped)
    return {"resolved": resolved, "skipped": skipped}
