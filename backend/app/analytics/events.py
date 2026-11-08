"""Curated historical events + event-window asset returns (v0)."""

from __future__ import annotations

import statistics

import pandas as pd

EVENTS = [
    {"date": "2019-07-31", "name": "美联储首次降息", "type": "货币政策"},
    {"date": "2019-08-23", "name": "中美关税升级", "type": "贸易"},
    {"date": "2020-03-09", "name": "原油价格战/疫情冲击", "type": "供给冲击"},
    {"date": "2020-03-23", "name": "美联储无限量 QE", "type": "货币政策"},
    {"date": "2020-11-09", "name": "疫苗有效性公布", "type": "风险偏好"},
    {"date": "2021-11-03", "name": "美联储启动 Taper", "type": "货币政策"},
    {"date": "2022-02-24", "name": "俄乌冲突爆发", "type": "地缘"},
    {"date": "2022-03-16", "name": "美联储首次加息", "type": "货币政策"},
    {"date": "2022-06-15", "name": "美联储 75bp 加息", "type": "货币政策"},
    {"date": "2022-09-26", "name": "英国国债/养老金危机", "type": "金融风险"},
    {"date": "2023-03-10", "name": "硅谷银行倒闭", "type": "金融风险"},
    {"date": "2023-10-07", "name": "巴以冲突爆发", "type": "地缘"},
    {"date": "2024-09-18", "name": "美联储 50bp 降息", "type": "货币政策"},
    {"date": "2025-04-02", "name": "美国关税 2.0", "type": "贸易"},
]

ASSETS = ["AU", "AG", "CU", "SC", "000300"]
HORIZONS = (20, 60)


def _forward_return(series: pd.Series, date: pd.Timestamp, horizon: int) -> float | None:
    index = series.index.searchsorted(date)
    if index >= len(series) - horizon:
        return None
    base = series.iloc[index]
    if not base:
        return None
    return round(float(series.iloc[index + horizon] / base - 1) * 100, 2)


def build_event_study(closes: pd.DataFrame, events: list[dict] | None = None) -> dict:
    events = events or EVENTS
    rows = []
    for event in events:
        date = pd.Timestamp(event["date"])
        row = {"date": event["date"], "name": event["name"], "type": event["type"], "returns": {}}
        for asset in ASSETS:
            if asset not in closes.columns:
                continue
            series = closes[asset].dropna()
            for horizon in HORIZONS:
                value = _forward_return(series, date, horizon)
                if value is not None:
                    row["returns"][f"{asset}_{horizon}d"] = value
        rows.append(row)

    aggregate: dict[str, dict] = {}
    for row in rows:
        bucket = aggregate.setdefault(row["type"], {})
        for key, value in row["returns"].items():
            bucket.setdefault(key, []).append(value)
    summary = {}
    for type_name, values in aggregate.items():
        summary[type_name] = {}
        for key, series in values.items():
            summary[type_name][key] = {
                "mean": round(statistics.mean(series), 2),
                "median": round(statistics.median(series), 2),
                "hit_rate": round(sum(1 for v in series if v > 0) / len(series), 2),
                "n": len(series),
            }
    return {
        "events": rows,
        "aggregate": summary,
        "note": "事件研究为历史窗口统计，样本有限，不代表未来；仅用于形成参照分布。",
    }
