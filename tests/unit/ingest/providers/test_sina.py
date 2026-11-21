"""Sina daily/quote JSONP parsers using recorded upstream samples (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers import sina
from app.ingest.providers.sina import parse_global_daily_jsonp

pytestmark = pytest.mark.unit

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


def test_parse_global_daily_jsonp():
    text = (
        'var _GC=([{"date":"2026-11-09","open":"4100.0","high":"4150.0",'
        '"low":"4090.0","close":"4133.1","volume":"0","position":"0"},'
        '{"date":"2026-11-10","open":"4133.0","high":"4156.2",'
        '"low":"4130.8","close":"4140.5","volume":"12","position":"34"}]);'
    )
    bars = parse_global_daily_jsonp(text)
    assert len(bars) == 2
    assert bars[-1].close == 4140.5
    assert bars[-1].volume == 12
    assert str(bars[-1].ts.date()) == "2026-11-10"
