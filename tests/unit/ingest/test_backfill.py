"""历史回补（`app.ingest.backfill`）的测试。

重点钉两件事：
1. 郑商所逐日文件聚成日线时取的是**主力合约**（持仓量最大），不是第一个合约；
2. 脏点订正只在「单根接口给的日期与缺口日期一致」时才写库，否则宁可删掉这根。
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.ingest import backfill
from app.ingest.contracts import Bar
from app.ingest.providers import czce
from app.ingest.symbols import TENCENT_KLINE_RAW, TENCENT_SINGLE_BAR

pytestmark = pytest.mark.unit


def _row(**kwargs) -> czce.CzceRow:
    base = dict(
        code="CF405", product="CF", prev_settle=None, open=None, high=None,
        low=None, close=None, settle=None, volume=None, open_interest=None,
        oi_change=None,
    )
    base.update(kwargs)
    return czce.CzceRow(**base)


# ---------------------------------------------------------------- CZCE bridge


def test_bar_from_czce_uses_main_contract():
    """两个合约都在：取持仓量最大的那个（近月主力），而不是列表第一个。"""
    rows = [
        _row(code="CF501", close=15000.0, open=14900.0, high=15100.0, low=14850.0,
             volume=10.0, open_interest=100.0),
        _row(code="CF405", close=16080.0, open=16000.0, high=16120.0, low=15980.0,
             volume=5000.0, open_interest=9000.0),
    ]
    bar = backfill._bar_from_czce(rows, date(2024, 1, 30))
    assert isinstance(bar, Bar)
    assert bar.close == 16080.0
    assert (bar.open, bar.high, bar.low) == (16000.0, 16120.0, 15980.0)
    assert bar.volume == 5000.0 and bar.open_interest == 9000.0
    assert bar.ts == datetime(2024, 1, 30, tzinfo=timezone.utc)


def test_bar_from_czce_falls_back_to_close_for_missing_ohlc():
    rows = [_row(code="SR909", close=5343.0, open_interest=8000.0)]
    bar = backfill._bar_from_czce(rows, date(2019, 4, 23))
    assert (bar.open, bar.high, bar.low, bar.close) == (5343.0, 5343.0, 5343.0, 5343.0)


def test_bar_from_czce_returns_none_without_rows():
    assert backfill._bar_from_czce([], date(2019, 4, 23)) is None
    assert backfill._bar_from_czce([_row(code="CF909")], date(2019, 4, 23)) is None


# ---------------------------------------------------------------- 单根接口映射


def test_single_bar_codes_are_known_kline_symbols():
    """订正脏点用的「单根接口」代码必须是已知腾讯标的（拼错会静默订正失败）。"""
    assert TENCENT_SINGLE_BAR
    assert set(TENCENT_SINGLE_BAR) <= set(TENCENT_KLINE_RAW)
    assert TENCENT_SINGLE_BAR["NDX"] == "usNDX"
    # 原始端点是带点的 us.NDX：它自己会把 2026-11-16 的行情写坏成 close=10.0
    assert TENCENT_KLINE_RAW["NDX"] == "us.NDX"


@pytest.mark.parametrize("symbol", ["SPX", "NDX", "DJIA"])
def test_single_bar_codes_have_no_dot(symbol: str):
    """「单根接口」依赖不带点的代码（带点会走原始端点，返回被写坏的历史）。"""
    assert "." not in TENCENT_SINGLE_BAR[symbol]
