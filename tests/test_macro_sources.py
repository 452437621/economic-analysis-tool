"""结构性宏观数据源（离线）：IMF DataMapper / 美国财政部 Fiscal Data / 世界银行 /
美联储 H.4.1 资产负债表 / 美联储 H.6 货币供应。

所有网络调用都被 monkeypatch 掉，只验证解析、落库契约与降级行为。
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ingest import pipeline
from app.ingest.providers import fed_h6, fed_h41, imf_datamapper, treasury_fiscal, worldbank
from app.ingest.providers.errors import ProviderError
from app.models.base import Base
from app.models.core import MacroObs, MacroSeries

#: 每个 IMF 指标在美国/中国上的假年值（2024 已发布，2027 是预测应被过滤）。
IMF_VALUES = {
    "GGXWDG_NGDP": {"USA": {"2024": 123.0, "2027": 140.0}, "CHN": {"2024": 88.0}},
    "GGXCNL_NGDP": {"USA": {"2024": -5.8}, "CHN": {"2024": -6.5}},
    "NGDP_RPCH": {"USA": {"2024": 2.8}, "CHN": {"2024": 5.0}},
    "PCPIPCH": {"USA": {"2024": 2.9}, "CHN": {"2024": 0.3}},
    "LUR": {"USA": {"2024": 4.0}, "CHN": {"2024": 5.1}},
    "GGR_NGDP": {"USA": {"2024": 17.0}, "CHN": {"2024": 25.0}},
    "GGX_NGDP": {"USA": {"2024": 23.0}, "CHN": {"2024": 33.0}},
}

DEBT_ROW = {"record_date": "2026-11-16", "tot_pub_debt_out_amt": "40617000000000.00"}


def _recent_months(count: int = 12) -> list[str]:
    """最近 ``count`` 个已结束的月份，格式 YYYY-MM。"""
    today = date.today()
    year, month = today.year, today.month
    months: list[str] = []
    for _ in range(count):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        months.append(f"{year:04d}-{month:02d}")
    return list(reversed(months))


def fake_imf_json(url: str, *, timeout: float = 20.0) -> dict:
    assert timeout == 20.0
    indicator = url.rstrip("/").split("/")[-2]
    return {"values": {indicator: IMF_VALUES[indicator]}}


def fake_treasury_rows(url: str, *, timeout: float = 30.0) -> list[dict]:
    assert timeout == 30.0
    if "debt_to_penny" in url:
        return [DEBT_ROW]
    rows: list[dict] = []
    for month in _recent_months():
        day = f"{month}-01"
        rows.append(
            {
                "record_date": day,
                "line_code_nbr": "120",
                "classification_desc": "Total",
                "current_month_rcpt_outly_amt": "500.0",
            }
        )
        rows.append(
            {
                "record_date": day,
                "line_code_nbr": "320",
                "classification_desc": "Net Interest",
                "current_month_rcpt_outly_amt": "120.0",
            }
        )
        rows.append(
            {
                "record_date": day,
                "line_code_nbr": "340",
                "classification_desc": "Total",
                "current_month_rcpt_outly_amt": "560.0",
            }
        )
        rows.append(
            {
                "record_date": day,
                "line_code_nbr": "130",
                "classification_desc": "Net Outlays",
                "current_month_rcpt_outly_amt": "null",
            }
        )
    return rows


def fake_worldbank_json(url: str, *, timeout: float = 45.0) -> list:
    assert timeout == 45.0
    assert "GC.DOD.TOTL.GD.ZS" in url or "NY.GDP.MKTP.CD" in url
    return [
        {"page": 1, "pages": 1},
        [
            {"date": "2024", "value": 29.0},
            {"date": "2023", "value": None},
        ],
    ]


@pytest.fixture()
def macro_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'macro.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _obs_count(factory) -> int:
    with factory() as session:
        return int(session.scalar(select(func.count()).select_from(MacroObs)) or 0)


def _stub_fed(monkeypatch, *, boom: bool = False) -> None:
    """美联储 H.4.1 / H.6 的抓取函数替换（离线）。

    H.4.1/H.6 只解析官方当前页，测试里必须 patch，否则会真实联网并把
    ``stats["obs"]``/``stats["series"]`` 抬高。
    """

    if boom:
        def _raise(*args, **kwargs):
            raise ProviderError("network down")

        monkeypatch.setattr(fed_h41, "fetch_current", _raise)
        monkeypatch.setattr(fed_h41, "fetch_history", _raise)
        monkeypatch.setattr(fed_h6, "fetch_current", _raise)
        monkeypatch.setattr(fed_h6, "fetch_history", _raise)
        return

    monkeypatch.setattr(
        fed_h41,
        "fetch_current",
        lambda **kwargs: {"asof": date(2026, 11, 11), "values": {"US_FED_ASSETS": 6.7e12}},
    )
    monkeypatch.setattr(fed_h41, "fetch_history", lambda **kwargs: {})
    monkeypatch.setattr(
        fed_h6,
        "fetch_current",
        lambda **kwargs: {"US_M2": {date(2026, 9, 1): 23.4e12}},
    )
    monkeypatch.setattr(fed_h6, "fetch_history", lambda **kwargs: {})


def _latest_value(session, code: str) -> float | None:
    return session.scalar(
        select(MacroObs.value)
        .join(MacroSeries, MacroObs.series_id == MacroSeries.id)
        .where(MacroSeries.code == code)
        .order_by(MacroObs.ts_utc.desc())
        .limit(1)
    )


# ---------------------------------------------------------------- 解析路径
def test_imf_and_worldbank_parsers(monkeypatch):
    monkeypatch.setattr(imf_datamapper, "_get_json", fake_imf_json)
    data = imf_datamapper.fetch("GGXWDG_NGDP", ["USA", "CHN"])
    assert data["USA"] == {"2024": 123.0, "2027": 140.0}
    assert data["CHN"] == {"2024": 88.0}

    monkeypatch.setattr(worldbank, "_get_json", fake_worldbank_json)
    years = worldbank.fetch("GC.DOD.TOTL.GD.ZS", "USA")
    assert years == {"2024": 29.0}  # None 已被过滤


def test_treasury_parsers(monkeypatch):
    monkeypatch.setattr(treasury_fiscal, "_get_rows", fake_treasury_rows)
    debt = treasury_fiscal.fetch_debt_to_penny(limit=5)
    assert debt and debt[0]["tot_pub_debt_out_amt"] == DEBT_ROW["tot_pub_debt_out_amt"]
    mts = treasury_fiscal.fetch_mts(table=9, page_size=60)
    line_codes = {str(row["line_code_nbr"]) for row in mts}
    assert {"120", "320", "340"}.issubset(line_codes)
    with pytest.raises(ProviderError):
        treasury_fiscal.fetch_mts(table=99)


# ---------------------------------------------------------------- collect_macro
def test_collect_macro_persists_contract_series(macro_db, monkeypatch):
    monkeypatch.setattr(imf_datamapper, "_get_json", fake_imf_json)
    monkeypatch.setattr(treasury_fiscal, "_get_rows", fake_treasury_rows)
    monkeypatch.setattr(worldbank, "_get_json", fake_worldbank_json)
    _stub_fed(monkeypatch)

    stats = pipeline.collect_macro()
    assert stats["obs"] > 0
    assert stats["series"] >= 10

    with macro_db() as session:
        assert _latest_value(session, "US_DEBT_GDP") == 123.0
        assert _latest_value(session, "US_NET_LENDING_GDP") == -5.8
        assert _latest_value(session, "CN_DEBT_GDP") == 88.0
        assert _latest_value(session, "US_FED_DEBT") == 40617000000000.0
        assert _latest_value(session, "US_MTS_RECEIPTS") == 500.0
        assert _latest_value(session, "US_MTS_INTEREST") == 120.0
        assert _latest_value(session, "US_MTS_OUTLAYS") == 560.0
        assert _latest_value(session, "US_MTS_DEFICIT") == 60.0
        assert _latest_value(session, "WB_US_DEBT_GDP") == 29.0
        # 年频观测落在 12-31，且预测年份（2027）不落库
        us_debt_dates = session.scalars(
            select(MacroObs.ts_utc)
            .join(MacroSeries, MacroObs.series_id == MacroSeries.id)
            .where(MacroSeries.code == "US_DEBT_GDP")
        ).all()
        assert [ts.date().isoformat() for ts in us_debt_dates] == ["2024-12-31"]


def test_collect_macro_is_idempotent(macro_db, monkeypatch):
    monkeypatch.setattr(imf_datamapper, "_get_json", fake_imf_json)
    monkeypatch.setattr(treasury_fiscal, "_get_rows", fake_treasury_rows)
    monkeypatch.setattr(worldbank, "_get_json", fake_worldbank_json)
    _stub_fed(monkeypatch)

    pipeline.collect_macro()
    first = _obs_count(macro_db)
    pipeline.collect_macro()
    assert _obs_count(macro_db) == first


def test_collect_macro_degrades_without_raising(macro_db, monkeypatch):
    def boom(*args, **kwargs):
        raise ProviderError("network down")

    monkeypatch.setattr(imf_datamapper, "_get_json", boom)
    monkeypatch.setattr(treasury_fiscal, "_get_rows", boom)
    monkeypatch.setattr(worldbank, "_get_json", boom)
    _stub_fed(monkeypatch, boom=True)

    stats = pipeline.collect_macro()
    assert stats["obs"] == 0
    assert stats["series"] == 0
    assert stats["degraded_reasons"]
    assert any("network down" in reason for reason in stats["degraded_reasons"])
    assert _obs_count(macro_db) == 0
