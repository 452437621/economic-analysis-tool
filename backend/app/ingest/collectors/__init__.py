"""Collector implementations for the ingest pipelines."""

from __future__ import annotations

from app.ingest.collectors.bars import (
    DAILY_BAR_LIMIT,
    MAX_TAIL_MOVE_PCT,
    _guard_tail_bar,
    collect_daily_bars,
)
from app.ingest.collectors.bodies import collect_bodies, purge_binary_bodies
from app.ingest.collectors.calendar import collect_calendar
from app.ingest.collectors.claims import extract_claims, extract_claims_llm
from app.ingest.collectors.macro import collect_macro
from app.ingest.collectors.news import collect_news
from app.ingest.collectors.positions import collect_positions
from app.ingest.collectors.quality import check_data_quality
from app.ingest.collectors.quotes import collect_quotes
from app.ingest.collectors.rates import collect_rates

__all__ = [
    "DAILY_BAR_LIMIT",
    "MAX_TAIL_MOVE_PCT",
    "_guard_tail_bar",
    "check_data_quality",
    "collect_bodies",
    "collect_calendar",
    "collect_daily_bars",
    "collect_macro",
    "collect_news",
    "collect_positions",
    "collect_quotes",
    "collect_rates",
    "extract_claims",
    "extract_claims_llm",
    "purge_binary_bodies",
]
