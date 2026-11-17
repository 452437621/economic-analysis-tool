"""V2.0 透明化（玻璃盒）与周期/长河/台账相关表。

设计依据：docs/19-透明化业务流程设计.md、docs/20-功能与接口设计.md。
本模块只定义结构，读写逻辑在 ``app.provenance`` 与 ``app.api.glassbox``。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, utcnow


class AnalysisRun(Base, TimestampMixin):
    """一次分析运行的元信息（透明化 L1：这次结果是怎么算出来的）。"""

    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_kind_asof", "kind", "asof"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    subject: Mapped[str] = mapped_column(String(60), nullable=False, default="all")
    asof: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    method_id: Mapped[str | None] = mapped_column(String(80))
    code_version: Mapped[str] = mapped_column(String(24), default="m3.0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_count: Mapped[int] = mapped_column(Integer, default=0)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    degraded_reasons: Mapped[list | None] = mapped_column(JSON)
    summary: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class AnalysisStep(Base):
    """运行内部步骤（透明化 L2：每个环节的输入、输出、耗时）。"""

    __tablename__ = "analysis_steps"
    __table_args__ = (Index("ix_analysis_steps_run_seq", "run_id", "seq"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="compute")
    status: Mapped[str] = mapped_column(String(16), default="ok")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    inputs: Mapped[dict | None] = mapped_column(JSON)
    outputs: Mapped[dict | None] = mapped_column(JSON)
    params: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class Derivation(Base):
    """推导结论（透明化 L3：结论、置信度、证据等级、反证与失效条件）。"""

    __tablename__ = "derivations"
    __table_args__ = (Index("ix_derivations_code_asof", "code", "asof"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(60), nullable=False, default="all")
    claim: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence_grade: Mapped[str] = mapped_column(String(2), default="E3")
    method_id: Mapped[str | None] = mapped_column(String(80))
    inputs: Mapped[list | None] = mapped_column(JSON)
    steps: Mapped[list | None] = mapped_column(JSON)
    rules_hit: Mapped[list | None] = mapped_column(JSON)
    caveats: Mapped[list | None] = mapped_column(JSON)
    falsifiers: Mapped[list | None] = mapped_column(JSON)
    opposing: Mapped[list | None] = mapped_column(JSON)
    asof: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DerivationLink(Base):
    """推导之间的父子关系（支撑 -> 结论），用于谱系图与版本影响分析。"""

    __tablename__ = "derivation_links"
    __table_args__ = (Index("ix_derivation_links_child", "child_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_id: Mapped[str] = mapped_column(
        ForeignKey("derivations.id", ondelete="CASCADE"), nullable=False
    )
    child_id: Mapped[str] = mapped_column(
        ForeignKey("derivations.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(24), default="supports")


class MethodRegistry(Base, TimestampMixin):
    """方法与规则登记表：每个结论都能追到方法版本与代码摘要。"""

    __tablename__ = "method_registry"

    method_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    kind: Mapped[str] = mapped_column(String(24), default="model")
    description: Mapped[str | None] = mapped_column(Text)
    code_sha: Mapped[str | None] = mapped_column(String(40))
    params_schema: Mapped[dict | None] = mapped_column(JSON)


class RuleHit(Base):
    """规则命中记录（透明化 L3：哪些规则被触发、为什么）。"""

    __tablename__ = "rule_hits"
    __table_args__ = (Index("ix_rule_hits_run", "run_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    fired: Mapped[bool] = mapped_column(Boolean, default=True)
    message: Mapped[str | None] = mapped_column(Text)
    inputs: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Observation(Base):
    """带 vintage 的原始观测（透明化 L5），用于防前视与数字溯源。"""

    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("code", "asof", "vintage_date", name="uq_observation"),
        Index("ix_observations_code_asof", "code", "asof"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    asof: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    vintage_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(24))
    source: Mapped[str | None] = mapped_column(String(80))
    evidence_grade: Mapped[str] = mapped_column(String(2), default="E0")
    extra: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IndicatorCatalog(Base, TimestampMixin):
    """指标目录：统一口径（单位、频率、方向、层）。"""

    __tablename__ = "indicator_catalog"

    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(24))
    freq: Mapped[str | None] = mapped_column(String(12))
    source: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(8))
    layer: Mapped[str | None] = mapped_column(String(12))
    direction: Mapped[str | None] = mapped_column(String(24))
    description: Mapped[str | None] = mapped_column(Text)


class Forecast(Base):
    """预测台账：登记 -> 到期 -> 对账 -> 校准（F24）。"""

    __tablename__ = "forecasts"
    __table_args__ = (Index("ix_forecasts_code_target", "code", "target_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL")
    )
    derivation_id: Mapped[str | None] = mapped_column(
        ForeignKey("derivations.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(60), nullable=False, default="all")
    direction: Mapped[str] = mapped_column(String(16), default="flat")
    horizon_days: Mapped[int] = mapped_column(Integer, default=20)
    made_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    target_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    point: Mapped[float | None] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float)
    upper: Mapped[float | None] = mapped_column(Float)
    probability: Mapped[float | None] = mapped_column(Float)
    method_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="open")
    baseline_value: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)


class ForecastOutcome(Base):
    """预测对账结果（Brier / 命中 / 实际值）。"""

    __tablename__ = "forecast_outcomes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    forecast_id: Mapped[str] = mapped_column(
        ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False
    )
    actual: Mapped[float | None] = mapped_column(Float)
    hit: Mapped[bool | None] = mapped_column(Boolean)
    brier: Mapped[float | None] = mapped_column(Float)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notes: Mapped[str | None] = mapped_column(Text)


class ScenarioRun(Base):
    """一次情景推演（四情景概率 + 资产映射）。"""

    __tablename__ = "scenario_runs"
    __table_args__ = (Index("ix_scenario_runs_run", "run_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE")
    )
    scenario_id: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    horizon: Mapped[str | None] = mapped_column(String(24))
    drivers: Mapped[list | None] = mapped_column(JSON)
    assets: Mapped[dict | None] = mapped_column(JSON)
    asof: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TimelineEvent(Base):
    """1500–2026 世界长河事件（长河页与周期对照）。"""

    __tablename__ = "timeline_events"
    __table_args__ = (
        UniqueConstraint("year", "title", name="uq_timeline_year_title"),
        Index("ix_timeline_events_year", "year"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="economy")
    layer: Mapped[str] = mapped_column(String(24), default="L")
    evidence_grade: Mapped[str] = mapped_column(String(2), default="B")
    related_power: Mapped[str | None] = mapped_column(String(24))
    summary: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(400))


class PowerIndex(Base):
    """霸权/实力指数时间序列（八项实力 + 储备货币份额）。"""

    __tablename__ = "power_index"
    __table_args__ = (
        UniqueConstraint("power", "year", "indicator", name="uq_power_index"),
        Index("ix_power_index_power_year", "power", "year"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    power: Mapped[str] = mapped_column(String(24), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    indicator: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16))
    evidence_grade: Mapped[str] = mapped_column(String(2), default="B")
    source_url: Mapped[str | None] = mapped_column(String(400))
