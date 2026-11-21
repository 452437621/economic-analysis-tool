"""Topic research storage: generic datasets, source runs and per-topic settings.

The topic framework keeps every external dataset in one long-table pair instead
of a bespoke table per source:

* ``topic_datasets`` is the catalog (one row per topic/dataset);
* ``topic_dataset_rows`` stores normalized payloads keyed by ``(dataset_id,
  as_of, row_key)``.

This lets a new research topic reuse the collector/storage layer without a
schema migration while still keeping indexed, queryable time series.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_id, utcnow


class TopicDataset(Base, TimestampMixin):
    __tablename__ = "topic_datasets"
    __table_args__ = (UniqueConstraint("topic_id", "dataset", name="uq_topic_dataset"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    dataset: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    source: Mapped[str | None] = mapped_column(String(80))
    freq: Mapped[str | None] = mapped_column(String(8))
    unit: Mapped[str | None] = mapped_column(String(40))
    primary_key: Mapped[str | None] = mapped_column(String(80))
    fields: Mapped[dict | None] = mapped_column(JSON)
    latest_as_of: Mapped[date | None] = mapped_column(Date)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TopicDatasetRow(Base):
    __tablename__ = "topic_dataset_rows"
    __table_args__ = (
        UniqueConstraint("dataset_id", "as_of", "row_key", name="uq_topic_row"),
        Index("ix_topic_row_dataset_asof", "dataset_id", "as_of"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("topic_datasets.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    row_key: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TopicSourceRun(Base):
    __tablename__ = "topic_source_runs"
    __table_args__ = (Index("ix_topic_source_run_topic_ts", "topic_id", "checked_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(String(40), nullable=False)
    dataset: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TopicSetting(Base):
    __tablename__ = "topic_settings"
    __table_args__ = (UniqueConstraint("topic_id", name="uq_topic_setting"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
