"""结构性读数：数据库实时序列优先，``cycle.yaml`` 人工观测兜底。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cycle import structural
from app.cycle.config import load_config
from app.cycle.indicators import build_readings
from app.cycle.market import Panel
from app.cycle.sustainability import sustainability
from app.ingest import store
from app.ingest.contracts import MacroPoint
from app.models.base import Base

pytestmark = pytest.mark.unit


def _ts(days_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def _seed(session, code: str, value: float, *, days_ago: int = 30, freq: str = "y") -> None:
    store.upsert_macro(
        session,
        code,
        [MacroPoint(code=code, ts=_ts(days_ago), value=value)],
        freq=freq,
    )


def _seed_months(session, code: str, value: float, months: int = 12) -> None:
    points = [
        MacroPoint(code=code, ts=_ts(15 + 30 * index), value=value) for index in range(months)
    ]
    store.upsert_macro(session, code, points, freq="m")


def _seed_annual(session, code: str, value: float, years: int = 5) -> None:
    points = [
        MacroPoint(code=code, ts=_ts(30 + 365 * index), value=value) for index in range(years)
    ]
    store.upsert_macro(session, code, points, freq="y")


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'structural.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


@pytest.fixture()
def config():
    return load_config()


# ---------------------------------------------------------------- 分档映射
def test_score_from_bands_interpolates(config):
    item = next(item for item in config["manual"] if item["id"] == "us_debt_gdp")
    bands = item["bands"]
    assert structural.score_from_bands(133, bands) == 77.5
    assert structural.score_from_bands(100, bands) == 50.0
    assert structural.score_from_bands(10, bands) == 25.0
    assert structural.score_from_bands(999, bands) == 100.0

    reserve = next(item for item in config["manual"] if item["id"] == "us_reserve_share")
    assert reserve["higher_is_worse"] is False
    assert structural.score_from_bands(56.7, reserve["bands"]) == 76.6

    with pytest.raises(ValueError):
        structural.score_from_bands(1.0, [])


# ---------------------------------------------------------------- live 优先
def test_resolve_prefers_live_series(db, config):
    _seed(db, "US_DEBT_GDP", 133.0, freq="y")
    db.commit()

    resolved = structural.resolve("us_debt_gdp", db, config)
    assert resolved["live"] is True
    assert resolved["degraded"] is False
    assert resolved["value"] == 133.0
    assert resolved["unit"] == "%"
    assert resolved["evidence"] == "E2"
    assert resolved["reason"] is None
    assert "IMF" in resolved["source"]


def test_resolve_debt_ratio_fallback(db, config):
    _seed(db, "US_FED_DEBT", 40617000000000.0, days_ago=1, freq="d")
    _seed(db, "WB_US_GDP", 30600000000000.0, days_ago=30, freq="y")
    db.commit()

    resolved = structural.resolve("us_debt_gdp", db, config)
    assert resolved["live"] is True
    assert abs(resolved["value"] - 132.7353) < 0.01
    assert "近似口径" in resolved["source"]


def test_resolve_stale_annual_falls_back(db, config):
    _seed(db, "US_DEBT_GDP", 133.0, days_ago=500, freq="y")
    db.commit()

    resolved = structural.resolve("us_debt_gdp", db, config)
    assert resolved["live"] is False
    assert resolved["degraded"] is True
    assert "回落人工观测" in resolved["reason"]


def test_resolve_interest_revenue_from_mts(db, config):
    _seed_months(db, "US_MTS_INTEREST", 120.0)
    _seed_months(db, "US_MTS_RECEIPTS", 500.0)
    db.commit()

    resolved = structural.resolve("us_interest_revenue", db, config)
    assert resolved["live"] is True
    assert resolved["value"] == 24.0
    assert resolved["evidence"] == "E2"


def test_resolve_deficit_from_net_lending(db, config):
    _seed(db, "US_NET_LENDING_GDP", -5.8, freq="y")
    db.commit()

    resolved = structural.resolve("us_deficit_gdp", db, config)
    assert resolved["live"] is True
    assert resolved["value"] == 5.8


# ---------------------------------------------------------------- 人工兜底
def test_resolve_falls_back_to_yaml(db, config):
    resolved = structural.resolve("us_debt_gdp", db, config)
    assert resolved["live"] is False
    assert resolved["degraded"] is True
    assert resolved["value"] == 133.0
    assert resolved["asof"] == "2026-11-13"
    assert resolved["evidence"] == "E2"  # 沿用 YAML 的证据等级
    assert "回落人工观测" in resolved["reason"]


def test_resolve_pure_manual_indicator_is_not_degraded(db, config):
    resolved = structural.resolve("us_polarization", db, config)
    assert resolved["live"] is False
    assert resolved["degraded"] is False
    assert "纯人工口径" in resolved["reason"]


def test_resolve_reports_unconnected_cofer(db, config):
    resolved = structural.resolve("us_reserve_share", db, config)
    assert resolved["live"] is False
    assert resolved["value"] == 56.7
    assert "COFER" in resolved["reason"]


# ---------------------------------------------------------------- 引擎集成
def test_build_readings_uses_live_structural_value(db, config):
    _seed(db, "US_DEBT_GDP", 133.0, freq="y")
    db.commit()

    readings = build_readings(Panel(daily=pd.DataFrame()), config, session=db)
    manual = next(reading for reading in readings if reading.id == "us_debt_gdp")
    assert manual.layer == "结构性/实时序列"
    assert manual.evidence == "E2"
    assert manual.value == 133.0
    assert manual.score_value == 77.5

    # 无 DB 数据时行为与改造前完全一致：YAML 值 + 人工观测层
    fallback = build_readings(Panel(daily=pd.DataFrame()), config, session=None)
    legacy = next(reading for reading in fallback if reading.id == "us_debt_gdp")
    assert legacy.layer == "结构性/人工观测"
    assert legacy.value == 133
    assert legacy.score_value == 78.0


def test_sustainability_uses_live_series(db, config):
    _seed(db, "US_DEBT_GDP", 133.0, freq="y")
    _seed(db, "US_NET_LENDING_GDP", -5.8, freq="y")
    _seed_months(db, "US_MTS_INTEREST", 120.0)
    _seed_months(db, "US_MTS_RECEIPTS", 500.0)
    _seed_annual(db, "US_GDP_GROWTH", 2.0, years=5)
    _seed(db, "US10Y_REAL", 2.9, days_ago=5, freq="d")
    db.commit()

    result = sustainability(config, session=db)
    assert result["available"] is True
    assert result["mode_id"] == "fiscal_dominance"
    assert result["risk"] == "中高"
    assert result["interest_to_revenue"] == 24.0
    assert result["deficit_to_gdp"] == 5.8
    assert result["r_minus_g"] == 0.9
    assert result["evidence"] == "E2"
    assert any("数据口径与 asof" in caveat for caveat in result["caveats"])


def test_sustainability_falls_back_to_manual_values(db, config):
    result = sustainability(config, session=db)
    assert result["available"] is True
    assert result["mode_id"] == "fiscal_dominance"
    assert result["interest_to_revenue"] == 25.0
    assert result["evidence"] == "E3"
    assert any("回落人工观测" in caveat for caveat in result["caveats"])


def test_sustainability_without_session_keeps_config_path(config):
    result = sustainability(config)
    assert result["available"] is True
    assert result["mode_id"] == "fiscal_dominance"
    assert result["interest_to_revenue"] == 25.0
    assert result["evidence"] == "E2"
