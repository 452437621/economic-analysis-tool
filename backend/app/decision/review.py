"""Prediction review: Brier score, hit rate and calibration buckets."""

from __future__ import annotations

from sqlalchemy import select

from app.models.core import Instrument, Outcome, Prediction, TradePlan
from app.platform.db import SessionLocal


def summarize(records: list[dict]) -> dict:
    if not records:
        return {"count": 0, "brier": None, "hit_rate": None, "calibration": []}
    n = len(records)
    brier = sum(record["brier"] for record in records) / n
    hit_rate = sum(record["actual"] for record in records) / n
    buckets: dict[str, list[dict]] = {}
    for record in records:
        lower = int(record["probability"] * 10) / 10
        key = f"{lower:.1f}-{lower + 0.1:.1f}"
        buckets.setdefault(key, []).append(record)
    calibration = [
        {
            "bucket": key,
            "n": len(items),
            "avg_probability": round(sum(item["probability"] for item in items) / len(items), 3),
            "hit_rate": round(sum(item["actual"] for item in items) / len(items), 3),
        }
        for key, items in sorted(buckets.items())
    ]
    return {
        "count": n,
        "brier": round(brier, 4),
        "hit_rate": round(hit_rate, 3),
        "calibration": calibration,
    }


def review() -> dict:
    records: list[dict] = []
    with SessionLocal() as session:
        rows = session.execute(
            select(Prediction, Outcome, TradePlan, Instrument)
            .join(Outcome, Outcome.prediction_id == Prediction.id)
            .join(TradePlan, TradePlan.id == Prediction.plan_id)
            .join(Instrument, Instrument.id == TradePlan.instrument_id)
        ).all()
        for prediction, outcome, plan, instrument in rows:
            records.append(
                {
                    "prediction_id": prediction.id,
                    "symbol": instrument.symbol,
                    "side": plan.side,
                    "probability": prediction.probability,
                    "actual": outcome.actual,
                    "brier": outcome.score if outcome.score is not None else (prediction.probability - outcome.actual) ** 2,
                    "resolved_at": prediction.resolved_at.isoformat() if prediction.resolved_at else None,
                    "notes": outcome.notes,
                }
            )
    summary = summarize(records)
    summary["records"] = records[-20:]
    return summary
