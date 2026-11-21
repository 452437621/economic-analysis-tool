"""Persona lens engine: evaluate readings, rules and asset scores."""

from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

from app.lens.common import (
    Reading,
    build_reading,
    clamp,
    evaluate_rule,
    metric_map,
    round_opt,
    score_label,
)
from app.lens.persona_expression import ExpressionError, evaluate_expression
from app.lens.persona_spec import ASSET_IDS, PersonaSpec, load_specs

log = logging.getLogger(__name__)

# ── 求值 ──────────────────────────────────────────────────────────────


def _last(series: pd.Series) -> float | None:
    if series is None or series.empty:
        return None
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        return None
    value = float(cleaned.iloc[-1])
    if not math.isfinite(value):
        return None
    return value


def build_readings(spec: PersonaSpec, frame: pd.DataFrame) -> list[Reading]:
    """按规格求值读数；单条失败只影响该条。"""
    readings: list[Reading] = []
    for item in spec.readings:
        rid = str(item.get("id") or "")
        label = str(item.get("label") or rid)
        unit = str(item.get("unit") or "")
        digits = int(item.get("digits") or 2)
        source = str(item.get("source") or "")
        evidence = str(item.get("evidence") or "E3")
        note = str(item.get("note") or "")
        try:
            series = evaluate_expression(str(item.get("expr") or ""), frame)
        except ExpressionError as exc:
            log.warning("persona %s reading %s: %s", spec.id, rid, exc)
            readings.append(
                Reading(
                    id=rid,
                    label=label,
                    unit=unit,
                    digits=digits,
                    source=source,
                    evidence=evidence,
                    note=note,
                    missing_reason=f"表达式不可用：{exc}",
                )
            )
            continue
        readings.append(
            build_reading(
                rid,
                label,
                series,
                unit=unit,
                digits=digits,
                source=source,
                evidence=evidence,
                note=note,
                missing_reason="该读数依赖的序列本地无数据",
            )
        )
    return readings


def build_scores(spec: PersonaSpec, frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """求值七类资产评分（−2…+2，long_bond 正 = 债券价格看多）。"""
    scores: dict[str, dict[str, Any]] = {}
    for asset in ASSET_IDS:
        expr = spec.scores.get(asset)
        if not expr:
            scores[asset] = {"score": 0.0, "label": "未给出", "why": "该透镜未对该资产建模"}
            continue
        try:
            series = evaluate_expression(expr, frame)
        except ExpressionError as exc:
            scores[asset] = {"score": 0.0, "label": "表达式错误", "why": str(exc)}
            continue
        raw = _last(series)
        if raw is None:
            scores[asset] = {"score": 0.0, "label": "数据不足", "why": f"表达式无有效值：{expr}"}
            continue
        value = clamp(raw, -2.0, 2.0) or 0.0
        scores[asset] = {
            "score": round(float(value), 2),
            "label": score_label(value),
            "why": expr,
        }
    return scores


def build_state(
    spec: PersonaSpec,
    readings: list[Reading],
    scores: dict[str, dict[str, Any]],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """汇总透镜立场：净评分、可用度、最强读数、命中规则。"""
    available = [item for item in readings if item.value is not None]
    score_values = [item["score"] for item in scores.values() if item["score"]]
    net = round(sum(score_values) / len(score_values), 2) if score_values else 0.0
    ranked = sorted(
        (item for item in available if item.z is not None),
        key=lambda item: abs(item.z or 0.0),
        reverse=True,
    )[:5]
    fired = [rule for rule in rules if rule.get("fired")]
    narrative_parts = [spec.thesis.strip()] if spec.thesis else []
    if ranked:
        narrative_parts.append(
            "最极端的读数："
            + "、".join(f"{item.label}（{item.value:.{item.digits}f}{item.unit or ''}，z={item.z:+.2f}）" for item in ranked[:3])
        )
    if fired:
        narrative_parts.append("命中规则：" + "、".join(f"{rule['id']} {rule.get('name') or ''}".strip() for rule in fired))
    else:
        narrative_parts.append("本轮无规则命中，框架给出的只是方向性倾斜。")
    return {
        "lean": {
            "score": net,
            "label": score_label(net),
        },
        "coverage": {
            "available": len(available),
            "total": len(readings),
        },
        "fired_rules": [rule["id"] for rule in fired],
        "critical_rules": [rule["id"] for rule in fired if rule.get("severity") == "critical"],
        "key_readings": [
            {
                "id": item.id,
                "label": item.label,
                "value": round_opt(item.value, item.digits),
                "unit": item.unit,
                "z": round_opt(item.z, 2),
            }
            for item in ranked
        ],
        "narrative": " ".join(part for part in narrative_parts if part),
    }


def build_persona(spec: PersonaSpec, frame: pd.DataFrame) -> dict[str, Any]:
    """运行一份人物透镜，返回 {spec, readings, metrics, rules, scores, state}。"""
    readings = build_readings(spec, frame)
    metrics = metric_map(readings)
    rules = [evaluate_rule(rule, metrics) for rule in spec.rules]
    scores = build_scores(spec, frame)
    state = build_state(spec, readings, scores, rules)
    return {
        "id": spec.id,
        "name": spec.name,
        "title": spec.title,
        "school": spec.school,
        "key_question": spec.key_question,
        "thesis": spec.thesis,
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metrics,
        "rules": rules,
        "scores": scores,
        "state": state,
        "catalog": spec.catalog(),
        "triggers": spec.triggers,
    }


def build_personas(frame: pd.DataFrame, specs: list[PersonaSpec] | None = None) -> list[dict[str, Any]]:
    """运行全部人物透镜；任何一份出错都不影响其它份。"""
    out: list[dict[str, Any]] = []
    for spec in specs if specs is not None else load_specs():
        try:
            out.append(build_persona(spec, frame))
        except Exception as exc:  # pragma: no cover - 防御性兜底
            log.warning("persona %s failed: %s", spec.id, exc)
            out.append(
                {
                    "id": spec.id,
                    "name": spec.name,
                    "title": spec.title,
                    "school": spec.school,
                    "key_question": spec.key_question,
                    "thesis": spec.thesis,
                    "readings": [],
                    "metrics": {},
                    "rules": [],
                    "scores": {asset: {"score": 0.0, "label": "运行失败", "why": str(exc)} for asset in ASSET_IDS},
                    "state": {"lean": {"score": 0.0, "label": "运行失败"}, "coverage": {"available": 0, "total": 0},
                              "fired_rules": [], "critical_rules": [], "key_readings": [], "narrative": str(exc)},
                    "catalog": spec.catalog(),
                    "triggers": spec.triggers,
                }
            )
    return out
