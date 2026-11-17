"""台账（M4）：原则库数据、核对逻辑、预测登记/结算、校准与接口形状。

使用独立 SQLite（``data/test/m4/ledger.db``）；原则核对直接喂指标字典，
不依赖周期引擎的运行结果，保证测试可独立复现。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ledger.engine import (
    _eval,
    build_metrics,
    calibration_summary,
    check_principles,
    register_forecast,
    run_ledger,
    score_forecasts,
    sync_principles,
)
from app.ledger.principles import CATEGORY_LABELS, EVIDENCE_LABELS, PRINCIPLES
from app.main import app
from app.models.base import Base
from app.models.v2 import Derivation, Forecast, ForecastOutcome, PrincipleCheck
from app.platform.db import get_session

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "test" / "m4" / "ledger.db"

CODES = {"ledger.principles", "ledger.calibration", "ledger.forecasts"}

METRICS = {
    "us_interest_revenue": 25.0,
    "long_position": 0.98,
    "us_r_minus_g": 0.9,
    "sofr_spread": 0.02,
    "global_debt_gdp": 311.0,
    "us_reserve_share": 56.7,
    "growth": 29.8,
    "polarization": 82.0,
    "us_tariffs": 60.0,
    "us_sanctions": 70.0,
    "cb_gold": 106.4,
    "us_inequality": 21.0,
    "us_protests": 65.0,
    "us_deficit_gdp": 5.8,
    "us_alliance_exit": 50.0,
    "gold_mom": 16.06,
    "oil_mom": 8.9,
}


@pytest.fixture(scope="module")
def ledger_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(ledger_db):
    with ledger_db() as session:
        yield session


@pytest.fixture()
def client(ledger_db):
    def override():
        with ledger_db() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


# -- 原则库数据 -------------------------------------------------------------


def test_principles_dataset_is_well_formed():
    assert len(PRINCIPLES) == 26
    ids = [item["id"] for item in PRINCIPLES]
    assert len(ids) == len(set(ids))
    assert {item["category"] for item in PRINCIPLES} == {"A", "B", "C", "D"}
    assert set(CATEGORY_LABELS) == {"A", "B", "C", "D"}
    counts: dict[str, int] = {}
    for item in PRINCIPLES:
        assert item["evidence"] in EVIDENCE_LABELS, item["id"]
        assert item["grade"] in {"A", "B", "C", "D"}, item["id"]
        assert item["statement"].strip()
        assert item["observable"].strip()
        assert item["falsifier"].strip()
        counts[item["category"]] = counts.get(item["category"], 0) + 1
        if "metric" in item:
            assert item["op"] in {">=", "<=", ">", "<"}, item["id"]
            assert isinstance(item["threshold"], (int, float)), item["id"]
    assert counts == {"A": 8, "B": 8, "C": 5, "D": 5}
    auto = [item for item in PRINCIPLES if "metric" in item]
    assert len(auto) == 19


def test_eval_returns_four_states():
    assert _eval(25.0, ">=", 20.0, 15.0)[0] == "hit"
    assert _eval(0.9, "<=", 0.0, 1.0)[0] == "near"
    assert _eval(0.02, ">=", 0.1, 0.05)[0] == "miss"
    assert _eval(10.0, None, None, None)[0] == "unknown"


# -- 指标汇总 ---------------------------------------------------------------


def test_build_metrics_merges_sources():
    state = {
        "readings": [
            {"id": "us_interest_revenue", "value": 25.0},
            {"id": "gold_mom", "value": 0.1606},
            {"id": "oil_mom", "value": 0.089},
            {"id": "us_reserve_share", "value": 56.7},
            {"id": "bad", "value": None},
        ],
        "composites": {"GROWTH": {"value": 29.8}},
        "long_cycle": {"position": 0.98},
    }
    alerts = {"alerts": [{"metric": "cb_gold", "value": 106.4}]}
    metrics = build_metrics(state, alerts)
    assert metrics["us_interest_revenue"] == 25.0
    assert metrics["gold_mom"] == pytest.approx(16.06)
    assert metrics["oil_mom"] == pytest.approx(8.9)
    assert metrics["growth"] == 29.8
    assert metrics["long_position"] == 0.98
    assert metrics["cb_gold"] == 106.4
    assert metrics["global_debt_gdp"] == 311.0
    assert "bad" not in metrics


def test_build_metrics_without_cycle_is_safe():
    metrics = build_metrics(None, None)
    assert metrics == {"global_debt_gdp": 311.0}


# -- 原则同步与核对 ---------------------------------------------------------


def test_sync_principles_is_idempotent(db):
    first = sync_principles(db)
    assert first["created"] == 26 and first["total"] == 26
    second = sync_principles(db)
    assert second["created"] == 0 and second["updated"] == 0
    db.commit()
    assert db.scalar(select(func.count()).select_from(select(PrincipleCheck.id).subquery())) == 0


def test_check_principles_statuses(db):
    sync_principles(db)
    checks = check_principles(db, METRICS, date(2026, 11, 17), "run-test")
    assert len(checks) == 26
    by_id = {item["id"]: item for item in checks}
    assert by_id["A2"]["status"] == "hit"
    assert by_id["A3"]["status"] == "hit"
    assert by_id["A4"]["status"] == "near"
    assert by_id["A6"]["status"] == "miss"
    assert by_id["A7"]["status"] == "hit"
    assert by_id["A8"]["status"] == "hit"
    assert by_id["B8"]["status"] == "miss"
    assert by_id["C4"]["status"] == "near"
    assert by_id["D3"]["status"] == "near"
    assert by_id["A1"]["status"] == "unknown"
    counts: dict[str, int] = {}
    for item in checks:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    assert counts == {"hit": 13, "near": 3, "miss": 3, "unknown": 7}
    db.commit()

    again = check_principles(db, METRICS, date(2026, 11, 17), "run-test-2")
    assert len(again) == 26
    rows = db.scalars(select(PrincipleCheck)).all()
    assert len(rows) == 26
    assert {row.run_id for row in rows} == {"run-test-2"}


# -- 预测登记与对账 ---------------------------------------------------------


def test_register_forecast_validation_and_target(db):
    register_forecast(
        db, code="cycle.dmi", direction="up", horizon_days=10, probability=0.7,
        baseline_value=50.0, notes="测试",
    )
    db.commit()
    row = db.scalars(select(Forecast)).one()
    assert row.status == "open"
    assert row.target_date.date() == (datetime.now(timezone.utc) + timedelta(days=10)).date()
    with pytest.raises(ValueError):
        register_forecast(db, code="unknown.code", direction="up", horizon_days=10)
    with pytest.raises(ValueError):
        register_forecast(db, code="cycle.dmi", direction="sideways", horizon_days=10)


def test_score_forecasts_hits_and_brier(db):
    forecast = register_forecast(
        db, code="cycle.dmi", direction="up", horizon_days=1, probability=0.8,
        baseline_value=50.0,
    )
    db.commit()
    result = score_forecasts(db, {"dmi": 60.0}, today=date.today() + timedelta(days=5))
    assert result["resolved"] == 1
    db.commit()
    db.refresh(forecast)
    assert forecast.status == "resolved"
    outcome = db.scalars(select(ForecastOutcome)).one()
    assert outcome.hit is True
    assert outcome.actual == 60.0
    assert outcome.brier == pytest.approx((0.8 - 1.0) ** 2)


def test_score_forecasts_miss_is_counted(db):
    forecast = register_forecast(
        db, code="cycle.dmi", direction="down", horizon_days=1, probability=0.7,
        baseline_value=50.0,
    )
    db.commit()
    result = score_forecasts(db, {"dmi": 60.0}, today=date.today() + timedelta(days=5))
    assert result["resolved"] == 1
    db.commit()
    db.refresh(forecast)
    assert forecast.status == "resolved"
    outcome = db.scalars(
        select(ForecastOutcome).where(ForecastOutcome.forecast_id == forecast.id)
    ).one()
    assert outcome.hit is False
    assert outcome.brier == pytest.approx(0.7**2)


def test_calibration_summary(db):
    summary = calibration_summary(db)
    assert summary["n"] >= 2
    assert summary["brier"] is not None
    assert summary["hit_rate"] is not None
    assert summary["by_horizon"]
    assert sum(item["n"] for item in summary["by_horizon"]) == summary["n"]


# -- 端到端编排 -------------------------------------------------------------


def test_run_ledger_end_to_end(db):
    result = run_ledger(db)
    assert result["status"] in {"ok", "degraded"}
    assert len(result["principles"]) == 26
    assert result["counts"]["total"] == 26
    codes = {
        row.code
        for row in db.scalars(select(Derivation)).all()
        if row.code in CODES
    }
    assert codes == CODES
    assert result["run_id"]
    second = run_ledger(db)
    assert second["run_id"] != result["run_id"]


def test_api_overview_and_principles(client):
    response = client.get("/api/v2/ledger/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["total"] == 26
    assert len(body["principles"]) == 26
    assert body["forecast_codes"]
    assert "calibration" in body

    response = client.get("/api/v2/ledger/principles")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 26

    response = client.get("/api/v2/ledger/calibration")
    assert response.status_code == 200
    assert "calibration" in response.json()


def test_api_create_and_list_forecast(client):
    payload = {
        "code": "cycle.growth",
        "direction": "down",
        "horizon_days": 20,
        "probability": 0.6,
        "baseline_value": 30.0,
        "notes": "接口测试",
    }
    response = client.post("/api/v2/ledger/forecasts", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["code"] == "cycle.growth"

    listing = client.get("/api/v2/ledger/forecasts?status=open").json()
    assert any(item["id"] == body["id"] for item in listing["items"])


def test_api_run(client):
    response = client.post("/api/v2/ledger/run")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["counts"]["total"] == 26
