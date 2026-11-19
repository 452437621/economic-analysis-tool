"""Shared primitives for the two-lens module (Fed lens / Song Hongbing lens).

Every number produced here is a pure function of the local daily panel or of a
gold-metrics series already stored in SQLite.  Nothing touches the network, so
the same inputs always reproduce the same readings — a hard requirement for the
provenance ledger to be meaningful.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cycle.market import Panel
from app.models.core import GoldMetric


# ── small numeric helpers ──────────────────────────────────────────────


def clamp(value: float | None, low: float, high: float) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return max(low, min(high, value))


def safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Ratio that yields NaN instead of inf when the denominator is zero."""
    return numerator.divide(denominator.where(denominator != 0))


def last_value(series: pd.Series) -> tuple[float | None, str | None]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None, None
    value = float(clean.iloc[-1])
    asof = clean.index[-1]
    return value, asof.strftime("%Y-%m-%d") if hasattr(asof, "strftime") else str(asof)


def value_days_ago(series: pd.Series, days: int) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    last_ts = clean.index[-1]
    try:
        cutoff = last_ts - pd.Timedelta(days=int(days))
    except (TypeError, ValueError):
        return None
    past = clean[clean.index <= cutoff]
    return float(past.iloc[-1]) if not past.empty else None


def change_over(series: pd.Series, days: int) -> float | None:
    last, _ = last_value(series)
    past = value_days_ago(series, days)
    if last is None or past is None:
        return None
    return last - past


def pct_change_over(series: pd.Series, days: int) -> float | None:
    last, _ = last_value(series)
    past = value_days_ago(series, days)
    if last is None or past is None or past == 0:
        return None
    return (last / past - 1.0) * 100.0


def z_series(
    series: pd.Series, window_days: int = 1260, min_obs: int = 120, clip: float = 3.5
) -> pd.Series:
    """Rolling z-score series (used to build composite stress indices)."""
    clean = pd.to_numeric(series, errors="coerce").astype("float64")
    window = f"{int(window_days)}D"
    mean = clean.rolling(window, min_periods=min_obs).mean()
    std = clean.rolling(window, min_periods=min_obs).std()
    z = (clean - mean) / std.where(std > 0)
    return z.clip(lower=-clip, upper=clip)


def z_last(series: pd.Series, window_days: int = 1260, min_obs: int = 120) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").astype("float64")
    window = f"{int(window_days)}D"
    mean = clean.rolling(window, min_periods=min_obs).mean()
    std = clean.rolling(window, min_periods=min_obs).std()
    z = (clean - mean) / std.where(std > 0)
    clean_z = z.dropna()
    if clean_z.empty:
        return None
    return float(clean_z.iloc[-1])


def percentile_last(series: pd.Series, window_days: int = 2520, min_obs: int = 250) -> float | None:
    """Percentile (0..1) of the latest value inside its trailing window."""
    clean = pd.to_numeric(series, errors="coerce").astype("float64")
    window = f"{int(window_days)}D"
    rank = clean.rolling(window, min_periods=min_obs).rank(pct=True)
    clean_rank = rank.dropna()
    if clean_rank.empty:
        return None
    return float(clean_rank.iloc[-1])


def rolling_corr(
    a: pd.Series, b: pd.Series, window_days: int = 252, min_obs: int = 30
) -> pd.Series:
    """Rolling correlation of daily percentage changes, aligned on the panel."""
    aligned = pd.concat([a, b], axis=1, join="inner")
    if aligned.empty or aligned.shape[1] < 2:
        return pd.Series(dtype="float64")
    ret_a = aligned.iloc[:, 0].pct_change(fill_method=None)
    ret_b = aligned.iloc[:, 1].pct_change(fill_method=None)
    window = f"{int(window_days)}D"
    return ret_a.rolling(window, min_periods=min_obs).corr(ret_b)


def drawdown_pct(series: pd.Series, window_days: int = 252, min_obs: int = 20) -> pd.Series:
    """Percentage below the trailing high (positive number, 0 at a new high)."""
    clean = pd.to_numeric(series, errors="coerce").astype("float64")
    window = f"{int(window_days)}D"
    peak = clean.rolling(window, min_periods=min_obs).max()
    return (1.0 - clean / peak.where(peak > 0)) * 100.0


