"""Eight key readings for the cycle compass front page.

The compass design shows eight numbers (US10Y, real yield, 10Y–2Y, gold,
gold/silver, LME copper, DXY, CN–US spread) with a z-score, a daily change
and a 30-point sparkline.  The cycle engine itself only scores normalized
dimensions; this module keeps the raw instrument-level readings in one place
so the UI never has to invent a number.

Everything here is E1/E2: measured series or a direct derivation of two
measured series.  When a series is missing we return ``missing: True`` with a
human readable reason instead of a placeholder value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar

WINDOW_OBS = 1260  # roughly five years of trading days

MACRO_CODES = {"US10Y", "US2Y", "CN10Y", "US10Y_REAL", "US10Y_BE", "US5Y", "US30Y", "EFFR", "SOFR"}


@dataclass(frozen=True)
class Spec:
    """One card: how to build its series from local data."""

    id: str
    label: str
    kind: str  # "macro" | "bar" | "ratio" | "diff"
    codes: tuple[str, ...]
    unit: str
    digits: int
    source: str


SPECS: tuple[Spec, ...] = (
    Spec("us10y", "美债 10Y", "macro", ("US10Y",), "%", 2, "FRED DGS10 / 本地 macro_obs"),
    Spec("us10y_real", "10Y 实际利率", "macro", ("US10Y_REAL",), "%", 2, "FRED DFII10 / 本地 macro_obs"),
    Spec("us10y_2y", "10Y–2Y 利差", "diff", ("US10Y", "US2Y"), "bp", 0, "US10Y − US2Y"),
    Spec("gold", "黄金", "bar", ("XAUUSD",), "美元", 2, "现货黄金日线"),
    Spec("gold_silver", "金银比", "ratio", ("XAUUSD", "SI"), "倍", 1, "XAUUSD ÷ 白银"),
    Spec("lme_copper", "LME 铜", "bar", ("HG",), "美元", 0, "铜连续合约日线"),
    Spec("dxy", "美元指数", "bar", ("DXY",), "", 2, "ICE DXY 日线"),
    Spec("cn_us_spread", "中美 10Y 利差", "diff", ("CN10Y", "US10Y"), "bp", 0, "CN10Y − US10Y"),
)

UNIT_SCALE = {"bp": 100.0}


def _macro_series(session: Session, code: str) -> pd.Series:
    rows = session.execute(
        select(MacroObs.ts_utc, MacroObs.value)
        .join(MacroSeries, MacroSeries.id == MacroObs.series_id)
        .where(MacroSeries.code == code)
        .order_by(MacroObs.ts_utc)
    ).all()
    if not rows:
        return pd.Series(dtype="float64")
    index = [_aware(ts).date() for ts, _ in rows]
    return pd.Series([float(v) for _, v in rows], index=pd.Index(index), dtype="float64")


def _bar_series(session: Session, code: str) -> pd.Series:
    rows = session.execute(
        select(MarketBar.ts_utc, MarketBar.close)
        .join(Instrument, Instrument.id == MarketBar.instrument_id)
        .where(Instrument.symbol == code, MarketBar.timeframe == "1d")
        .order_by(MarketBar.ts_utc)
    ).all()
    if not rows:
        return pd.Series(dtype="float64")
    index = [_aware(ts).date() for ts, _ in rows]
    return pd.Series([float(v) for _, v in rows], index=pd.Index(index), dtype="float64")


def _aware(value) -> datetime:  # noqa: ANN001
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build(session: Session, spec: Spec) -> tuple[pd.Series, str | None]:
    if spec.kind == "macro":
        return _macro_series(session, spec.codes[0]), None
    if spec.kind == "bar":
        return _bar_series(session, spec.codes[0]), None
    series = [
        _macro_series(session, code) if code in MACRO_CODES else _bar_series(session, code)
        for code in spec.codes
    ]
    left, right = series
    if left.empty or right.empty:
        return pd.Series(dtype="float64"), f"缺少 {' / '.join(spec.codes)} 序列"
    joined = pd.concat([left.rename("l"), right.rename("r")], axis=1).dropna()
    if joined.empty:
        return pd.Series(dtype="float64"), "两条序列没有重叠日期"
    if spec.kind == "ratio":
        return joined["l"] / joined["r"], None
    return joined["l"] - joined["r"], None


def _zscore(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 60:
        return None
    window = clean.tail(WINDOW_OBS)
    std = float(window.std())
    if not std:
        return None
    z = (float(clean.iloc[-1]) - float(window.mean())) / std
    return round(max(-4.0, min(4.0, z)), 2)


def _spark(series: pd.Series, points: int = 30) -> list[dict]:
    clean = pd.to_numeric(series, errors="coerce").dropna().tail(points)
    scale = 100.0
    return [
        {"date": index.isoformat(), "value": round(float(value) * scale, 4)}
        for index, value in clean.items()
    ]


def build_readings(session: Session) -> dict:
    """Return the eight compass readings plus provenance for the UI."""

    items: list[dict] = []
    for spec in SPECS:
        series, reason = _build(session, spec)
        if series.empty:
            items.append(
                {
                    "id": spec.id,
                    "label": spec.label,
                    "missing": True,
                    "reason": reason or "本地没有该序列",
                    "source": spec.source,
                    "evidence": "E1",
                }
            )
            continue
        clean = pd.to_numeric(series, errors="coerce").dropna()
        scale = UNIT_SCALE.get(spec.unit, 1.0)
        value = float(clean.iloc[-1]) * scale
        prev = float(clean.iloc[-2]) * scale if len(clean) > 1 else None
        digits = spec.digits
        items.append(
            {
                "id": spec.id,
                "label": spec.label,
                "missing": False,
                "value": round(value, digits),
                "unit": spec.unit,
                "digits": digits,
                "z": _zscore(clean),
                "delta_1d": round(value - prev, digits) if prev is not None else None,
                "asof": clean.index[-1].isoformat(),
                "spark": _spark(clean),
                "source": spec.source,
                "evidence": "E2",
                "reason": None,
            }
        )
    return {
        "items": items,
        "total": len(items),
        "missing": sum(1 for item in items if item.get("missing")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "读数直接取本地 macro_obs / market_bars；z 为相对最近约 5 年（1260 个观测）的 z-score；"
        "delta_1d 为最近两个观测之差；缺失时返回 missing=true 并给出原因，不填占位值。",
    }
