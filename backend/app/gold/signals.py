"""Golden-model signals ported from the standalone ``golden_analysis`` project.

The standalone project computed a 0-100 composite from twelve hand-written
signals on a long gold history.  Here the *orthogonal* signals are folded into
the system's existing indicator score (actual rates, DXY, central-bank buying,
ETF and COT are already covered by ``app.gold.registry`` and must not be
double-counted).  Everything is derived from the system's own SQLite data:

* ``market_bars``: XAUUSD / GC / AU, SI, DXY, SPX, NDX, CL, USDCNH, HG
* ``macro_obs``:    US10Y_REAL, US10Y_BE

All calculations only use observations at or before the evaluation date
(rolling windows end "today"), so there is no look-ahead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.data import load_frames
from app.topics.scoring import clip, factor, norm_pct

TRADING_DAYS = 252
GOLD_CANDIDATES = ("XAUUSD", "GC", "AU")
SILVER_CANDIDATES = ("SI", "AG")

SIGNAL_META = {
    "fair_value": ("GOLD_VALUATION_GAP", "实际利率估值缺口", "估值模型"),
    "trend": ("GOLD_TREND_MA", "趋势（MA50/MA200）", "价格与宏观驱动"),
    "volatility": ("GOLD_VOL_20D_PCT", "20 日波动率状态", "价格与宏观驱动"),
    "silver_ratio": ("GOLD_SILVER_RATIO", "金银比", "价格与宏观驱动"),
    "inflation_expectation": ("GOLD_BREAKEVEN_10Y", "10 年盈亏平衡通胀", "价格与宏观驱动"),
    "seasonality": ("GOLD_SEASONALITY", "月度季节性", "价格与宏观驱动"),
}

DEFAULT_WEIGHTS = {
    "fair_value": 12.0,
    "trend": 14.0,
    "volatility": 5.0,
    "silver_ratio": 5.0,
    "inflation_expectation": 5.0,
    "seasonality": 4.0,
}


# ---------------------------------------------------------------------------
# Small indicator helpers (ported from golden_analysis/gold/factors.py)
# ---------------------------------------------------------------------------
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    result = 100.0 - 100.0 / (1.0 + rs)
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    result = result.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
    return result


def realized_vol(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window, min_periods=max(5, window // 2)).std() * math.sqrt(TRADING_DAYS) * 100.0


def drawdown(close: pd.Series) -> pd.Series:
    peak = close.cummax()
    return close / peak - 1.0


def pct_rank_last(series: pd.Series, min_obs: int = 30) -> float | None:
    values = series.dropna()
    if len(values) < min_obs:
        return None
    current = float(values.iloc[-1])
    return float((values <= current).sum()) / len(values) * 100.0


def _zscore_last(values: pd.Series, min_obs: int = 30) -> float | None:
    clean = values.dropna()
    if len(clean) < min_obs:
        return None
    std = float(clean.std(ddof=1))
    if not std:
        return None
    return (float(clean.iloc[-1]) - float(clean.mean())) / std


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[float, float, float] | None:
    """Return ``(intercept, slope, residual_std)`` for a simple OLS fit."""
    mask = np.isfinite(y) & np.isfinite(x)
    y, x = y[mask], x[mask]
    if len(y) < 10:
        return None
    design = np.column_stack([np.ones(len(x)), x])
    try:
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    resid = y - design @ beta
    dof = max(1, len(y) - 2)
    return float(beta[0]), float(beta[1]), float(np.sqrt((resid @ resid) / dof))


def _ret(series: pd.Series, days: int) -> float | None:
    clean = series.dropna()
    if len(clean) <= days:
        return None
    base = float(clean.iloc[-1 - days])
    if not base:
        return None
    return (float(clean.iloc[-1]) / base - 1.0) * 100.0


def _safe_float(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------
@dataclass
class GoldSignalContext:
    gold: pd.Series
    signals: list[dict[str, Any]] = field(default_factory=list)
    momentum: dict[str, Any] | None = None
    valuation: dict[str, Any] | None = None
    seasonality: dict[str, Any] | None = None
    regime: dict[str, Any] | None = None
    performance: dict[str, Any] | None = None
    technical: dict[str, Any] | None = None
    correlations: list[dict[str, Any]] = field(default_factory=list)
    coverage: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return not self.gold.empty


def _price_series(closes: pd.DataFrame) -> tuple[pd.Series, str]:
    for symbol in GOLD_CANDIDATES:
        if symbol in closes.columns:
            series = closes[symbol].dropna()
            if len(series) >= 30:
                return series, symbol
    return pd.Series(dtype=float), ""


def _silver_series(closes: pd.DataFrame) -> tuple[pd.Series, str]:
    for symbol in SILVER_CANDIDATES:
        if symbol in closes.columns:
            series = closes[symbol].dropna()
            if len(series) >= 30:
                return series, symbol
    return pd.Series(dtype=float), ""


def _weights(spec=None) -> dict[str, float]:
    if spec is not None and spec.signal_weights:
        return {**DEFAULT_WEIGHTS, **{key: float(value) for key, value in spec.signal_weights.items()}}
    return dict(DEFAULT_WEIGHTS)


def _add_signal(
    out: list[dict[str, Any]],
    *,
    key: str,
    weights: dict[str, float],
    score: float,
    value: float | None,
    change: float | None,
    explain: str,
    source: str,
    available: bool,
    as_of: str | None,
    unit: str = "",
    freq: str = "d",
) -> None:
    code, name, category = SIGNAL_META[key]
    out.append(
        factor(
            code=code,
            name=name,
            category="price",
            category_label=category,
            weight=weights.get(key, 0.0),
            direction=1,
            score=score if available else 0.0,
            available=available,
            value=value,
            change=change,
            unit=unit,
            freq=freq,
            source=source,
            note=explain,
            explain=explain,
            as_of=as_of,
            kind="signal",
        )
    )


def build_signal_context(session: Session, spec=None) -> GoldSignalContext:
    frames = load_frames(session)
    closes = frames.closes
    macro = frames.macro
    gold, gold_symbol = _price_series(closes)
    if gold.empty:
        reason = "黄金价格序列缺失（XAUUSD/GC/AU），量化信号未计算。"
        return GoldSignalContext(
            gold=gold,
            signals=unavailable_signals(reason, spec),
            notes=[reason],
        )
    gold = gold.sort_index()
    as_of = gold.index[-1].date().isoformat()
    weights = _weights(spec)
    signals: list[dict[str, Any]] = []

    # ---- 1) 实际利率估值模型 ------------------------------------------------
    valuation: dict[str, Any] | None = None
    if "US10Y_REAL" in macro.columns:
        real = macro["US10Y_REAL"].reindex(gold.index).ffill()
        frame = pd.DataFrame({"gold": np.log(gold), "real": real}).dropna()
        window = min(750, len(frame))
        if window >= 120:
            sample = frame.tail(window)
            fit = _ols(sample["gold"].to_numpy(), sample["real"].to_numpy())
            if fit is not None:
                intercept, slope, resid_std = fit
                current_real = float(sample["real"].iloc[-1])
                current_price = float(gold.iloc[-1])
                fair = math.exp(intercept + slope * current_real)
                gap = (current_price / fair - 1.0) * 100.0
                resid = sample["gold"] - (intercept + slope * sample["real"])
                z = float(resid.iloc[-1] / resid_std) if resid_std else None
                pctile = pct_rank_last(resid.reset_index(drop=True), 60)
                score = 0.0
                if z is not None:
                    score += -0.7 * clip(z / 2.0)
                if pctile is not None:
                    score += -0.3 * norm_pct(pctile)
                detail = (
                    f"实际利率模型公允价 {fair:,.0f} 美元，现价较公允价 {gap:+.1f}%"
                    + (f"，残差 z={z:+.2f}" if z is not None else "")
                    + (f"，2003 年以来第 {pctile:.0f} 百分位" if pctile is not None else "")
                    + "。"
                )
                _add_signal(
                    signals,
                    key="fair_value",
                    weights=weights,
                    score=score,
                    value=gap,
                    change=gap,
                    explain=detail,
                    source=f"{gold_symbol} × US10Y_REAL",
                    available=True,
                    as_of=as_of,
                    unit="%",
                )
                valuation = {
                    "ok": True,
                    "fair_value": _safe_float(fair, 2),
                    "current_price": _safe_float(current_price, 2),
                    "gap_pct": _safe_float(gap, 2),
                    "z_score": _safe_float(z, 3),
                    "percentile": _safe_float(pctile, 1),
                    "window": int(window),
                    "real_yield": _safe_float(current_real, 4),
                    "beta": _safe_float(slope, 4),
                    "history": {
                        "dates": [item.date().isoformat() for item in sample.index[-180:]],
                        "fair": [
                            _safe_float(math.exp(intercept + slope * value), 2)
                            for value in sample["real"].tail(180)
                        ],
                        "actual": [_safe_float(value, 2) for value in sample["gold"].tail(180).map(math.exp)],
                    },
                }
        if valuation is None:
            signals.append(_unavailable("fair_value", weights, "实际利率样本不足（<120 个交易日）", as_of))
    else:
        signals.append(_unavailable("fair_value", weights, "缺少 US10Y_REAL 宏观序列", as_of))

    # ---- 2) 趋势 ------------------------------------------------------------
    ma50 = sma(gold, 50)
    ma200 = sma(gold, 200)
    if len(gold) >= 210 and not math.isnan(ma200.iloc[-1]):
        price = float(gold.iloc[-1])
        ratio200 = price / float(ma200.iloc[-1]) - 1.0
        cross = float(ma50.iloc[-1]) / float(ma200.iloc[-1]) - 1.0
        score = 0.6 * clip(ratio200 / 0.10) + 0.4 * clip(cross / 0.05)
        detail = (
            f"现价{'高于' if ratio200 >= 0 else '低于'} MA200 {abs(ratio200) * 100:.1f}%，"
            f"MA50 {'高于' if cross >= 0 else '低于'} MA200 {abs(cross) * 100:.1f}%，"
            f"中期趋势{'向上' if cross >= 0 else '向下'}。"
        )
        _add_signal(
            signals,
            key="trend",
            weights=weights,
            score=score,
            value=ratio200 * 100,
            change=cross * 100,
            explain=detail,
            source=gold_symbol,
            available=True,
            as_of=as_of,
            unit="%",
        )
    else:
        signals.append(_unavailable("trend", weights, "MA200 样本不足", as_of))

    # ---- 3) 波动率 ----------------------------------------------------------
    returns = gold.pct_change()
    vol20 = realized_vol(returns, 20)
    vol_pctile = pct_rank_last(vol20.dropna(), 60)
    if vol_pctile is not None:
        level = float(vol20.iloc[-1])
        state = "高波动" if level > 20.0 else "低波动"
        detail = f"20 日年化波动率 {level:.1f}%（{state}），历史分位 {vol_pctile:.0f}%；高波动环境建议降低仓位。"
        _add_signal(
            signals,
            key="volatility",
            weights=weights,
            score=-0.5 * norm_pct(vol_pctile),
            value=level,
            change=None,
            explain=detail,
            source=gold_symbol,
            available=True,
            as_of=as_of,
            unit="%",
        )
    else:
        signals.append(_unavailable("volatility", weights, "波动率样本不足", as_of))

    # ---- 4) 金银比 ----------------------------------------------------------
    silver, silver_symbol = _silver_series(closes)
    if not silver.empty:
        ratio = (gold / silver.reindex(gold.index).ffill()).dropna()
        ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
        ratio_pct = pct_rank_last(ratio, 60)
        if ratio_pct is not None:
            level = float(ratio.iloc[-1])
            detail = (
                f"金银比 {level:.1f}，历史分位 {ratio_pct:.0f}%；比值越高说明黄金相对白银越贵，"
                "存在均值回归压力。"
            )
            _add_signal(
                signals,
                key="silver_ratio",
                weights=weights,
                score=-0.6 * norm_pct(ratio_pct),
                value=level,
                change=None,
                explain=detail,
                source=f"{gold_symbol}/{silver_symbol}",
                available=True,
                as_of=as_of,
            )
        else:
            signals.append(_unavailable("silver_ratio", weights, "金银比样本不足", as_of))
    else:
        signals.append(_unavailable("silver_ratio", weights, "白银序列缺失（SI/AG）", as_of))

    # ---- 5) 通胀预期 --------------------------------------------------------
    if "US10Y_BE" in macro.columns:
        be = macro["US10Y_BE"].reindex(gold.index).ffill()
        be_pct = pct_rank_last(be.dropna(), 60)
        if be_pct is not None:
            level = float(be.iloc[-1])
            chg63 = None
            clean = be.dropna()
            if len(clean) > 63:
                chg63 = (float(clean.iloc[-1]) - float(clean.iloc[-64])) * 100.0
            score = 0.6 * clip((chg63 or 0.0) / 40.0) + 0.4 * norm_pct(be_pct)
            detail = (
                f"10 年盈亏平衡通胀 {level:.2f}%（近 3 个月 {(chg63 or 0):+.0f}bp），"
                f"历史分位 {be_pct:.0f}%；通胀预期升温时黄金的抗通胀属性通常受益。"
            )
            _add_signal(
                signals,
                key="inflation_expectation",
                weights=weights,
                score=score,
                value=level,
                change=chg63,
                explain=detail,
                source="US10Y_BE",
                available=True,
                as_of=as_of,
                unit="%",
            )
        else:
            signals.append(_unavailable("inflation_expectation", weights, "盈亏平衡通胀样本不足", as_of))
    else:
        signals.append(_unavailable("inflation_expectation", weights, "缺少 US10Y_BE 宏观序列", as_of))

    # ---- 6) 季节性 ----------------------------------------------------------
    seasonality, seasonal_signal = _build_seasonality(gold, as_of)
    if seasonal_signal is not None:
        signals.append(
            factor(
                code="GOLD_SEASONALITY",
                name=SIGNAL_META["seasonality"][1],
                category="price",
                category_label=SIGNAL_META["seasonality"][2],
                weight=weights.get("seasonality", 0.0),
                direction=1,
                score=seasonal_signal["score"],
                available=True,
                value=seasonal_signal["avg_return"],
                change=seasonal_signal["win_rate"],
                unit="%",
                freq="m",
                source="月度金价收益",
                note=seasonal_signal["detail"],
                explain=seasonal_signal["detail"],
                as_of=as_of,
                kind="signal",
            )
        )
    else:
        signals.append(_unavailable("seasonality", weights, "季节性样本不足 10 年", as_of))

    # ---- 复合动量（替换现有 GOLD_MOM_20D_PCT 的得分口径）---------------------
    momentum = None
    r3m = _ret(gold, 63)
    rsi14 = rsi(gold, 14)
    rsi_value = float(rsi14.iloc[-1]) if len(rsi14) and not math.isnan(rsi14.iloc[-1]) else None
    if r3m is not None and rsi_value is not None:
        score = 0.6 * clip(r3m / 10.0) + 0.4 * clip((rsi_value - 50.0) / 30.0)
        momentum = {
            "score": score,
            "value": r3m,
            "change": r3m,
            "rsi14": rsi_value,
            "explain": f"近 3 个月收益 {r3m:+.1f}%，RSI14={rsi_value:.1f}；动量因子刻画短中期资金流向。",
        }

    technical = _build_technical(gold, ma50, ma200, rsi14, vol20, as_of)
    regime = _build_regime(vol20, vol_pctile, ma50, ma200, gold, as_of)
    performance = _build_performance(gold, as_of)
    correlations = _build_correlations(closes, macro, gold, as_of)
    coverage = _build_coverage(closes, macro, gold_symbol, silver_symbol)

    return GoldSignalContext(
        gold=gold,
        signals=signals,
        momentum=momentum,
        valuation=valuation,
        seasonality=seasonality,
        regime=regime,
        performance=performance,
        technical=technical,
        correlations=correlations,
        coverage=coverage,
        notes=[],
    )


def _unavailable(key: str, weights: dict[str, float], reason: str, as_of: str) -> dict[str, Any]:
    code, name, category = SIGNAL_META[key]
    return factor(
        code=code,
        name=name,
        category="price",
        category_label=category,
        weight=weights.get(key, 0.0),
        direction=1,
        score=0.0,
        available=False,
        note=reason,
        explain=reason,
        as_of=as_of,
        kind="signal",
    )


def unavailable_signals(reason: str, spec=None) -> list[dict[str, Any]]:
    """Return all configured signals in the unavailable state (degrades cleanly)."""
    weights = _weights(spec)
    return [_unavailable(key, weights, reason, "") for key in SIGNAL_META]


def _build_seasonality(gold: pd.Series, as_of: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    monthly = gold.resample("ME").last().dropna()
    if len(monthly) < 120:
        return None, None
    rets = monthly.pct_change().dropna() * 100.0
    frame = pd.DataFrame({"ret": rets})
    frame["month"] = frame.index.month
    stats = frame.groupby("month")["ret"].agg(["mean", "count", lambda series: (series > 0).mean()])
    stats.columns = ["avg_return", "count", "win_rate"]
    months = [int(item) for item in stats.index]
    avg = [_safe_float(item, 3) for item in stats["avg_return"]]
    win = [_safe_float(item, 4) for item in stats["win_rate"]]
    counts = [int(item) for item in stats["count"]]
    current_month = int(as_of[5:7])
    idx = months.index(current_month) if current_month in months else None
    block = {
        "ok": True,
        "months": months,
        "avg_return": avg,
        "win_rate": win,
        "count": counts,
        "current_month": current_month,
        "source": "gold_monthly",
        "sample_years": len(monthly) // 12,
    }
    if idx is None or avg[idx] is None or win[idx] is None:
        return block, None
    score = 0.6 * clip(avg[idx] / 1.5) + 0.4 * clip((win[idx] - 0.5) * 4.0)
    block["current_avg_return"] = avg[idx]
    block["current_win_rate"] = win[idx]
    return block, {
        "score": score,
        "avg_return": avg[idx],
        "win_rate": win[idx],
        "detail": (
            f"历史 {current_month} 月平均收益 {avg[idx]:+.2f}%、胜率 {win[idx] * 100:.0f}%"
            f"（样本 {len(monthly) // 12} 年）；季节性是弱信号，仅作辅助参考。"
        ),
    }


def _build_technical(
    gold: pd.Series,
    ma50: pd.Series,
    ma200: pd.Series,
    rsi14: pd.Series,
    vol20: pd.Series,
    as_of: str,
) -> dict[str, Any]:
    ma20 = sma(gold, 20)
    close = float(gold.iloc[-1])
    mid = ma20.iloc[-1] if len(ma20) else np.nan
    std = gold.rolling(20, min_periods=20).std().iloc[-1] if len(gold) >= 20 else np.nan
    upper = mid + 2 * std if not math.isnan(mid) and not math.isnan(std) else None
    lower = mid - 2 * std if not math.isnan(mid) and not math.isnan(std) else None
    pct_b = (close - lower) / (upper - lower) * 100 if upper and lower and upper != lower else None
    return {
        "as_of": as_of,
        "price": _safe_float(close, 3),
        "ma20": _safe_float(ma20.iloc[-1], 3) if len(ma20) else None,
        "ma50": _safe_float(ma50.iloc[-1], 3) if len(ma50) else None,
        "ma200": _safe_float(ma200.iloc[-1], 3) if len(ma200) else None,
        "rsi14": _safe_float(rsi14.iloc[-1], 2) if len(rsi14) else None,
        "boll_mid": _safe_float(mid, 3),
        "boll_upper": _safe_float(upper, 3),
        "boll_lower": _safe_float(lower, 3),
        "boll_pct_b": _safe_float(pct_b, 2),
        "vol_20d": _safe_float(vol20.iloc[-1], 2) if len(vol20) else None,
    }


def _build_regime(
    vol20: pd.Series,
    vol_pctile: float | None,
    ma50: pd.Series,
    ma200: pd.Series,
    gold: pd.Series,
    as_of: str,
) -> dict[str, Any]:
    price = float(gold.iloc[-1])
    ma_50 = float(ma50.iloc[-1]) if len(ma50) and not math.isnan(ma50.iloc[-1]) else None
    ma_200 = float(ma200.iloc[-1]) if len(ma200) and not math.isnan(ma200.iloc[-1]) else None
    vol = float(vol20.iloc[-1]) if len(vol20) and not math.isnan(vol20.iloc[-1]) else None
    return {
        "as_of": as_of,
        "vol_20d": _safe_float(vol, 2),
        "vol_pctile": _safe_float(vol_pctile, 1),
        "vol_state": None if vol is None else ("高波动" if vol > 20.0 else "低波动"),
        "trend_state": (
            None
            if ma_50 is None or ma_200 is None
            else ("向上" if ma_50 >= ma_200 else "向下")
        ),
        "ma50": _safe_float(ma_50, 3),
        "ma200": _safe_float(ma_200, 3),
        "price_vs_ma200_pct": _safe_float((price / ma_200 - 1) * 100, 2) if ma_200 else None,
    }


def _build_performance(gold: pd.Series, as_of: str) -> dict[str, Any]:
    returns = gold.pct_change().dropna()
    close = gold.dropna()
    peak = close.cummax()
    max_dd = float((close / peak - 1.0).min() * 100.0) if len(close) else None
    vol20 = realized_vol(returns, 20)
    vol60 = realized_vol(returns, 60)
    var95 = float(returns.tail(250).quantile(0.05) * 100.0) if len(returns) >= 60 else None
    ann_1y = _ret(close, TRADING_DAYS)
    ann_3y = _annualized(close, 3 * TRADING_DAYS)
    ann_5y = _annualized(close, 5 * TRADING_DAYS)
    sharpe = None
    if len(returns) >= TRADING_DAYS:
        tail = returns.tail(TRADING_DAYS)
        std = float(tail.std(ddof=1))
        if std:
            sharpe = (float(tail.mean()) * TRADING_DAYS - 0.02) / (std * math.sqrt(TRADING_DAYS))
    ytd_base = close[close.index < pd.Timestamp(f"{as_of[:4]}-01-01")]
    ytd = None
    if len(ytd_base) and float(ytd_base.iloc[-1]):
        ytd = (float(close.iloc[-1]) / float(ytd_base.iloc[-1]) - 1.0) * 100.0
    return {
        "as_of": as_of,
        "r_1d": _safe_float(_ret(close, 1), 2),
        "r_1w": _safe_float(_ret(close, 5), 2),
        "r_1m": _safe_float(_ret(close, 21), 2),
        "r_3m": _safe_float(_ret(close, 63), 2),
        "r_ytd": _safe_float(ytd, 2),
        "r_1y": _safe_float(ann_1y, 2),
        "r_3y_ann": _safe_float(ann_3y, 2),
        "r_5y_ann": _safe_float(ann_5y, 2),
        "max_drawdown_pct": _safe_float(max_dd, 2),
        "vol_20d": _safe_float(vol20.iloc[-1], 2) if len(vol20) else None,
        "vol_60d": _safe_float(vol60.iloc[-1], 2) if len(vol60) else None,
        "var_95_pct": _safe_float(var95, 2),
        "sharpe_1y": _safe_float(sharpe, 2),
    }


def _annualized(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    base = float(close.iloc[-1 - days])
    if not base:
        return None
    years = days / TRADING_DAYS
    try:
        return ((float(close.iloc[-1]) / base) ** (1.0 / years) - 1.0) * 100.0
    except (ValueError, ZeroDivisionError):
        return None


CORRELATION_SPECS = (
    ("US10Y_REAL", "美债 10Y 实际利率", "rate"),
    ("DXY", "美元指数", "pct"),
    ("SI", "白银", "pct"),
    ("HG", "铜", "pct"),
    ("CL", "WTI 原油", "pct"),
    ("SPX", "标普 500", "pct"),
    ("NDX", "纳斯达克 100", "pct"),
    ("USDCNH", "USDCNH", "pct"),
)


def _build_correlations(
    closes: pd.DataFrame,
    macro: pd.DataFrame,
    gold: pd.Series,
    as_of: str,
) -> list[dict[str, Any]]:
    gold_ret = gold.pct_change()
    rows: list[dict[str, Any]] = []
    for code, label, kind in CORRELATION_SPECS:
        if code in macro.columns:
            source = macro[code].reindex(gold.index).ffill().diff()
        elif code in closes.columns:
            source = closes[code].reindex(gold.index).ffill().pct_change()
        else:
            continue
        pair = pd.DataFrame({"gold": gold_ret, "factor": source}).dropna()
        if len(pair) < 60:
            continue
        corr60 = pair.tail(60)["gold"].corr(pair.tail(60)["factor"])
        corr1y = pair.tail(TRADING_DAYS)["gold"].corr(pair.tail(TRADING_DAYS)["factor"])
        corr3y = pair.tail(3 * TRADING_DAYS)["gold"].corr(pair.tail(3 * TRADING_DAYS)["factor"])
        rows.append(
            {
                "code": code,
                "name": label,
                "kind": kind,
                "corr_60d": _safe_float(corr60, 3),
                "corr_1y": _safe_float(corr1y, 3),
                "corr_3y": _safe_float(corr3y, 3),
                "n": int(len(pair)),
                "as_of": as_of,
            }
        )
    return rows


def _build_coverage(
    closes: pd.DataFrame,
    macro: pd.DataFrame,
    gold_symbol: str,
    silver_symbol: str,
) -> list[dict[str, Any]]:
    codes = [
        (gold_symbol, closes, "黄金"),
        (silver_symbol, closes, "白银"),
        ("DXY", closes, "美元指数"),
        ("SPX", closes, "标普 500"),
        ("NDX", closes, "纳斯达克 100"),
        ("CL", closes, "WTI 原油"),
        ("HG", closes, "铜"),
        ("USDCNH", closes, "USDCNH"),
        ("US10Y_REAL", macro, "美债 10Y 实际利率"),
        ("US10Y_BE", macro, "10 年盈亏平衡通胀"),
    ]
    rows: list[dict[str, Any]] = []
    for code, frame, label in codes:
        if not code or code not in frame.columns:
            rows.append({"code": code, "name": label, "count": 0, "ok": False, "note": "序列缺失"})
            continue
        series = frame[code].dropna()
        rows.append(
            {
                "code": code,
                "name": label,
                "count": int(len(series)),
                "start": series.index[0].date().isoformat() if len(series) else None,
                "end": series.index[-1].date().isoformat() if len(series) else None,
                "ok": len(series) >= 60,
                "note": "" if len(series) >= 60 else "样本不足",
            }
        )
    return rows
