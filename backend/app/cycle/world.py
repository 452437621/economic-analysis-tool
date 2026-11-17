"""World order: internal/external stage judgments and the power index."""

from __future__ import annotations

from app.cycle.config import load_config

POWER_WEIGHTS = {
    "education": 0.08,
    "innovation": 0.18,
    "cost": 0.10,
    "military": 0.20,
    "trade": 0.12,
    "output": 0.12,
    "finance": 0.10,
    "reserve": 0.10,
}


def _stage_name(stages: list[dict], stage: int) -> str | None:
    for item in stages:
        if int(item.get("id", 0)) == int(stage):
            return item.get("name")
    return None


def world_state(config: dict | None = None) -> dict:
    cfg = config or load_config()
    world = cfg.get("world") or {}
    internal = list(world.get("internal_stages") or [])
    external = list(world.get("external_stages") or [])
    judgments = {item["id"]: item for item in world.get("judgments") or []}

    def judgment(item_id: str, stages: list[dict]) -> dict | None:
        item = judgments.get(item_id)
        if not item:
            return None
        return {
            "id": item_id,
            "name": item.get("name"),
            "stage": int(item.get("stage")),
            "stage_name": _stage_name(stages, int(item.get("stage"))),
            "confidence": float(item.get("confidence", 0.5)),
            "evidence": item.get("evidence", "E4"),
            "asof": str(item.get("asof")),
            "reason": item.get("reason"),
            "falsifier": item.get("falsifier"),
            "source": item.get("source"),
            "url": item.get("url"),
            "degraded": True,
            "degrade_reason": "阶段判定为人工叙事映射（E4），不是模型自动分类",
        }

    power = world.get("power_index") or {}
    components = list(power.get("components") or [])
    total_weight = sum(POWER_WEIGHTS.get(c["id"], 0.0) for c in components)
    spi = (
        sum(POWER_WEIGHTS.get(c["id"], 0.0) * float(c["value"]) for c in components) / total_weight
        if total_weight
        else None
    )
    reserve = world.get("reserve_currency") or {}
    return {
        "us_internal": judgment("us_internal", internal),
        "global_order": judgment("global_order", external),
        "power_index": {
            "name": power.get("name"),
            "value": round(spi, 1) if spi is not None else None,
            "asof": str(power.get("asof")),
            "evidence": power.get("evidence", "E4"),
            "components": [
                {"id": c["id"], "name": c["name"], "value": float(c["value"]), "weight": POWER_WEIGHTS.get(c["id"], 0.0)}
                for c in components
            ],
            "degraded": True,
            "degrade_reason": "八项实力为人工评分（E4），需接入 WIPO/SIPRI/GFCI 等原始数据源后替换",
        },
        "reserve_currency": {
            "code": reserve.get("code"),
            "share": float(reserve.get("share")) if reserve.get("share") is not None else None,
            "asof": str(reserve.get("asof")),
            "evidence": reserve.get("evidence"),
            "source": reserve.get("source"),
            "url": reserve.get("url"),
        },
        "note": "内部秩序与国际秩序分开判定：两者可以处于不同阶段（docs/23 §5）。",
    }
