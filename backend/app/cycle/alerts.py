"""Alert rules evaluated against the current readings."""

from __future__ import annotations

from app.cycle.config import load_config

SEVERITY_LABEL = {"high": "高", "medium": "中", "low": "低"}


def _compare(op: str, left: float, right: float) -> bool:
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    return False


def evaluate(metrics: dict[str, dict], config: dict | None = None) -> dict:
    """Evaluate every configured alert.

    ``metrics`` maps a metric id to ``{"value": float, "name": str, "unit": str,
    "asof": str, "source": str}``; missing metrics are reported as unknown
    instead of silently passing.
    """
    cfg = config or load_config()
    rules = list(cfg.get("alerts") or [])
    alerts = []
    counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for rule in rules:
        metric_id = rule.get("metric")
        metric = metrics.get(metric_id or "")
        if not metric or metric.get("value") is None:
            alerts.append(
                {
                    "id": rule.get("id"),
                    "name": rule.get("name"),
                    "severity": rule.get("severity"),
                    "severity_label": SEVERITY_LABEL.get(rule.get("severity"), rule.get("severity")),
                    "metric": metric_id,
                    "metric_name": rule.get("name"),
                    "value": None,
                    "threshold": rule.get("threshold"),
                    "op": rule.get("op"),
                    "triggered": None,
                    "status": "unknown",
                    "distance": None,
                    "why": rule.get("why"),
                    "falsifier": rule.get("falsifier"),
                    "reason": "指标缺失，无法评估（不会默认为未触发）",
                }
            )
            counts["unknown"] += 1
            continue
        value = float(metric["value"])
        threshold = float(rule.get("threshold", 0))
        triggered = _compare(str(rule.get("op")), value, threshold)
        if str(rule.get("op")).startswith((">", ">=")):
            distance = value - threshold
        else:
            distance = threshold - value
        status = "triggered" if triggered else "normal"
        if triggered:
            counts[rule.get("severity", "low")] = counts.get(rule.get("severity", "low"), 0) + 1
        alerts.append(
            {
                "id": rule.get("id"),
                "name": rule.get("name"),
                "severity": rule.get("severity"),
                "severity_label": SEVERITY_LABEL.get(rule.get("severity"), rule.get("severity")),
                "metric": metric_id,
                "metric_name": metric.get("name") or rule.get("name"),
                "value": round(value, 4),
                "unit": metric.get("unit"),
                "asof": metric.get("asof"),
                "threshold": threshold,
                "op": rule.get("op"),
                "triggered": triggered,
                "status": status,
                "distance": round(distance, 4),
                "why": rule.get("why"),
                "falsifier": rule.get("falsifier"),
                "source": metric.get("source"),
            }
        )
    alerts.sort(key=lambda item: (item["status"] != "triggered", item["severity"] != "high", item["severity"] != "medium"))
    return {
        "counts": counts,
        "total": len(alerts),
        "triggered": sum(1 for item in alerts if item["triggered"]),
        "unknown": counts["unknown"],
        "alerts": alerts,
        "note": "预警是规则命中，不是预测；每条都给出失效条件，触发后应人工复核。",
    }
