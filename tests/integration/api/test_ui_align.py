"""V2.0 UI 对齐接口（A5/A6/A1/A2/A7/A8/A10）。

独立 SQLite 文件（``data/test/m0/v2-ui-align.db``）+ 依赖覆盖，与其它用例隔离。
A1 会写 ``config/cycle.overrides.yaml`` 与 ``data/audit/cycle-config.jsonl``，
因此用 fixture 在测试后恢复/删除，绝不让测试产物留在仓库里。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cycle.config import AUDIT_PATH, OVERRIDES_PATH, load_config
from app.main import app
from app.models.base import Base
from app.models.core import (
    Brief,
    Claim,
    Document,
    DocumentSpan,
    EconomicEvent,
    Job,
    MacroObs,
    MacroSeries,
)
from app.models.v2 import AnalysisRun, Derivation, MethodRegistry
from app.platform.db import get_session
from tests.helpers import ROOT

pytestmark = [pytest.mark.integration, pytest.mark.api, pytest.mark.slow]

DB_PATH = ROOT / "data" / "test" / "m0" / "v2-ui-align.db"


def _seed(session) -> None:
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            MacroSeries(id="s-fresh", code="TEST_FRESH", name="fresh", unit="idx", freq="d"),
            MacroSeries(id="s-stale", code="TEST_STALE", name="stale", unit="idx", freq="d"),
            MacroObs(series_id="s-fresh", ts_utc=now - timedelta(days=1), value=1.0),
            MacroObs(series_id="s-stale", ts_utc=now - timedelta(days=60), value=2.0),
            Job(name="ui-align-ok", cron="0 * * * *", enabled=True, last_status="ok"),
            Job(name="ui-align-error", cron="0 * * * *", enabled=True, last_status="error"),
            MethodRegistry(
                method_id="cycle.engine.v1",
                name="EPIC-C cycle engine",
                version="1.0",
                kind="model",
                code_sha="deadbeefcafe",
            ),
            Derivation(
                id="der-state-1",
                code="cycle.state.world",
                claim="test cycle state",
                value={
                    "composites": {
                        "DMI": {"name": "DMI", "value": 55.0},
                        "ICI": {"name": "ICI", "value": 60.0},
                        "ECI": {"name": "ECI", "value": 50.0},
                        "GROWTH": {"name": "GROWTH", "value": 45.0},
                        "INFLATION": {"name": "INFLATION", "value": 40.0},
                        "LIQUIDITY": {"name": "LIQUIDITY", "value": 45.0},
                    }
                },
                asof=now,
            ),
            Document(
                id="doc-1",
                url_hash="hash-doc-1",
                url="https://example.com/ui-align",
                title="UI align fixture doc",
            ),
            Claim(
                id="claim-1",
                document_id="doc-1",
                type="fact",
                subject="fixture",
                predicate="supports",
                value=1.0,
            ),
            DocumentSpan(
                id="span-1",
                document_id="doc-1",
                start=0,
                end=4,
                quote="test",
                claim_id="claim-1",
            ),
            Brief(
                id="brief-with-evidence",
                kind="manual",
                trade_date=date(2026, 11, 17),
                markdown=(
                    "## 0. 一句话主线\n\n"
                    "> **一句话主线：** 测试主线（自动摘要，置信度标注待 M2 证据链完善）\n\n"
                    "新闻 `[D:doc-1]`\n"
                ),
                meta={"claims": 1},
            ),
            Brief(
                id="brief-plain",
                kind="manual",
                trade_date=date(2026, 11, 16),
                markdown="## plain\n\nno document refs",
                meta={},
            ),
        ]
    )
    event_ts = (now + timedelta(days=2)).replace(tzinfo=None)
    session.add_all(
        [
            EconomicEvent(
                id="ev-1",
                ts_utc=event_ts,
                name="UI-Align NFP",
                category="labor",
                country="US",
                importance=3,
                source_code="test",
                forecast=1.5,
                previous=1.2,
                actual=1.4,
                unit="%",
            ),
            EconomicEvent(
                id="ev-2",
                ts_utc=event_ts + timedelta(days=1),
                name="UI-Align CPI",
                category="inflation",
                country="US",
                importance=2,
                source_code="test",
            ),
        ]
    )
    session.commit()


@pytest.fixture(scope="module")
def align_db():
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
def db(align_db):
    with align_db() as session:
        yield session


@pytest.fixture()
def client(align_db):
    def override():
        with align_db() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
def empty_client():
    """Client backed by a schema-only in-memory database (empty-data behaviour)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)
    engine.dispose()


@pytest.fixture()
def clean_cycle_files():
    """Snapshot overrides/audit files and restore (or delete) them afterwards."""
    had_overrides = OVERRIDES_PATH.exists()
    overrides_backup = OVERRIDES_PATH.read_bytes() if had_overrides else None
    had_audit = AUDIT_PATH.exists()
    audit_backup = AUDIT_PATH.read_bytes() if had_audit else None
    load_config.cache_clear()
    yield
    if overrides_backup is None:
        OVERRIDES_PATH.unlink(missing_ok=True)
    else:
        OVERRIDES_PATH.write_bytes(overrides_backup)
    if audit_backup is None:
        AUDIT_PATH.unlink(missing_ok=True)
    else:
        AUDIT_PATH.write_bytes(audit_backup)
    load_config.cache_clear()


