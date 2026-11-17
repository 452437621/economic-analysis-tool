"""Debt sustainability and the three deleveraging modes."""

from __future__ import annotations

from app.cycle.config import load_config


def _manual_value(config: dict, indicator_id: str) -> dict | None:
    return next((item for item in config.get("manual") or [] if item.get("id") == indicator_id), None)


def sustainability(config: dict | None = None) -> dict:
    cfg = config or load_config()
    r_g = _manual_value(cfg, "us_r_minus_g")
    interest = _manual_value(cfg, "us_interest_revenue")
    deficit = _manual_value(cfg, "us_deficit_gdp")
    debt = _manual_value(cfg, "us_debt_gdp")
    if not (r_g and interest and deficit):
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

    return {
        "available": True,
        "mode": mode,
        "mode_id": mode_id,
        "explanation": explanation,
        "risk": risk,
        "r_minus_g": round(rg_value, 2),
        "interest_to_revenue": round(interest_value, 1),
        "deficit_to_gdp": round(deficit_value, 1),
        "debt_to_gdp": float(debt["value"]) if debt else None,
        "thresholds": {"interest_watch": 20, "interest_alarm": 30, "deficit_watch": 5},
        "readings": [
            {"id": "r_minus_g", "name": "r−g", "value": round(rg_value, 2), "unit": "pp", "asof": str(r_g["asof"])},
            {
                "id": "interest_to_revenue",
                "name": "利息/财政收入",
                "value": round(interest_value, 1),
                "unit": "%",
                "asof": str(interest["asof"]),
            },
            {
                "id": "deficit_to_gdp",
                "name": "赤字/GDP",
                "value": round(deficit_value, 1),
                "unit": "%",
                "asof": str(deficit["asof"]),
            },
        ],
        "evidence": "E2",
        "confidence": 0.7,
        "caveats": [
            "r−g 用 10Y 实际利率减潜在增速近似，未考虑期限结构与通胀意外；",
            "利息/财政收入为联邦口径，不含州与地方债务；",
            "E2 为跨来源推算，具体阈值 20%/30% 来自 docs/22 的经验区间。",
        ],
    }
