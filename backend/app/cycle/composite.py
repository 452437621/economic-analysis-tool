"""Composite scores (DMI / ICI / ECI / growth / inflation / liquidity)."""

from __future__ import annotations

from app.cycle.config import EVIDENCE_WEIGHT, load_config
from app.cycle.indicators import Reading, evidence_weight


def _expected_weights(score_id: str, config: dict) -> tuple[float, int, int]:
    total = 0.0
    count = 0
    manual = 0
    for item in list(config.get("indicators") or []) + list(config.get("manual") or []):
        if item.get("score") != score_id:
            continue
        total += float(item.get("weight", 0))
        count += 1
        if item in (config.get("manual") or []):
            manual += 1
    return total, count, manual


def composite(score_id: str, readings: list[Reading], config: dict | None = None) -> dict:
    cfg = config or load_config()
    used = [r for r in readings if r.score == score_id and r.score_value is not None and r.weight > 0]
    expected_weight, expected_count, manual_count = _expected_weights(score_id, cfg)
    spec = (cfg.get("scores") or {}).get(score_id, {})

    if not used or expected_weight <= 0:
        return {
            "id": score_id,
            "name": spec.get("name", score_id),
            "value": None,
            "coverage": 0.0,
            "confidence": 0.0,
            "evidence": None,
            "components": [],
            "degraded": True,
            "degrade_reason": "该分量的指标全部缺失",
            "manual_ratio": 0.0,
        }

    used_weight = sum(r.weight for r in used)
    coverage = min(1.0, used_weight / expected_weight) if expected_weight else 0.0
    value = sum(r.weight * float(r.score_value) for r in used) / used_weight
    quality = evidence_weight(used)
    stale_penalty = 0.0
    for reading in used:
        if reading.stale_days is not None and reading.stale_days > 180:
            stale_penalty = max(stale_penalty, min(0.25, reading.stale_days / 3650.0))
    confidence = round(min(0.92, (coverage**0.5) * quality * (1.0 - stale_penalty)), 2)
    manual_ratio = (
        sum(r.weight for r in used if r.evidence == "E4") / used_weight if used_weight else 0.0
    )
    if manual_ratio >= 0.6:
        confidence = min(confidence, 0.45)

    evidence = max((r.evidence for r in used), key=lambda grade: EVIDENCE_WEIGHT.get(grade, 0.0))
    components = [
        {
            "id": r.id,
            "name": r.name,
            "weight": round(r.weight / used_weight, 3),
            "score": round(float(r.score_value), 1),
            "value": r.value,
            "unit": r.unit,
            "asof": r.asof,
            "z": r.z,
            "evidence": r.evidence,
            "stale_days": r.stale_days,
            "why": r.why,
        }
        for r in used
    ]
    missing = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "weight": item.get("weight"),
        }
        for item in list(cfg.get("indicators") or []) + list(cfg.get("manual") or [])
        if item.get("score") == score_id
        and item.get("id") not in {r.id for r in used}
    ]
    return {
        "id": score_id,
        "name": spec.get("name", score_id),
        "value": round(value, 1),
        "coverage": round(coverage, 3),
        "confidence": confidence,
        "evidence": evidence,
        "components": sorted(components, key=lambda c: -c["weight"]),
        "missing": missing,
        "manual_ratio": round(manual_ratio, 3),
        "manual_count": manual_count,
        "expected_count": expected_count,
        "degraded": coverage < 0.999,
        "degrade_reason": (
            f"仅覆盖 {coverage * 100:.0f}% 的配置权重，缺失指标："
            + "、".join(m["name"] for m in missing[:3])
            if coverage < 0.999
            else None
        ),
    }


def all_composites(readings: list[Reading], config: dict | None = None) -> dict[str, dict]:
    cfg = config or load_config()
    return {score_id: composite(score_id, readings, cfg) for score_id in (cfg.get("scores") or {})}