# ---------------------------------------------------------------- A5 coverage
def test_coverage_empty_database_is_zero_not_error(empty_client):
    response = empty_client.get("/api/system/coverage")
    assert response.status_code == 200
    payload = response.json()
    assert payload["series_total"] == 0
    assert payload["series_covered"] == 0
    assert payload["jobs_total"] == 0
    assert payload["jobs_ok"] == 0
    assert payload["data_quality_pct"] == 0.0
    assert payload["last_sync"] is None
    assert isinstance(payload["as_of"], str)
    assert "60%" in payload["method"]


def test_coverage_shape_and_math(client):
    payload = client.get("/api/system/coverage").json()
    assert payload["series_total"] == 2
    assert payload["series_covered"] == 1
    assert payload["jobs_total"] == 2
    assert payload["jobs_ok"] == 1
    # 60% × 0.5 + 40% × 0.5 = 50.0
    assert payload["data_quality_pct"] == pytest.approx(50.0)
    assert payload["last_sync"] is not None


# ---------------------------------------------------------------- A6 cycle meta
def test_cycle_meta_shape(client):
    response = client.get("/api/v2/cycle/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rule_version"] == "2.0.0"
    assert payload["calibration_n"] == 0
    assert payload["brier"] is None
    assert payload["coverage"] == {"series_covered": 1, "series_total": 2}
    assert isinstance(payload["methods"], list)
    entry = next(row for row in payload["methods"] if row["method_id"] == "cycle.engine.v1")
    assert entry["version"] == "1.0"
    assert entry["code_sha"] == "deadbeefcafe"
    calibration_date = datetime.strptime(payload["next_calibration"], "%Y-%m-%d").date()
    assert calibration_date.weekday() < 5
    assert payload["generated_at"]


