"""Event-window study driven by the economic calendar (1/3/5 trading days)."""

from __future__ import annotations

import statistics

import pandas as pd

ASSETS = ["AU", "CU", "SC", "000300", "DXY", "SPX"]
HORIZONS = (1, 3, 5)
KEYWORDS = (
    ("非农", "就业"),
    ("失业", "就业"),
    ("CPI", "通胀"),
    ("PPI", "通胀"),
    ("GDP", "增长"),
    ("PMI", "景气"),
    ("利率", "利率"),
    ("零售", "消费"),
    ("工业", "工业"),
    ("贸易", "贸易"),
)
CATEGORY_ORDER = ("通胀", "就业", "增长", "景气", "利率", "消费", "工业", "贸易", "其他")


def categorize(name: str) -> str:
    for keyword, category in KEYWORDS:
        if keyword in name:
            return category
    return "其他"


def _forward_return(series: pd.Series, date: pd.Timestamp, horizon: int) -> float | None:
    if series.empty:
        return None
    index = series.index.searchsorted(date, side="left")
    if index >= len(series) - horizon or index >= len(series):
        return None
    base = float(series.iloc[index])
    if not base:
        return None
    return round(float(series.iloc[index + horizon] / base - 1) * 100, 2)


def build_calendar_study(
    closes: pd.DataFrame,
    events: list[dict],
    *,
    max_events: int = 400,
) -> dict:
    groups: dict[tuple[str, str], dict[str, dict[int, list[float]]]] = {}
    used = 0
    for event in events[:max_events]:
        try:
            date = pd.Timestamp(event["ts"]).normalize()
        except (KeyError, ValueError):
            continue
        country = (event.get("country") or "全球").strip() or "全球"
        category = categorize(event.get("name") or "")
        bucket = groups.setdefault((country, category), {})
        used += 1
        for asset in ASSETS:
            if asset not in closes.columns:
                continue
            series = closes[asset].dropna()
            for horizon in HORIZONS:
                value = _forward_return(series, date, horizon)
                if value is None:
                    continue
                bucket.setdefault(asset, {}).setdefault(horizon, []).append(value)

    records = []
    for (country, category), assets in groups.items():
        assets_payload: dict[str, dict] = {}
        for asset, horizons in assets.items():
            item: dict = {}
            for horizon, values in horizons.items():
                if not values:
                    continue
                item[f"{horizon}d"] = round(statistics.mean(values), 2)
                item[f"{horizon}d_hit"] = round(sum(1 for v in values if v > 0) / len(values), 2)
                item[f"{horizon}d_n"] = len(values)
            if item:
                assets_payload[asset] = item
        if not assets_payload:
            continue
        records.append(
            {
                "country": country,
                "category": category,
                "n": max((value.get("1d_n", 0) for value in assets_payload.values()), default=0),
                "assets": assets_payload,
            }
        )
    records.sort(key=lambda row: (row["country"], CATEGORY_ORDER.index(row["category"]) if row["category"] in CATEGORY_ORDER else 99))
    return {
        "window": "1/3/5 trading days",
        "events": used,
        "groups": records,
        "note": "日历事件窗口统计：以事件日（或其后首个交易日）为基准，样本有限，仅供形成参照分布。",
    }
