"""Deterministic driver ranking for briefs: what is moving the market now."""

from __future__ import annotations

POSITION_SYMBOLS = {
    "au": "AU",
    "ag": "AG",
    "cu": "CU",
    "al": "AL",
    "zn": "ZN",
    "ni": "NI",
    "cf": "CF",
    "sr": "SR",
    "m": "M",
    "p": "P",
    "i": "I",
}


def _direction(value: float, up: str, down: str) -> str:
    return up if value > 0 else down


def rank_drivers(
    wind: dict | None,
    indicators: dict[str, dict],
    positions: list[dict],
    events: list[dict],
    regimes: dict[str, dict] | None = None,
    limit: int = 6,
) -> list[dict]:
    drivers: list[dict] = []

    if wind:
        score = float(wind.get("score") or 0)
        if abs(score) >= 10:
            drivers.append(
                {
                    "name": "市场风向",
                    "direction": str(wind.get("label") or "中性"),
                    "strength": round(min(abs(score) / 100, 1.0), 2),
                    "evidence": f"风向得分 {score:+.1f}；A股宽度/动量/利率综合",
                }
            )
        us10 = (wind.get("components") or {}).get("us10y_change_20d_pp")
        if us10 is not None and abs(us10) >= 0.1:
            drivers.append(
                {
                    "name": "美国利率",
                    "direction": _direction(us10, "上行（压制黄金/成长）", "下行（支撑黄金/成长）"),
                    "strength": round(min(abs(us10) / 0.5, 1.0), 2),
                    "evidence": f"10Y 20 日变动 {us10:+.2f}pp",
                }
            )

    dxy = (indicators.get("DXY") or {}).get("change_20d")
    if dxy is not None and abs(dxy) >= 1.0:
        drivers.append(
            {
                "name": "美元",
                "direction": _direction(dxy, "走强（压制商品/新兴市场）", "走弱（支撑商品/新兴市场）"),
                "strength": round(min(abs(dxy) / 5.0, 1.0), 2),
                "evidence": f"DXY 20 日 {dxy:+.2f}%",
            }
        )

    divergences = []
    for position in positions:
        product = str(position.get("product") or "").lower()
        symbol = POSITION_SYMBOLS.get(product)
        if not symbol:
            continue
        ratio = position.get("net_ratio")
        trend = (indicators.get(symbol) or {}).get("change_20d")
        if ratio is None or trend is None or abs(ratio) < 0.05 or abs(trend) < 1.0:
            continue
        if (ratio > 0 and trend < 0) or (ratio < 0 and trend > 0):
            divergences.append((abs(ratio), position, trend))
    if divergences:
        divergences.sort(key=lambda item: item[0], reverse=True)
        _, position, trend = divergences[0]
        side = "净多" if position["net_ratio"] > 0 else "净空"
        drivers.append(
            {
                "name": f"持仓背离：{position.get('name')}",
                "direction": f"会员{side}与价格趋势相反",
                "strength": round(min(abs(position["net_ratio"]) * 2, 1.0), 2),
                "evidence": f"净占比 {position['net_ratio'] * 100:+.1f}%，20 日动量 {trend:+.2f}%",
            }
        )

    high_events = [
        event for event in events if event.get("type") in ("trade", "geopolitical", "monetary_policy")
    ]
    if high_events:
        drivers.append(
            {
                "name": "事件驱动",
                "direction": "风险溢价",
                "strength": round(min(len(high_events) / 5, 1.0), 2),
                "evidence": f"近 7 天 {len(high_events)} 条高影响事件；如：{high_events[0].get('title', '')[:40]}",
            }
        )

    if regimes:
        for country, payload in regimes.items():
            confidence = float(payload.get("confidence") or 0)
            if confidence >= 0.35:
                drivers.append(
                    {
                        "name": f"{country}周期（市场隐含）",
                        "direction": str(payload.get("quadrant") or ""),
                        "strength": round(confidence, 2),
                        "evidence": f"置信 {confidence:.0%}；增长/通胀动量合成",
                    }
                )

    drivers.sort(key=lambda item: item["strength"], reverse=True)
    return drivers[:limit]
