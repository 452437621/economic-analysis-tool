"""数据流水线缺口回归：僵尸分析运行收尾、预测自动登记、错过的定时作业补跑。

独立 SQLite（``data/test/m0/pipeline-gaps.db``）；每个用例前清空相关表，
避免用例之间互相污染（也避免依赖执行顺序）。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.jobs import supervisor
from app.jobs.plan import JOB_PLANS
from app.ledger.engine import (
    AUTO_FORECAST_CODES,
    AUTO_FORECAST_HORIZONS,
    auto_register_forecasts,
    register_forecast,
    run_ledger,
    score_forecasts,
)
from app.models.base import Base
from app.models.core import (
    AnalyticsResult,
    Instrument,
    Job,
    JobRun,
    MacroObs,
    MacroSeries,
    MarketBar,
)
from app.models.v2 import AnalysisRun, AnalysisStep, Derivation, Forecast, ForecastOutcome
from app.provenance.engine import reconcile_stale_analysis_runs

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "test" / "m0" / "pipeline-gaps.db"
CST = ZoneInfo("Asia/Shanghai")

STATE_VALUE = {
    "readings": [],
    "composites": {
        "DMI": {"name": "DMI", "value": 71.3},
        "ICI": {"name": "ICI", "value": 72.8},
        "ECI": {"name": "ECI", "value": 58.2},
        "GROWTH": {"name": "GROWTH", "value": 28.3},
        "INFLATION": {"name": "INFLATION", "value": 21.1},
        "LIQUIDITY": {"name": "LIQUIDITY", "value": 47.6},
    },
}

TABLES = (
    ForecastOutcome,
    Forecast,
    AnalysisStep,
    AnalysisRun,
    JobRun,
    Job,
    MarketBar,
    Instrument,
    MacroObs,
    MacroSeries,
    AnalyticsResult,
)


@pytest.fixture(scope="module")
def pipeline_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(pipeline_db):
    with pipeline_db() as session:
        for model in TABLES:
            session.execute(delete(model))
        session.commit()
        yield session


def _seed_pipeline_inputs(session) -> None:
    """预测登记所需的本地输入：黄金评分、XAUUSD 日线、US10Y 观测。"""
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            AnalyticsResult(
                id="ar-gold",
                kind="gold",
                subject="gold",
                asof=now,
                payload={"score": -12.5},
            ),
            Instrument(id="inst-xauusd", symbol="XAUUSD", name="XAUUSD", asset_class="metal"),
            MarketBar(
                instrument_id="inst-xauusd",
                timeframe="1d",
                ts_utc=now - timedelta(days=1),
                open=2380.0,
                high=2420.0,
                low=2370.0,
                close=2400.0,
            ),
            MacroSeries(id="ms-us10y", code="US10Y", name="US 10Y", unit="%", freq="d"),
            MacroObs(series_id="ms-us10y", ts_utc=now - timedelta(days=1), value=4.2),
        ]
    )
    session.commit()


# -- 1. 僵尸 analysis_runs 收尾 -------------------------------------------------


def test_reconcile_stale_analysis_runs_marks_only_stale(db):
    now = datetime.now(timezone.utc)
    stale = AnalysisRun(
        id="run-stale",
        kind="gold",
        subject="all",
        asof=now - timedelta(days=2),
        status="running",
        started_at=now - timedelta(days=2),
    )
    fresh = AnalysisRun(
        id="run-fresh",
        kind="cycle",
        subject="world",
        asof=now,
        status="running",
        started_at=now - timedelta(minutes=5),
    )
    db.add_all([stale, fresh])
    db.commit()

    assert reconcile_stale_analysis_runs(db) == 1
    db.commit()
    db.refresh(stale)
    db.refresh(fresh)
    assert stale.status == "interrupted"
    assert stale.finished_at is not None
    assert stale.degraded is True
    assert any("进程中断" in item["message"] for item in stale.degraded_reasons)
    # 未超过 stale_minutes 的运行不动
    assert fresh.status == "running"
    assert fresh.finished_at is None

    # all=True 时连 5 分钟前的也收尾（进程刚重启的全面对账）
    assert reconcile_stale_analysis_runs(db, all=True) == 1
    db.commit()
    db.refresh(fresh)
    assert fresh.status == "interrupted"
    assert fresh.finished_at is not None


# -- 2. 预测自动登记 -----------------------------------------------------------


def test_auto_register_forecasts_without_state_is_noop(db):
    assert auto_register_forecasts(db, None) == 0
    assert auto_register_forecasts(db, {}) == 0
    assert db.scalars(select(Forecast)).all() == []


def test_auto_register_forecasts_creates_and_is_idempotent(db):
    _seed_pipeline_inputs(db)
    today = date.today()
    added = auto_register_forecasts(db, STATE_VALUE, today=today)
    db.commit()
    assert added == len(AUTO_FORECAST_CODES) * len(AUTO_FORECAST_HORIZONS)

    rows = db.scalars(select(Forecast)).all()
    assert len(rows) == added
    assert {row.horizon_days for row in rows} == set(AUTO_FORECAST_HORIZONS)
    targets = {row.target_date.date() for row in rows}
    assert targets == {today + timedelta(days=horizon) for horizon in AUTO_FORECAST_HORIZONS}
    codes = {row.code for row in rows}
    assert codes == set(AUTO_FORECAST_CODES)
    for row in rows:
        assert row.status == "open"
        assert row.baseline_value is not None
        assert 0.5 <= row.probability <= 0.85
        assert row.point is not None
        # 新库历史不足：方向只能是合法的三选一，flat 不算异常
        assert row.direction in {"up", "down", "flat"}

    # 同一天再跑一次：幂等，不重复灌
    assert auto_register_forecasts(db, STATE_VALUE, today=today) == 0
    db.commit()
    assert len(db.scalars(select(Forecast)).all()) == added


def test_auto_register_forecasts_uses_slope_rule(db):
    """10 天里 DMI 从 50 升到 60 → 60 天折算幅度远超 ±2 分阈值 → 判 up。"""
    _seed_pipeline_inputs(db)
    start = datetime.now(timezone.utc) - timedelta(days=9)
    for index in range(10):
        run_id = f"run-cycle-{index}"
        started = start + timedelta(days=index)
        db.add(
            AnalysisRun(
                id=run_id,
                kind="cycle",
                subject="world",
                asof=started,
                status="ok",
                started_at=started,
            )
        )
        db.add(
            AnalysisStep(
                id=f"step-{index}",
                run_id=run_id,
                seq=1,
                name="composite_scores",
                kind="compute",
                status="ok",
                started_at=started,
                outputs={"DMI": 50.0 + index, "ICI": 60.0, "ECI": 55.0},
            )
        )
    db.commit()

    assert auto_register_forecasts(db, STATE_VALUE, today=date.today()) > 0
    db.commit()
    dmi_rows = db.scalars(select(Forecast).where(Forecast.code == "cycle.dmi")).all()
    assert len(dmi_rows) == len(AUTO_FORECAST_HORIZONS)
    assert {row.direction for row in dmi_rows} == {"up"}
    assert all(row.probability == pytest.approx(0.85) for row in dmi_rows)
    assert all(row.point > row.baseline_value for row in dmi_rows)


def test_run_ledger_registers_forecasts_step(db):
    """台账编排里必须先自动登记再结算，新增条数写进步骤输出与 claim。"""
    _seed_pipeline_inputs(db)
    now = datetime.now(timezone.utc)
    db.add(
        Derivation(
            id="der-state-world",
            code="cycle.state.world",
            subject="world",
            claim="cycle state fixture",
            value=STATE_VALUE,
            asof=now,
        )
    )
    db.commit()

    result = run_ledger(db)
    assert result["status"] in {"ok", "degraded"}
    expected = len(AUTO_FORECAST_CODES) * len(AUTO_FORECAST_HORIZONS)
    step = db.scalars(
        select(AnalysisStep).where(AnalysisStep.name == "register_forecasts")
    ).one()
    assert step.outputs["added"] == expected
    claim = db.scalars(
        select(Derivation).where(Derivation.code == "ledger.forecasts")
    ).one()
    assert "本轮自动登记新增" in claim.claim
    open_rows = db.scalars(select(Forecast).where(Forecast.status == "open")).all()
    assert len(open_rows) == expected


# -- 3. score_forecasts 端到端（同时验证 Instrument.symbol / MarketBar.ts_utc）--


def test_score_forecasts_resolves_xauusd_forecast(db):
    _seed_pipeline_inputs(db)
    forecast = register_forecast(
        db,
        code="xauusd",
        direction="up",
        horizon_days=30,
        probability=0.7,
        baseline_value=2300.0,
        target_date=date.today() - timedelta(days=1),
    )
    db.commit()

    result = score_forecasts(db, {}, today=date.today())
    db.commit()
    assert result["resolved"] == 1
    db.refresh(forecast)
    assert forecast.status == "resolved"
    outcome = db.scalars(
        select(ForecastOutcome).where(ForecastOutcome.forecast_id == forecast.id)
    ).one()
    assert outcome.actual == pytest.approx(2400.0)
    assert outcome.hit is True
    assert outcome.brier == pytest.approx((0.7 - 1.0) ** 2)
    assert 0.0 <= outcome.brier <= 1.0


# -- 4. 启动调度自检（数据优先、阻断下游、幂等） ---------------------------


SELECTED = {
    name: JOB_PLANS[name]
    for name in ("collect_daily_bars", "check_data_quality", "analyze")
}


def _seed_schedule_jobs(db) -> None:
    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    db.add_all(
        [
            Job(name=name, cron="schedule-test", enabled=True, last_run_at=yesterday)
            for name in SELECTED
        ]
    )
    db.commit()


@pytest.fixture()
def fake_schedule(pipeline_db, monkeypatch):
    calls: list[str] = []

    def fake_run_job(name: str) -> dict:
        calls.append(name)
        with pipeline_db() as session:
            now = datetime.now(timezone.utc)
            session.add(JobRun(job_name=name, status="ok", started_at=now, finished_at=now))
            job = session.scalar(select(Job).where(Job.name == name))
            if job is not None:
                job.last_run_at = now
                job.last_status = "ok"
            session.commit()
        return {"job": name, "status": "ok"}

    monkeypatch.setattr(supervisor, "JOB_PLANS", SELECTED)
    monkeypatch.setattr(supervisor, "SessionLocal", pipeline_db)
    monkeypatch.setattr(supervisor, "run_job", fake_run_job)
    monkeypatch.setattr(
        supervisor,
        "assess_readiness",
        lambda session, now=None: supervisor.Readiness(status="ok", reasons=[], datasets={}),
    )
    return calls


def test_schedule_check_runs_data_before_analysis(db, fake_schedule):
    _seed_schedule_jobs(db)
    now = datetime.now(CST)
    report = supervisor.run_schedule_check(trigger="manual", now=now)
    assert fake_schedule == ["collect_daily_bars", "check_data_quality", "analyze"]
    assert report["status"] == "ok"
    assert report["readiness"]["status"] == "ok"


def test_schedule_check_blocks_downstream_when_data_missing(db, fake_schedule, monkeypatch):
    _seed_schedule_jobs(db)
    monkeypatch.setattr(
        supervisor,
        "assess_readiness",
        lambda session, now=None: supervisor.Readiness(
            status="blocked",
            reasons=[
                {
                    "code": "readiness.daily_bars",
                    "severity": "critical",
                    "message": "日线不完整",
                    "action_job": "collect_daily_bars",
                }
            ],
            datasets={},
        ),
    )
    now = datetime.now(CST)
    report = supervisor.run_schedule_check(trigger="manual", now=now)
    assert "analyze" not in fake_schedule
    assert any(item["name"] == "analyze" for item in report["blocked"])
    assert report["status"] == "blocked"


def test_schedule_check_is_idempotent_after_jobs_run(db, fake_schedule):
    _seed_schedule_jobs(db)
    now = datetime.now(CST)
    first = supervisor.run_schedule_check(trigger="manual", now=now)
    assert first["status"] == "ok"
    second = supervisor.run_schedule_check(trigger="manual", now=now)
    assert second["jobs"] == []
    assert fake_schedule == ["collect_daily_bars", "check_data_quality", "analyze"]


CHAIN_SELECTED = {
    name: JOB_PLANS[name]
    for name in ("check_data_quality", "analyze", "cycle")
}


def test_blocked_job_propagates_to_its_dependents(db, pipeline_db, monkeypatch):
    """check_data_quality degraded → analyze blocked → cycle must also be blocked."""
    calls: list[str] = []

    def fake_run_job(name: str) -> dict:
        calls.append(name)
        status = "degraded" if name == "check_data_quality" else "ok"
        with pipeline_db() as session:
            now = datetime.now(timezone.utc)
            session.add(JobRun(job_name=name, status=status, started_at=now, finished_at=now))
            session.commit()
        return {"job": name, "status": status}

    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    db.add_all(
        [
            Job(name=name, cron="schedule-test", enabled=True, last_run_at=yesterday)
            for name in CHAIN_SELECTED
        ]
    )
    db.commit()
    monkeypatch.setattr(supervisor, "JOB_PLANS", CHAIN_SELECTED)
    monkeypatch.setattr(supervisor, "SessionLocal", pipeline_db)
    monkeypatch.setattr(supervisor, "run_job", fake_run_job)
    monkeypatch.setattr(
        supervisor,
        "assess_readiness",
        lambda session, now=None: supervisor.Readiness(status="ok", reasons=[], datasets={}),
    )

    report = supervisor.run_schedule_check(trigger="manual", now=datetime.now(CST))
    assert calls == ["check_data_quality"]
    assert "analyze" in {item["name"] for item in report["blocked"]}
    assert "cycle" in {item["name"] for item in report["blocked"]}
    assert report["status"] == "degraded"


def test_dry_run_does_not_write_skipped_rows(db, pipeline_db, monkeypatch):
    db.add_all(
        [
            Job(
                name=name,
                cron="schedule-test",
                enabled=True,
                last_run_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
            for name in CHAIN_SELECTED
        ]
    )
    db.commit()
    monkeypatch.setattr(supervisor, "JOB_PLANS", CHAIN_SELECTED)
    monkeypatch.setattr(supervisor, "SessionLocal", pipeline_db)
    monkeypatch.setattr(
        supervisor,
        "assess_readiness",
        lambda session, now=None: supervisor.Readiness(
            status="blocked",
            reasons=[{"code": "readiness.macro", "message": "宏观缺失"}],
            datasets={},
        ),
    )
    before = len(db.scalars(select(JobRun)).all())
    report = supervisor.run_schedule_check(
        trigger="manual", now=datetime.now(CST), dry_run=True, run_data=False
    )
    after = len(db.scalars(select(JobRun)).all())
    assert after == before
    assert report["blocked"]
