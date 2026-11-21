"""Song lens readings: dollar circulation, debt and gold readings."""

from __future__ import annotations

import pandas as pd

from app.cycle.market import Panel
from app.lens.common import (
    Reading,
    last_value,
    low_freq_column,
    percentile_last,
    ratio,
    rolling_corr,
    ttm,
    z_series,
)
from app.lens.song_catalog import _META, _missing, _reading

_low_freq = low_freq_column


def _yoy_pct(series: pd.Series, periods: int | None = None) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    if periods is None:
        # daily series -> 252 observations; monthly/quarterly passed explicitly.
        periods = 252
    if len(clean) <= periods:
        return None
    base = float(clean.iloc[-1 - periods])
    if base == 0:
        return None
    return (float(clean.iloc[-1]) / base - 1.0) * 100.0


def build_readings(panel: Panel, gold_metric) -> list[Reading]:
    """``gold_metric`` is a callable ``code -> pd.Series`` bound to the session."""
    readings: list[Reading] = []
    dxy = panel.series("DXY")
    readings.append(_reading("song.dxy", dxy, change_days=63))

    dxy_pct = percentile_last(dxy, 252, min_obs=120)
    if dxy_pct is not None:
        readings.append(
            Reading(
                id="song.dxy_pct",
                label=_META["song.dxy_pct"]["label"],
                value=dxy_pct * 100,
                unit="%",
                digits=0,
                asof=last_value(dxy)[1],
                source=_META["song.dxy_pct"]["source"],
                evidence="E2",
                note=_META["song.dxy_pct"]["note"],
            )
        )
    else:
        readings.append(_missing("song.dxy_pct"))

    readings.append(
        Reading(
            id="song.dxy_yoy",
            label=_META["song.dxy_yoy"]["label"],
            value=_yoy_pct(dxy),
            unit="%",
            digits=1,
            asof=last_value(dxy)[1],
            source=_META["song.dxy_yoy"]["source"],
            evidence="E1",
            note=_META["song.dxy_yoy"]["note"],
        )
    )

    real10 = panel.series("US10Y_REAL")
    readings.append(_reading("song.real10", real10, change_days=252, change_label="1年"))

    gdp = _low_freq(panel, "WB_US_GDP")
    debt = _low_freq(panel, "US_FED_DEBT")
    if not gdp.empty and not debt.empty:
        debt_gdp = debt / gdp.where(gdp > 0) * 100
        readings.append(_reading("song.debt_gdp", debt_gdp, change_days=63, pct_window=2520))
    else:
        readings.append(_missing("song.debt_gdp"))

    deficit = _low_freq(panel, "US_MTS_DEFICIT")
    if not gdp.empty and not deficit.empty:
        deficit_gdp = ttm(deficit) / gdp.where(gdp > 0) * 100
        readings.append(_reading("song.deficit_gdp", deficit_gdp, change_days=63, pct_window=2520))
    else:
        readings.append(_missing("song.deficit_gdp"))

    interest = _low_freq(panel, "US_MTS_INTEREST")
    receipts = _low_freq(panel, "US_MTS_RECEIPTS")
    if not interest.empty and not receipts.empty:
        ratio_series = ttm(interest) / ttm(receipts).where(ttm(receipts) > 0) * 100
        readings.append(
            _reading("song.interest_receipts", ratio_series, change_days=63, pct_window=2520)
        )
    else:
        readings.append(_missing("song.interest_receipts"))

    gold = panel.series("XAUUSD")
    readings.append(_reading("song.gold", gold, change_days=252, change_label="1年"))
    readings.append(_reading("song.gold_silver", ratio(panel, "XAUUSD", "SI"), change_days=63))
    readings.append(_reading("song.copper_gold", ratio(panel, "CU", "XAUUSD"), change_days=126, change_label="6个月"))
    readings.append(_reading("song.oil_gold", ratio(panel, "BZ", "XAUUSD"), change_days=126, change_label="6个月"))
    readings.append(
        _reading(
            "song.gold_corr",
            rolling_corr(gold, real10, 252),
            change_days=63,
            pct_window=1260,
        )
    )

    premium = gold_metric("CN_GOLD_PREMIUM_PCT")
    readings.append(_reading("song.cn_premium", premium, change_days=63, pct_window=2520))

    reserves = gold_metric("CN_GOLD_RESERVES_USD")
    yoy = _yoy_pct(reserves, 12)
    if yoy is not None:
        readings.append(
            Reading(
                id="song.cn_reserves_yoy",
                label=_META["song.cn_reserves_yoy"]["label"],
                value=yoy,
                unit="%",
                digits=1,
                asof=last_value(reserves)[1],
                change=yoy,
                change_label="12个月",
                source=_META["song.cn_reserves_yoy"]["source"],
                evidence="E1",
                note=_META["song.cn_reserves_yoy"]["note"],
            )
        )
    else:
        readings.append(_missing("song.cn_reserves_yoy"))

    cb_gold = gold_metric("CB_GOLD_GLOBAL_TONNES")
    readings.append(_reading("song.cb_gold", cb_gold, change_days=365, change_label="4个季度"))

    comex = gold_metric("COMEX_GOLD_INVENTORY_TONNES")
    if not comex.empty and len(comex.dropna()) > 20:
        flow = comex.dropna() - comex.dropna().shift(20)
        readings.append(
            _reading("song.comex_gold_flow", flow, change_days=20, change_label="20日")
        )
    else:
        readings.append(_missing("song.comex_gold_flow"))

    lease = gold_metric("SGE_GOLD_LEASE_3M_PCT")
    readings.append(_reading("song.gold_lease", lease, change_days=63))

    readings.append(_reading("song.usdcnh", panel.series("USDCNH"), change_days=63))
    readings.append(
        _reading("song.em_relative", ratio(panel, "HSI", "SPX"), change_days=126, change_label="6个月")
    )
    readings.append(
        _reading("song.csi_spx", ratio(panel, "000300", "SPX"), change_days=126, change_label="6个月")
    )

    us10 = panel.series("US10Y")
    readings.append(_reading("song.us10y", us10, change_days=252, change_label="1年"))
    us10_pct = percentile_last(us10, 1260, min_obs=250)
    if us10_pct is not None:
        readings.append(
            Reading(
                id="song.us10y_pct",
                label=_META["song.us10y_pct"]["label"],
                value=us10_pct * 100,
                unit="%",
                digits=0,
                asof=last_value(us10)[1],
                source=_META["song.us10y_pct"]["source"],
                evidence="E2",
                note=_META["song.us10y_pct"]["note"],
            )
        )
    else:
        readings.append(_missing("song.us10y_pct"))

    readings.append(_reading("song.jp30y", panel.series("JP30Y"), change_days=252, change_label="1年"))

    spread = panel.series("SOFR_EFFR") * 100
    readings.append(_reading("song.sofr_effr", spread, change_days=21, change_label="1个月"))
    if not spread.empty:
        spike_series = spread - spread.shift(5)
        readings.append(
            _reading("song.sofr_spike", spike_series, change_days=21, change_label="1个月")
        )
    else:
        readings.append(_missing("song.sofr_spike"))

    corr = rolling_corr(panel.series("DXY"), us10, 60)
    readings.append(_reading("song.dxy_us10y_corr", corr, change_days=63, pct_window=1260))

    oil_ret = panel.series("BZ").pct_change(21, fill_method=None)
    gold_ret = gold.pct_change(21, fill_method=None)
    geo = z_series(oil_ret) - z_series(gold_ret)
    readings.append(_reading("song.geo_divergence", geo, change_days=21, change_label="1个月"))

    cpi = _low_freq(panel, "WB_US_CPI").dropna()
    readings.append(_reading("song.us_cpi", cpi, change_days=365, change_label="1年"))

    for missing_id in ("song.reserve_share", "song.comex_silver", "song.cips"):
        readings.append(_missing(missing_id))
    return readings
