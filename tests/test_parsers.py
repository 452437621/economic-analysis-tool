"""Offline parser tests using recorded upstream samples (no network)."""

from __future__ import annotations

from app.ingest.providers import eastmoney, rss, sina, treasury
from app.ingest.symbols import compute_dxy

SINA_DAILY = (
    '/*<script>location.href=\'//sina.com\';</script>*/ var _AU0=(['
    '{"d":"2026-11-06","o":"880.000","h":"885.000","l":"870.000","c":"875.000","v":"1000","p":"200000"},'
    '{"d":"2026-11-05","o":"870.000","h":"882.000","l":"868.000","c":"880.000","v":"1200","p":"201000"}'
    "]);"
)

SINA_NF = (
    'var hq_str_nf_AU0="黄金连续,023000,873.020,874.800,865.000,0.000,874.580,874.640,'
    '874.580,0.000,879.220,3,1,149122.000,147551,沪,黄金,2026-11-07,1";'
)

SINA_HF = (
    'var hq_str_hf_GC="4083.170,,4079.600,4080.000,4116.200,4035.100,05:59:59,4113.500,'
    '4098.500,0,1,1,2026-11-07,纽约黄金,0";'
)

SINA_FX = (
    'var hq_str_fx_susdcnh="06:47:00,6.670500,6.670800,6.673600,40,6.673100,6.673400,'
    '6.669400,6.670500,离岸人民币（香港）,-0.050000,-0.003100,0.0005994,'
    ',6.995700,6.642700,,2026-11-08";'
)

EM_QUOTE = {
    "rc": 0,
    "data": {
        "f43": 1329,
        "f44": 1372,
        "f45": 1318,
        "f46": 1350,
        "f47": 2279676,
        "f48": 3059247286.0,
        "f57": "603993",
        "f58": "洛阳钼业",
        "f60": 1401,
        "f170": -514,
    },
}

EM_KLINE = {
    "data": {
        "klines": [
            "2026-11-05,13.90,14.01,14.05,13.80,1900000,2650000000.0,1.8",
            "2026-11-06,13.50,13.29,13.72,13.18,2279676,3059247286.0,4.0",
        ]
    }
}

TREASURY_NOMINAL = (
    'Date,"1 Mo","2 Mo","3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"\n'
    "11/06/2026,4.02,4.15,4.19,4.23,4.33,4.50,4.55,4.60,4.70,4.84,5.10,5.20\n"
    "11/05/2026,4.01,4.14,4.18,4.22,4.32,4.49,4.54,4.59,4.69,4.83,5.09,5.19\n"
)
TREASURY_REAL = (
    'Date,"5 YR","7 YR","10 YR","20 YR","30 YR"\n'
    "11/06/2026,2.35,2.48,2.63,2.91,3.07\n"
    "11/05/2026,2.33,2.46,2.60,2.90,3.05\n"
)

RSS_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<title>FRB: Press Release</title>
<item>
  <title>Federal Reserve issues FOMC statement</title>
  <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261106a.htm</link>
  <guid>https://www.federalreserve.gov/x</guid>
  <pubDate>Fri, 06 Nov 2026 18:00:00 GMT</pubDate>
  <description>&lt;p&gt;Recent indicators suggest that economic activity has continued to expand.&lt;/p&gt;</description>
</item>
</channel></rss>"""


def test_sina_daily_jsonp_parsed_and_sorted():
    bars = sina.parse_daily_jsonp(SINA_DAILY)
    assert len(bars) == 2
    assert bars[0].ts.day == 5  # sorted ascending
    assert bars[-1].close == 875.0
    assert bars[-1].open_interest == 200000


def test_sina_domestic_quote():
    quote = sina.parse_domestic_quote(SINA_NF, "AU")
    assert quote is not None
    assert quote.price == 874.58
    assert quote.prev_close == 879.22
    assert quote.volume == 149122.0
    assert quote.open_interest == 147551.0
    assert quote.change_pct is not None and quote.change_pct < 0


def test_sina_overseas_quote():
    quote = sina.parse_overseas_quote(SINA_HF, "GC")
    assert quote is not None
    assert quote.price == 4083.17
    assert quote.prev_close == 4098.5
    assert quote.high == 4116.2
    assert quote.delay_sec == 900


def test_sina_fx_quote():
    quote = sina.parse_fx_quote(SINA_FX, "USDCNH")
    assert quote is not None
    assert quote.price == 6.6705
    assert round(quote.prev_close, 4) == 6.6736
    assert quote.ts.year == 2026


def test_eastmoney_quote_and_kline():
    quote = eastmoney.parse_quote(EM_QUOTE, "603993")
    assert quote is not None
    assert quote.price == 13.29
    assert quote.prev_close == 14.01
    assert round(quote.change_pct, 2) == -5.14
    bars = eastmoney.parse_kline(EM_KLINE)
    assert len(bars) == 2
    assert bars[-1].close == 13.29
    assert bars[-1].volume == 2279676.0


def test_treasury_curves_and_breakevens():
    nominal = treasury.parse_curve_csv(TREASURY_NOMINAL, treasury.NOMINAL_COLUMNS)
    real = treasury.parse_curve_csv(TREASURY_REAL, treasury.REAL_COLUMNS)
    assert nominal["US10Y"][-1].value == 4.84
    assert real["US10Y_REAL"][-1].value == 2.63
    merged = {**nominal, **real}
    treasury.add_breakevens(merged)
    assert merged["US10Y_BE"][-1].value == 2.21
    assert merged["US5Y_BE"][-1].value == 2.25


def test_rss_parse():
    items = rss.parse_feed(RSS_XML, "美联储")
    assert len(items) == 1
    item = items[0]
    assert item.title.startswith("Federal Reserve")
    assert item.published_at is not None
    assert item.published_at.tzinfo is not None
    assert "economic activity" in (item.summary or "")


def test_dxy_proxy():
    prices = {
        "EURUSD": 1.1139,
        "USDJPY": 158.41,
        "GBPUSD": 1.3355,
        "USDCAD": 1.4125,
        "USDSEK": 9.8842,
        "USDCHF": 0.8194,
    }
    dxy = compute_dxy(prices)
    assert dxy is not None
    assert 95 < dxy < 110
    prices.pop("USDCHF")
    assert compute_dxy(prices) is None