def ratio(panel: Panel, numerator: str, denominator: str) -> pd.Series:
    left = panel.series(numerator)
    right = panel.series(denominator)
    if left.empty or right.empty:
        return pd.Series(dtype="float64")
    return safe_div(left, right)


def ttm(series: pd.Series, periods: int = 12) -> pd.Series:
    """Trailing twelve observations (monthly series)."""
    return pd.to_numeric(series, errors="coerce").rolling(periods, min_periods=periods).sum()


def load_gold_series(session: Session, code: str) -> pd.Series:
    rows = session.execute(
        select(GoldMetric.as_of, GoldMetric.value)
        .where(GoldMetric.code == code)
        .order_by(GoldMetric.as_of)
    ).all()
    if not rows:
        return pd.Series(dtype="float64")
    frame = pd.DataFrame(rows, columns=["as_of", "value"])
    frame["as_of"] = pd.to_datetime(frame["as_of"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    frame = frame.drop_duplicates(subset=["as_of"], keep="last")
    return frame.set_index("as_of")["value"].astype("float64").sort_index()


def monthly_value_at(series: pd.Series, months_ago: int) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) <= months_ago:
        return None
    return float(clean.iloc[-1 - months_ago])


# ── reading model ──────────────────────────────────────────────────────


@dataclass
class Reading:
    """One auditable lens reading (a named number plus its context)."""

    id: str
    label: str
    value: float | None = None
    unit: str = ""
    digits: int = 2
    asof: str | None = None
    change: float | None = None
    change_label: str = ""
    z: float | None = None
    percentile: float | None = None
    source: str = ""
    evidence: str = "E3"
    note: str = ""
    missing_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "value": _round(self.value, self.digits),
            "unit": self.unit,
            "digits": self.digits,
            "asof": self.asof,
            "change": _round(self.change, max(self.digits, 1)),
            "change_label": self.change_label,
            "z": _round(self.z, 2),
            "percentile": _round(self.percentile, 3),
            "source": self.source,
            "evidence": self.evidence,
            "note": self.note,
            "missing_reason": self.missing_reason,
        }


def _round(value: float | None, digits: int) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def build_reading(
    reading_id: str,
    label: str,
    series: pd.Series,
    *,
    unit: str = "",
    digits: int = 2,
    source: str = "",
    evidence: str = "E3",
    change_days: int = 63,
    change_label: str = "3个月",
    z_window: int = 1260,
    pct_window: int = 2520,
    note: str = "",
    missing_reason: str = "本地库缺该序列",
    value_transform: str | None = None,
) -> Reading:
    """Build a reading from a level series, adding change / z / percentile."""
    clean = pd.to_numeric(series, errors="coerce").astype("float64")
    value, asof = last_value(clean)
    if value is None:
        return Reading(
            id=reading_id,
            label=label,
            unit=unit,
            digits=digits,
            source=source,
            evidence=evidence,
            note=note,
            missing_reason=missing_reason,
        )
    change = change_over(clean, change_days)
    return Reading(
        id=reading_id,
        label=label,
        value=value,
        unit=unit,
        digits=digits,
        asof=asof,
        change=change,
        change_label=change_label,
        z=z_last(clean, z_window),
        percentile=percentile_last(clean, pct_window),
        source=source,
        evidence=evidence,
        note=note,
    )


def round_opt(value: float | None, digits: int = 2) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def reading_from_catalog(
    meta: dict[str, dict[str, Any]],
    reading_id: str,
    series: pd.Series,
    **kwargs: Any,
) -> Reading:
    """Build a reading from catalog metadata (single source for unit/digits/evidence)."""
    item = meta[reading_id]
    kwargs.pop("digits", None)
    kwargs.pop("unit", None)
    return build_reading(
        reading_id,
        item["label"],
        series,
        unit=item.get("unit", ""),
        digits=int(item.get("digits", 2)),
        source=item.get("source", ""),
        evidence=item.get("evidence", "E3"),
        note=item.get("note", ""),
        **kwargs,
    )


def missing_from_catalog(meta: dict[str, dict[str, Any]], reading_id: str) -> Reading:
    """A placeholder reading for a series the local database does not carry."""
    item = meta[reading_id]
    return Reading(
        id=reading_id,
        label=item["label"],
        unit=item.get("unit", ""),
        digits=int(item.get("digits", 2)),
        source=item.get("source", ""),
        evidence=item.get("evidence", "E3"),
        note=item.get("note", ""),
        missing_reason="本地库缺该序列，需新增数据源",
    )


