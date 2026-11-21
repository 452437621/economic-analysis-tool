"""Luoyang analysis regressions: degrades on missing columns and bad math domains."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.topics.luoyang import analysis

pytestmark = pytest.mark.unit


def _panel(periods: int = 800) -> pd.DataFrame:
    index = pd.bdate_range("2023-01-02", periods=periods, freq="B")
    close = np.linspace(10.0, 16.0, periods)
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "close_raw": close,
            "volume": np.full(periods, 1_000_000.0),
            "amount": np.full(periods, 1.2e9),
            "pe_ttm": np.linspace(8.0, 20.0, periods),
            "pb_mrq": np.linspace(1.5, 3.5, periods),
            "ps_ttm": np.linspace(1.0, 2.0, periods),
            "total_shares": np.full(periods, 2.14e10),
            "total_market_cap": np.full(periods, 2.8e11),
            "shfe_cu": np.linspace(70_000.0, 90_000.0, periods),
            "hs300_close": np.linspace(3_500.0, 3_900.0, periods),
        },
        index=index,
    )


def _data(panel: pd.DataFrame, **overrides) -> SimpleNamespace:
    base = dict(
        panel=panel,
        price=panel[["close"]].copy(),
        financials=pd.DataFrame(),
        statements=pd.DataFrame(),
        segments=pd.DataFrame(),
        margin=pd.DataFrame(),
        flows=pd.DataFrame(),
        dividends=pd.DataFrame(),
        announcements=pd.DataFrame(),
        reports=pd.DataFrame(),
        snapshots={},
        notes=[],
        latest_price=float(panel["close"].iloc[-1]),
        latest_date=panel.index[-1].date(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_valuation_tolerates_missing_pb_and_ps_columns():
    panel = _panel()
    data = _data(panel[["open", "high", "low", "close", "close_raw", "volume", "pe_ttm", "total_shares"]])
    result = analysis.valuation(data)
    assert result["ok"] is True
    assert result["pb_mrq"] is None
    assert result["pb_percentile"]["5y"]["ok"] is False
    assert result["pb_band_5y"]["ok"] is False
    assert result["series"]["pb_mrq"] == []


def test_decomposition_survives_negative_pe():
    panel = _panel(400)
    # PE crosses zero, so log(PE_end / PE_start) would raise without a guard.
    panel["pe_ttm"] = np.linspace(-5.0, 8.0, len(panel))
    result = analysis._decomposition(panel)
    assert isinstance(result, dict)
    for block in result.values():
        if "contrib_valuation_pctpts" in block:
            assert block["contrib_valuation_pctpts"] is None or isinstance(
                block["contrib_valuation_pctpts"], float
            )


def test_composite_treats_zero_percentile_as_cheap():
    block = analysis.composite(
        {"pb_percentile": {"5y": {"pct": 0.0}}},
        {"technical_score": 50},
        {"ok": True, "cu_pct_5y": 50, "weighted": {"expected_return_pct": 0}},
        {"rolling": {"current": {}}},
        {"valuation": 30, "technical": 25, "copper": 20, "scenario": 15, "relative": 10},
    )
    valuation = next(item for item in block["factors"] if item["code"] == "valuation")
    assert valuation["available"] is True
    assert valuation["score"] == pytest.approx(100.0)


def test_position_builds_averaging_table_and_returns():
    panel = _panel()
    result = analysis.position(
        _data(panel),
        {"pb_percentile": {"5y": {"pct": 30}}, "dividend": {"current_yield_pct": 2.5}},
        {"technical_score": 60},
        {"ok": False},
        {"buy_price": 15.0, "dividends": [{"date": "2026-05-27", "per_share": 0.3}]},
        {"buy_price": 14.0, "add_prices": [12.0, 11.0], "add_ratios": [0.25, 0.5]},
        {},
    )
    assert result["ok"] is True
    assert result["buy_price"] == 14.0
    assert result["pnl_pct"] is not None
    assert len(result["averaging_table"]) == 2
    assert "cost_25" in result["averaging_table"][0]


def test_events_expose_flat_reaction_columns():
    panel = _panel()
    financials = pd.DataFrame(
        {"report_date_name": ["2026 一季报"], "epsjb": [0.3]},
        index=pd.to_datetime(["2026-04-30"]),
    )
    rows = analysis.events(_data(panel, financials=financials), panel)
    assert rows
    row = rows[0]
    assert "next_day" in row and "five_day" in row
    assert row["reaction"]["next_day_ret_pct"] == row["next_day"]


def test_events_use_the_announcement_date_when_available():
    panel = _panel()
    financials = pd.DataFrame(
        {"report_date_name": ["2026 一季报"], "notice_date": ["2026-04-29"], "epsjb": [0.3]},
        index=pd.to_datetime(["2026-03-31"]),
    )
    rows = analysis.events(_data(panel, financials=financials), panel)
    assert rows[0]["date"] == "2026-04-29"


def test_dividend_block_degrades_when_all_rows_are_incomplete():
    panel = _panel()
    dividends = pd.DataFrame(
        {"pretax_bonus_rmb": [None], "ex_dividend_date": [None]},
        index=pd.to_datetime(["2026-03-31"]),
    )
    block = analysis._dividend_block(_data(panel, dividends=dividends), 10.0)
    assert block["ttm_ps"] is None
    assert block["history"] == []


def test_hac_standard_errors_are_not_inflated():
    rng = np.random.default_rng(7)
    x = rng.normal(size=300)
    y = 1.0 + 2.0 * x + rng.normal(scale=0.4, size=300)
    plain = analysis.ols(y, x, ["x"])
    hac = analysis.ols(y, x, ["x"], hac_lags=5)
    assert plain["ok"] and hac["ok"]
    assert np.isfinite(hac["coef"]["x"]["se"])
    # The old implementation inflated SE by ~sqrt(dof).
    assert hac["coef"]["x"]["se"] < plain["coef"]["x"]["se"] * 5


def test_pct_rank_and_band():
    series = pd.Series(np.arange(1.0, 31.0))
    assert analysis._pct_rank(series)["pct"] == 100.0
    band = analysis._band(series)
    assert band["ok"] is True
    assert band["p10"] < band["p50"] < band["p90"]
