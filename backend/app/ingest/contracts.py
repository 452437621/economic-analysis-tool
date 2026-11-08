"""Data contracts shared by ingestion providers and storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    open_interest: float | None = None


@dataclass(slots=True)
class Quote:
    symbol: str
    ts: datetime
    price: float
    prev_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    bid: float | None = None
    ask: float | None = None
    delay_sec: int = 0

    @property
    def change(self) -> float | None:
        if self.prev_close in (None, 0):
            return None
        return self.price - self.prev_close

    @property
    def change_pct(self) -> float | None:
        if self.prev_close in (None, 0):
            return None
        return (self.price / self.prev_close - 1.0) * 100


@dataclass(slots=True)
class MacroPoint:
    code: str
    ts: datetime
    value: float


@dataclass(slots=True)
class NewsItem:
    source: str
    url: str
    title: str
    published_at: datetime | None = None
    summary: str | None = None
    guid: str | None = None
