"""Shared scoring primitives for topic research.

Every topic expresses its drivers as factors in the same ``-1..1`` space:
``score`` is the direction-adjusted factor score, ``weight`` its relative
importance and ``contribution = weight * score``.  The composite is the
available-weight-normalised average mapped to ``-100..100``; unavailable
factors keep their weight in ``total_weight`` but add nothing to the numerator,
so coverage honestly reports how much of the model is actually observed.
"""

from __future__ import annotations

from typing import Any, Iterable

SCORE_MIN = -100.0
SCORE_MAX = 100.0


def clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def norm_pct(percentile: float | None) -> float:
    """Map a 0..100 percentile into -1..1 (50 -> 0)."""
    if percentile is None:
        return 0.0
    return clip((float(percentile) - 50.0) / 50.0)


def signal_of(score: float) -> str:
    if score >= 0.15:
        return "bullish"
    if score <= -0.15:
        return "bearish"
    return "neutral"


def label_for_score(score: float) -> str:
    if score >= 50:
        return "强多"
    if score >= 18:
        return "偏多"
    if score <= -50:
        return "强空"
    if score <= -18:
        return "偏空"
    return "中性"


def factor(
    *,
    code: str,
    name: str,
    category: str,
    category_label: str,
    weight: float,
    direction: int,
    score: float,
    available: bool,
    value: float | None = None,
    change: float | None = None,
    unit: str = "",
    freq: str = "",
    source: str = "",
    note: str = "",
    explain: str = "",
    as_of: str | None = None,
    manual: bool = False,
    kind: str = "indicator",
) -> dict[str, Any]:
    """Build the common factor dict consumed by both the API and the UI."""
    raw_score = clip(float(score)) if available else 0.0
    factor_score = raw_score * int(direction) if available else 0.0
    return {
        "code": code,
        "name": name,
        "category": category,
        "category_label": category_label,
        "unit": unit,
        "freq": freq,
        "source": source,
        "weight": round(float(weight), 4),
        "direction": int(direction),
        "value": round(value, 6) if value is not None else None,
        "change": round(change, 6) if change is not None else None,
        "score": round(factor_score * 100, 1),
        "contribution": round(float(weight) * factor_score, 4),
        "signal": signal_of(factor_score) if available else "unavailable",
        "available": bool(available),
        "manual": bool(manual),
        "note": note,
        "explain": explain,
        "as_of": as_of,
        "kind": kind,
        "raw_score": round(raw_score, 6) if available else None,
    }


def combine_factors(factors: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Composite score/coverage over all factors (available only in numerator)."""
    items = [item for item in factors if float(item.get("weight") or 0) > 0]
    total_weight = sum(float(item["weight"]) for item in items)
    available_weight = sum(float(item["weight"]) for item in items if item.get("available"))
    weighted = sum(
        float(item["weight"]) * float(item.get("score") or 0.0) / 100.0
        for item in items
        if item.get("available")
    )
    score = round(weighted / available_weight * 100, 1) if available_weight else 0.0
    coverage = round(available_weight / total_weight * 100, 1) if total_weight else 0.0
    return {
        "score": max(SCORE_MIN, min(SCORE_MAX, score)),
        "label": label_for_score(score),
        "coverage": coverage,
        "available_weight": round(available_weight, 2),
        "total_weight": round(total_weight, 2),
        "available_count": sum(1 for item in items if item.get("available")),
        "total_count": len(items),
    }


def score_0_100(score: float) -> float:
    return round((clip(score, SCORE_MIN, SCORE_MAX) + 100.0) / 2.0, 1)
