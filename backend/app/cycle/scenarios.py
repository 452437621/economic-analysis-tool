"""Four forward scenarios with explicit, auditable probability adjustments."""

from __future__ import annotations

from app.cycle.config import load_config


def _pct(reading: dict | None) -> float | None:
    if not reading or reading.get("value") is None:
        return None
    return float(reading["value"])


def _near(value: float, center: float, width: float) -> float:
    """1 at the centre, linearly down to 0 at ``width`` away."""
    return max(0.0, 1.0 - abs(value - center) / width)


def _clip(value: float, low: float = -0.12, high: float = 0.15) -> float:
    return max(low, min(high, value))


def _adjustments(
    d: float | None, g: float | None, i: float | None, liq: float | None
) -> dict[str, float]:
    """Rule-based deviations from the base priors.

    Missing inputs contribute zero instead of being silently replaced by a
    neutral 50, so a missing reading cannot masquerade as evidence.
    """
    return {
        "S1": _clip(0.10 * max(0.0, ((d or 0.0) - 55.0) / 45.0)) if d is not None else 0.0,
        "S2": _clip(0.10 * _near(g, 50.0, 25.0) + 0.04 * _near(i, 40.0, 25.0))
        if g is not None and i is not None
        else 0.0,
        "S3": _clip(0.12 * max(0.0, (45.0 - g) / 45.0) + 0.06 * max(0.0, (50.0 - liq) / 50.0))
        if g is not None and liq is not None
        else 0.0,
        "S4": _clip(0.08 * max(0.0, (g - 60.0) / 40.0) * max(0.0, (50.0 - i) / 50.0), 0.0, 0.10)
        if g is not None and i is not None
        else 0.0,
    }


def _fmt(value: float | None, suffix: str = "") -> str:
    return "缺失" if value is None else f"{value:.0f}{suffix}"


def scenarios(
    dmi: dict,
    growth: dict,
    inflation: dict,
    liquidity: dict,
    config: dict | None = None,
) -> dict:
    cfg = config or load_config()
    base = {item["id"]: float(item.get("base", 0.0)) for item in cfg.get("scenarios") or []}
    if not base:
        return {"available": False, "reason": "情景配置缺失", "scenarios": []}

    d = _pct(dmi)
    g = _pct(growth)
    i = _pct(inflation)
    liq = _pct(liquidity)
    missing = [
        name
        for name, value in (("DMI", d), ("增长", g), ("通胀", i), ("流动性", liq))
        if value is None
    ]

    adjustments = _adjustments(d, g, i, liq)
    weights = {key: max(0.02, base.get(key, 0.0) + adjustments.get(key, 0.0)) for key in base}
    total = sum(weights.values())
    probabilities = {key: round(value / total, 3) for key, value in weights.items()}
    # 四舍五入后的残差补到最大项，确保总和为 1.000
    drift = round(1.0 - sum(probabilities.values()), 3)
    largest = max(probabilities, key=probabilities.get)
    probabilities[largest] = round(probabilities[largest] + drift, 3)

    triggers = {
        "S1": [
            f"债务/货币压力 DMI={_fmt(d)}（≥55 表示长周期后段）",
            "利息/财政收入 ≥20% 时，财政主导概率上升",
        ],
        "S2": [f"通胀分数 {_fmt(i)}（接近 50 时软着陆空间更大）", f"流动性分数 {_fmt(liq)}"],
        "S3": [f"增长分数 {_fmt(g)}（<40 时信用事件概率上升）", "SOFR−EFFR 溢价走阔是预警信号"],
        "S4": ["生产率与利润率数据未接入，该情景为叙事占位，权重不宜过高"],
    }
    notes = []
    for item in cfg.get("scenarios") or []:
        sid = item["id"]
        notes.append(
            {
                "id": sid,
                "name": item.get("name"),
                "probability": probabilities[sid],
                "base": base[sid],
                "adjustment": round(adjustments.get(sid, 0.0), 3),
                "desc": item.get("desc"),
                "assets": item.get("assets"),
                "triggers": triggers.get(sid, []),
            }
        )
    caveats = [
        "情景概率是规则化先验，尚未做样本外校准（需 M4 的预测台账积累后回测）；",
        "S4 缺少生产率数据支撑，仅为叙事占位；",
        "概率之和强制为 1，不代表真实分布的严谨分解。",
    ]
    if missing:
        caveats.insert(0, f"缺失输入：{'、'.join(missing)}；相关调整项按 0 处理，不做中性化猜测。")
    confidence = round(min(0.6, 0.3 + 0.2 * float(dmi.get("coverage") or 0)), 2)
    if missing:
        confidence = round(confidence * 0.6, 2)
    return {
        "available": True,
        "degraded": bool(missing),
        "missing_inputs": missing,
        "horizon": "未来 6–36 个月",
        "sum": round(sum(probabilities.values()), 3),
        "scenarios": notes,
        "formula": (
            "概率 = 归一化(基准 + 调整)；S1=0.10×max(0,(DMI−55)/45)，"
            "S2=0.10×near(增长,50,25)+0.04×near(通胀,40,25)，"
            "S3=0.12×max(0,(45−增长)/45)+0.06×max(0,(50−流动性)/50)，"
            "S4=0.08×max(0,(增长−60)/40)×max(0,(50−通胀)/50)；调整幅度截断在 [−0.12, 0.15]。"
            "这是规则化先验，不是统计模型输出；缺失输入不计调整。"
        ),
        "evidence": "E3",
        "confidence": confidence,
        "caveats": caveats,
    }
