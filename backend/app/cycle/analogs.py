"""Historical analog matching over the monthly score panel."""

from __future__ import annotations

import math

import pandas as pd


def _cosine(a: pd.Series, b: pd.Series) -> float:
    dot = float((a * b).sum())
    norm = math.sqrt(float((a * a).sum())) * math.sqrt(float((b * b).sum()))
    return dot / norm if norm else 0.0


def find_analogs(
    zscores: pd.DataFrame,
    scores: pd.DataFrame | None = None,
    top: int = 5,
    min_gap_months: int = 12,
) -> dict:
    if zscores.empty:
        return {"available": False, "reason": "历史标准化面板为空", "analogs": []}
    frame = zscores.dropna(how="all")
    if len(frame) < 24:
        return {"available": False, "reason": "历史样本不足 24 个月，无法做类比", "analogs": []}
    current = frame.iloc[-1]
    columns = [column for column in frame.columns if pd.notna(current.get(column))]
    if len(columns) < 4:
        return {"available": False, "reason": "当前可用维度不足 4 个，无法做类比", "analogs": []}
    matrix = frame[columns]
    candidates = matrix.iloc[:-min_gap_months] if len(matrix) > min_gap_months else matrix.iloc[:-1]
    candidates = candidates.dropna(thresh=max(3, int(len(columns) * 0.8)))
    if candidates.empty:
        return {"available": False, "reason": "剔除最近 12 个月后没有可比样本", "analogs": []}

    rows = []
    for month, row in candidates.iterrows():
        similarity = _cosine(current[columns].astype(float), row.astype(float))
        distance = float((current[columns].astype(float) - row.astype(float)).pow(2).sum() ** 0.5)
        rows.append(
            {
                "month": month.strftime("%Y-%m"),
                "similarity": round(similarity, 3),
                "distance": round(distance, 3),
                "state": (
                    {
                        "growth": round(float(scores.loc[month, "GROWTH"]), 1)
                        if scores is not None and "GROWTH" in scores.columns and month in scores.index and pd.notna(scores.loc[month, "GROWTH"])
                        else None,
                        "inflation": round(float(scores.loc[month, "INFLATION"]), 1)
                        if scores is not None and "INFLATION" in scores.columns and month in scores.index and pd.notna(scores.loc[month, "INFLATION"])
                        else None,
                    }
                ),
            }
        )
    rows.sort(key=lambda item: -item["similarity"])
    picked: list[dict] = []
    for row in rows:
        if len(picked) >= top:
            break
        month = row["month"]
        if any(abs(_month_index(month) - _month_index(other["month"])) < min_gap_months for other in picked):
            continue
        picked.append(row)
    return {
        "available": True,
        "n": len(candidates),
        "dimensions": columns,
        "min_gap_months": min_gap_months,
        "analogs": picked,
        "caveats": [
            f"样本内比较：候选 {len(candidates)} 个月，样本期 {frame.index.min():%Y-%m} 至 {frame.index.max():%Y-%m}；",
            "相似 ≠ 相同：宏观结构、政策反应函数与微观参与者都已变化，类比只能提示路径集合；",
            "维度仅覆盖本地已有行情/宏观序列，不含债务存量、地缘冲突等慢变量。",
        ],
    }


def _month_index(month: str) -> int:
    year, mon = month.split("-")
    return int(year) * 12 + int(mon)
