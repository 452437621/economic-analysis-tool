"""Collection pipelines: quotes, daily bars, US yields, official news.

This module is kept as a thin facade so that every historical import path and
monkeypatch target (``app.ingest.pipeline.collect_*``, provider module aliases,
source definitions and macro metadata) keeps working after the collector
implementations moved to :mod:`app.ingest.collectors`.
"""

from __future__ import annotations

from app.ingest import store
from app.ingest.collectors import (
    DAILY_BAR_LIMIT,
    MAX_TAIL_MOVE_PCT,
    _guard_tail_bar,
    check_data_quality,
    collect_bodies,
    collect_calendar,
    collect_daily_bars,
    collect_macro,
    collect_news,
    collect_positions,
    collect_quotes,
    collect_rates,
    extract_claims,
    extract_claims_llm,
    purge_binary_bodies,
)
from app.ingest.collectors.quotes import _quote_symbols
from app.ingest.http import HttpClient
from app.ingest.macro_meta import (
    IMF_ANNUAL_SERIES,
    MACRO_SERIES_META,
    MTS_LINE_SERIES,
    WORLDBANK_ANNUAL_SERIES,
)
from app.ingest.providers import eastmoney, rss, sina, tencent
from app.ingest.sources import (
    NEWS_FEEDS,
    NEWS_FEEDS_SLOW,
    SOURCE_CZCE,
    SOURCE_ECB,
    SOURCE_EM,
    SOURCE_FED_RESEARCH,
    SOURCE_FRANKFURTER,
    SOURCE_FRED,
    SOURCE_IMF,
    SOURCE_JGB,
    SOURCE_NYFED,
    SOURCE_SHFE,
    SOURCE_SINA,
    SOURCE_TENCENT,
    SOURCE_TREASURY,
    SOURCE_TREASURY_FISCAL,
    SOURCE_WORLDBANK,
    SOURCES,
)
from app.platform.db import SessionLocal

__all__ = [
    "DAILY_BAR_LIMIT",
    "IMF_ANNUAL_SERIES",
    "MACRO_SERIES_META",
    "MAX_TAIL_MOVE_PCT",
    "MTS_LINE_SERIES",
    "NEWS_FEEDS",
    "NEWS_FEEDS_SLOW",
    "SOURCES",
    "SOURCE_CZCE",
    "SOURCE_ECB",
    "SOURCE_EM",
    "SOURCE_FED_RESEARCH",
    "SOURCE_FRANKFURTER",
    "SOURCE_FRED",
    "SOURCE_IMF",
    "SOURCE_JGB",
    "SOURCE_NYFED",
    "SOURCE_SHFE",
    "SOURCE_SINA",
    "SOURCE_TENCENT",
    "SOURCE_TREASURY",
    "SOURCE_TREASURY_FISCAL",
    "SOURCE_WORLDBANK",
    "WORLDBANK_ANNUAL_SERIES",
    "HttpClient",
    "SessionLocal",
    "_guard_tail_bar",
    "_quote_symbols",
    "check_data_quality",
    "collect_bodies",
    "collect_calendar",
    "collect_daily_bars",
    "collect_macro",
    "collect_news",
    "collect_positions",
    "collect_quotes",
    "collect_rates",
    "eastmoney",
    "extract_claims",
    "extract_claims_llm",
    "purge_binary_bodies",
    "rss",
    "sina",
    "store",
    "tencent",
]
