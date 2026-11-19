"""EPIC 2.0 双透镜（美联储主席 × 宋鸿兵）：配置、引擎与 API。

测试使用独立 SQLite 文件 ``data/test/m0/lens-engine.db``，只 seed 透镜引擎
用到的日频/月频序列与黄金指标，避免污染其它用例共享的测试库。缺失的序列
（如 COMEX 白银库存、COFER、CIPS）正是透镜要显式标注的数据缺口。
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.lenses import router
from app.lens import engine as lens_engine
from app.lens import persona
from app.main import app
from app.models.base import Base, new_id
from app.models.core import GoldMetric, Instrument, MacroObs, MacroSeries, MarketBar
from app.models.v2 import AnalysisRun, Derivation, Forecast, Observation, RuleHit
from app.platform.db import get_session

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "test" / "m0" / "lens-engine.db"
DAYS = 420
END = "2026-11-16"
ASSETS = (
    "us_equity",
    "gold",
    "silver",
    "usd",
    "cn_equity",
    "long_bond",
    "commodities",
)

MACRO_DAILY = {
    "US2Y": 3.9,
    "US5Y": 4.1,
    "US10Y": 4.3,
    "US30Y": 4.9,
    "US10Y_REAL": 2.1,
    "US5Y_REAL": 1.9,
    "US10Y_BE": 2.2,
    "US5Y_BE": 2.1,
    "EFFR": 3.9,
    "SOFR_EFFR": 0.02,
    "JP30Y": 2.6,
    "US_FED_DEBT": 40.0e12,
}

MACRO_MONTHLY = {
    "WB_US_GDP": 29.0e12,
    "WB_US_CPI": 3.1,
    "US_MTS_DEFICIT": 0.30e12,
    "US_MTS_INTEREST": 0.09e12,
    "US_MTS_RECEIPTS": 0.42e12,
    "US_MTS_OUTLAYS": 0.72e12,
}

BARS = {
    "XAUUSD": 3300.0,
    "SPX": 6000.0,
    "NDX": 21000.0,
    "CU": 9000.0,
    "SI": 41.0,
    "BZ": 78.0,
    "CL": 74.0,
    "DXY": 100.0,
    "000300": 4000.0,
    "HSI": 24000.0,
    "USDCAD": 1.36,
    "USDCNH": 7.10,
    "USDJPY": 150.0,
}

GOLD_METRICS = {
    "GOLD_PRICE_USD": 3300.0,
    "COMEX_GOLD_INVENTORY_TONNES": 1200.0,
    "CB_GOLD_GLOBAL_TONNES": 36000.0,
    "CN_GOLD_RESERVES_USD": 190.0e9,
    "CN_GOLD_PREMIUM_PCT": 1.2,
    "SGE_GOLD_LEASE_3M_PCT": 1.8,
}


def _daily_series(start: float, step: float, n: int = DAYS) -> list[float]:
    return [start + step * index + 0.004 * math.sin(index / 9.0) for index in range(n)]


def _seed(session: Session) -> None:
    dates = pd.date_range(end=END, periods=DAYS, freq="D")
    for code, start in MACRO_DAILY.items():
        step = start * 0.0002
        series = MacroSeries(
            id=new_id(), code=code, name=code, unit="%", freq="daily", country="US"
        )
        session.add(series)
        session.flush()
        session.add_all(
            [
                MacroObs(id=new_id(), series_id=series.id, ts_utc=stamp.to_pydatetime(), value=value)
                for stamp, value in zip(dates, _daily_series(start, step), strict=True)
            ]
        )
    month_dates = pd.date_range(end=END, periods=24, freq="MS")
    for code, base in MACRO_MONTHLY.items():
        series = MacroSeries(
            id=new_id(), code=code, name=code, unit="USD", freq="monthly", country="US"
        )
        session.add(series)
        session.flush()
        session.add_all(
            [
                MacroObs(
                    id=new_id(),
                    series_id=series.id,
                    ts_utc=stamp.to_pydatetime(),
                    value=base * (1.0 + 0.002 * index),
                )
                for index, stamp in enumerate(month_dates)
            ]
        )
    for symbol, start in BARS.items():
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
                    open=value,
                    high=value * 1.005,
                    low=value * 0.995,
                    close=value,
                    volume=1000,
                )
                for stamp, value in zip(dates, _daily_series(start, start * 0.0008), strict=True)
            ]
        )
    for code, base in GOLD_METRICS.items():
        session.add_all(
            [
                GoldMetric(
                    id=new_id(),
                    code=code,
                    as_of=stamp.date(),
                    value=base * (1.0 + 0.0005 * index),
                    source="test",
                )
                for index, stamp in enumerate(month_dates)
            ]
        )
    session.commit()


@pytest.fixture(scope="module")
def lens_db():
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
def db(lens_db):
    with lens_db() as session:
        yield session


@pytest.fixture()
def client(lens_db):
    def override():
        with lens_db() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------- config
def test_config_rules_and_weights():
    cfg = lens_engine.load_config()
    weights = cfg["synthesis"]["weights"]
    # 多透镜：美联储 / 宋鸿兵 / 宏观层 / 微观层 / 9 位人物
    assert set(weights) == {
        "fed", "song", "macro", "micro",
        "dalio", "druckenmiller", "marks", "gundlach",
        "el_erian", "pozsar", "pettis", "koo", "policy_actors",
    }
    assert abs(sum(weights.values()) - 1.0) < 0.01
    assert len(cfg["fed_rules"]) == 12
    assert len(cfg["song_rules"]) == 12
    assert len(cfg["macro_rules"]) == 6
    assert len(cfg["micro_rules"]) == 6
    assert {rule["id"] for rule in cfg["fed_rules"]} == {f"F{i}" for i in range(1, 13)}
    # S6/S14 因缺可计算指标未纳入（见 config/lens.yaml 注释与 docs/27 §4.4），
    # 其余 12 条保留原始编号（S1–S5、S7–S13），不重新编号。
    assert {rule["id"] for rule in cfg["song_rules"]} == {
        "S1", "S2", "S3", "S4", "S5", "S7", "S8", "S9", "S10", "S11", "S12", "S13",
    }
    for rule in cfg["fed_rules"] + cfg["song_rules"] + cfg["macro_rules"] + cfg["micro_rules"]:
        assert rule["severity"] in {"info", "watch", "warn", "critical"}
        assert rule["when"].get("all") or rule["when"].get("any")
        assert rule["message"] and rule["falsifier"]
    gaps = {gap["id"] for gap in cfg["data_gaps"]}
    assert {"song.comex_silver", "song.reserve_share", "fed.hy_oas", "macro.m2_history"} <= gaps


def test_persona_specs_load_and_validate():
    specs = persona.load_specs()
    assert {spec.id for spec in specs} == {
        "dalio", "druckenmiller", "marks", "gundlach",
        "el_erian", "pozsar", "pettis", "koo", "policy_actors",
    }
    for spec in specs:
        assert issues_problem(spec) == [], f"{spec.id} 配置有问题：{issues_problem(spec)}"
        assert 8 <= len(spec.readings) <= 16
        assert 8 <= len(spec.rules) <= 12
        assert set(spec.scores) == {
            "us_equity", "gold", "silver", "usd", "cn_equity", "long_bond", "commodities",
        }
        assert spec.key_question and spec.thesis


def issues_problem(spec) -> list[str]:
    """只做结构性校验（不检查列名，允许测试库缺少部分序列）。"""
    return [issue for issue in persona.validate_spec(spec) if "unknown column" not in issue]


# ---------------------------------------------------------------- engine
def test_run_lenses_end_to_end(db):
    result = lens_engine.run_lenses(db)

    assert result["run"]["status"] in {"ok", "degraded"}
    assert result["run"]["id"]
    assert result["config_version"] == "2.0.0"

    fed = result["fed"]
    song = result["song"]
    assert len(fed["readings"]) == 21
    assert len(song["readings"]) == 31
    assert 0 <= fed["state"]["stance"] <= 100
    assert fed["state"]["regime"]["id"] in {
        "reflation",
        "stagflation",
        "goldilocks",
        "deflation",
    }
    assert fed["state"]["fed_put"]["id"] in {"at_strike", "near", "far"}
    assert song["state"]["phase"]["id"] in {"hot", "cold", "transition", "reverse"}
    assert song["state"]["dollar_heart"]["id"] in {"normal", "murmur", "angina", "infarction"}
    assert song["state"]["gold_regime"]["id"] in {"strategic", "accumulate", "trade", "avoid"}

    rules = result["rules"]
    assert len(rules["fed"]) == 12
    assert len(rules["song"]) == 12
    assert len(rules["macro"]) == 6
    assert len(rules["micro"]) == 6
    assert {item["status"] for item in rules["fed"]} <= {"fired", "miss", "unknown"}
    # S9 依赖 COMEX 白银库存，测试库没有该序列，必须诚实地标 unknown。
    s9 = next(item for item in rules["song"] if item["id"] == "S9")
    assert s9["status"] == "unknown"

    # 宏观层 / 微观层
    macro = result["macro"]
    micro = result["micro"]
    assert macro["state"]["regime"]["id"] in {
        "reflation", "stagflation", "goldilocks", "deflation",
    }
    assert len(macro["readings"]) == 14
    assert len(micro["readings"]) == 14
    assert set(macro["scores"]) == set(ASSETS)
    assert set(micro["scores"]) == set(ASSETS)

    # 9 份人物透镜：读数可能因测试库缺列而降级，但结构与评分必须齐备。
    personas = result["personas"]
    assert len(personas) == len(persona.load_specs())
    for item in personas:
        assert item["state"]["lean"]["score"] == item["state"]["lean"]["score"]  # 非 NaN
        assert -2.0 <= item["state"]["lean"]["score"] <= 2.0
        assert len(item["state"]["fired_rules"]) <= len(item["rules"])
        assert set(item["scores"]) == set(ASSETS)

    synthesis = result["synthesis"]
    assert synthesis["consensus_count"] >= 0
    assert len(synthesis["assets"]) == 7
    assert synthesis["lens_count"] == 13
    assert set(synthesis["weights"]) == {
        "fed", "song", "macro", "micro", "dalio", "druckenmiller", "marks",
        "gundlach", "el_erian", "pozsar", "pettis", "koo", "policy_actors",
    }
    assert synthesis["outlook"]["horizon_days"] == 90
    assert synthesis["outlook"]["invalidators"]
    assert 0.3 <= synthesis["confidence"] <= 0.85
    assert synthesis["rule_metrics"], "synthesis 必须落库 rule_metrics 供只读接口重建规则"
    assert synthesis["layer_metrics"]["macro"], "宏观层指标需落库，供只读接口重建规则"

    # 决策要素：每个资产都要有止损/仓位/权重说明，组合层给出总敞口与组合风险。
    portfolio = synthesis["portfolio"]
    assert portfolio["basis"]
    assert 0 <= portfolio["gross_weight_pct"] <= 100
    assert 0 <= portfolio["cash_weight_pct"] <= 100
    assert portfolio["portfolio_risk_pct"] >= 0
    assert len(portfolio["rules"]) >= 4
    assert isinstance(portfolio["positions"], list)
    for asset in synthesis["assets"]:
        plan = asset["plan"]
        assert plan["side"] in {"long", "short", "flat"}
        assert 1.5 <= plan["stop_pct"] <= 8.0
        assert plan["weight_pct"] >= 0
        if plan["actionable"]:
            assert abs(asset["consensus"]) >= 0.25
            assert plan["risk_pct"] >= 0.3
            assert plan["weight_pct"] <= 30.0
            assert plan["stop_note"]
        else:
            assert plan["weight_pct"] == 0

    codes = {
        row.code
        for row in db.scalars(
            select(Derivation).where(Derivation.run_id == result["run"]["id"])
        )
    }
    assert {"lens.fed.state", "lens.song.state", "lens.macro.state",
            "lens.micro.state", "lens.synthesis"} <= codes
    assert sum(1 for code in codes if code.startswith("lens.persona.")) == len(personas)

    observations = db.scalars(select(Observation).where(Observation.code.like("lens.%"))).all()
    # 只记录有值的读数（缺失项留给 data_gaps 与 reading.missing_reason），
    # 加上 7 类资产的共识分与各透镜 lean；因此数量少于全部读数之和。
    assert len(observations) >= 40
    prefixes = {row.code.split(".")[1] for row in observations}
    persona_ids = {spec.id for spec in persona.load_specs()}
    assert prefixes <= {"fed", "song", "macro", "micro", "score"} | persona_ids
    assert {"fed", "song", "score"} <= prefixes

    hits = db.scalars(select(RuleHit).where(RuleHit.run_id == result["run"]["id"])).all()
    # 规则命中统一前缀 lens.（降级原因记为 degrade.lens.*）。
    assert hits, "至少应写入一条规则命中"
    assert all(
        hit.rule_id.startswith("lens.") or hit.rule_id.startswith("degrade.lens.")
        for hit in hits
    )


def test_run_lenses_is_idempotent(db):
    first = lens_engine.run_lenses(db)
    second = lens_engine.run_lenses(db)
    assert first["run"]["id"] != second["run"]["id"]
    rows = db.scalars(select(Derivation).where(Derivation.code.like("lens.%"))).all()
    # 推导 id 由方法+code+输入稳定决定，重跑 upsert 同一行并归到最新运行。
    # 13 套透镜 + 1 条合成 = 14 条推导。
    assert len(rows) == 1 + 2 + 2 + len(persona.load_specs())
    assert {row.run_id for row in rows} == {second["run"]["id"]}
    states = db.scalars(select(AnalysisRun).where(AnalysisRun.kind == "lens")).all()
    assert len(states) >= 2


# ---------------------------------------------------------------- API
def test_api_state_payload(client):
    response = client.get("/api/v2/lenses/state", params={"refresh": "true"})
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["config_version"] == "2.0.0"
    assert payload["run"]["status"] in {"ok", "degraded"}
    assert payload["disclaimer"]

    assert payload["fed"]["method_id"] == "lens.fed.v1"
    assert payload["song"]["method_id"] == "lens.song.v1"
    assert len(payload["fed"]["readings"]) == 21
    assert len(payload["song"]["readings"]) == 31
    assert payload["fed"]["derivation"]["code"] == "lens.fed.state"
    assert payload["song"]["derivation"]["code"] == "lens.song.state"

    # 宏观层 / 微观层 / 人物透镜对外暴露
    assert payload["macro"] is not None and payload["micro"] is not None
    assert len(payload["macro"]["readings"]) == 14
    assert len(payload["micro"]["readings"]) == 14
    assert payload["macro"]["state"]["regime"]["label"]
    assert len(payload["personas"]) == len(persona.load_specs())
    first = payload["personas"][0]
    assert {"id", "name", "state", "scores", "catalog"} <= set(first)
    assert first["state"]["lean"]["label"]
    assert first["state"]["coverage"]["total"] >= 8

    assert len(payload["rules"]["fed"]) == 12
    assert len(payload["rules"]["song"]) == 12
    assert len(payload["rules"]["macro"]) == 6
    assert len(payload["rules"]["micro"]) == 6
    assert len(payload["rules"]["personas"]) == len(payload["personas"])
    assert {item["id"] for item in payload["rules"]["fed"]} == {f"F{i}" for i in range(1, 13)}
    assert {item["id"] for item in payload["rules"]["song"]} == {
        "S1", "S2", "S3", "S4", "S5", "S7", "S8", "S9", "S10", "S11", "S12", "S13",
    }
    s9 = next(item for item in payload["rules"]["song"] if item["id"] == "S9")
    assert s9["status"] == "unknown"

    assert payload["synthesis"]["derivation"]["code"] == "lens.synthesis"
    assert len(payload["synthesis"]["assets"]) == 7
    assert payload["synthesis"]["lens_count"] == 13
    assert payload["data_gaps"]

    # 二次读取走落库路径，仍能重建全部规则（含未命中项）与人物透镜。
    again = client.get("/api/v2/lenses/state").json()
    assert len(again["rules"]["fed"]) == 12
    assert len(again["rules"]["song"]) == 12
    assert len(again["rules"]["macro"]) == 6
    assert len(again["rules"]["micro"]) == 6
    assert len(again["personas"]) == len(payload["personas"])
    assert again["asof"] == payload["asof"]


def test_api_run_and_forecasts(client):
    run = client.post("/api/v2/lenses/run")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["run"]["status"] in {"ok", "degraded"}

    codes = client.get("/api/v2/lenses/forecast-codes")
    assert codes.status_code == 200
    assert any(item["asset"] == "gold" for item in codes.json()["items"])

    created = client.post(
        "/api/v2/lenses/forecasts",
        json={
            "asset": "gold",
            "direction": "up",
            "horizon_days": 63,
            "probability": 0.62,
            "notes": "测试：实际利率见顶 + 央行购金",
        },
    )
    assert created.status_code == 201, created.text
    forecast = created.json()
    assert forecast["asset"] == "gold"
    assert forecast["code"] == "lens.gold"
    assert forecast["direction"] == "up"
    assert forecast["status"] == "open"
    assert forecast["target_date"]

    listed = client.get("/api/v2/lenses/forecasts").json()
    assert any(item["id"] == forecast["id"] for item in listed["items"])
    assert len(listed["open"]) >= 1

    bad = client.post(
        "/api/v2/lenses/forecasts",
        json={"asset": "gold", "direction": "sideways", "horizon_days": 30},
    )
    assert bad.status_code == 422

    row = client.get("/api/v2/lenses/state").json()
    assert row["fed"]["derivation"]["id"]


def test_api_ping_reports_llm_availability(client):
    response = client.get("/api/v2/lenses/ping")
    assert response.status_code == 200
    payload = response.json()
    assert "available" in payload
    if not payload["available"]:
        response = client.post(
            "/api/v2/lenses/commentary", json={"question": "黄金现在能不能配？"}
        )
        assert response.status_code == 503


def test_lens_forecast_settles_through_ledger(lens_db, db):
    """透镜预测进入统一台账后，到期必须能按标的收盘价结算（不能被永久 pending）。"""
    from datetime import timedelta

    from app.ledger.engine import score_forecasts

    row = lens_engine.create_forecast(
        db, asset="gold", direction="up", horizon_days=21, baseline_value=1.0
    )
    row.target_date = date.today() - timedelta(days=1)
    db.commit()

    score_forecasts(db, metrics={})
    db.commit()
    db.refresh(row)

    assert row.status == "resolved"


def test_position_layer_scales_down_to_risk_budget():
    """组合权重必须被两个上限约束住：总敞口 ≤ 80%、组合风险 ≤ 6%。"""
    from app.lens import position

    rows = [
        {"id": "us_equity", "label": "美股", "symbol": "SPX", "last": 5000.0,
         "consensus": 1.8, "direction": "up", "agreement": "共振多"},
        {"id": "gold", "label": "黄金", "symbol": "XAUUSD", "last": 3000.0,
         "consensus": -1.6, "direction": "down", "agreement": "共振空"},
        {"id": "silver", "label": "白银", "symbol": "SI", "last": 40.0,
         "consensus": 1.2, "direction": "up", "agreement": "共振多"},
        {"id": "usd", "label": "美元", "symbol": "DXY", "last": 100.0,
         "consensus": 0.1, "direction": "flat", "agreement": "弱信号"},
    ]
    portfolio = position.build_decisions(rows, panel=None)

    assert portfolio["gross_weight_pct"] <= position.MAX_GROSS_PCT + 0.05
    assert portfolio["portfolio_risk_pct"] <= position.MAX_PORTFOLIO_RISK_PCT + 0.05
    assert portfolio["cash_weight_pct"] >= 0
    flat = next(row for row in rows if row["id"] == "usd")["plan"]
    assert flat["actionable"] is False
    long_plan = next(row for row in rows if row["id"] == "us_equity")["plan"]
    assert long_plan["actionable"] is True
    assert long_plan["side"] == "long"
    assert long_plan["stop_level"] < rows[0]["last"]
    short_plan = next(row for row in rows if row["id"] == "gold")["plan"]
    assert short_plan["side"] == "short"
    assert short_plan["stop_level"] > rows[1]["last"]


def test_lens_synthesis_claim_mentions_portfolio(db):
    """合成推导的 claim 必须把组合敞口写进结论，而不是只藏在 value 里。"""
    result = lens_engine.run_lenses(db)
    row = db.scalars(select(Derivation).where(Derivation.code == "lens.synthesis")).first()
    assert row is not None
    assert "组合建议总敞口" in row.claim
    assert result["synthesis"]["portfolio"]["gross_weight_pct"] >= 0
