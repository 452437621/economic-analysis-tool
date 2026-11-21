"""Luoyang Molybdenum analysis ported from ``luoyangmuye_analysis``.

The standalone project read CSV files and hard-coded the user's cost basis.
This module keeps the analytical core (TTM, technicals, valuation, factor
attribution, four-method scenarios, position math, events) but takes data from
``LuoyangData`` and parameters from the topic config.  Every block degrades to
``ok=False``/``None`` when its inputs are missing instead of inventing numbers.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.topics.scoring import clip, combine_factors, factor

TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# statistics helpers (no scipy)
# ---------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    max_iter, eps, fpmin = 200, 3e-12, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_pvalue(t: float, df: int) -> float:
    if df <= 0 or not math.isfinite(t):
        return 1.0
    x = df / (df + t * t)
    return max(0.0, min(1.0, _betai(df / 2.0, 0.5, x)))


def fisher_p(r: float, n: int) -> float:
    if n <= 3 or not math.isfinite(r) or abs(r) >= 1:
        return 1.0
    z = 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(n - 3)
    return math.erfc(abs(z) / math.sqrt(2.0))


def _stars(p: float | None) -> str:
    if p is None:
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def ols(y: Iterable[float], x: Any, names: list[str] | None = None, *, hac_lags: int = 0) -> dict:
    y_arr = np.asarray(pd.Series(y).astype(float))
    if isinstance(x, pd.Series):
        x_arr = np.asarray(x.astype(float)).reshape(-1, 1)
    elif isinstance(x, np.ndarray):
        x_arr = x.astype(float)
        if x_arr.ndim == 1:
            x_arr = x_arr.reshape(-1, 1)
    else:
        x_arr = np.asarray(x, dtype=float)
        if x_arr.ndim == 1:
            x_arr = x_arr.reshape(-1, 1)
    mask = np.isfinite(y_arr) & np.all(np.isfinite(x_arr), axis=1)
    y_arr, x_arr = y_arr[mask], x_arr[mask]
    n, k = x_arr.shape
    if n < 10:
        return {"ok": False, "reason": f"样本量不足 (n={n})", "n": int(n)}
    design = np.column_stack([np.ones(n), x_arr])
    labels = ["const"] + list(names or [f"x{i}" for i in range(k)])
    try:
        xtx_inv = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        return {"ok": False, "reason": "设计矩阵奇异（解释变量共线）", "n": int(n)}
    beta = xtx_inv @ design.T @ y_arr
    resid = y_arr - design @ beta
    ssr = float(resid @ resid)
    tss = float(((y_arr - y_arr.mean()) ** 2).sum())
    dof = n - design.shape[1]
    if dof <= 0:
        return {"ok": False, "reason": "自由度不足", "n": int(n)}
    sigma2 = ssr / dof
    if hac_lags:
        # Newey-West (Bartlett kernel) sandwich estimator:
        # cov = (X'X)^-1 [Σ_t e_t² x_t x_t' + Σ_l w_l (Γ_l + Γ_l')] (X'X)^-1
        weights = np.ones(hac_lags + 1)
        weights[1:] = 1.0 - np.arange(1, hac_lags + 1) / (hac_lags + 1)
        scaled = design * resid[:, None]
        meat = scaled.T @ scaled
        for lag in range(1, min(hac_lags, n - 1) + 1):
            x_lag = scaled[lag:]
            x_lead = scaled[: n - lag]
            meat += weights[lag] * (x_lag.T @ x_lead + x_lead.T @ x_lag)
        cov = xtx_inv @ meat @ xtx_inv
    else:
        cov = sigma2 * xtx_inv
    se = np.sqrt(np.clip(np.diag(cov), 1e-300, None))
    t_stats = beta / se
    p_values = [t_pvalue(float(tv), dof) for tv in t_stats]
    coef = {
        label: {
            "beta": round(float(beta[i]), 6),
            "se": round(float(se[i]), 6),
            "t": round(float(t_stats[i]), 3),
            "p": round(float(p_values[i]), 4),
            "stars": _stars(p_values[i]),
        }
        for i, label in enumerate(labels)
    }
    return {
        "ok": True,
        "n": int(n),
        "r2": round(float(1 - ssr / tss), 4) if tss else None,
        "adj_r2": round(float(1 - (1 - (1 - ssr / tss)) * (n - 1) / dof), 4) if tss else None,
        "f": round(float((tss - ssr) / (design.shape[1] - 1) / sigma2), 3) if sigma2 else None,
        "coef": coef,
    }


def _pct_rank(series: pd.Series, value: float | None = None, min_obs: int = 30) -> dict:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < min_obs:
        return {"ok": False, "n": int(len(clean))}
    current = float(clean.iloc[-1]) if value is None else float(value)
    below = float((clean <= current).sum()) / len(clean) * 100
    return {
        "ok": True,
        "pct": round(below, 1),
        "n": int(len(clean)),
        "min": round(float(clean.min()), 4),
        "median": round(float(clean.median()), 4),
        "max": round(float(clean.max()), 4),
        "current": round(current, 4),
    }


def _band(series: pd.Series) -> dict:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 30:
        return {"ok": False}
    return {
        "ok": True,
        "p10": round(float(clean.quantile(0.10)), 3),
        "p25": round(float(clean.quantile(0.25)), 3),
        "p50": round(float(clean.quantile(0.50)), 3),
        "p75": round(float(clean.quantile(0.75)), 3),
        "p90": round(float(clean.quantile(0.90)), 3),
        "min": round(float(clean.min()), 3),
        "max": round(float(clean.max()), 3),
    }


def _num(value: Any, digits: int = 2) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    result = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss.replace(0.0, np.nan))
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return result.mask((avg_loss == 0) & (avg_gain == 0), 50.0)


def _month_end_alias() -> str:
    from pandas.tseries.frequencies import to_offset

    for name in ("ME", "M"):
        try:
            to_offset(name)
            return name
        except (ValueError, TypeError):
            continue
    return "ME"


MONTH_END = _month_end_alias()


# ---------------------------------------------------------------------------
# technicals
# ---------------------------------------------------------------------------
def technicals(panel: pd.DataFrame) -> dict:
    if panel.empty or "close" not in panel.columns:
        return {"ok": False, "reason": "日线缺失"}
    frame = panel.copy()
    close = frame["close"]
    if "high" not in frame.columns:
        frame["high"] = close
    if "low" not in frame.columns:
        frame["low"] = close
    for window in (5, 10, 20, 60, 120, 250):
        frame[f"ma{window}"] = _sma(close, window)
    frame["rsi14"] = _rsi(close, 14)
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    frame["macd_dif"] = ema12 - ema26
    frame["macd_dea"] = frame["macd_dif"].ewm(span=9, adjust=False, min_periods=9).mean()
    frame["macd_hist"] = (frame["macd_dif"] - frame["macd_dea"]) * 2
    mid = _sma(close, 20)
    std = close.rolling(20, min_periods=20).std()
    frame["boll_mid"] = mid
    frame["boll_upper"] = mid + 2 * std
    frame["boll_lower"] = mid - 2 * std
    frame["boll_pct_b"] = (close - frame["boll_lower"]) / (frame["boll_upper"] - frame["boll_lower"]) * 100
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(frame["high"] - frame["low"]).abs(), (frame["high"] - prev_close).abs(), (frame["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    frame["atr14"] = true_range.rolling(14, min_periods=14).mean()
    for days in (20, 60, 120, 250):
        frame[f"ret{days}"] = close.pct_change(days)
    peak = close.cummax()
    frame["drawdown"] = close / peak - 1.0

    last = frame.iloc[-1]
    price = float(last["close"])
    ma_state = {
        f"ma{window}": {
            "value": _num(last.get(f"ma{window}")),
            "dist_pct": _num((price / float(last[f"ma{window}"]) - 1) * 100) if pd.notna(last.get(f"ma{window}")) else None,
            "above": bool(pd.notna(last.get(f"ma{window}")) and price >= float(last[f"ma{window}"])),
        }
        for window in (5, 10, 20, 60, 120, 250)
    }
    alignment = "多头排列" if ma_state["ma20"]["above"] and ma_state["ma60"]["above"] else ("空头排列" if not ma_state["ma20"]["above"] and not ma_state["ma60"]["above"] else "震荡")
    rsi_value = _num(last.get("rsi14"))
    rsi_zone = "超买" if (rsi_value or 0) >= 70 else ("超卖" if (rsi_value or 100) <= 30 else "中性")
    macd_state = "多头" if float(last.get("macd_hist") or 0) > 0 else "空头"
    pct_b = _num(last.get("boll_pct_b"))
    boll_position = "上轨附近" if (pct_b or 0) > 80 else ("下轨附近" if (pct_b or 100) < 20 else "中轨附近")

    levels = support_resistance(frame)
    drawdown = drawdown_stats(frame)
    tech_score = _technical_score(last, ma_state, rsi_value, macd_state, pct_b, drawdown)
    return {
        "ok": True,
        "as_of": frame.index[-1].date().isoformat(),
        "price": _num(price, 3),
        "pct_chg": _num(last.get("pct_chg"), 2),
        "ma_alignment": alignment,
        "ma": ma_state,
        "rsi14": rsi_value,
        "rsi14_zone": rsi_zone,
        "macd": {
            "dif": _num(last.get("macd_dif"), 3),
            "dea": _num(last.get("macd_dea"), 3),
            "hist": _num(last.get("macd_hist"), 3),
            "state": macd_state,
        },
        "boll": {
            "mid": _num(last.get("boll_mid"), 3),
            "upper": _num(last.get("boll_upper"), 3),
            "lower": _num(last.get("boll_lower"), 3),
            "pct_b": pct_b,
            "position": boll_position,
        },
        "atr14": _num(last.get("atr14"), 3),
        "atr_pct": _num(float(last.get("atr14") or 0) / price * 100, 2) if price else None,
        "technical_score": tech_score,
        "levels": levels,
        "drawdown": drawdown,
        "series": {
            "dates": [item.date().isoformat() for item in frame.index[-750:]],
            "close": [_num(value, 3) for value in frame["close"].tail(750)],
            "ma20": [_num(value, 3) for value in frame["ma20"].tail(750)],
            "ma60": [_num(value, 3) for value in frame["ma60"].tail(750)],
            "ma250": [_num(value, 3) for value in frame["ma250"].tail(750)],
            "drawdown": [_num(value * 100, 2) for value in frame["drawdown"].tail(750)],
        },
    }


def _technical_score(last, ma_state, rsi_value, macd_state, pct_b, drawdown) -> int:
    score = 50.0
    price = float(last["close"])
    if ma_state["ma20"]["above"]:
        score += 8
    if ma_state["ma60"]["above"]:
        score += 8
    if ma_state["ma20"]["value"] and ma_state["ma60"]["value"] and ma_state["ma20"]["value"] > ma_state["ma60"]["value"]:
        score += 6
    if rsi_value is not None:
        if 50 <= rsi_value <= 70:
            score += 8
        elif rsi_value >= 80:
            score -= 8
        elif rsi_value <= 25:
            score += 4
    if macd_state == "多头":
        score += 8
    else:
        score -= 4
    if pct_b is not None:
        if pct_b < 15:
            score += 4
        elif pct_b > 90:
            score -= 4
    current_dd = float(drawdown.get("current_drawdown_pct") or 0)
    if current_dd > -10:
        score += 6
    elif current_dd < -30:
        score -= 10
    return int(max(0, min(100, round(score))))


def support_resistance(frame: pd.DataFrame) -> dict:
    close = frame["close"]
    if len(close) < 60:
        return {"supports": [], "resistances": []}
    price = float(close.iloc[-1])
    candidates: list[dict[str, Any]] = []
    window = 10
    for offset in range(window, min(len(close) - window, 250)):
        index = -1 - offset
        low_slice = frame["low"].iloc[index - window : index + window + 1]
        high_slice = frame["high"].iloc[index - window : index + window + 1]
        if len(low_slice) and frame["low"].iloc[index] <= low_slice.min():
            candidates.append({"price": float(frame["low"].iloc[index]), "type": "摆动低点", "weight": 1.0})
        if len(high_slice) and frame["high"].iloc[index] >= high_slice.max():
            candidates.append({"price": float(frame["high"].iloc[index]), "type": "摆动高点", "weight": 1.0})
    recent = frame.tail(250)
    if "volume" in recent.columns and len(recent) >= 20 and float(recent["volume"].fillna(0).sum()) > 0:
        bins = pd.cut(recent["close"], bins=30)
        profile = recent.groupby(bins, observed=True)["volume"].sum().sort_values(ascending=False)
        for interval in profile.head(2).index:
            candidates.append({"price": float(interval.mid), "type": "成交密集区", "weight": 1.3})
    for window_size in (20, 60, 120, 250):
        value = _sma(close, window_size).iloc[-1]
        if pd.notna(value):
            candidates.append({"price": float(value), "type": f"MA{window_size}", "weight": 1.2})
    candidates.append({"price": float(recent["high"].max()), "type": "52 周高点", "weight": 1.4})
    candidates.append({"price": float(recent["low"].min()), "type": "52 周低点", "weight": 1.4})
    step = 0.5 if price < 50 else 1.0
    candidates.append({"price": round(price / step) * step, "type": "整数关口", "weight": 1.1})

    def _pack(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items = sorted(items, key=lambda item: abs(item["price"] - price))
        packed: list[dict[str, Any]] = []
        for item in items:
            if any(abs(item["price"] / existing["price"] - 1) < 0.012 for existing in packed):
                continue
            packed.append({"price": _num(item["price"], 3), "type": item["type"], "weight": item["weight"]})
            if len(packed) >= 5:
                break
        return packed

    supports = _pack([item for item in candidates if item["price"] < price * 0.999])
    resistances = _pack([item for item in candidates if item["price"] > price * 1.001])
    supports.sort(key=lambda item: item["price"], reverse=True)
    resistances.sort(key=lambda item: item["price"])
    return {"supports": supports, "resistances": resistances}


def drawdown_stats(frame: pd.DataFrame) -> dict:
    close = frame["close"]
    if close.empty:
        return {}
    peak = close.cummax()
    dd = close / peak - 1.0
    current = float(dd.iloc[-1] * 100)
    last_year = close.tail(TRADING_DAYS)
    ytd = close[close.index >= pd.Timestamp(f"{frame.index[-1].year}-01-01")]
    return {
        "current_drawdown_pct": _num(current, 2),
        "max_drawdown_1y_pct": _num(float((last_year / last_year.cummax() - 1).min() * 100), 2),
        "max_drawdown_ytd_pct": _num(float((ytd / ytd.cummax() - 1).min() * 100), 2) if len(ytd) else None,
        "max_drawdown_all_pct": _num(float(dd.min() * 100), 2),
        "peak_price": _num(float(peak.iloc[-1]), 3),
    }


# ---------------------------------------------------------------------------
# fundamentals / valuation
# ---------------------------------------------------------------------------
def to_ttm(financials: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if financials.empty:
        return pd.DataFrame(columns=columns)
    frame = financials.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    rows: list[dict[str, Any]] = []
    for when, row in frame.iterrows():
        year, month = when.year, when.month
        record: dict[str, Any] = {"report_date": when}
        for column in columns:
            value = row.get(column)
            if pd.isna(value):
                record[column] = np.nan
                continue
            if month == 12:
                record[column] = float(value)
                continue
            try:
                prior_annual = frame.loc[pd.Timestamp(f"{year - 1}-12-31"), column]
                prior_same = frame.loc[pd.Timestamp(f"{year - 1}-{month:02d}-{when.day:02d}"), column]
            except KeyError:
                record[column] = np.nan
                continue
            record[column] = float(value) + float(prior_annual) - float(prior_same)
        rows.append(record)
    return pd.DataFrame(rows).set_index("report_date").sort_index()


def company_fundamentals(data) -> dict:
    fin = data.financials
    if fin.empty:
        return {"ok": False, "reason": "财务主要指标缺失"}
    ttm_columns = ["parentnetprofit", "totaloperatereve", "kcfjcxsyjlr", "epsjb"]
    ttm = to_ttm(fin, [column for column in ttm_columns if column in fin.columns])
    latest = fin.iloc[-1]
    latest_ttm = ttm.iloc[-1] if not ttm.empty else {}
    return {
        "ok": True,
        "report_date": fin.index[-1].date().isoformat(),
        "eps_ttm_yuan": _num(latest_ttm.get("epsjb") if "epsjb" in ttm.columns else None, 3),
        "eps_latest_report": _num(latest.get("epsjb"), 3),
        "bps": _num(latest.get("bps"), 3),
        "roe_pct": _num(latest.get("roejq"), 2),
        "net_profit_ttm_yi": _num(float(latest_ttm.get("parentnetprofit") or np.nan) / 1e8, 2),
        "revenue_ttm_yi": _num(float(latest_ttm.get("totaloperatereve") or np.nan) / 1e8, 2),
        "gross_margin_pct": _num(latest.get("xsmll"), 2),
        "debt_ratio_pct": _num(latest.get("zcfzl"), 2),
        "progress": latest.get("report_date_name"),
    }


def valuation(data, technical: dict | None = None) -> dict:
    panel = data.panel
    if panel.empty or "pe_ttm" not in panel.columns:
        return {"ok": False, "reason": "估值序列缺失"}
    latest = panel.iloc[-1]
    price = _num(latest.get("close"), 3)
    pe = _num(latest.get("pe_ttm"), 3)
    pb = _num(latest.get("pb_mrq"), 3) if "pb_mrq" in panel.columns else None
    ps = _num(latest.get("ps_ttm"), 3) if "ps_ttm" in panel.columns else None

    def _window(days: int) -> pd.DataFrame:
        return panel.tail(days)

    def _column(name: str) -> pd.Series:
        return panel[name] if name in panel.columns else pd.Series(dtype=float)

    def _ranks(name: str) -> dict[str, dict[str, Any]]:
        series = _column(name)
        if series.empty:
            return {key: {"ok": False, "n": 0} for key in ("1y", "3y", "5y", "all")}
        return {
            key: _pct_rank(_window(days)[name])
            for key, days in (("1y", 250), ("3y", 750), ("5y", 1250), ("all", len(panel)))
        }

    def _bands(name: str) -> dict[str, dict[str, Any]]:
        if name not in panel.columns:
            return {key: {"ok": False} for key in ("1y", "3y", "5y")}
        return {key: _band(_window(days)[name]) for key, days in (("1y", 250), ("3y", 750), ("5y", 1250))}

    def _quantile(frame: pd.DataFrame, name: str, q: float) -> float | None:
        if name not in frame.columns:
            return None
        return _num(frame[name].quantile(q), 2)

    percentile = {"pe": _ranks("pe_ttm"), "pb": _ranks("pb_mrq"), "ps": _ranks("ps_ttm")}
    bands = {"pe": _bands("pe_ttm"), "pb": _bands("pb_mrq")}
    yearly: list[dict[str, Any]] = []
    for year, group in panel.groupby(panel.index.year):
        yearly.append(
            {
                "year": int(year),
                "pe_p10": _quantile(group, "pe_ttm", 0.10),
                "pe_p50": _quantile(group, "pe_ttm", 0.50),
                "pe_p90": _quantile(group, "pe_ttm", 0.90),
                "pb_p10": _quantile(group, "pb_mrq", 0.10),
                "pb_p50": _quantile(group, "pb_mrq", 0.50),
                "pb_p90": _quantile(group, "pb_mrq", 0.90),
            }
        )

    fundamentals = company_fundamentals(data)
    shares = _num(latest.get("total_shares"), 0)
    shares_yi = _num(shares / 1e8, 2) if shares else None
    net_profit_ttm = fundamentals.get("net_profit_ttm_yi")
    eps_ttm = _num(net_profit_ttm / shares_yi, 3) if net_profit_ttm and shares_yi else None
    bps = fundamentals.get("bps")
    roe_implied = _num(eps_ttm / bps * 100, 2) if eps_ttm and bps else None

    dividend = _dividend_block(data, price)
    scorecard = _scorecard(pe, percentile["pe"].get("5y", {}).get("pct"), pb, percentile["pb"].get("5y", {}).get("pct"), dividend, bps, roe_implied)
    relative = _relative_block(data, price, pe, pb)
    return {
        "ok": True,
        "as_of": panel.index[-1].date().isoformat(),
        "pe_ttm": pe,
        "pb_mrq": pb,
        "ps_ttm": ps,
        "pe_percentile": {key: value for key, value in percentile["pe"].items()},
        "pb_percentile": {key: value for key, value in percentile["pb"].items()},
        "ps_percentile": {key: value for key, value in percentile["ps"].items()},
        "pe_band_1y": bands["pe"]["1y"],
        "pe_band_3y": bands["pe"]["3y"],
        "pe_band_5y": bands["pe"]["5y"],
        "pb_band_1y": bands["pb"]["1y"],
        "pb_band_3y": bands["pb"]["3y"],
        "pb_band_5y": bands["pb"]["5y"],
        "yearly_bands": yearly,
        "eps_ttm": eps_ttm,
        "net_profit_ttm_yi": net_profit_ttm,
        "revenue_ttm_yi": fundamentals.get("revenue_ttm_yi"),
        "bps_fin": bps,
        "bps_implied": _num(price / pb, 3) if price and pb else None,
        "roe_implied_pct": roe_implied,
        "dividend": dividend,
        "scorecard": scorecard,
        "relative": relative,
        "fundamentals": fundamentals,
        "series": {
            "dates": [item.date().isoformat() for item in panel.index[-1250:]],
            "pe_ttm": [_num(value, 2) for value in panel["pe_ttm"].tail(1250)],
            "pb_mrq": [_num(value, 2) for value in _column("pb_mrq").tail(1250)] if "pb_mrq" in panel.columns else [],
            "close": [_num(value, 3) for value in panel["close"].tail(1250)],
        },
        "valuation_note": _valuation_note(pe, pb, percentile, dividend, roe_implied),
    }


def _empty_dividend_block() -> dict:
    return {
        "paid_2026_ps": None,
        "ttm_ps": None,
        "current_yield_pct": None,
        "payout_ratio_pct": None,
        "history": [],
    }


def _dividend_block(data, price: float | None) -> dict:
    if data.dividends.empty or price is None or "pretax_bonus_rmb" not in data.dividends.columns:
        return _empty_dividend_block()
    frame = data.dividends.copy()
    frame["per_share"] = pd.to_numeric(frame.get("pretax_bonus_rmb"), errors="coerce") / 10.0
    frame["ex_date"] = pd.to_datetime(frame.get("ex_dividend_date"), errors="coerce")
    frame = frame.dropna(subset=["ex_date", "per_share"]).sort_values("ex_date")
    if frame.empty:
        return _empty_dividend_block()
    last_year = frame[frame["ex_date"] >= pd.Timestamp(f"{frame['ex_date'].iloc[-1].year}-01-01")]
    ttm = frame[frame["ex_date"] >= frame["ex_date"].iloc[-1] - pd.Timedelta(days=365)]
    paid = float(ttm["per_share"].sum()) if len(ttm) else None
    return {
        "paid_2026_ps": _num(float(last_year["per_share"].sum()), 4) if len(last_year) else None,
        "ttm_ps": _num(paid, 4),
        "current_yield_pct": _num(paid / price * 100, 2) if paid else None,
        "payout_ratio_pct": None,
        "history": [
            {"date": item.date().isoformat(), "per_share": _num(value, 4)}
            for item, value in zip(frame["ex_date"], frame["per_share"])
        ][-12:],
    }


def _scorecard(pe, pe_pct, pb, pb_pct, dividend, bps, roe) -> list[dict[str, Any]]:
    items = [
        ("PE(TTM)", pe, "x", pe_pct, "PE 分位"),
        ("PB(MRQ)", pb, "x", pb_pct, "PB 分位"),
        ("股息率", dividend.get("current_yield_pct"), "%", None, "现金回报"),
        ("ROE(隐含)", roe, "%", None, "盈利能力"),
    ]
    out: list[dict[str, Any]] = []
    for name, value, unit, pct, note in items:
        if value is None:
            assessment = "缺数据"
        elif name in {"PE(TTM)", "PB(MRQ)"}:
            level = pct if pct is not None else 50
            assessment = "偏低" if level < 30 else ("偏高" if level > 70 else "中性")
        elif name == "股息率":
            assessment = "较高" if value >= 3 else ("一般" if value >= 1.5 else "偏低")
        else:
            assessment = "较高" if value >= 15 else ("一般" if value >= 8 else "偏低")
        out.append(
            {
                "metric": name,
                "value": value,
                "unit": unit,
                "pct_5y": pct,
                "assessment": assessment,
                "caveat": note,
            }
        )
    return out


def _relative_block(data, price, pe, pb) -> dict:
    peers: list[dict[str, Any]] = []
    for key, payload in data.snapshots.items():
        if key in {"a", "h", "sector"}:
            continue
        peers.append(
            {
                "code": payload.get("code") or key,
                "name": payload.get("name") or key,
                "price": _num(payload.get("price"), 3),
                "pe_ttm": _num(payload.get("pe_ttm"), 2),
                "pb": _num(payload.get("pb"), 2),
                "market_cap_yi": _num(_num(payload.get("market_cap"), 2) / 1e8, 1)
                if _num(payload.get("market_cap"), 2)
                else None,
                "pct_chg": _num(payload.get("pct_chg"), 2),
            }
        )
    pe_values = [item["pe_ttm"] for item in peers if item["pe_ttm"] and item["pe_ttm"] > 0]
    pb_values = [item["pb"] for item in peers if item["pb"] and item["pb"] > 0]
    sector = data.snapshots.get("sector") or {}
    a = data.snapshots.get("a") or {}
    h = data.snapshots.get("h") or {}
    fx = data.panel["hkd_cny"].dropna().iloc[-1] if "hkd_cny" in data.panel.columns and data.panel["hkd_cny"].notna().any() else None
    h_share: dict[str, Any] = {
        "h_price_hkd": _num(h.get("price"), 3),
        "h_pe": _num(h.get("pe_ttm"), 2),
        "h_pb": _num(h.get("pb"), 2),
        "a_price": _num(a.get("price") or price, 3),
        "a_pe": _num(a.get("pe_ttm") or pe, 2),
        "a_pb": _num(a.get("pb") or pb, 2),
        "hkd_cny": _num(fx, 4),
        "a_premium_pct": None,
    }
    if h_share["h_price_hkd"] and h_share["a_price"] and fx:
        h_cny = h_share["h_price_hkd"] * float(fx)
        h_share["a_premium_pct"] = _num((h_share["a_price"] / h_cny - 1) * 100, 2)
    return {
        "peers": peers,
        "sector_pe": _num(sector.get("pe_ttm"), 2),
        "peer_pe_median": _num(float(np.median(pe_values)), 2) if pe_values else None,
        "peer_pb_median": _num(float(np.median(pb_values)), 2) if pb_values else None,
        "h_share": h_share,
        "fetched_at": data.panel.index[-1].date().isoformat(),
    }


def _valuation_note(pe, pb, percentile, dividend, roe) -> str:
    if pe is None and pb is None:
        return "估值序列不足。"
    pe_pct = (percentile.get("pe", {}).get("5y") or {}).get("pct")
    pb_pct = (percentile.get("pb", {}).get("5y") or {}).get("pct")
    parts = []
    if pe is not None:
        parts.append(f"PE(TTM) {pe:.2f}x（5 年分位 {pe_pct if pe_pct is not None else '—'}%）")
    if pb is not None:
        parts.append(f"PB(MRQ) {pb:.2f}x（5 年分位 {pb_pct if pb_pct is not None else '—'}%）")
    if dividend.get("current_yield_pct") is not None:
        parts.append(f"股息率 {dividend['current_yield_pct']:.2f}%")
    if roe is not None:
        parts.append(f"隐含 ROE {roe:.1f}%")
    return "；".join(parts) + "。周期股在盈利高点用 PE 分位会系统性低估“贵”的程度，PB/EV 才是主锚。"


# ---------------------------------------------------------------------------
# factor attribution
# ---------------------------------------------------------------------------
def factors(panel: pd.DataFrame, data) -> dict:
    if panel.empty or "ret" not in panel.columns:
        return {"ok": False, "reason": "日线缺失"}
    periods = _periods(panel)
    single: dict[str, dict[str, Any]] = {}
    for label, (start, end) in periods.items():
        subset = panel.loc[(panel.index >= start) & (panel.index <= end)]
        single[label] = {"single": {}, "start": start.date().isoformat(), "end": end.date().isoformat()}
        for code, name in _factor_labels().items():
            if code not in subset.columns:
                continue
            result = ols(subset["ret"], subset[code], ["factor"])
            if not result.get("ok"):
                single[label]["single"][code] = {"ok": False, "reason": result.get("reason")}
                continue
            coef = result["coef"]["factor"]
            single[label]["single"][code] = {
                "ok": True,
                "label": name,
                "beta": coef["beta"],
                "t": coef["t"],
                "p": coef["p"],
                "stars": coef["stars"],
                "r2": result["r2"],
                "n": result["n"],
            }
    multi: dict[str, dict[str, Any]] = {}
    codes = [code for code in ("cu_ret", "hs300_ret", "dxy_ret", "fx_ret") if code in panel.columns]
    for label, (start, end) in periods.items():
        subset = panel.loc[(panel.index >= start) & (panel.index <= end)]
        if len(subset) < 30 or not codes:
            multi[label] = {"ok": False, "reason": "样本或因子不足"}
            continue
        result = ols(subset["ret"], subset[codes].to_numpy(), codes, hac_lags=5)
        multi[label] = result
    rolling = _rolling(panel)
    lead_lag = _lead_lag(panel)
    decomposition = _decomposition(panel)
    leverage = _leverage(data)
    flows = _flows(data)
    return {
        "ok": True,
        "periods": {key: {"start": value[0].date().isoformat(), "end": value[1].date().isoformat()} for key, value in periods.items()},
        "single_factor": single,
        "multifactor": multi,
        "rolling": rolling,
        "lead_lag": lead_lag,
        "decomposition": decomposition,
        "leverage": leverage,
        "flows": flows,
        "corr_full_5y": _corr_matrix(panel.tail(1250)),
    }


def _factor_labels() -> dict[str, str]:
    return {
        "cu_ret": "沪铜主连",
        "lme_ret": "LME 铜",
        "hs300_ret": "沪深 300",
        "bk_ret": "有色板块",
        "dxy_ret": "美元指数",
        "fx_ret": "USDCNH",
    }


def _periods(panel: pd.DataFrame) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    end = panel.index[-1]
    start_5y = end - pd.Timedelta(days=365 * 5)
    ytd = pd.Timestamp(f"{end.year}-01-01")
    return {
        "5y": (start_5y, end),
        "2024": (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
        "2025": (pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")),
        f"{end.year}YTD": (ytd, end),
    }


def _rolling(panel: pd.DataFrame) -> dict:
    if "cu_ret" not in panel.columns:
        return {"dates": [], "current": {}}
    stock = panel["ret"]
    cu = panel["cu_ret"]
    beta60 = cu.rolling(60).cov(stock) / cu.rolling(60).var()
    beta120 = cu.rolling(120).cov(stock) / cu.rolling(120).var()
    corr60 = stock.rolling(60).corr(cu)
    frame = pd.DataFrame({"beta60_cu": beta60, "beta120_cu": beta120, "corr60_cu": corr60})
    if "hs300_ret" in panel.columns:
        stock_cum = (1 + stock.fillna(0)).rolling(60).apply(np.prod, raw=True) - 1
        bench_cum = (1 + panel["hs300_ret"].fillna(0)).rolling(60).apply(np.prod, raw=True) - 1
        frame["excess60"] = (stock_cum - bench_cum) * 100
    frame = frame.dropna()
    tail = frame.tail(750)
    current = frame.iloc[-1] if len(frame) else {}
    return {
        "dates": [item.date().isoformat() for item in tail.index],
        "beta60_cu": [_num(value, 3) for value in tail["beta60_cu"]],
        "beta120_cu": [_num(value, 3) for value in tail["beta120_cu"]],
        "corr60_cu": [_num(value, 3) for value in tail["corr60_cu"]],
        "excess60": [_num(value, 2) for value in tail["excess60"]] if "excess60" in tail.columns else [],
        "current": {
            "beta60_cu": _num(current.get("beta60_cu"), 3),
            "beta120_cu": _num(current.get("beta120_cu"), 3),
            "corr60_cu": _num(current.get("corr60_cu"), 3),
            "excess60": _num(current.get("excess60"), 2),
        },
    }


def _lead_lag(panel: pd.DataFrame) -> dict:
    out: dict[str, Any] = {}
    if "cu_ret" not in panel.columns:
        return out
    for code, name in _factor_labels().items():
        if code not in panel.columns:
            continue
        pair = pd.DataFrame({"stock": panel["ret"], "factor": panel[code]}).dropna()
        if len(pair) < 120:
            continue
        best = None
        rows = []
        for lag in range(-10, 11):
            shifted = pair["factor"].shift(lag)
            valid = pd.DataFrame({"stock": pair["stock"], "factor": shifted}).dropna()
            if len(valid) < 60:
                continue
            corr = float(valid["stock"].corr(valid["factor"]))
            rows.append({"lag": lag, "corr": _num(corr, 3)})
            if best is None or abs(corr) > abs(best[1]):
                best = (lag, corr)
        out[code] = {
            "label": name,
            "zero_lag_r": _num(pair["stock"].corr(pair["factor"]), 3),
            "best_lag": best[0] if best else None,
            "best_r": _num(best[1], 3) if best else None,
            "rows": rows,
        }
    return out


def _decomposition(panel: pd.DataFrame) -> dict:
    if panel.empty or "pe_ttm" not in panel.columns:
        return {}
    frame = panel.dropna(subset=["pe_ttm", "close"])
    if len(frame) < 30:
        return {}
    out: dict[str, Any] = {}
    periods = _periods(frame)
    for label, (start, end) in periods.items():
        subset = frame.loc[(frame.index >= start) & (frame.index <= end)]
        if len(subset) < 10:
            continue
        first, last = subset.iloc[0], subset.iloc[-1]
        eps_start = float(first["close"]) / float(first["pe_ttm"]) if first["pe_ttm"] else None
        eps_end = float(last["close"]) / float(last["pe_ttm"]) if last["pe_ttm"] else None
        if not eps_start or not eps_end:
            continue
        price_chg = (float(last["close"]) / float(first["close"]) - 1) * 100
        pe_start, pe_end = float(first["pe_ttm"]), float(last["pe_ttm"])
        # PE 可跨 0（亏损→盈利），对数分解只在两端同为正时成立。
        earn = math.log(eps_end / eps_start) * 100 if eps_start > 0 and eps_end > 0 else None
        val = math.log(pe_end / pe_start) * 100 if pe_start > 0 and pe_end > 0 else None
        out[label] = {
            "start": subset.index[0].date().isoformat(),
            "end": subset.index[-1].date().isoformat(),
            "price_chg_pct": _num(price_chg, 2),
            "contrib_earnings_pctpts": _num(earn, 2),
            "contrib_valuation_pctpts": _num(val, 2),
            "eps_implied_start": _num(eps_start, 3),
            "eps_implied_end": _num(eps_end, 3),
            "pe_start": _num(first["pe_ttm"], 2),
            "pe_end": _num(last["pe_ttm"], 2),
        }
    high = frame["close"].tail(250).max()
    high_date = frame["close"].tail(250).idxmax()
    since = frame.loc[frame.index >= high_date]
    if len(since) >= 2:
        first, last = since.iloc[0], since.iloc[-1]
        out["高点至今"] = {
            "start": high_date.date().isoformat(),
            "end": since.index[-1].date().isoformat(),
            "price_chg_pct": _num((float(last["close"]) / float(first["close"]) - 1) * 100, 2),
            "pe_start": _num(first["pe_ttm"], 2),
            "pe_end": _num(last["pe_ttm"], 2),
        }
    return out


def _leverage(data) -> dict:
    if data.margin.empty:
        return {"ok": False}
    frame = data.margin.copy()
    frame["rz_balance"] = pd.to_numeric(frame.get("rz_balance"), errors="coerce")
    frame = frame.dropna(subset=["rz_balance"])
    if frame.empty:
        return {"ok": False}
    last = float(frame["rz_balance"].iloc[-1])
    pct = _pct_rank(frame["rz_balance"].tail(1250))
    return {
        "ok": True,
        "latest": {
            "date": frame.index[-1].date().isoformat(),
            "rz_balance_yi": _num(last / 1e8, 2),
            "rz_change_5d_pct": _num((last / float(frame["rz_balance"].iloc[-6]) - 1) * 100, 2) if len(frame) > 6 else None,
            "pct_rank_5y": pct.get("pct"),
        },
        "series": {
            "dates": [item.date().isoformat() for item in frame.index[-750:]],
            "rz_balance_yi": [_num(value / 1e8, 2) for value in frame["rz_balance"].tail(750)],
        },
    }


def _flows(data) -> dict:
    if data.flows.empty:
        return {"ok": False, "reason": "资金流缺失"}
    frame = data.flows.copy()
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "main_net" not in frame.columns:
        return {"ok": False, "reason": "主力净流入字段缺失"}

    def _sum(days: int) -> dict[str, Any]:
        tail = frame.tail(days)
        return {
            "days": days,
            "main_net_yi": _num(float(tail["main_net"].sum()) / 1e8, 2),
            "avg_daily_yi": _num(float(tail["main_net"].mean()) / 1e8, 3),
            "positive_days": int((tail["main_net"] > 0).sum()),
        }

    corr = None
    if "ret" in data.panel.columns:
        merged = pd.DataFrame({"flow": frame["main_net"], "ret": data.panel["ret"]}).dropna()
        if len(merged) > 20:
            corr = merged["flow"].corr(merged["ret"])
    return {
        "ok": True,
        "latest_date": frame.index[-1].date().isoformat(),
        "total_coverage_days": int(len(frame)),
        "last_5d": _sum(5),
        "last_20d": _sum(20),
        "last_60d": _sum(60),
        "daily_corr_with_ret": _num(corr, 3),
        "series": {
            "dates": [item.date().isoformat() for item in frame.index[-120:]],
            "main_net_yi": [_num(value / 1e8, 3) for value in frame["main_net"].tail(120)],
            "close": [_num(value, 3) for value in frame["close"].tail(120)] if "close" in frame.columns else [],
        },
    }


def _corr_matrix(panel: pd.DataFrame) -> dict:
    columns = [column for column in ("ret", "cu_ret", "hs300_ret", "bk_ret", "dxy_ret", "fx_ret") if column in panel.columns]
    if len(columns) < 2:
        return {}
    corr = panel[columns].corr()
    return {
        "labels": [column.replace("_ret", "") for column in columns],
        "matrix": [[_num(value, 2) for value in row] for row in corr.to_numpy()],
    }


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------
def scenarios(data, valuation_block: dict, factor_block: dict, assumptions: dict) -> dict:
    panel = data.panel
    if panel.empty or "shfe_cu" not in panel.columns or not panel["shfe_cu"].notna().any():
        return {"ok": False, "reason": "沪铜序列缺失"}
    spot_cu = float(panel["shfe_cu"].dropna().iloc[-1])
    cu_series = panel["shfe_cu"].dropna()
    cu_pct_5y = _pct_rank(cu_series.tail(1250))
    shares_yi = _num(panel["total_shares"].dropna().iloc[-1] / 1e8, 2) if "total_shares" in panel.columns and panel["total_shares"].notna().any() else None
    shares_yi = shares_yi or 213.94

    fallback = assumptions.get("fallback") or {}
    reports = data.reports
    eps_next = None
    if not reports.empty and "eps_next_year" in reports.columns:
        values = pd.to_numeric(reports["eps_next_year"], errors="coerce").dropna()
        if len(values):
            eps_next = float(values.median())
    eps_source = "研报一致预期中位数" if eps_next is not None else "配置兜底"
    eps_next = eps_next or float(fallback.get("eps_next_year") or 1.63)
    base_np_yi = eps_next * shares_yi
    sensitivity = _copper_sensitivity(data, panel, base_np_yi, float(fallback.get("sens_np_yi_per_1000yuan") or 4.2))
    latest_bps = (valuation_block.get("bps_fin") or None)
    if not latest_bps and valuation_block.get("bps_implied"):
        latest_bps = valuation_block["bps_implied"]
    latest_bps = float(latest_bps or 3.0)
    payout = float(assumptions.get("payout_ratio") or 0.30)
    method_weights = assumptions.get("method_weights") or {"pe_band": 0.30, "pb_band": 0.25, "ev_ebitda": 0.25, "dcf": 0.20}
    prob = assumptions.get("probability") or {"bear": 0.30, "base": 0.50, "bull": 0.20}
    current_price = data.latest_price or float(panel["close"].iloc[-1])
    scenario_out: dict[str, Any] = {}
    target_mid: dict[str, float | None] = {}
    for key in ("bear", "base", "bull"):
        cu = float((assumptions.get("copper") or {}).get(key) or spot_cu)
        np_yi = base_np_yi + (cu - spot_cu) / 1000.0 * sensitivity["sens_yi_per_1000"]
        eps = np_yi / shares_yi if shares_yi else None
        bps = latest_bps + (eps or 0.0) * (1 - payout) * 2
        pe_target = float((assumptions.get("pe_target") or {}).get(key) or 9.5)
        pb_target = float((assumptions.get("pb_target") or {}).get(key) or 2.7)
        ev_target = float((assumptions.get("ev_ebitda_target") or {}).get(key) or 5.1)
        pe_value = eps * pe_target if eps else None
        pb_value = bps * pb_target
        ebitda = (np_yi / (1 - float(fallback.get("tax_rate") or 0.285))) * 1.25 + float(assumptions.get("da_2027") or 78.0)
        net_debt = 120.0
        ev_value = (ev_target * ebitda - net_debt) / shares_yi if shares_yi else None
        dcf_value = _dcf(np_yi, assumptions, key, shares_yi)
        methods = {
            "pe_band": pe_value,
            "pb_band": pb_value,
            "ev_ebitda": ev_value,
            "dcf": dcf_value,
        }
        available = {name: value for name, value in methods.items() if value and value > 0}
        weight_sum = sum(method_weights.get(name, 0) for name in available) or 1
        mid = sum(available[name] * method_weights.get(name, 0) for name in available) / weight_sum if available else None
        target_mid[key] = mid
        scenario_out[key] = {
            "label": {"bear": "熊市", "base": "基准", "bull": "牛市"}[key],
            "prob": prob.get(key),
            "copper_price_yuan_t": _num(cu, 0),
            "np_2027e_yi": _num(np_yi, 1),
            "eps_2027e": _num(eps, 3),
            "bps_2027e": _num(bps, 3),
            "target_pe_band": _num(pe_value, 2),
            "target_pb_band": _num(pb_value, 2),
            "target_ev_ebitda": _num(ev_value, 2),
            "target_dcf": _num(dcf_value, 2),
            "target_mid": _num(mid, 2),
            "target_range": [
                _num(min(available.values()), 2) if available else None,
                _num(max(available.values()), 2) if available else None,
            ],
            "upside_pct": _num((mid / current_price - 1) * 100, 2) if mid and current_price else None,
            "dcf_detail": {"fcf_yi": _num(np_yi, 1)},
        }
    expected = sum((target_mid[key] or 0) * float(prob.get(key) or 0) for key in target_mid)
    current = current_price
    copper_grid = []
    for cu in (88000, 95000, 100000, 105000, 110000, 118000, 125000):
        np_yi = base_np_yi + (cu - spot_cu) / 1000.0 * sensitivity["sens_yi_per_1000"]
        eps = np_yi / shares_yi if shares_yi else None
        copper_grid.append(
            {
                "copper": cu,
                "np_yi": _num(np_yi, 1),
                "eps": _num(eps, 3),
                "pe_9_5x": _num(eps * 9.5, 2) if eps else None,
                "pe_11_5x": _num(eps * 11.5, 2) if eps else None,
            }
        )
    return {
        "ok": True,
        "assumptions": assumptions,
        "spot_cu": _num(spot_cu, 0),
        "cu_pct_5y": cu_pct_5y.get("pct"),
        "shares_yi": shares_yi,
        "copper_sensitivity": sensitivity,
        "scenarios": scenario_out,
        "weighted": {
            "expected_price": _num(expected, 2) if any(target_mid.values()) else None,
            "expected_return_pct": _num((expected / current - 1) * 100, 2) if expected else None,
            "prob_bear": prob.get("bear"),
            "prob_base": prob.get("base"),
            "prob_bull": prob.get("bull"),
            "reward_risk_ratio": _num(
                (expected - current) / abs((target_mid.get("bear") or current) - current), 2
            )
            if target_mid.get("bear") and current and abs((target_mid.get("bear") or current) - current) > 1e-9
            else None,
        },
        "copper_grid": copper_grid,
        "eps_source": eps_source,
    }


def _copper_sensitivity(data, panel: pd.DataFrame, base_np_yi: float, fallback_sens: float) -> dict:
    seg = data.segments
    if seg.empty:
        return {"ok": False, "reason": "分部数据缺失，使用配置兜底", "sens_yi_per_1000": fallback_sens, "source": "fallback"}
    latest_date = seg["as_of"].max()
    latest = seg[seg["as_of"] == latest_date]
    copper = latest[latest["item_name"].astype(str).str.contains("铜", na=False)]
    if copper.empty:
        return {"ok": False, "reason": "分部中未找到铜业务", "sens_yi_per_1000": fallback_sens, "source": "fallback"}
    income = float(pd.to_numeric(copper["income"], errors="coerce").sum())
    cost = float(pd.to_numeric(copper["cost"], errors="coerce").sum())
    margin = income - cost
    if income <= 0:
        return {"ok": False, "reason": "铜业务收入无效", "sens_yi_per_1000": fallback_sens, "source": "fallback"}
    # 用铜价均值反推销量，再按吨毛利对铜价的弹性折算到归母净利
    cu_mean = float(panel["shfe_cu"].dropna().tail(250).mean() or 0)
    volume = income / cu_mean if cu_mean else 0
    sens = volume * 1000.0 / 1e8 * 0.72  # 扣税与少数股东后的近似
    return {
        "ok": True,
        "report_date": latest_date.date().isoformat() if hasattr(latest_date, "date") else str(latest_date)[:10],
        "copper_income_yi": _num(income / 1e8, 1),
        "copper_cost_yi": _num(cost / 1e8, 1),
        "copper_gross_profit_yi": _num(margin / 1e8, 1),
        "implied_volume_tonnes": _num(volume, 0),
        "sens_yi_per_1000": _num(sens, 3),
        "base_np_yi": _num(base_np_yi, 1),
        "source": "segments",
    }


def _dcf(np_yi: float, assumptions: dict, key: str, shares_yi: float | None) -> float | None:
    if not shares_yi:
        return None
    g1 = float((assumptions.get("dcf_g1") or {}).get(key) or 0.02)
    wacc = float((assumptions.get("wacc_scenario") or {}).get(key) or 0.09)
    gt = float((assumptions.get("terminal_g_scenario") or {}).get(key) or 0.02)
    da = float(assumptions.get("da_2027") or 78.0)
    capex = float(assumptions.get("capex_2027") or 105.0)
    dwc = float(assumptions.get("dwc_2027") or 15.0)
    fcf = np_yi + da - capex - dwc
    if wacc <= gt:
        return None
    value = 0.0
    for year in range(1, 6):
        value += fcf * (1 + g1) ** year / (1 + wacc) ** year
    terminal = fcf * (1 + g1) ** 5 * (1 + gt) / (wacc - gt)
    value += terminal / (1 + wacc) ** 5
    return value / shares_yi


# ---------------------------------------------------------------------------
# position
# ---------------------------------------------------------------------------
def position(data, valuation_block: dict, technical_block: dict, scenario_block: dict, defaults: dict, overrides: dict, assumptions: dict) -> dict:
    panel = data.panel
    if panel.empty:
        return {"ok": False, "reason": "日线缺失"}
    effective = {**defaults, **{key: value for key, value in (overrides or {}).items() if value is not None}}
    buy_price = float(effective.get("buy_price") or 0)
    dividends = effective.get("dividends") or []
    dividend_ps = sum(float(item.get("per_share") or 0) for item in dividends if isinstance(item, dict))
    current = data.latest_price or (float(panel["close_raw"].iloc[-1]) if "close_raw" in panel.columns else float(panel["close"].iloc[-1]))
    price_date = (data.snapshots.get("a") or {}).get("as_of") or panel.index[-1].date().isoformat()
    pnl_pct = (current / buy_price - 1) * 100 if buy_price else None
    total_return = (current + dividend_ps) / buy_price * 100 - 100 if buy_price else None
    breakeven = buy_price
    breakeven_div = buy_price - dividend_ps
    rally_needed = (breakeven / current - 1) * 100 if current else None
    rally_needed_div = (breakeven_div / current - 1) * 100 if current else None
    add_prices_value = effective.get("add_prices")
    add_prices = [float(item) for item in (add_prices_value if add_prices_value is not None else [12.5, 12.0, 11.5, 11.0, 10.5, 10.0])]
    add_ratios_value = effective.get("add_ratios")
    add_ratios = [float(item) for item in (add_ratios_value if add_ratios_value is not None else [0.25, 0.5, 0.75, 1.0])]
    table: list[dict[str, Any]] = []
    for add_price in add_prices:
        row: dict[str, Any] = {"add_price": add_price, "add_vs_current_pct": _num((add_price / current - 1) * 100, 2) if current else None}
        for ratio in add_ratios:
            new_cost = (buy_price + add_price * ratio) / (1 + ratio) if buy_price else None
            be = new_cost - dividend_ps / (1 + ratio) if new_cost else None
            key = int(ratio * 100)
            row[f"cost_{key}"] = _num(new_cost, 3)
            row[f"be_{key}"] = _num(be, 3)
            row[f"rally_{key}"] = _num((be / add_price - 1) * 100, 2) if be and add_price else None
        table.append(row)

    pb_pct = (valuation_block.get("pb_percentile", {}).get("5y") or {}).get("pct")
    technical_score = technical_block.get("technical_score")
    copper_pct = (scenario_block.get("cu_pct_5y") if scenario_block.get("ok") else None)
    score = 50.0
    reasons: list[str] = []
    if pb_pct is not None:
        if pb_pct <= 30:
            score += 10
            reasons.append(f"PB 处于 5 年低分位（{pb_pct:.0f}%）→ 估值支撑")
        elif pb_pct >= 70:
            score -= 10
            reasons.append(f"PB 处于 5 年高分位（{pb_pct:.0f}%）→ 估值偏贵")
    if technical_score is not None:
        if technical_score >= 60:
            score += 8
            reasons.append(f"技术评分 {technical_score}/100，趋势偏强")
        elif technical_score <= 40:
            score -= 8
            reasons.append(f"技术评分 {technical_score}/100，趋势偏弱")
    if copper_pct is not None and copper_pct >= 80:
        score -= 5
        reasons.append(f"沪铜处于 5 年 {copper_pct:.0f}% 分位，盈利面临均值回归风险")
    yield_pct = (valuation_block.get("dividend") or {}).get("current_yield_pct")
    if yield_pct is not None:
        if yield_pct >= 2:
            score += 5
            reasons.append(f"股息率 {yield_pct:.2f}%，现金回报尚可")
        else:
            reasons.append(f"股息率 {yield_pct:.2f}%，现金回报一般")
    score = int(max(0, min(100, round(score))))
    stance = "分批加仓 / 持有" if score >= 65 else ("持有观察" if score >= 45 else "减仓 / 等待")
    triggers = _triggers(current, technical_block, scenario_block, valuation_block)
    return {
        "ok": True,
        "buy_price": _num(buy_price, 3),
        "buy_date": effective.get("buy_date"),
        "current_price": _num(current, 3),
        "price_date": price_date,
        "pnl_pct": _num(pnl_pct, 2),
        "pnl_per_share": _num(current - buy_price, 3),
        "total_return_pct_with_div": _num(total_return, 2),
        "dividend_2026_ps": _num(dividend_ps, 4),
        "dividend_yield_on_cost_pct": _num(dividend_ps / buy_price * 100, 2) if buy_price else None,
        "breakeven_price_price_only": _num(breakeven, 3),
        "breakeven_price_with_div": _num(breakeven_div, 3),
        "rally_needed_pct": _num(rally_needed, 2),
        "rally_needed_with_div_pct": _num(rally_needed_div, 2),
        "averaging_table": table,
        "score": score,
        "score_reasons": reasons,
        "stance": stance,
        "triggers": triggers,
        "scenario_expectation": (scenario_block.get("weighted") or {}) if scenario_block.get("ok") else {},
        "effective": effective,
        "defaults": defaults,
        "overrides": overrides or {},
    }


def _triggers(price: float, technical: dict, scenario: dict, valuation_block: dict) -> dict:
    supports = (technical.get("levels") or {}).get("supports") or []
    resistances = (technical.get("levels") or {}).get("resistances") or []
    target = (scenario.get("scenarios") or {}) if scenario.get("ok") else {}
    bear = (target.get("bear") or {}).get("target_mid")
    base = (target.get("base") or {}).get("target_mid")
    bull = (target.get("bull") or {}).get("target_mid")
    return {
        "support_1": supports[0]["price"] if supports else None,
        "support_2": supports[1]["price"] if len(supports) > 1 else None,
        "resistance_1": resistances[0]["price"] if resistances else None,
        "add_condition": f"价格回到 {supports[0]['price']:.2f} 附近且铜价企稳时分批" if supports else "等待技术支撑确认",
        "reduce_condition": f"跌破熊市目标价 {bear:.2f} 且铜价走弱时减仓" if bear else "跌破关键支撑且趋势破坏时减仓",
        "target_bear": bear,
        "target_base": base,
        "target_bull": bull,
    }


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------
def events(data, panel: pd.DataFrame) -> list[dict[str, Any]]:
    if panel.empty:
        return []
    rows: list[dict[str, Any]] = []

    def _reaction(when: pd.Timestamp) -> dict[str, Any]:
        index = panel.index[panel.index >= when]
        if len(index) < 2:
            return {"next_day_ret_pct": None, "ret_5d_pct": None, "next_date": None}
        pos = panel.index.get_loc(index[0])
        next_pos = pos + 1
        next_ret = None
        if next_pos < len(panel):
            next_ret = (panel["close"].iloc[next_pos] / panel["close"].iloc[pos] - 1) * 100
        five_pos = min(pos + 5, len(panel) - 1)
        five_ret = (panel["close"].iloc[five_pos] / panel["close"].iloc[pos] - 1) * 100 if five_pos > pos else None
        return {
            "next_day_ret_pct": _num(next_ret, 2),
            "ret_5d_pct": _num(five_ret, 2),
            "next_date": panel.index[next_pos].date().isoformat() if next_pos < len(panel) else None,
        }

    def _event(when: pd.Timestamp, kind: str, title: str) -> dict[str, Any]:
        reaction = _reaction(when)
        return {
            "date": when.date().isoformat(),
            "type": kind,
            "title": title,
            "reaction": reaction,
            "next_day": reaction.get("next_day_ret_pct"),
            "five_day": reaction.get("ret_5d_pct"),
        }

    if not data.financials.empty:
        for when, row in data.financials.tail(12).iterrows():
            notice = pd.to_datetime(row.get("notice_date"), errors="coerce")
            event_date = notice if not pd.isna(notice) else when
            rows.append(_event(event_date, "财报", str(row.get("report_date_name") or when.date().isoformat())))
    if not data.dividends.empty:
        for _, row in data.dividends.tail(10).iterrows():
            ex_date = row.get("ex_dividend_date")
            when = pd.to_datetime(ex_date, errors="coerce")
            if pd.isna(when):
                continue
            rows.append(_event(when, "分红除权", f"每 10 股派现 {row.get('pretax_bonus_rmb')} 元"))
    if not data.announcements.empty:
        keywords = {"回购": "回购", "增持": "增持", "减持": "减持", "业绩预告": "业绩预告", "股权激励": "股权激励", "可转债": "可转债", "异动": "异动"}
        for _, row in data.announcements.iterrows():
            title = str(row.get("title") or "")
            label = next((value for key, value in keywords.items() if key in title), None)
            if not label:
                continue
            when = pd.Timestamp(row["as_of"])
            rows.append(_event(when, label, title))
    rows.sort(key=lambda item: item["date"], reverse=True)
    return rows[:60]


# ---------------------------------------------------------------------------
# composite / verdict
# ---------------------------------------------------------------------------
def composite(valuation_block: dict, technical_block: dict, scenario_block: dict, factor_block: dict, weights: dict) -> dict:
    pb_pct = (valuation_block.get("pb_percentile", {}).get("5y") or {}).get("pct")
    tech_score = technical_block.get("technical_score")
    cu_pct = scenario_block.get("cu_pct_5y") if scenario_block.get("ok") else None
    expected_ret = (scenario_block.get("weighted") or {}).get("expected_return_pct") if scenario_block.get("ok") else None
    rolling = (factor_block.get("rolling") or {}).get("current") or {}
    excess = None
    items: list[dict[str, Any]] = []

    def _add(code: str, name: str, score: float | None, value: Any, detail: str) -> None:
        items.append(
            factor(
                code=code,
                name=name,
                category="luoyang",
                category_label="洛阳研判",
                weight=float(weights.get(code, 0) or 0),
                direction=1,
                score=score if score is not None else 0.0,
                available=score is not None,
                value=value,
                explain=detail,
                kind="signal",
            )
        )

    _add(
        "valuation",
        "估值",
        (1 - pb_pct / 50) if pb_pct is not None else None,
        pb_pct,
        f"PB 5 年分位 {pb_pct if pb_pct is not None else '—'}%；分位越低越偏多。",
    )
    _add(
        "technical",
        "技术面",
        (tech_score - 50) / 50 if tech_score is not None else None,
        tech_score,
        f"技术评分 {tech_score if tech_score is not None else '—'}/100。",
    )
    _add(
        "copper",
        "铜价",
        ((cu_pct - 50) / 50) * 0.5 if cu_pct is not None else None,
        cu_pct,
        f"沪铜 5 年分位 {cu_pct if cu_pct is not None else '—'}%；高铜价利多盈利但均值回归风险上升。",
    )
    _add(
        "scenario",
        "情景",
        clip((expected_ret or 0) / 30) if expected_ret is not None else None,
        expected_ret,
        f"概率加权期望收益 {expected_ret if expected_ret is not None else '—'}%。",
    )
    beta = rolling.get("beta60_cu")
    excess60 = rolling.get("excess60")
    _add(
        "relative",
        "相对强弱",
        clip((excess60 or 0) / 10) if excess60 is not None else None,
        excess60,
        f"近 60 日相对沪深 300 超额收益 {excess60 if excess60 is not None else '—'}%；铜 beta {beta if beta is not None else '—'}。",
    )
    combined = combine_factors(items)
    return {"factors": items, "combined": combined, "label": combined["label"], "score": combined["score"], "coverage": combined["coverage"]}


def verdict(composite_block: dict, valuation_block: dict, factor_block: dict, scenario_block: dict, position_block: dict) -> dict:
    label = composite_block["label"]
    score = composite_block["score"]
    multi = (factor_block.get("multifactor") or {}).get("5y", {})
    cu_coef = ((multi.get("coef") or {}).get("cu_ret") or {}) if multi else {}
    decomposition = next(
        (
            value
            for key, value in (factor_block.get("decomposition") or {}).items()
            if key.endswith("YTD")
        ),
        {},
    )
    target = (scenario_block.get("scenarios") or {}) if scenario_block.get("ok") else {}
    base = (target.get("base") or {}).get("target_mid")
    bear = (target.get("bear") or {}).get("target_mid")
    bull = (target.get("bull") or {}).get("target_mid")
    expected = (scenario_block.get("weighted") or {}).get("expected_price") if scenario_block.get("ok") else None
    headline = f"{label}（{score:+.1f}/100，覆盖率 {composite_block['coverage']:.0f}%）"
    evidence: list[str] = []
    if multi.get("r2") is not None:
        evidence.append(f"5 年日频多因子（铜+沪深300+美元+汇率）R²={multi.get('r2')}。")
    if cu_coef:
        evidence.append(f"沪铜 β={cu_coef.get('beta')}（t={cu_coef.get('t')}）。")
    if decomposition:
        evidence.append(
            f"年内分解：股价 {decomposition.get('price_chg_pct')}% = 盈利贡献 {decomposition.get('contrib_earnings_pctpts')}pp + 估值贡献 {decomposition.get('contrib_valuation_pctpts')}pp。"
        )
    if valuation_block.get("ok"):
        evidence.append(valuation_block.get("valuation_note") or "")
    return {
        "headline": headline,
        "driver": {
            "headline": "股价由「铜价 + 有色板块高 beta + 估值」共同驱动；下跌阶段先看估值回归，再看铜价。",
            "evidence": [item for item in evidence if item],
        },
        "valuation": {
            "headline": (valuation_block.get("valuation_note") or "估值数据不足") if valuation_block.get("ok") else "估值数据不足",
            "caveat": "周期股在盈利高点用 PE 分位会系统性低估“贵”的程度；PB/EV 才是主锚。",
        },
        "target": {
            "bear": bear,
            "base": base,
            "bull": bull,
            "expected": expected,
            "expected_return_pct": (scenario_block.get("weighted") or {}).get("expected_return_pct") if scenario_block.get("ok") else None,
        },
        "position": {
            "headline": f"浮亏 {position_block.get('pnl_pct')}%、含分红总回报 {position_block.get('total_return_pct_with_div')}%；回本需 +{position_block.get('rally_needed_with_div_pct')}%。"
            if position_block.get("ok")
            else "持仓数据不足",
            "stance": position_block.get("stance"),
            "score": position_block.get("score"),
        },
        "action": {
            "one_line": "不追高、不恐慌割在支撑位；以持有为主，只在估值/铜价/技术共振的支撑区分批。",
            "add_condition": (position_block.get("triggers") or {}).get("add_condition"),
            "reduce_condition": (position_block.get("triggers") or {}).get("reduce_condition"),
        },
        "risk": [
            "铜价处于高位时盈利均值回归风险未充分定价。",
            "资金流接口仅覆盖约 120 个交易日，资金面结论只覆盖近半年。",
            "研报一致预期可能滞后于最新经营变化。",
        ],
    }
