"""CZCE daily report parser and dominant-contract selection (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers import czce

pytestmark = pytest.mark.unit

CZCE_TEXT = """\t\t\t\t\t郑州商品交易所期货每日行情表(2026-11-06)
合约代码|昨结算    |今开盘    |最高价    |最低价    |今收盘    |今结算    |涨跌1    |涨跌2    |成交量(手)|持仓量    |增减量    |成交额(万元)|交割结算价
SR611 |5,025.00  |5,026.00  |5,026.00  |5,025.00  |5,025.00  |5,025.00  |0.00     |0.00     |23        |3,300     |-14       |115.58      |5,073.00
SR701 |5,253.00  |5,244.00  |5,266.00  |5,202.00  |5,215.00  |5,233.00  |-38.00   |-20.00   |423,474   |613,091   |17,627    |2,215,959.85|
CF701 |15,340.00 |15,360.00 |15,415.00 |15,265.00 |15,385.00 |15,345.00 |45.00    |5.00     |304,926   |627,506   |-4,122    |2,339,789.24|
"""


def test_czce_parse_and_main_contract():
    rows = czce.parse_daily(CZCE_TEXT)
    assert "SR" in rows and "CF" in rows
    sr_main = czce.main_contract(rows["SR"])
    assert sr_main is not None
    assert sr_main.code == "SR701"
    assert sr_main.close == 5215.0
    assert sr_main.open_interest == 613091.0