# ---------------------------------------------------------------- A1 config PATCH
def test_cycle_config_patch_persists_and_audits(client, clean_cycle_files):
    response = client.patch(
        "/api/v2/cycle/config",
        json={"alerts": {"W1": 6.5}, "note": "ui alignment test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["changed"] == ["W1"]
    assert payload["overrides"]["alerts"]["W1"] == 6.5
    assert payload["version"]

    # 落盘：只写 overrides 文件，cycle.yaml 不变
    assert OVERRIDES_PATH.exists()
    written = yaml.safe_load(OVERRIDES_PATH.read_text(encoding="utf-8"))
    assert written["alerts"]["W1"] == 6.5

    # load_config 合并后，GET /config 看到的是覆盖后的阈值
    config = client.get("/api/v2/cycle/config").json()
    w1 = next(alert for alert in config["alerts"] if alert["id"] == "W1")
    assert w1["threshold"] == 6.5
    other = next(alert for alert in config["alerts"] if alert["id"] == "W2")
    assert other["threshold"] != 6.5

    # 审计行
    lines = AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(lines[-1])
    assert entry["note"] == "ui alignment test"
    assert entry["version"] == payload["version"]
    assert entry["changes"][0]["rule_id"] == "W1"


def test_cycle_config_patch_rejects_invalid(client, clean_cycle_files):
    unknown = client.patch("/api/v2/cycle/config", json={"alerts": {"NOPE": 1.0}})
    assert unknown.status_code == 400
    zero = client.patch("/api/v2/cycle/config", json={"alerts": {"W1": 0}})
    assert zero.status_code == 400
    too_big = client.patch("/api/v2/cycle/config", json={"alerts": {"W1": 2_000_000_000}})
    assert too_big.status_code == 400


# ---------------------------------------------------------------- A2 scenario
def test_cycle_scenario_is_memory_only(client, db):
    response = client.post(
        "/api/v2/cycle/scenario",
        json={"overrides": {"DMI": 70.0, "GROWTH": 40.0}},
    )
    assert response.status_code == 200
    payload = response.json()
    for side in ("baseline", "scenario"):
        assert set(payload[side]) >= {
            "composites",
            "long_cycle",
            "short_cycle",
            "scenarios",
            "sustainability",
        }
    assert payload["baseline"]["composites"]["DMI"]["value"] == 55.0
    assert payload["scenario"]["composites"]["DMI"]["value"] == 70.0
    assert payload["baseline"]["composites"]["GROWTH"]["value"] == 45.0
    assert payload["scenario"]["composites"]["GROWTH"]["value"] == 40.0
    deltas = payload["deltas"]
    assert isinstance(deltas["phase_changed"], bool)
    assert isinstance(deltas["state_changed"], bool)
    assert set(deltas["scenario_probability_delta"]) == {"S1", "S2", "S3", "S4"}
    assert abs(sum(deltas["scenario_probability_delta"].values())) < 0.01
    assert payload["applied"] == {"DMI": 70.0, "GROWTH": 40.0}

    # 纯内存：不建 run、不写推导
    assert int(db.scalar(select(func.count()).select_from(AnalysisRun)) or 0) == 0
    assert int(db.scalar(select(func.count()).select_from(Derivation)) or 0) == 1


def test_cycle_scenario_503_without_run(empty_client):
    response = empty_client.post("/api/v2/cycle/scenario", json={"overrides": {"DMI": 60}})
    assert response.status_code == 503


def test_cycle_scenario_rejects_bad_composite(client):
    unknown = client.post("/api/v2/cycle/scenario", json={"overrides": {"NOPE": 60}})
    assert unknown.status_code == 400
    out_of_range = client.post("/api/v2/cycle/scenario", json={"overrides": {"DMI": 101}})
    assert out_of_range.status_code == 400


# ---------------------------------------------------------------- A7 calendar
def test_calendar_exposes_consensus_columns(client):
    response = client.get("/api/market/calendar", params={"days": 7})
    assert response.status_code == 200
    items = response.json()["items"]
    nfp = next(item for item in items if item["name"] == "UI-Align NFP")
    assert nfp["forecast"] == 1.5
    assert nfp["previous"] == 1.2
    assert nfp["actual"] == 1.4
    assert nfp["unit"] == "%"
    cpi = next(item for item in items if item["name"] == "UI-Align CPI")
    assert cpi["forecast"] is None
    assert cpi["previous"] is None
    assert cpi["actual"] is None
    assert cpi["unit"] is None


def test_calendar_event_detail(client):
    response = client.get("/api/market/calendar/ev-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "test"
    assert payload["actual"] == 1.4
    assert payload["forecast"] == 1.5
    assert payload["unit"] == "%"
    missing = client.get("/api/market/calendar/does-not-exist")
    assert missing.status_code == 404


# ---------------------------------------------------------------- A8 eras
def test_timeline_eras_stage_fields(client):
    response = client.get("/api/v2/timeline/eras")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 6
    for era in items:
        assert "golden_age" in era
        assert "turning" in era
        assert isinstance(era["current_stage"], str) and era["current_stage"]
    multipolar = next(era for era in items if era["id"] == "multipolar")
    assert multipolar["golden_age"] is None
    assert multipolar["turning"] is None
    usa = next(era for era in items if era["id"] == "usa")
    assert usa["golden_age"] == [1945, 1971]
    assert usa["turning"] == [1971, 2008]


# ---------------------------------------------------------------- A10 briefs
def test_brief_detail_evidence_and_thesis(client):
    response = client.get("/api/briefs/brief-with-evidence")
    assert response.status_code == 200
    payload = response.json()
    # 原有字段保留
    assert {"id", "kind", "trade_date", "created_at", "markdown", "meta"} <= set(payload)
    assert payload["evidence_ids"] == ["claim-1", "span-1"]
    assert payload["main_thesis"] == "测试主线"


def test_brief_detail_without_evidence(client):
    payload = client.get("/api/briefs/brief-plain").json()
    assert payload["evidence_ids"] == []
    assert payload["main_thesis"] is None


# ------------------------------------------------- A4 cycle readings (compass)
def test_cycle_readings_contract(client):
    """8 张读数卡：缺数据时必须给 reason，不能编造数值。"""
    response = client.get("/api/v2/cycle/readings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 8
    assert payload["missing"] == sum(1 for item in payload["items"] if item["missing"])
    ids = [item["id"] for item in payload["items"]]
    assert ids == [
        "us10y",
        "us10y_real",
        "us10y_2y",
        "gold",
        "gold_silver",
        "lme_copper",
        "dxy",
        "cn_us_spread",
    ]
    for item in payload["items"]:
        assert {"id", "label", "missing", "source", "evidence"} <= set(item)
        if item["missing"]:
            assert item.get("reason")
            assert "value" not in item
        else:
            assert isinstance(item["value"], (int, float))
            assert len(item["spark"]) > 0


def test_cycle_state_normalizes_legacy_payload(client):
    """旧运行只写了 composites 时不崩：band/position/confidence 等字段补齐为稳定结构。"""

    resp = client.get("/api/v2/cycle/state")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    state = payload["state"]["value"]
    long_cycle = state["long_cycle"]
    assert isinstance(long_cycle["band"], list) and len(long_cycle["band"]) == 2
    assert long_cycle["band"][1] >= long_cycle["band"][0]
    for key in ("phase", "score", "position", "confidence", "phase_id", "next_phase"):
        assert key in long_cycle
    short_cycle = state["short_cycle"]
    for key in ("state", "raw_state", "hysteresis_held", "confidence", "growth_12m_change"):
        assert key in short_cycle
    for key in ("DMI", "ICI", "ECI", "GROWTH", "INFLATION", "LIQUIDITY"):
        assert isinstance(state["composites"][key], dict)
        assert "name" in state["composites"][key]
    assert payload["generated_at"]
    assert isinstance(payload["indicators"], list)