def low_freq_column(panel: Panel, code: str) -> pd.Series:
    """Low-frequency macro column carried forward to the next release."""
    if code not in panel.daily.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(panel.daily[code], errors="coerce").ffill()


def format_reading(reading: Reading) -> str:
    """Compact display string used in narrative sentences."""
    if reading.value is None:
        return "缺"
    return f"{reading.value:.{reading.digits}f}{reading.unit or ''}"


def metric_map(readings: Iterable[Reading]) -> dict[str, dict[str, float | None]]:
    """Flatten readings for the rule evaluator: {id: {value, chg, z, pct}}."""
    out: dict[str, dict[str, float | None]] = {}
    for reading in readings:
        out[reading.id] = {
            "value": reading.value,
            "chg": reading.change,
            "z": reading.z,
            "pct": reading.percentile,
        }
    return out


# ── rule evaluation ────────────────────────────────────────────────────


_OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "abs_gt": lambda a, b: abs(a) > b,
    "abs_lt": lambda a, b: abs(a) < b,
}


def _condition_true(condition: dict, metrics: dict[str, dict[str, float | None]]) -> tuple[bool, str]:
    metric_id = str(condition.get("metric") or "")
    field_name = str(condition.get("field") or "value")
    op_name = str(condition.get("op") or ">")
    threshold = condition.get("value")
    entry = metrics.get(metric_id) or {}
    raw = entry.get(field_name)
    if raw is None or threshold is None:
        return False, f"{metric_id}.{field_name} 缺失"
    compare = _OPS.get(op_name)
    if compare is None:
        return False, f"不支持的比较符 {op_name}"
    try:
        ok = bool(compare(float(raw), float(threshold)))
    except (TypeError, ValueError):
        return False, f"{metric_id}.{field_name} 非数值"
    return ok, f"{metric_id}.{field_name}={raw:.3f} {op_name} {threshold:g}"


def evaluate_rule(rule: dict, metrics: dict[str, dict[str, float | None]]) -> dict[str, Any]:
    """Evaluate one declarative rule from ``config/lens.yaml``.

    Returns a dict with ``fired`` / ``status`` (fired/miss/unknown), the human
    readable message and the per-condition trace used by the evidence drawer.
    """
    conditions = rule.get("when") or {}
    all_conditions = list(conditions.get("all") or [])
    any_conditions = list(conditions.get("any") or [])
    trace: list[dict[str, Any]] = []
    unknown = False

    all_results: list[bool] = []
    for condition in all_conditions:
        ok, text = _condition_true(condition, metrics)
        if "缺失" in text:
            unknown = True
        all_results.append(ok)
        trace.append({"condition": text, "met": ok})

    any_results: list[bool] = []
    for condition in any_conditions:
        ok, text = _condition_true(condition, metrics)
        if "缺失" in text:
            unknown = True
        any_results.append(ok)
        trace.append({"condition": text, "met": ok})

    fired = True
    if all_conditions:
        fired = fired and all(all_results)
    if any_conditions:
        fired = fired and any(any_results)
    if not all_conditions and not any_conditions:
        fired = False

    status = "fired" if fired else ("unknown" if unknown else "miss")
    return {
        "id": rule.get("id"),
        "name": rule.get("name"),
        "severity": rule.get("severity", "info"),
        "message": rule.get("message"),
        "falsifier": rule.get("falsifier"),
        "assets": rule.get("assets") or [],
        "status": status,
        "fired": fired,
        "trace": trace,
        "sources": rule.get("sources") or [],
    }


def state_color(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 0.9:
        return "bull"
    if score >= 0.25:
        return "lean-bull"
    if score <= -0.9:
        return "bear"
    if score <= -0.25:
        return "lean-bear"
    return "neutral"


def score_label(score: float | None) -> str:
    if score is None:
        return "数据不足"
    if score >= 1.2:
        return "强多"
    if score >= 0.4:
        return "偏多"
    if score > -0.4:
        return "中性"
    if score > -1.2:
        return "偏空"
    return "强空"
