"""M2 unit tests: HTML extraction, CZCE parsing, claim extraction."""

from __future__ import annotations

from app.ingest.providers import czce
from app.ingest.providers.html_extract import extract_main_text
from app.knowledge.extract import extract_numeric_claims

HTML = """
<html><head><script>var x = 1;</script><style>.a{}</style></head>
<body>
<nav>Home | Markets</nav>
<main>
  <h1>FOMC statement</h1>
  <p>Recent indicators suggest that economic activity has continued to expand.</p>
  <p>Inflation remains somewhat elevated at 2.8% while unemployment is 4.1%.</p>
</main>
<footer>Disclaimer</footer>
</body></html>
"""

CZCE_TEXT = """\t\t\t\t\t郑州商品交易所期货每日行情表(2026-11-06)
合约代码|昨结算    |今开盘    |最高价    |最低价    |今收盘    |今结算    |涨跌1    |涨跌2    |成交量(手)|持仓量    |增减量    |成交额(万元)|交割结算价
SR611 |5,025.00  |5,026.00  |5,026.00  |5,025.00  |5,025.00  |5,025.00  |0.00     |0.00     |23        |3,300     |-14       |115.58      |5,073.00
SR701 |5,253.00  |5,244.00  |5,266.00  |5,202.00  |5,215.00  |5,233.00  |-38.00   |-20.00   |423,474   |613,091   |17,627    |2,215,959.85|
CF701 |15,340.00 |15,360.00 |15,415.00 |15,265.00 |15,385.00 |15,345.00 |45.00    |5.00     |304,926   |627,506   |-4,122    |2,339,789.24|
"""


def test_extract_main_text_removes_noise():
    text = extract_main_text(HTML)
    assert "FOMC statement" in text
    assert "2.8%" in text
    assert "Home | Markets" not in text
    assert "var x = 1" not in text
    assert "Disclaimer" not in text


def test_czce_parse_and_main_contract():
    rows = czce.parse_daily(CZCE_TEXT)
    assert "SR" in rows and "CF" in rows
    sr_main = czce.main_contract(rows["SR"])
    assert sr_main is not None
    assert sr_main.code == "SR701"
    assert sr_main.close == 5215.0
    assert sr_main.open_interest == 613091.0


def test_claim_extraction_with_default_subject():
    text = "The ECB said inflation was 2.5% in October. Unemployment at 4.1%."
    claims = extract_numeric_claims(text, default_subject="欧洲央行")
    assert len(claims) >= 2
    assert claims[0].subject == "欧洲央行"
    assert claims[0].value == 2.5
    assert claims[0].unit == "%"
    assert claims[1].subject == "欧洲央行"
    assert text[claims[0].start : claims[0].end].strip().startswith("The ECB")


def test_claim_spans_are_exact():
    text = "The Federal Reserve kept the rate at 4.25% and said inflation was 2.8%."
    claims = extract_numeric_claims(text)
    assert claims
    for claim in claims:
        assert text[claim.start : claim.end].strip() == claim.quote
