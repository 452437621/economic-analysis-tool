"""Normalized storage helpers: idempotent upserts for market data, macro, documents."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.ingest.contracts import Bar, MacroPoint, NewsItem, Quote
from app.models.base import new_id
from app.models.core import (
    Document,
    Instrument,
    MacroObs,
    MacroSeries,
    MarketBar,
    Quote as QuoteRow,
    Source,
    SourceHealth,
)
from app.platform.config import settings

logger = logging.getLogger(__name__)

_CHUNK = 200

# 行情按分钟采集：值没变化时最多每 240 秒落一行，避免闭市/休市期间每分钟
# 重复写入同一串数字（每天 36 标的 × 1440 分钟 ≈ 5 万行）。
QUOTE_DEDUPE_SEC = 240

# 参与去重比较的字段：价格/成交量变了就要落新行，source 或延迟档位变了也要落。
_QUOTE_VALUE_FIELDS = (
    "price",
    "prev_close",
    "open",
    "high",
    "low",
    "volume",
    "open_interest",
    "bid",
    "ask",
)

_TRANSIENT_SQLITE_ERRORS = (
    "unable to open database file",
    "database is locked",
    "database table is locked",
    "disk i/o error",
)


def _execute_retry(session: Session, stmt, *, retries: int = 4, delay: float = 0.8):  # noqa: ANN001
    """Execute a statement, retrying transient SQLite file/lock errors.

    多行 UPSERT 在 Windows + 杀毒/索引程序占用 WAL 文件时可能瞬时 SQLITE_CANTOPEN；
    UPSERT 本身幂等，重试安全。
    """
    for attempt in range(1, retries + 1):
        try:
            return session.execute(stmt)
        except OperationalError as exc:
            message = str(getattr(exc, "orig", exc)).lower()
            session.rollback()
            if attempt == retries or not any(msg in message for msg in _TRANSIENT_SQLITE_ERRORS):
                raise
            logger.warning("sqlite transient error (attempt %s/%s): %s", attempt, retries, exc.orig)
            time.sleep(delay * attempt)
    return None


def get_source(
    session: Session,
    name: str,
    *,
    kind: str = "api",
    tier: str = "S2",
    reliability: float = 0.8,
    base_url: str | None = None,
) -> Source:
    source = session.scalar(select(Source).where(Source.name == name))
    if source is None:
        source = Source(
            name=name,
            kind=kind,
            tier=tier,
            reliability=reliability,
            base_url=base_url,
        )
        session.add(source)
        session.flush()
    return source


def get_instrument(session: Session, symbol: str) -> Instrument | None:
    return session.scalar(select(Instrument).where(Instrument.symbol == symbol))


def instrument_ids(session: Session, symbols: list[str]) -> dict[str, str]:
    rows = session.scalars(select(Instrument).where(Instrument.symbol.in_(symbols))).all()
    return {row.symbol: row.id for row in rows}


def upsert_bars(
    session: Session,
    instrument_id: str,
    timeframe: str,
    bars: list[Bar],
    source_id: str | None,
    delay_sec: int = 0,
) -> int:
    rows = [
        {
            "id": new_id(),
            "instrument_id": instrument_id,
            "timeframe": timeframe,
            "ts_utc": bar.ts,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "open_interest": bar.open_interest,
            "source_id": source_id,
            "delay_sec": delay_sec,
        }
        for bar in bars
    ]
    for start in range(0, len(rows), _CHUNK):
        chunk = rows[start : start + _CHUNK]
        stmt = sqlite_insert(MarketBar).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_id", "timeframe", "ts_utc"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "open_interest": stmt.excluded.open_interest,
                "source_id": stmt.excluded.source_id,
                "delay_sec": stmt.excluded.delay_sec,
            },
        )
        _execute_retry(session, stmt)
    return len(rows)


def _latest_quote_rows(session: Session, instrument_ids: list[str]) -> dict[str, QuoteRow]:
    """Newest stored quote per instrument (one query, index seek per instrument)."""
    if not instrument_ids:
        return {}
    newest = (
        select(QuoteRow.instrument_id, func.max(QuoteRow.ts_utc).label("ts_utc"))
        .where(QuoteRow.instrument_id.in_(instrument_ids))
        .group_by(QuoteRow.instrument_id)
        .subquery()
    )
    rows = session.scalars(
        select(QuoteRow).join(
            newest,
            and_(
                QuoteRow.instrument_id == newest.c.instrument_id,
                QuoteRow.ts_utc == newest.c.ts_utc,
            ),
        )
    ).all()
    return {row.instrument_id: row for row in rows}


def _is_unchanged(previous: QuoteRow, row: dict, now: datetime, dedupe_sec: int) -> bool:
    """True when re-storing ``row`` would only duplicate ``previous``."""
    if dedupe_sec <= 0:
        return False
    if previous.source_id != row["source_id"] or previous.delay_sec != row["delay_sec"]:
        return False
    if any(getattr(previous, field) != row[field] for field in _QUOTE_VALUE_FIELDS):
        return False
    previous_ts = previous.ts_utc
    if previous_ts.tzinfo is None:
        previous_ts = previous_ts.replace(tzinfo=timezone.utc)
    return (now - previous_ts).total_seconds() < dedupe_sec


def upsert_quotes(
    session: Session,
    quotes: list[Quote],
    symbol_to_id: dict[str, str],
    source_id: str | None,
    *,
    dedupe_sec: int = QUOTE_DEDUPE_SEC,
) -> int:
    """Store quote snapshots, one row per instrument per source minute.

    Unchanged values are refreshed at most every ``dedupe_sec`` seconds so a
    one-minute collection cadence does not bloat the table (the readers only
    ever need the newest row per instrument).
    """
    now = datetime.now(timezone.utc)
    resolved: list[tuple[str, dict]] = []
    for quote in quotes:
        instrument_id = symbol_to_id.get(quote.symbol)
        if not instrument_id:
            logger.warning("quote skipped, instrument not found: %s", quote.symbol)
            continue
        ts = quote.ts.astimezone(timezone.utc).replace(second=0, microsecond=0)
        row = {
            "id": new_id(),
            "instrument_id": instrument_id,
            "ts_utc": ts,
            "price": quote.price,
            "prev_close": quote.prev_close,
            "change_pct": quote.change_pct,
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "volume": quote.volume,
            "open_interest": quote.open_interest,
            "bid": quote.bid,
            "ask": quote.ask,
            "source_id": source_id,
            "delay_sec": quote.delay_sec,
        }
        resolved.append((instrument_id, row))

    latest = _latest_quote_rows(session, [instrument_id for instrument_id, _ in resolved])
    by_instrument: dict[str, dict] = {}
    for instrument_id, row in resolved:
        previous = latest.get(instrument_id)
        if previous is not None and _is_unchanged(previous, row, now, dedupe_sec):
            continue
        by_instrument[instrument_id] = row

    rows = list(by_instrument.values())
    if not rows:
        return 0
    stmt = sqlite_insert(QuoteRow).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["instrument_id", "ts_utc"],
        set_={
            "price": stmt.excluded.price,
            "prev_close": stmt.excluded.prev_close,
            "change_pct": stmt.excluded.change_pct,
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "volume": stmt.excluded.volume,
            "open_interest": stmt.excluded.open_interest,
            "bid": stmt.excluded.bid,
            "ask": stmt.excluded.ask,
            "source_id": stmt.excluded.source_id,
            "delay_sec": stmt.excluded.delay_sec,
        },
    )
    _execute_retry(session, stmt)
    return len(rows)


def ensure_series(
    session: Session,
    code: str,
    *,
    name: str | None = None,
    unit: str | None = None,
    freq: str | None = "d",
    country: str | None = None,
    source_id: str | None = None,
) -> MacroSeries:
    series = session.scalar(select(MacroSeries).where(MacroSeries.code == code))
    if series is None:
        series = MacroSeries(
            code=code,
            name=name or code,
            unit=unit,
            freq=freq,
            country=country,
            source_id=source_id,
        )
        session.add(series)
        session.flush()
    elif freq and series.freq != freq:
        # 频率是元数据而不是观测值：月频序列必须先纠正频率，否则质检会把它当"停更的日频序列"告警
        series.freq = freq
        session.flush()
    return series


def upsert_macro(
    session: Session,
    code: str,
    points: list[MacroPoint],
    *,
    source_id: str | None = None,
    name: str | None = None,
    unit: str | None = None,
    country: str | None = None,
    freq: str | None = None,
) -> int:
    if not points:
        return 0
    series = ensure_series(
        session, code, name=name, unit=unit, freq=freq, country=country, source_id=source_id
    )
    rows = [
        {
            "id": new_id(),
            "series_id": series.id,
            "ts_utc": point.ts,
            "value": point.value,
            "revision": 0,
        }
        for point in points
    ]
    for start in range(0, len(rows), _CHUNK * 2):
        chunk = rows[start : start + _CHUNK * 2]
        stmt = sqlite_insert(MacroObs).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "ts_utc", "revision"],
            set_={"value": stmt.excluded.value},
        )
        _execute_retry(session, stmt)
    return len(rows)


def save_raw(source_slug: str, filename: str, payload: bytes) -> str:
    """Persist raw upstream payload for provenance; returns workspace-relative path."""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    folder = settings.data_dir / "raw" / source_slug / day
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(payload)
    try:
        return str(path.relative_to(settings.data_dir.parent))
    except ValueError:
        return str(path)


def save_document(
    session: Session,
    item: NewsItem,
    source_id: str | None,
    raw_path: str | None = None,
) -> bool:
    url_hash = hashlib.sha256(item.url.encode("utf-8")).hexdigest()
    exists = session.scalar(select(Document.id).where(Document.url_hash == url_hash))
    if exists:
        return False
    session.add(
        Document(
            source_id=source_id,
            url_hash=url_hash,
            url=item.url,
            title=item.title,
            published_at=item.published_at,
            lang="en",
            raw_path=raw_path,
            body_status="metadata",
            meta={
                "summary": item.summary,
                "guid": item.guid,
                "provider": item.source,
            },
        )
    )
    return True


def record_health(
    session: Session,
    source_id: str,
    *,
    ok: bool,
    latency_ms: int | None = None,
    error: str | None = None,
) -> None:
    session.add(
        SourceHealth(
            source_id=source_id,
            ok=ok,
            latency_ms=latency_ms,
            error=(error or "")[:1000] or None,
        )
    )


def prune_quotes(session: Session, keep_days: int | None = None) -> int:
    """Drop intraday quote rows older than the retention window.

    Only the newest row per instrument is ever read (snapshot/watchlist/alerts),
    so minute-level history is bounded to keep the SQLite file from growing
    without limit. ``keep_days=0`` disables the prune.
    """
    days = settings.quotes_retention_days if keep_days is None else keep_days
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = session.execute(delete(QuoteRow).where(QuoteRow.ts_utc < cutoff))
    session.commit()
    return int(result.rowcount or 0)


def prune_source_health(session: Session, keep_days: int = 90) -> int:
    """Bound ``source_health`` growth; the panel only needs recent attempts."""
    if keep_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    result = session.execute(delete(SourceHealth).where(SourceHealth.ts < cutoff))
    session.commit()
    return int(result.rowcount or 0)


def count_rows(session: Session, model) -> int:  # noqa: ANN001
    return int(session.scalar(select(func.count()).select_from(model)) or 0)
