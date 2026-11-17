"""Phase classification with threshold hysteresis.

Hysteresis is explicit and cheap: a phase only flips once the score exits the
previous phase band by ``hysteresis`` points, and the previous phase is read
from the latest persisted derivation (no hidden in-memory state).
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def _find_phase(phases: list[dict], value: float) -> dict | None:
    for phase in phases:
        low, high = phase["band"]
        if low <= value <= high:
            return phase
    return phases[-1] if value > phases[-1]["band"][1] else phases[0]


def long_cycle(
    dmi: dict,
    config: dict,
    previous_phase: str | None = None,
) -> dict:
    section = config.get("long_cycle") or {}
    phases = list(section.get("phases") or [])
    hysteresis = float(section.get("hysteresis", 3.0))
    if not phases or dmi.get("value") is None:
        return {
            "available": False,
            "reason": "DMI 缺失，无法定位长债务周期",
            "phase": None,
            "confidence": 0.0,
        }
    score = float(dmi["value"])
    plain = _find_phase(phases, score)
    chosen = plain
    held = False
    if previous_phase:
        previous = next(
            (p for p in phases if p.get("name") == previous_phase or p.get("id") == previous_phase),
            None,
        )
        if previous and previous["id"] != plain["id"]:
            low, high = previous["band"]
            if low - hysteresis <= score <= high + hysteresis:
                chosen = previous
                held = True
    position = (score - chosen["band"][0]) / max(1.0, chosen["band"][1] - chosen["band"][0])
    confidence = float(dmi.get("confidence") or 0.0)
    if held:
        confidence = round(confidence * 0.95, 2)
    return {
        "available": True,
        "phase_id": chosen["id"],
        "phase": chosen["name"],
        "score": round(score, 1),
        "band": chosen["band"],
        "position": round(max(0.0, min(1.0, position)), 3),
        "meaning": chosen.get("meaning"),
        "asset_implication": chosen.get("asset"),
        "hysteresis_held": held,
        "previous_phase": previous_phase,
        "confidence": confidence,
        "evidence": dmi.get("evidence"),
        "coverage": dmi.get("coverage"),
        "next_phase": (
            phases[phases.index(chosen) + 1]["name"] if phases.index(chosen) + 1 < len(phases) else None
        ),
        "exit_condition": (
            f"DMI 跌破 {chosen['band'][0] - hysteresis:.0f} 或升破 {chosen['band'][1] + hysteresis:.0f} 才切换阶段"
        ),
    }


def _eval_rule(rule: str, variables: dict[str, float]) -> bool:
    namespace = dict(variables)
    namespace["__builtins__"] = {}
    try:
        return bool(eval(rule, namespace))  # noqa: S307 - config-authored rule
    except Exception:  # pragma: no cover - defensive
        return False


def short_cycle(
    growth: dict,
    inflation: dict,
    liquidity: dict,
    growth_d12: float | None,
    config: dict,
    previous_state: str | None = None,
    previous_raw: str | None = None,
) -> dict:
    section = config.get("short_cycle") or {}
    states = list(section.get("states") or [])
    if growth.get("value") is None:
        return {"available": False, "reason": "增长分数缺失，无法定位短周期", "state": None, "confidence": 0.0}
    variables = {
        "growth": float(growth["value"]),
        "inflation": float(inflation.get("value") or 50.0),
        "liq": float(liquidity.get("value") or 50.0),
        "d12": float(growth_d12 or 0.0),
    }
    matched = None
    for rule in section.get("rules") or []:
        if _eval_rule(str(rule.get("when")), variables):
            matched = rule
            break
    if matched is None:
        matched = {"state": section.get("default", "放缓"), "meaning": "未命中显式规则，按默认态处理"}
    state = matched["state"]
    held = False
    if previous_state and previous_state != state and previous_state in states:
        # 需要「连续两次运行都命中同一新状态」才切换：上一次的 raw_state
        # 已经等于本次状态时视为确认，否则先保留旧态，避免单点跳变。
        held = previous_raw != state
    confidence = round(
        min(0.85, 0.35 + 0.45 * float(growth.get("coverage") or 0) + 0.1 * abs(variables["d12"]) / 10.0), 2
    )
    return {
        "available": True,
        "state": previous_state if held else state,
        "raw_state": state,
        "meaning": matched.get("meaning"),
        "hysteresis_held": held,
        "variables": {k: round(v, 1) for k, v in variables.items()},
        "confidence": confidence,
        "evidence": growth.get("evidence"),
        "growth_12m_change": round(growth_d12, 1) if growth_d12 is not None else None,
    }


def liquidity_state(liquidity: dict) -> dict:
    if liquidity.get("value") is None:
        return {"available": False, "state": None, "confidence": 0.0}
    value = float(liquidity["value"])
    state = "宽松" if value >= 60 else ("中性" if value >= 40 else "收紧")
    return {
        "available": True,
        "state": state,
        "score": round(value, 1),
        "meaning": {
            "宽松": "短端价格与美元流动性支持风险资产",
            "中性": "金融条件中性，等待数据确认方向",
            "收紧": "实际利率与美元走强压制估值与信用",
        }[state],
        "confidence": liquidity.get("confidence"),
        "evidence": liquidity.get("evidence"),
    }


def inventory_cycle(panel, config: dict) -> dict:
    section = config.get("inventory_cycle") or {}
    proxies = list(section.get("proxies") or [])
    frames = []
    for code in proxies:
        series = panel.series(code)
        if series.empty:
            continue
        frames.append(series.pct_change(60) * 100)
    if not frames:
        return {"available": False, "reason": "工业品序列缺失", "state": None, "confidence": 0.0}
    price_mom = pd.concat(frames, axis=1).mean(axis=1).dropna()
    if price_mom.empty:
        return {"available": False, "reason": "工业品动量不可计算", "state": None, "confidence": 0.0}
    latest = float(price_mom.iloc[-1])
    inv_proxy = float(price_mom.diff(20).iloc[-1]) if len(price_mom) > 21 else 0.0
    variables = {"price_mom": latest, "inv_mom": inv_proxy}
    matched = None
    for rule in section.get("rules") or []:
        if _eval_rule(str(rule.get("when")), variables):
            matched = rule
            break
    if matched is None:
        matched = {"state": "被动补库"}
    state = matched["state"]
    for item in section.get("states") or []:
        if item.get("id") == state:
            matched = {**matched, **item}
            break
    return {
        "available": True,
        "state": state,
        "price_momentum_60d": round(latest, 2),
        "inventory_proxy_20d": round(inv_proxy, 2),
        "degraded": True,
        "degrade_reason": "本地无库存序列，以工业品价格动量及其 20 日变化代理库存方向（E1）",
        "meaning": matched.get("meaning"),
        "asset_implication": matched.get("asset"),
        "evidence": "E1",
        "confidence": 0.35,
        "proxies": [code for code in proxies if not panel.series(code).empty],
    }


def political_calendar(config: dict, today: date | None = None) -> dict:
    ref = today or date.today()
    events = []
    for item in config.get("political_calendar") or []:
        event_date = item.get("date")
        if hasattr(event_date, "date"):
            event_date = event_date.date()
        if event_date is None:
            continue
        days = (event_date - ref).days
        events.append(
            {
                "date": event_date.strftime("%Y-%m-%d"),
                "name": item.get("name"),
                "importance": item.get("importance", 1),
                "note": item.get("note"),
                "days": days,
                "past": days < 0,
            }
        )
    events.sort(key=lambda e: (e["past"], abs(e["days"])))
    upcoming = [e for e in events if not e["past"]]
    nearest = upcoming[0] if upcoming else None
    return {
        "events": events,
        "nearest": nearest,
        "days_to_nearest": nearest["days"] if nearest else None,
        "window": "高不确定性窗口" if nearest and nearest["days"] <= 30 else "常态窗口",
    }
