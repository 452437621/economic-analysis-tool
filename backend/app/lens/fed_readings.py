"""Fed lens readings: levels/ratios computed from the local panel."""

from __future__ import annotations

import pandas as pd

from app.cycle.market import Panel
from app.lens.common import (
    Reading,
    drawdown_pct,
    last_value,
    low_freq_column,
    ratio,
    rolling_corr,
    z_series,
)
from app.lens.fed_catalog import _META, _missing, _reading

_low_freq = low_freq_column


def _composite(panel: Panel) -> pd.Series:
    spx = panel.series("SPX")
    dxy = panel.series("DXY")
    real10 = panel.series("US10Y_REAL")
    sofr_spread = panel.series("SOFR_EFFR")
    parts: list[pd.Series] = []
    if not spx.empty:
        parts.append(-z_series(spx.pct_change(63, fill_method=None)))
    if not dxy.empty:
        parts.append(z_series(dxy.pct_change(63, fill_method=None)))
    if not real10.empty:
        parts.append(z_series(real10.diff(63)))
    if not sofr_spread.empty:
        parts.append(z_series(sofr_spread))
    if not parts:
        return pd.Series(dtype="float64")
    frame = pd.concat(parts, axis=1)
    fci = frame.mean(axis=1, skipna=True)
    return fci.where(frame.notna().sum(axis=1) >= 2)


def build_readings(panel: Panel) -> list[Reading]:
    readings: list[Reading] = []
    effr = panel.series("EFFR")
    be10 = panel.series("US10Y_BE")
    real10 = panel.series("US10Y_REAL")
    us10 = panel.series("US10Y")
    us2 = panel.series("US2Y")
    us5 = panel.series("US5Y")
    us30 = panel.series("US30Y")

    readings.append(_reading("fed.effr", effr, change_days=63))
    readings.append(_reading("fed.real_policy", effr - be10, change_days=63))
    readings.append(_reading("fed.real10", real10, change_days=63))
    readings.append(_reading("fed.real5", panel.series("US5Y_REAL"), change_days=63))
    readings.append(_reading("fed.curve_2s10s", (us10 - us2) * 100, change_days=63))
    readings.append(_reading("fed.curve_5s30s", (us30 - us5) * 100, change_days=63))
    readings.append(_reading("fed.be10", be10, change_days=63))
    readings.append(_reading("fed.be5", panel.series("US5Y_BE"), change_days=63))
    readings.append(
        _reading("fed.sofr_effr", panel.series("SOFR_EFFR") * 100, change_days=21, change_label="1个月")
    )
    readings.append(_reading("fed.dxy", panel.series("DXY"), change_days=63))

    fci = _composite(panel)
    readings.append(_reading("fed.fci", fci, change_days=63, z_window=1260))

    copper_gold = ratio(panel, "CU", "XAUUSD")
    readings.append(_reading("fed.growth", z_series(copper_gold), change_days=63, digits=2))
    readings.append(_reading("fed.inflation", z_series(be10), change_days=63, digits=2))

    spx = panel.series("SPX")
    readings.append(
        _reading("fed.spx_drawdown", drawdown_pct(spx), change_days=21, change_label="1个月", digits=1)
    )

    gdp = _low_freq(panel, "WB_US_GDP")
    valuation = (spx / gdp.where(gdp > 0) * 1e12) if not spx.empty and not gdp.empty else pd.Series(dtype="float64")
    readings.append(_reading("fed.spx_valuation", valuation, change_days=252, change_label="1年", pct_window=2520))

    readings.append(_reading("fed.ndx_ratio", ratio(panel, "NDX", "SPX"), change_days=63))
    readings.append(
        _reading(
            "fed.gold_real_corr",
            rolling_corr(panel.series("XAUUSD"), real10, 252),
            change_days=63,
            pct_window=1260,
        )
    )

    unemployment = _low_freq(panel, "WB_US_UNEMPLOYMENT").dropna()
    if len(unemployment) > 4:
        unemployment = unemployment.copy()
        # annual series: a 4-observation change is the 12-month change.
        change = float(unemployment.iloc[-1] - unemployment.iloc[-5]) if len(unemployment) >= 5 else None
        last, asof = last_value(unemployment)
        readings.append(
            Reading(
                id="fed.unemployment",
                label=_META["fed.unemployment"]["label"],
                value=last,
                unit="%",
                digits=1,
                asof=asof,
                change=change,
                change_label="12个月",
                source=_META["fed.unemployment"]["source"],
                evidence="E1",
                note=_META["fed.unemployment"]["note"],
            )
        )
    else:
        readings.append(_missing("fed.unemployment"))

    for missing_id in ("fed.payload", "fed.hy_oas", "fed.m2"):
        readings.append(_missing(missing_id))
    return readings
