"""Layer frame builder shared by the macro and micro layers."""

from __future__ import annotations

import pandas as pd

from app.lens.persona_spec import TAIL_ROWS

def build_frame(panel, gold_extras: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """面板 → 表达式求值用的宽表（尾部窗口 + 低频序列前值填充）。"""
    if panel is None or getattr(panel, "daily", None) is None or panel.daily.empty:
        return pd.DataFrame()
    frame = panel.daily.tail(TAIL_ROWS).copy()
    for code, series in (gold_extras or {}).items():
        if series is None or series.empty:
            continue
        data = pd.to_numeric(series, errors="coerce")
        index = pd.to_datetime(data.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("UTC").tz_localize(None)
        data.index = index.normalize()
        data = data[~data.index.duplicated(keep="last")].sort_index()
        frame[str(code)] = data.reindex(frame.index).ffill(limit=40)
    # 宏观低频序列（月度/年度/周度）需要长前值填充，否则同一条序列在日频
    # 面板上只有发布当天有值，任何比值表达式都会塌成 NaN。
    return frame.ffill(limit=800)


def _metric(metrics: dict[str, dict[str, float | None]], key: str, field: str = "value") -> float | None:
    return (metrics.get(key) or {}).get(field)


def _direction(value: float | None, threshold: float, above: str, below: str) -> str:
    if value is None:
        return "数据不足"
    return above if value >= threshold else below
