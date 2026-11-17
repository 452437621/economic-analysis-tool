"""世界长河（M3）：数据集、入库幂等、推导与接口形状。

数据集测试直接对 ``dataset.py`` 做完整性校验；入库测试使用独立 SQLite
（``data/test/m3/timeline.db``），避免污染其它用例共享的测试库。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.base import Base
from app.models.v2 import Derivation, PowerIndex, TimelineEvent
from app.platform.db import get_session
from app.timeline import dataset
from app.timeline.engine import run_timeline, seed_events, seed_powers

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "test" / "m3" / "timeline.db"

CODES = {"timeline.position", "timeline.power.shift", "timeline.catalog"}


@pytest.fixture(scope="module")
def timeline_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture()
def db(timeline_db):
    with timeline_db() as session:
        yield session


@pytest.fixture()
def client(timeline_db):
    def override():
        with timeline_db() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)


# -- 数据集完整性 -----------------------------------------------------------


def test_dataset_events_are_well_formed():
    assert len(dataset.EVENTS) >= 60
    seen: set[tuple[int, str]] = set()
    for item in dataset.EVENTS:
        year = int(item["year"])
        assert 1400 <= year <= 2030, item["title"]
        assert item["layer"] in {"L", "B", "S", "E"}, item["title"]
        assert item["grade"] in {"A", "B", "C"}, item["title"]
        assert item["category"] in dataset.CATEGORY_LABELS, item["title"]
        assert item["power"] in dataset.POWER_LABELS, item["title"]
        key = (year, item["title"])
        assert key not in seen, f"duplicate event: {key}"
        seen.add(key)
        if item["grade"] == "A":
            assert str(item.get("source", "")).startswith("http"), f"A 级事件必须有来源: {item['title']}"


def test_dataset_span_and_eras():
    years = [int(item["year"]) for item in dataset.EVENTS]
    assert min(years) <= 1500
    assert max(years) >= 2026
    assert len(dataset.ERAS) == 6
    ids = {era["id"] for era in dataset.ERAS}
    assert {"china_ming", "iberia", "netherlands", "uk", "usa", "multipolar"} <= ids
    for era in dataset.ERAS:
        assert era["lesson"], era["id"]
        assert int(era["rise"]) <= int(era["peak"])


def test_dataset_power_series():
    gdp_powers = {item["power"] for item in dataset.GDP_SHARE}
    assert {"china", "usa", "uk"} <= gdp_powers
    china_1820 = [item for item in dataset.GDP_SHARE if item["power"] == "china" and item["year"] == 1820]
    assert china_1820 and china_1820[0]["value"] == pytest.approx(28.60, abs=0.01)
    us_1870 = [item for item in dataset.GDP_SHARE if item["power"] == "usa" and item["year"] == 1870]
    assert us_1870 and us_1870[0]["value"] == pytest.approx(9.85, abs=0.01)
    usd_2026 = [item for item in dataset.RESERVE_SHARE if item["currency"] == "USD" and item["year"] == 2026]
    assert usd_2026 and usd_2026[0]["value"] == pytest.approx(56.70, abs=0.01)


def test_dataset_lessons_and_analogs():
    assert [item["id"] for item in dataset.LESSONS] == [f"H{i}" for i in range(1, 11)]
    assert len(dataset.ANALOGS) == 3
    for analog in dataset.ANALOGS:
        assert 0 < analog["similarity"] < 1
        assert analog["similar"] and analog["different"]
    assert len(dataset.DIMENSIONS) == 6


# -- 入库与推导 -------------------------------------------------------------


def test_seed_events_is_idempotent(db):
    first = seed_events(db)
    db.commit()
    assert first["created"] == len(dataset.EVENTS)
    second = seed_events(db)
    db.commit()
    assert second["created"] == 0
    assert second["updated"] == len(dataset.EVENTS)
    assert db.scalar(select(func.count()).select_from(TimelineEvent)) == len(dataset.EVENTS)


def test_seed_powers_is_idempotent(db):
    total = len(dataset.GDP_SHARE) + len(dataset.RESERVE_SHARE)
    first = seed_powers(db)
    db.commit()
    assert first["total"] == total
    second = seed_powers(db)
    db.commit()
    assert second["created"] == 0
    assert db.scalar(select(func.count()).select_from(PowerIndex)) == total


def test_run_timeline_end_to_end(db):
    result = run_timeline(db)
    assert result["status"] in {"ok", "degraded"}
    assert result["events"] == len(dataset.EVENTS)
    assert result["run_id"]
    codes = {row.code for row in db.scalars(select(Derivation).where(Derivation.code.in_(CODES))).all()}
    assert codes == CODES
    position = db.scalar(select(Derivation).where(Derivation.code == "timeline.position"))
    assert position is not None
    assert position.evidence_grade == "E2"
    value = position.value or {}
    assert len(value["dimensions"]) == 6
    assert len(value["analogs"]) == 3
    # 有周期引擎结果时，五维会带上实时值；没有时应显式降级而不是编造
    assert value.get("cycle") is None or "composites" in value["cycle"]


def test_run_timeline_twice_keeps_single_catalog(db):
    run_timeline(db)
    run_timeline(db)
    assert db.scalar(select(func.count()).select_from(TimelineEvent)) == len(dataset.EVENTS)
    catalog = db.scalars(select(Derivation).where(Derivation.code == "timeline.catalog")).all()
    assert len(catalog) == 1


# -- 接口 -----------------------------------------------------------------


def test_timeline_overview(client):
    payload = client.get("/api/v2/timeline/overview")
    assert payload.status_code == 200
    data = payload.json()
    assert data["counts"]["events"] == len(dataset.EVENTS)
    assert data["counts"]["eras"] == 6
    assert len(data["eras"]) == 6
    assert len(data["events"]) == len(dataset.EVENTS)
    assert data["events"][0]["title"]
    assert data["powers"]["gdp"] and data["powers"]["reserve"]
    assert data["position"] is not None
    assert data["lessons"][0]["id"] == "H1"


def test_timeline_events_filters(client):
    layer = client.get("/api/v2/timeline/events", params={"layer": "S"})
    assert layer.status_code == 200
    items = layer.json()["items"]
    assert items and all(item["layer"] == "S" for item in items)

    search = client.get("/api/v2/timeline/events", params={"q": "黄金"})
    assert search.status_code == 200
    assert search.json()["total"] >= 1

    era = client.get("/api/v2/timeline/events", params={"era": "netherlands"})
    assert era.status_code == 200
    assert era.json()["total"] >= 3

    bad = client.get("/api/v2/timeline/events", params={"era": "nope"})
    assert bad.status_code == 404


def test_timeline_position_and_run(client):
    position = client.get("/api/v2/timeline/position")
    assert position.status_code == 200
    assert position.json()["code"] == "timeline.position"

    run = client.post("/api/v2/timeline/run")
    assert run.status_code == 200
    body = run.json()
    assert body["ok"] is True
    assert body["events"] == len(dataset.EVENTS)
    assert body["run_id"]
