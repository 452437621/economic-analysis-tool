"""Single-source registry for external data sources and news feeds.

This module deliberately imports nothing from ``app`` so it can be shared by the
collector implementations, ``chains.py``, ``backfill.py`` and the API without
creating import cycles.
"""

from __future__ import annotations


SOURCE_SINA = dict(
    name="新浪财经", kind="market", tier="S2", reliability=0.85, base_url="https://finance.sina.com.cn"
)
SOURCE_EM = dict(
    name="东方财富", kind="market", tier="S2", reliability=0.85, base_url="https://quote.eastmoney.com"
)
SOURCE_TENCENT = dict(
    name="腾讯财经", kind="market", tier="S2", reliability=0.8, base_url="https://gu.qq.com"
)
SOURCE_TREASURY = dict(
    name="美国财政部", kind="official", tier="S1", reliability=0.95, base_url="https://home.treasury.gov"
)
SOURCE_JGB = dict(
    name="日本财务省", kind="official", tier="S1", reliability=0.95, base_url="https://www.mof.go.jp"
)
SOURCE_ECB = dict(
    name="欧洲央行", kind="official", tier="S1", reliability=0.95, base_url="https://data.ecb.europa.eu"
)
SOURCE_SHFE = dict(
    name="上海期货交易所", kind="official", tier="S1", reliability=0.95, base_url="https://www.shfe.com.cn"
)
SOURCE_CZCE = dict(
    name="郑州商品交易所", kind="official", tier="S1", reliability=0.95, base_url="https://www.czce.com.cn"
)
SOURCE_NYFED = dict(
    name="纽约联储", kind="official", tier="S1", reliability=0.95, base_url="https://markets.newyorkfed.org"
)
SOURCE_FRANKFURTER = dict(
    name="Frankfurter(ECB参考汇率)", kind="market", tier="S2", reliability=0.9, base_url="https://api.frankfurter.app"
)
SOURCE_IMF = dict(
    name="IMF DataMapper", kind="official", tier="S1", reliability=0.9, base_url="https://www.imf.org"
)
SOURCE_WORLDBANK = dict(
    name="世界银行", kind="official", tier="S1", reliability=0.9, base_url="https://data.worldbank.org"
)
SOURCE_TREASURY_FISCAL = dict(
    name="美国财政部FiscalData",
    kind="official",
    tier="S1",
    reliability=0.95,
    base_url="https://fiscaldata.treasury.gov",
)
SOURCE_FED_RESEARCH = dict(
    name="美联储H.4.1/H.6",
    kind="official",
    tier="S1",
    reliability=0.95,
    base_url="https://www.federalreserve.gov",
)
SOURCE_FRED = dict(
    name="FRED",
    kind="official",
    tier="S1",
    reliability=0.9,
    base_url="https://fred.stlouisfed.org",
)

NEWS_FEEDS = [
    dict(name="美联储", url="https://www.federalreserve.gov/feeds/press_all.xml", kind="rss", tier="S1"),
    dict(name="欧洲央行", url="https://www.ecb.europa.eu/rss/press.html", kind="rss", tier="S1"),
    dict(name="日本央行", url="https://www.boj.or.jp/en/rss/whatsnew.xml", kind="rss", tier="S1"),
    dict(name="美国能源信息署", url="https://www.eia.gov/rss/todayinenergy.xml", kind="rss", tier="S1"),
    dict(name="美国贸易代表办公室", url="https://ustr.gov/rss.xml", kind="rss", tier="S1"),
]

# 体积大/更新慢的官方源，单独低频采集
NEWS_FEEDS_SLOW = [
    dict(name="国家统计局", url="https://www.stats.gov.cn/sj/zxfb/rss.xml", kind="rss", tier="S1"),
]

SOURCES: dict[str, dict] = {
    "sina": SOURCE_SINA,
    "eastmoney": SOURCE_EM,
    "tencent": SOURCE_TENCENT,
    "treasury": SOURCE_TREASURY,
    "jgb": SOURCE_JGB,
    "ecb": SOURCE_ECB,
    "shfe": SOURCE_SHFE,
    "czce": SOURCE_CZCE,
    "nyfed": SOURCE_NYFED,
    "frankfurter": SOURCE_FRANKFURTER,
    "imf": SOURCE_IMF,
    "worldbank": SOURCE_WORLDBANK,
    "treasury_fiscal": SOURCE_TREASURY_FISCAL,
    "fed_research": SOURCE_FED_RESEARCH,
    "fred": SOURCE_FRED,
}


__all__ = [
    "SOURCE_SINA",
    "SOURCE_EM",
    "SOURCE_TENCENT",
    "SOURCE_TREASURY",
    "SOURCE_JGB",
    "SOURCE_ECB",
    "SOURCE_SHFE",
    "SOURCE_CZCE",
    "SOURCE_NYFED",
    "SOURCE_FRANKFURTER",
    "SOURCE_IMF",
    "SOURCE_WORLDBANK",
    "SOURCE_TREASURY_FISCAL",
    "SOURCE_FED_RESEARCH",
    "SOURCE_FRED",
    "NEWS_FEEDS",
    "NEWS_FEEDS_SLOW",
    "SOURCES",
]
