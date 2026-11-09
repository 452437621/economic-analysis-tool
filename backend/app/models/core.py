"""Core schema: sources, market data, knowledge graph, decision & operations."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id, utcnow


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # official/media/exchange/proxy
    base_url: Mapped[str | None] = mapped_column(String(500))
    tier: Mapped[str] = mapped_column(String(8), default="S3")  # S1..S6
    reliability: Mapped[float] = mapped_column(Float, default=0.6)
    license: Mapped[str | None] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SourceHealth(Base):
    __tablename__ = "source_health"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class Instrument(Base, TimestampMixin):
    __tablename__ = "instruments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(40))
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)  # metal/energy/fx/rate/equity
    currency: Mapped[str | None] = mapped_column(String(8))
    contract_size: Mapped[float | None] = mapped_column(Float)
    tick_value: Mapped[float | None] = mapped_column(Float)
    margin_pct: Mapped[float | None] = mapped_column(Float)
    domestic_proxy_of: Mapped[str | None] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    extra: Mapped[dict | None] = mapped_column(JSON)


class MarketBar(Base):
    __tablename__ = "market_bars"
    __table_args__ = (
        UniqueConstraint("instrument_id", "timeframe", "ts_utc", name="uq_bar_key"),
        Index("ix_bars_instrument_tf_ts", "instrument_id", "timeframe", "ts_utc"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)  # 1m/5m/1h/1d
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    open_interest: Mapped[float | None] = mapped_column(Float)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    delay_sec: Mapped[int] = mapped_column(Integer, default=0)


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("instrument_id", "ts_utc", name="uq_quote_key"),
        Index("ix_quotes_instrument_ts", "instrument_id", "ts_utc"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    prev_close: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    open_interest: Mapped[float | None] = mapped_column(Float)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    delay_sec: Mapped[int] = mapped_column(Integer, default=0)


class MacroSeries(Base, TimestampMixin):
    __tablename__ = "macro_series"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    freq: Mapped[str | None] = mapped_column(String(16))  # d/w/m/q
    country: Mapped[str | None] = mapped_column(String(8))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))


class MacroObs(Base):
    __tablename__ = "macro_obs"
    __table_args__ = (
        UniqueConstraint("series_id", "ts_utc", "revision", name="uq_macro_obs"),
        Index("ix_macro_obs_series_ts", "series_id", "ts_utc"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    series_id: Mapped[str] = mapped_column(ForeignKey("macro_series.id", ondelete="CASCADE"))
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lang: Mapped[str | None] = mapped_column(String(8))
    sha256: Mapped[str | None] = mapped_column(String(64))
    raw_path: Mapped[str | None] = mapped_column(Text)
    body_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/extracted/stored/skipped
    meta: Mapped[dict | None] = mapped_column(JSON)


class DocumentSpan(Base):
    __tablename__ = "document_spans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    end: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    claim_id: Mapped[str | None] = mapped_column(String(32), index=True)


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # fact/data/forecast/opinion/rumor
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    predicate: Mapped[str] = mapped_column(String(200), nullable=False)
    object: Mapped[dict | list | str | None] = mapped_column(JSON)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/conflicted/retracted
    extracted_by: Mapped[str | None] = mapped_column(String(120))


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # asset/institution/person/country/indicator
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    aliases: Mapped[list | None] = mapped_column(JSON)
    meta: Mapped[dict | None] = mapped_column(JSON)


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(60))
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[float | None] = mapped_column(Float)
    source_ids: Mapped[list | None] = mapped_column(JSON)
    meta: Mapped[dict | None] = mapped_column(JSON)


class EventInstrument(Base):
    __tablename__ = "event_instruments"

    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )


class Thesis(Base, TimestampMixin):
    __tablename__ = "theses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    asset_ids: Mapped[list | None] = mapped_column(JSON)
    direction: Mapped[str | None] = mapped_column(String(8))  # long/short/neutral
    prior: Mapped[float | None] = mapped_column(Float)
    posterior: Mapped[float | None] = mapped_column(Float)
    horizon_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/watch/closed/invalidated
    invalidation: Mapped[str | None] = mapped_column(Text)
    main_driver: Mapped[str | None] = mapped_column(Text)


class ThesisEvidence(Base):
    __tablename__ = "thesis_evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    thesis_id: Mapped[str] = mapped_column(ForeignKey("theses.id", ondelete="CASCADE"))
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"))
    weight: Mapped[float] = mapped_column(Float, default=0.5)
    note: Mapped[str | None] = mapped_column(Text)


class Scenario(Base, TimestampMixin):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    thesis_id: Mapped[str] = mapped_column(ForeignKey("theses.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    triggers: Mapped[str | None] = mapped_column(Text)
    impacts: Mapped[dict | None] = mapped_column(JSON)


class Signal(Base, TimestampMixin):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(40), nullable=False)  # breakout/momentum/reversion/spread/event
    instrument_id: Mapped[str | None] = mapped_column(ForeignKey("instruments.id", ondelete="SET NULL"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    direction: Mapped[str | None] = mapped_column(String(8))
    strength: Mapped[float | None] = mapped_column(Float)
    params: Mapped[dict | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)


class TradePlan(Base, TimestampMixin):
    __tablename__ = "trade_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id", ondelete="SET NULL"))
    instrument_id: Mapped[str | None] = mapped_column(ForeignKey("instruments.id", ondelete="SET NULL"))
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_low: Mapped[float | None] = mapped_column(Float)
    entry_high: Mapped[float | None] = mapped_column(Float)
    stop: Mapped[float | None] = mapped_column(Float)
    targets: Mapped[dict | None] = mapped_column(JSON)
    size: Mapped[float | None] = mapped_column(Float)
    risk_pct: Mapped[float | None] = mapped_column(Float)
    time_stop_days: Mapped[int | None] = mapped_column(Integer)
    invalidation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/confirmed/executed/closed/invalid
    evidence_claim_ids: Mapped[list | None] = mapped_column(JSON)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    thesis_id: Mapped[str | None] = mapped_column(ForeignKey("theses.id", ondelete="SET NULL"))
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("trade_plans.id", ondelete="SET NULL"))
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    horizon_days: Mapped[int | None] = mapped_column(Integer)
    made_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open/resolved
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    brier: Mapped[float | None] = mapped_column(Float)


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id", ondelete="CASCADE"))
    actual: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    cron: Mapped[str | None] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")
    detail: Mapped[str | None] = mapped_column(Text)


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(40))
    object_id: Mapped[str | None] = mapped_column(String(32))
    before_hash: Mapped[str | None] = mapped_column(String(64))
    after_hash: Mapped[str | None] = mapped_column(String(64))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GraphEdge(Base, TimestampMixin):
    __tablename__ = "graph_edges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    src_node: Mapped[str] = mapped_column(String(80), nullable=False)
    dst_node: Mapped[str] = mapped_column(String(80), nullable=False)
    mechanism: Mapped[str | None] = mapped_column(Text)
    sign: Mapped[int | None] = mapped_column(Integer)  # 1 positive, -1 negative
    lag_days: Mapped[float | None] = mapped_column(Float)
    strength: Mapped[float | None] = mapped_column(Float)
    regime: Mapped[str | None] = mapped_column(String(40))
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_claim_ids: Mapped[list | None] = mapped_column(JSON)


class DocumentBody(Base):
    __tablename__ = "document_bodies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    word_count: Mapped[int | None] = mapped_column(Integer)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DataCheck(Base):
    __tablename__ = "data_checks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # reconcile/freshness
    dataset: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(40))
    check_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expected: Mapped[float | None] = mapped_column(Float)
    actual: Mapped[float | None] = mapped_column(Float)
    deviation: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str | None] = mapped_column(Text)


class Brief(Base):
    __tablename__ = "briefs"
    __table_args__ = (UniqueConstraint("kind", "trade_date", name="uq_brief"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # premarket/postmarket/manual
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalyticsResult(Base):
    __tablename__ = "analytics_results"
    __table_args__ = (
        UniqueConstraint("kind", "subject", "asof", name="uq_analytics"),
        Index("ix_analytics_kind_asof", "kind", "asof"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    subject: Mapped[str] = mapped_column(String(60), nullable=False, default="all")
    asof: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    code_version: Mapped[str] = mapped_column(String(20), default="m3.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlanCheck(Base):
    __tablename__ = "plan_checks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("trade_plans.id", ondelete="CASCADE"))
    rule: Mapped[str] = mapped_column(String(80), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlanDetail(Base):
    __tablename__ = "plan_details"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("trade_plans.id", ondelete="CASCADE"), unique=True
    )
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    level: Mapped[str] = mapped_column(String(16), default="info")  # info/warn/critical
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON)


class WatchItem(Base, TimestampMixin):
    __tablename__ = "watchlist"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    group: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[int] = mapped_column(Integer, default=3)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class EconomicEvent(Base):
    __tablename__ = "economic_events"
    __table_args__ = (UniqueConstraint("ts_utc", "name", name="uq_event_ts_name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str | None] = mapped_column(String(40))
    country: Mapped[str | None] = mapped_column(String(40))
    importance: Mapped[int] = mapped_column(Integer, default=2)
    source_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"
    __table_args__ = (UniqueConstraint("trade_date", "product", name="uq_pos_date_product"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    product: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    long_pos: Mapped[int] = mapped_column(Integer, default=0)
    short_pos: Mapped[int] = mapped_column(Integer, default=0)
    net_pos: Mapped[int] = mapped_column(Integer, default=0)
    net_ratio: Mapped[float | None] = mapped_column(Float)
    long_chg: Mapped[int] = mapped_column(Integer, default=0)
    short_chg: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

