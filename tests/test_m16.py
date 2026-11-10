"""M16 tests: Sina DCE position parsing and dominant contract selection."""

from __future__ import annotations

from datetime import date

from app.ingest.providers.sina_positions import choose_contract, parse_tables

HTML = """
<table><tr><th>名次</th><th>会员简称</th><th>多单持仓</th><th>比上交易增减</th></tr>
<tr><td>1</td><td>方正中期</td><td>5,698</td><td>522</td></tr>
<tr><td>2</td><td>国泰君安</td><td>4,336</td><td>-3,119</td></tr>
<tr><td>合计</td><td></td><td>10,034</td><td></td></tr></table>
<table><tr><th>名次</th><th>会员简称</th><th>空单持仓</th><th>比上交易增减</th></tr>
<tr><td>1</td><td>国投期货</td><td>2,946</td><td>-1,142</td></tr>
<tr><td>2</td><td>中泰期货</td><td>2,717</td><td>-82</td></tr>
<tr><td>合计</td><td></td><td>5,663</td><td></td></tr></table>
"""


def test_choose_contract_skips_near_expiry():
    options = ["M2611", "M2612", "M2701", "M2703", "M2705"]
    assert choose_contract(options, date(2026, 11, 9)) == "M2701"


def test_choose_contract_returns_none_without_future():
    assert choose_contract(["M2611"], date(2026, 11, 25), min_days=45) is None


def test_parse_tables_sums_ranked_positions():
    parsed = parse_tables(HTML)
    assert parsed["long_pos"] == 10034
    assert parsed["short_pos"] == 5663
    assert parsed["long_chg"] == -2597
    assert parsed["short_chg"] == -1224
    assert len(parsed["members"]) == 4
    assert {member["side"] for member in parsed["members"]} == {"long", "short"}
