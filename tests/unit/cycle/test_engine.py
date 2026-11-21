"""EPIC-C 2.0 周期引擎（M2）：配置、分量、阶段、情景、预警与端到端。

测试使用独立的 SQLite 文件（``data/test/m0/cycle-engine.db``），只 seed 引擎
表达式真正引用的序列，避免污染其它用例共享的测试库。
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.cycle import DERIVATION_CODES
from app.cycle.alerts import evaluate
from app.cycle.analogs import find_analogs
from app.cycle.composite import all_composites, composite
from app.cycle.config import load_config
from app.cycle.engine import run_cycle
from app.cycle.history import build_history
from app.cycle.indicators import Reading, build_readings, phi, phi_series
from app.cycle.market import Panel, eval_expression, zscore
from app.cycle.phases import (
    inventory_cycle,
    liquidity_state,
    long_cycle,
    political_calendar,
    short_cycle,
)
from app.cycle.scenarios import scenarios
from app.cycle.sustainability import sustainability
from app.cycle.world import world_state
from app.main import app
from app.models.base import Base, new_id
from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar
from app.models.v2 import Derivation, ScenarioRun
from app.platform.db import get_session
from tests.helpers import ROOT

pytestmark = [pytest.mark.unit, pytest.mark.slow]

DB_PATH = ROOT / "data" / "test" / "m0" / "cycle-engine.db"
DAYS = 420
END = "2026-11-16"

MACRO = {
    "US10Y": (4.2, 0.004),
    "US2Y": (4.0, 0.003),
    "US30Y": (4.8, 0.005),
    "US10Y_BE": (2.2, 0.0006),
    "US10Y_REAL": (2.0, 0.004),
    "EFFR": (3.9, 0.0002),
    "SOFR_EFFR": (0.02, 0.0001),
    "CN10Y": (1.7, 0.0004),
    "CN2Y": (1.3, 0.0004),
}

BARS = {
    "CU": (9000.0, 3.0),
    "XAUUSD": (3300.0, 1.5),
    "SPX": (6000.0, 2.0),
    "SC": (500.0, 0.2),
    "DXY": (100.0, 0.02),
    "000300": (4000.0, -0.8),
    "I": (700.0, 0.1),
    "ZN": (2500.0, 0.7),
    "NI": (12000.0, 3.0),
}


def _seed(session: Session) -> None:
    dates = pd.date_range(end=END, periods=DAYS, freq="D")
    for code, (start, step) in MACRO.items():
        series = MacroSeries(
            id=new_id(), code=code, name=code, unit="%", freq="daily", country="US"
        )
        session.add(series)
        session.flush()
        session.add_all(
            [
                MacroObs(
                    id=new_id(),
                    series_id=series.id,
                    ts_utc=stamp.to_pydatetime(),
                    value=start + step * index + 0.005 * math.sin(index / 9.0),
                )
                for index, stamp in enumerate(dates)
            ]
        )
    for symbol, (start, step) in BARS.items():
        instrument = Instrument(
            id=new_id(),
            symbol=symbol,
            name=symbol,
            exchange="TEST",
            asset_class="test",
            currency="USD",
            active=True,
        )
        session.add(instrument)
        session.flush()
        session.add_all(
            [
                MarketBar(
                    id=new_id(),
                    instrument_id=instrument.id,
                    timeframe="1d",
                    ts_utc=stamp.to_pydatetime(),
                    open=start + step * index,
                    high=start + step * index + 5,
                    low=start + step * index - 5,
                    close=start + step * index,
                    volume=1000,
                )
                for index, stamp in enumerate(dates)
            ]
        )
    session.commit()


@pytest.fixture(scope="module")
def cycle_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        _seed(session)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(cycle_db):
    with cycle_db() as session:
        yield session


def _reading(rid: str, score: str, weight: float, value: float, evidence: str = "E1", **extra) -> Reading:
    payload = {
        "id": rid,
        "name": rid,
        "score": score,
        "weight": weight,
        "direction": 1.0,
        "value": value,
        "unit": "%",
        "asof": "2026-11-16",
        "z": 0.0,
        "score_value": value,
        "evidence": evidence,
        "source": "test",
        "layer": "test",
        "why": "test",
        "caveat": None,
        "stale_days": 0,
    }
    payload.update(extra)
    return Reading(**payload)


# ---------------------------------------------------------------- config
def test_config_sections_and_shapes():
    cfg = load_config()
    for key in ("normalization", "scores", "indicators", "manual"):
        assert key in cfg
    assert set(cfg["scores"]) == {"DMI", "ICI", "ECI", "GROWTH", "INFLATION", "LIQUIDITY"}
    for spec in cfg["indicators"]:
        assert spec["score"] in cfg["scores"]
        assert spec["direction"] in (1, -1)
        assert 0 < float(spec["weight"]) <= 1
        assert spec.get("expr")
    for spec in cfg["manual"]:
        assert spec["score"] in cfg["scores"]
        assert spec["evidence"] in ("E0", "E1", "E2", "E3", "E4")
        assert spec.get("source")
    assert cfg["normalization"]["min_obs"] <= cfg["normalization"]["window_days"]
    assert (cfg.get("_meta") or {}).get("version") == "2.0.0"


# ---------------------------------------------------------------- math
def test_phi_on_scalar_and_series():
    assert phi(0.0) == pytest.approx(0.5)
    assert phi(1.96) == pytest.approx(0.975, abs=1e-3)
    series = phi_series(pd.Series([0.0, 1.96, np.nan]))
    assert math.isclose(series.iloc[0], 0.5, abs_tol=1e-9)
    assert math.isclose(series.iloc[1], 0.975, abs_tol=1e-3)
    assert math.isnan(series.iloc[2])


def test_eval_expression_supports_numeric_column_names():
    index = pd.date_range(end="2026-11-16", periods=80, freq="D")
    panel = Panel(daily=pd.DataFrame({"000300": np.linspace(4000, 4200, 80)}, index=index))
    result = eval_expression(panel, "000300 / 000300.shift(60) - 1")
    assert result.notna().sum() == 20
    assert result.iloc[-1] > 0


def test_zscore_clips_and_respects_min_obs():
    index = pd.date_range(end="2026-11-16", periods=300, freq="D")
    series = pd.Series(np.linspace(1.0, 3.0, 300), index=index)
    z = zscore(series, window_days=250, min_obs=100, clip=2.0)
    assert z.iloc[:99].isna().all()
    assert z.notna().sum() > 0
    assert z.dropna().abs().max() <= 2.0


# ---------------------------------------------------------------- composites
def test_composite_renormalises_missing_components():
    config = {
        "scores": {"DMI": {"name": "债务货币"}},
        "indicators": [
            {"id": "a", "name": "a", "score": "DMI", "weight": 0.5},
            {"id": "b", "name": "b", "score": "DMI", "weight": 0.5},
        ],
        "manual": [],
    }
    readings = [_reading("a", "DMI", 0.5, 90.0)]
    result = composite("DMI", readings, config)
    assert result["coverage"] == pytest.approx(0.5)
    assert result["value"] == pytest.approx(90.0)
    assert result["degraded"] is True
    assert "缺失" in (result.get("degrade_reason") or "")


def test_composite_caps_confidence_when_all_e4():
    readings = [_reading("p", "ICI", 1.0, 80.0, evidence="E4")]
    result = composite("ICI", readings, load_config())
    assert result["confidence"] <= 0.45


def test_all_composites_returns_six_scores():
    readings = [_reading("x", "GROWTH", 1.0, 55.0)]
    results = all_composites(readings, load_config())
    assert set(results) == {"DMI", "ICI", "ECI", "GROWTH", "INFLATION", "LIQUIDITY"}
    assert results["DMI"]["value"] is None


# ---------------------------------------------------------------- phases
def test_long_cycle_phase_and_position():
    cfg = load_config()
    dmi = {"value": 69.7, "confidence": 0.9, "evidence": "E1", "coverage": 1.0}
    result = long_cycle(dmi, cfg)
    assert result["phase_id"] == "top"
    assert result["position"] > 0.9
    assert result["next_phase"]


def test_long_cycle_hysteresis_holds_previous_phase():
    cfg = load_config()
    held = long_cycle({"value": 54.0, "confidence": 0.9}, cfg, previous_phase="顶部")
    assert held["hysteresis_held"] is True
    assert held["phase_id"] == "top"
    switched = long_cycle({"value": 45.0, "confidence": 0.9}, cfg, previous_phase="顶部")
    assert switched["hysteresis_held"] is False
    assert switched["phase_id"] == "bubble_late"


def test_short_cycle_rules_and_two_step_confirmation():
    cfg = load_config()
    result = short_cycle(
        {"value": 35.0, "coverage": 1.0},
        {"value": 20.0},
        {"value": 45.0},
        -18.0,
        cfg,
    )
    assert result["state"] == "衰退"
    held = short_cycle(
        {"value": 35.0, "coverage": 1.0},
        {"value": 20.0},
        {"value": 45.0},
        -18.0,
        cfg,
        previous_state="过热",
        previous_raw=None,
    )
    assert held["state"] == "过热"
    assert held["hysteresis_held"] is True
    confirmed = short_cycle(
        {"value": 35.0, "coverage": 1.0},
        {"value": 20.0},
        {"value": 45.0},
        -18.0,
        cfg,
        previous_state="过热",
        previous_raw="衰退",
    )
    assert confirmed["state"] == "衰退"
    assert confirmed["hysteresis_held"] is False


def test_liquidity_state_thresholds():
    assert liquidity_state({"value": 65})["state"] == "宽松"
    assert liquidity_state({"value": 45})["state"] == "中性"
    assert liquidity_state({"value": 30})["state"] == "收紧"
    assert liquidity_state({"value": None})["available"] is False


def test_inventory_cycle_is_explicitly_degraded():
    index = pd.date_range(end="2026-11-16", periods=200, freq="D")
    daily = pd.DataFrame(
        {code: np.linspace(100, 90, 200) for code in ("CU", "I", "ZN", "NI")}, index=index
    )
    result = inventory_cycle(Panel(daily=daily), load_config())
    assert result["available"] is True
    assert result["degraded"] is True
    assert result["evidence"] == "E1"
    assert result["confidence"] == pytest.approx(0.35)
    assert result["state"] in ("主动补库", "被动补库", "主动去库", "被动去库")


def test_political_calendar_window():
    cfg = load_config()
    near = political_calendar(cfg, date(2026, 12, 20))
    assert near["nearest"]["date"] == "2027-01-10"
    assert near["window"] == "高不确定性窗口"
    far = political_calendar(cfg, date(2026, 10, 1))
    assert far["window"] == "常态窗口"


# ---------------------------------------------------------------- models
def test_scenarios_sum_to_one_and_react_to_growth():
    cfg = load_config()
    weak = scenarios({"value": 20}, {"value": 20}, {"value": 20}, {"value": 30}, cfg)
    assert weak["sum"] == pytest.approx(1.0)
    strong = scenarios({"value": 70}, {"value": 75}, {"value": 45}, {"value": 70}, cfg)
    assert strong["sum"] == pytest.approx(1.0)
    weak_s3 = next(item for item in weak["scenarios"] if item["id"] == "S3")
    strong_s3 = next(item for item in strong["scenarios"] if item["id"] == "S3")
    assert weak_s3["probability"] > strong_s3["probability"]
    # S1 调整量可手算复核：0.10 × max(0,(DMI−55)/45)
    s1 = next(item for item in weak["scenarios"] if item["id"] == "S1")
    assert s1["adjustment"] == pytest.approx(0.10 * max(0.0, (20 - 55) / 45.0), abs=1e-3)
    assert "公式" not in (weak.get("formula") or "")


def test_sustainability_fiscal_dominance():
    result = sustainability(load_config())
    assert result["mode_id"] == "fiscal_dominance"
    assert result["interest_to_revenue"] == pytest.approx(25.0)
    assert result["evidence"] == "E2"


def test_world_state_separates_internal_and_external():
    result = world_state(load_config())
    assert result["us_internal"]["stage_name"] == "财政糟糕与冲突"
    assert result["global_order"]["stage_name"] == "多极摩擦"
    assert abs(sum(item["weight"] for item in result["power_index"]["components"]) - 1.0) < 1e-6
    assert result["us_internal"]["degraded"] is True
    assert result["us_internal"]["evidence"] == "E4"


def test_alerts_unknown_and_triggered():
    cfg = load_config()
    only_30y = {"us_30y": {"value": 6.0, "unit": "%", "asof": "2026-11-16", "name": "30Y"}}
    result = evaluate(only_30y, cfg)
    triggered = {item["id"] for item in result["alerts"] if item["status"] == "triggered"}
    unknown = {item["id"] for item in result["alerts"] if item["status"] == "unknown"}
    assert "W1" in triggered
    assert "W4" in unknown
    assert result["counts"]["unknown"] >= 10
    missing_op = evaluate({}, cfg)
    assert missing_op["triggered"] == 0


def test_analogs_exclude_recent_months():
    index = pd.date_range(end="2026-11-01", periods=72, freq="MS")
    rng = np.random.default_rng(7)
    zscores = pd.DataFrame(rng.normal(size=(72, 5)), index=index, columns=["a", "b", "c", "d", "e"])
    scores = pd.DataFrame(rng.uniform(20, 80, size=(72, 2)), index=index, columns=["GROWTH", "INFLATION"])
    zscores.iloc[-1] = zscores.iloc[10]
    result = find_analogs(zscores, scores, top=3, min_gap_months=12)
    assert result["available"] is True
    months = [item["month"] for item in result["analogs"]]
    assert months, "至少应命中一个历史类比"
    assert len(set(months)) == len(months)
    assert all(month <= "2025-11" for month in months)
    assert len(result["caveats"]) >= 1


# ---------------------------------------------------------------- history
def test_build_history_monthly_frame(db):
    from app.cycle.market import load_panel

    panel = load_panel(db)
    hist = build_history(panel, load_config())
    assert hist.months > 0
    assert {"DMI", "GROWTH", "INFLATION", "LIQUIDITY"} <= set(hist.scores.columns)
    assert set(hist.scores.columns) <= {"DMI", "ICI", "ECI", "GROWTH", "INFLATION", "LIQUIDITY"}
    assert hist.scores["GROWTH"].dropna().between(0, 100).all()


# ---------------------------------------------------------------- end to end
def test_run_cycle_end_to_end(db):
    result = run_cycle(db)
    assert result["status"] in ("ok", "degraded")
    assert result["asof"]
    assert set(result["composites"]) == {"DMI", "ICI", "ECI", "GROWTH", "INFLATION", "LIQUIDITY"}
    assert result["long_cycle"]["phase_id"] in {
        "normal",
        "bubble_early",
        "bubble_late",
        "top",
        "deflationary",
        "printing",
        "debasement",
    }
    assert result["short_cycle"]["state"] in ("复苏", "扩张", "过热", "放缓", "衰退")
    assert result["scenarios"]["sum"] == pytest.approx(1.0)
    assert len(result["readings"]) >= 25
    assert result["history"]["months"]
    codes = {row.code for row in db.scalars(select(Derivation).where(Derivation.run_id == result["run_id"]))}
    assert set(DERIVATION_CODES.values()) <= codes
    scenario_rows = db.scalars(select(ScenarioRun).where(ScenarioRun.run_id == result["run_id"])).all()
    assert len(scenario_rows) == 4
    assert sum(row.probability for row in scenario_rows) == pytest.approx(1.0, abs=1e-3)


def test_run_cycle_is_idempotent_and_updates_same_derivations(db):
    first = run_cycle(db)
    second = run_cycle(db)
    first_rows = db.scalars(select(Derivation).where(Derivation.run_id == first["run_id"])).all()
    second_rows = db.scalars(select(Derivation).where(Derivation.run_id == second["run_id"])).all()
    # 推导 id 由「方法 + 输入 + code」稳定决定：重跑复用同一行，并归到最新运行，
    # 因此上一轮运行不再直接持有这些推导（运行本身仍保留步骤记录）。
    assert not first_rows
    assert set(DERIVATION_CODES.values()) <= {row.code for row in second_rows}
    assert second["run_id"] != first["run_id"]


# ---------------------------------------------------------------- API
@pytest.fixture()
def client(cycle_db):
    def override():
        with cycle_db() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


def test_cycle_api_state_and_config(client):
    config = client.get("/api/v2/cycle/config")
    assert config.status_code == 200
    assert config.json()["version"] == "2.0.0"

    state = client.get("/api/v2/cycle/state")
    assert state.status_code == 200
    payload = state.json()
    assert payload["state"]["code"] == DERIVATION_CODES["state"]
    assert len(payload["indicators"]) >= 25
    assert payload["scenarios"]["value"]["sum"] == pytest.approx(1.0)
    assert payload["alerts"]["value"]["counts"]["high"] >= 0

    for path in ("indicators", "history", "analogs", "scenarios", "alerts"):
        response = client.get(f"/api/v2/cycle/{path}")
        assert response.status_code == 200, path


def test_cycle_api_layer_filter_and_run(client):
    filtered = client.get("/api/v2/cycle/indicators", params={"layer": "通胀"})
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert items and all(item["layer"] == "通胀" for item in items)

    run = client.post("/api/v2/cycle/run")
    assert run.status_code == 200
    body = run.json()
    assert body["ok"] is True
    assert body["summary"]["short"] in ("复苏", "扩张", "过热", "放缓", "衰退")
    assert len(body["summary"]["scenarios"]) == 4
