"""Resolve every configured indicator into an auditable reading."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

from app.cycle.config import EVIDENCE_WEIGHT, load_config, stale_days
from app.cycle.market import Panel, indicator_series, zscore

MARKET_EVIDENCE = "E1"


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def phi_series(values: pd.Series) -> pd.Series:
    """Vectorised normal CDF; keeps NaN as NaN (used by monthly history)."""
    frame = pd.to_numeric(values, errors="coerce")
    array = frame.to_numpy(dtype="float64", na_value=np.nan)
    filled = np.nan_to_num(array, nan=0.0)
    mapped = 0.5 * (1.0 + np.vectorize(math.erf)(filled / math.sqrt(2.0)))
    mapped = np.where(np.isnan(array), np.nan, mapped)
    return pd.Series(mapped, index=values.index, dtype="float64")


@dataclass
class Reading:
    id: str
    name: str
    score: str
    weight: float
    direction: float
    value: float | None
    unit: str | None
    asof: str | None
    z: float | None
    score_value: float | None
    evidence: str
    source: str
    layer: str | None
    why: str | None
    caveat: str | None
    stale_days: int | None
    degraded: bool = False
    degrade_reason: str | None = None

    def dict(self) -> dict:
        return asdict(self)


def _market_readings(panel: Panel, specs: list[dict], norm: dict) -> list[Reading]:
    out: list[Reading] = []
    window = int(norm.get("window_days", 2520))
    min_obs = int(norm.get("min_obs", 250))
    clip = float(norm.get("clip_z", 3.5))
    for spec in specs:
        series = indicator_series(panel, spec)
        clean = series.dropna()
        direction = float(spec.get("direction", 1))
        weight = float(spec.get("weight", 0))
        if clean.empty:
            out.append(
                Reading(
                    id=spec["id"],
                    name=spec["name"],
                    score=spec["score"],
                    weight=weight,
                    direction=direction,
                    value=None,
                    unit=spec.get("unit"),
                    asof=None,
                    z=None,
                    score_value=None,
                    evidence=MARKET_EVIDENCE,
                    source="本地行情/宏观序列（未取到值）",
                    layer=spec.get("layer"),
                    why=spec.get("why"),
                    caveat=spec.get("caveat"),
                    stale_days=None,
                    degraded=True,
                    degrade_reason="序列为空或表达式引用的数据未采集",
                )
            )
            continue
        z_series = zscore(clean, window_days=window, min_obs=min_obs, clip=clip)
        z_last = z_series.dropna()
        value = float(clean.iloc[-1])
        asof_ts = clean.index[-1]
        asof = asof_ts.strftime("%Y-%m-%d")
        z = float(z_last.iloc[-1]) if not z_last.empty else None
        score_value = round(100.0 * phi(direction * z), 1) if z is not None else None
        out.append(
            Reading(
                id=spec["id"],
                name=spec["name"],
                score=spec["score"],
                weight=weight,
                direction=direction,
                value=round(value, 4),
                unit=spec.get("unit"),
                asof=asof,
                z=round(z, 3) if z is not None else None,
                score_value=score_value,
                evidence=MARKET_EVIDENCE,
                source="本地行情/宏观序列（z 为 10 年滚动标准化）",
                layer=spec.get("layer"),
                why=spec.get("why"),
                caveat=spec.get("caveat"),
                stale_days=(date.today() - asof_ts.date()).days,
                degraded=z is None,
                degrade_reason=None if z is not None else "样本不足，无法做 10 年标准化",
            )
        )
    return out


def _manual_readings(items: list[dict]) -> list[Reading]:
    out: list[Reading] = []
    for item in items:
        observed = item.get("asof")
        if hasattr(observed, "date"):
            observed = observed.date()
        days = stale_days(observed)
        out.append(
            Reading(
                id=item["id"],
                name=item["name"],
                score=item["score"],
                weight=float(item.get("weight", 0)),
                direction=1.0,
                value=item.get("value"),
                unit=item.get("unit"),
                asof=str(observed) if observed else None,
                z=None,
                score_value=float(item["score_value"]),
                evidence=str(item.get("evidence", "E4")),
                source=str(item.get("source", "")),
                layer="结构性/人工观测",
                why=str(item.get("scale", "")),
                caveat="人工观测与专家映射，更新频率低，结论须随来源更新",
                stale_days=days,
                degraded=(days or 0) > 400,
                degrade_reason=f"人工观测已 {days} 天未更新" if (days or 0) > 400 else None,
            )
        )
    return out


def build_readings(panel: Panel, config: dict | None = None) -> list[Reading]:
    cfg = config or load_config()
    norm = cfg.get("normalization") or {}
    readings = _market_readings(panel, list(cfg.get("indicators") or []), norm)
    readings.extend(_manual_readings(list(cfg.get("manual") or [])))
    return readings


def evidence_weight(readings: list[Reading]) -> float:
    if not readings:
        return 0.0
    return sum(EVIDENCE_WEIGHT.get(r.evidence, 0.5) for r in readings) / len(readings)
