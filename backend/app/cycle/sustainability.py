"""Debt sustainability and the three deleveraging modes.

The four inputs (r−g, interest/revenue, deficit/GDP, debt/GDP) are resolved
through :mod:`app.cycle.structural`: a fresh database series wins, the
hand-maintained ``cycle.yaml`` observation is the fallback. Passing
``session=None`` keeps the historical config-only behaviour (used by the
read-only scenario snapshot and by callers that have no database handle).
"""

from __future__ import annotations

from app.cycle.config import load_config
from app.cycle.structural import resolve

#: structural id → reading label shown in the sustainability panel.
_READINGS = [
    ("us_r_minus_g", "r_minus_g", "r−g", 2),
    ("us_interest_revenue", "interest_to_revenue", "利息/财政收入", 1),
    ("us_deficit_gdp", "deficit_to_gdp", "赤字/GDP", 1),
]


def _metric(config: dict, session, structural_id: str) -> dict:
    return resolve(structural_id, session, config)


def _evidence(metrics: list[dict], session) -> str:
    if session is None:
        return "E2"
    return "E2" if all(metric.get("live") for metric in metrics) else "E3"


def sustainability(config: dict | None = None, session=None) -> dict:
    cfg = config or load_config()
    r_g = _metric(cfg, session, "us_r_minus_g")
    interest = _metric(cfg, session, "us_interest_revenue")
    deficit = _metric(cfg, session, "us_deficit_gdp")
    debt = _metric(cfg, session, "us_debt_gdp")
    if not (r_g["value"] is not None and interest["value"] is not None and deficit["value"] is not None):
        return {"available": False, "reason": "债务可持续性所需的三个结构性读数缺失"}

    rg_value = float(r_g["value"])
    interest_value = float(interest["value"])
    deficit_value = float(deficit["value"])

    if interest_value >= 30:
        risk = "高"
    elif interest_value >= 20:
        risk = "中高"
    elif interest_value >= 12:
        risk = "中"
    else:
        risk = "低"

    if interest_value >= 20 and rg_value > 0 and deficit_value >= 5:
        mode = "财政主导（利息货币化）"
        explanation = (
            "利息支出已占财政收入的 20% 以上，且 r−g 为正、赤字高于 5%，"
            "靠增长还债不可行，只能靠金融抑制（压低实际利率）与通胀稀释。"
        )
        mode_id = "fiscal_dominance"
    elif rg_value < 0 and interest_value >= 15:
        mode = "通缩化债"
        explanation = "r−g 为负时，若不印钞，债务/收入比会在名义收入下滑中被动上升，需要债务重组。"
        mode_id = "deflationary"
    else:
        mode = "通胀化债"
        explanation = "名义增长高于利率，债务/收入比可以自然下行，但需要容忍较高通胀。"
        mode_id = "inflation"

    resolved_metrics = {
        "us_r_minus_g": r_g,
        "us_interest_revenue": interest,
        "us_deficit_gdp": deficit,
    }
    readings = []
    for structural_id, reading_id, name, digits in _READINGS:
        resolved = resolved_metrics[structural_id]
        readings.append(
            {
                "id": reading_id,
                "name": name,
                "value": (
                    round(float(resolved["value"]), digits) if resolved["value"] is not None else None
                ),
                "unit": "pp" if reading_id == "r_minus_g" else "%",
                "asof": resolved.get("asof"),
            }
        )

    fallback_names = [
        name for structural_id, _, name, _ in _READINGS if not resolved_metrics[structural_id].get("live")
    ]
    debt_asof = debt.get("asof") if debt["value"] is not None else "缺失"
    provenance = (
        "数据口径与 asof：r−g {}、利息/收入 {}、赤字 {}、债务/GDP {}（{}）".format(
            r_g.get("asof"),
            interest.get("asof"),
            deficit.get("asof"),
            debt_asof,
            "来源于 DB 实时官方序列" if session is not None else "人工观测（未提供 DB 会话）",
        )
    )
    caveats = [
        "r−g 用 10Y 实际利率减潜在增速近似，未考虑期限结构与通胀意外；",
        "利息/财政收入为联邦口径，不含州与地方债务；",
        "E2 为跨来源推算，具体阈值 20%/30% 来自 docs/22 的经验区间。",
        provenance,
    ]
    if fallback_names:
        caveats.append("以下读数回落人工观测：" + "、".join(fallback_names))

    return {
        "available": True,
        "mode": mode,
        "mode_id": mode_id,
        "explanation": explanation,
        "risk": risk,
        "r_minus_g": round(rg_value, 2),
        "interest_to_revenue": round(interest_value, 1),
        "deficit_to_gdp": round(deficit_value, 1),
        "debt_to_gdp": float(debt["value"]) if debt["value"] is not None else None,
        "thresholds": {"interest_watch": 20, "interest_alarm": 30, "deficit_watch": 5},
        "readings": readings,
        "evidence": _evidence([r_g, interest, deficit, debt], session),
        "confidence": 0.7,
        "caveats": caveats,
    }
