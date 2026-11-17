"""Gold monitoring tests: offline provider parsers, scoring and API contracts."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import openpyxl
import pytest
import xlrd
from fastapi.testclient import TestClient

from app.gold import providers
from app.gold.registry import INDICATORS, manual_codes
from app.gold.scoring import compute_gold_score
from app.main import app
from app.models.core import GoldMetric
from app.platform.db import SessionLocal, init_db


class _FakeResponse:
    def __init__(self, *, content: bytes = b"", text: str = "", payload: dict | None = None, status: int = 200):
        self.content = content
        self.text = text
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class _FakeClient:
    """上下文管理器替身：按 URL 返回预置响应。"""

    responses: dict[str, _FakeResponse] = {}

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, **kwargs):
        for key, response in self.responses.items():
            if key in url:
                return response
        return _FakeResponse(status=404)


def _xlsx_bytes(rows: list[tuple]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(("London Vault Holdings Data", None, None))
    sheet.append(("Month End", "Gold", "Silver"))
    sheet.append((None, "Troy Ounces ('000s)", "Troy Ounces ('000s)"))
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _cftc_zip(rows: list[dict]) -> bytes:
    header = list(rows[0].keys()) if rows else []
    text = ",".join(f'"{name}"' for name in header) + "\n"
    for row in rows:
        text += ",".join(f'"{row[name]}"' for name in header) + "\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("f_year.txt", text)
    return buffer.getvalue()


def test_registry_is_consistent():
    assert len(INDICATORS) >= 19
    assert "LBMA_GOLD_TONNES" in INDICATORS
    assert "ETF_GLOBAL_TONNES" in INDICATORS
    assert "COT_MONEY_NET" in INDICATORS
    manual = manual_codes()
    # 已找到自动数据源的手动指标应转入自动采集
    assert "CB_GOLD_GLOBAL_TONNES" not in manual
    assert "COMEX_GOLD_INVENTORY_TONNES" not in manual
    assert "MM_BANK_GOLD_NET" not in manual
    # BIS 官方无公开序列，仍保留手动录入
    assert "BIS_GOLD_LEASE_RATE" in manual or "BIS_GOLD_SWAP_USD" in manual
    for item in INDICATORS.values():
        assert item.weight >= 0
        assert item.direction in (1, -1)
        assert item.category


def test_lbma_provider_parses_monthly_holdings(monkeypatch):
    page = _FakeResponse(
        text='<a href="https://cdn.lbma.org.uk/downloads/LBMA-London-Vault-Holdings-Data-October-2026.xlsx">xlsx</a>'
    )
    xlsx = _FakeResponse(
        content=_xlsx_bytes([("2026-10", 316682, 928810.59), ("2026-09", 315756, 931898)])
    )
    _FakeClient.responses = {"london-vault-data": page, ".xlsx": xlsx}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_lbma_vault()
    assert result.ok, result.error
    gold = [record for record in result.records if record["code"] == "LBMA_GOLD_TONNES"]
    assert len(gold) == 2
    # 316,682 koz ≈ 9,849 tonnes
    assert 9800 < gold[0]["value"] < 9900


def test_wgc_etf_provider_sums_regions(monkeypatch):
    payload = {
        "chartData": {
            "data": {
                # 持仓总量按周度序列取（上游每周更新）；月度序列只用来算月流量
                "Weekly": {
                    "tonnes": {
                        "columns": ["Date", "North America", "Europe", "Asia", "Other", "Gold, US$/oz"],
                        "set": [
                            [1735689600000, 2000.0, 1400.0, 500.0, 70.0, 4000.0],
                            [1738368000000, 2010.0, 1410.0, 505.0, 72.0, 4100.0],
                        ],
                    }
                },
                "Monthly": {
                    "tonnes": {
                        "columns": ["Date", "North America", "Europe", "Asia", "Other", "Gold, US$/oz"],
                        "set": [
                            [1735689600000, 2000.0, 1400.0, 500.0, 70.0, 4000.0],
                            [1738368000000, 2010.0, 1410.0, 505.0, 72.0, 4100.0],
                        ],
                    }
                },
            }
        }
    }
    _FakeClient.responses = {"holdings-chart2": _FakeResponse(payload=payload)}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_wgc_etf()
    assert result.ok, result.error
    holdings = [record for record in result.records if record["code"] == "ETF_GLOBAL_TONNES"]
    flows = [record for record in result.records if record["code"] == "ETF_FLOW_1M_TONNES"]
    assert len(holdings) == 2
    assert holdings[-1]["value"] == 2010.0 + 1410.0 + 505.0 + 72.0
    assert flows and flows[-1]["value"] == pytest.approx(27.0)


def test_wgc_etf_holdings_prefer_weekly_series(monkeypatch):
    """持仓总量必须取周度序列：月度序列会永远滞后一个月（2026-11 的真实故障）。"""
    payload = {
        "chartData": {
            "data": {
                "Weekly": {
                    "tonnes": {
                        "set": [
                            [1763424000000, 2100.0, 1500.0, 540.0, 80.0, 4100.0],
                        ]
                    }
                },
                "Monthly": {
                    "tonnes": {
                        "set": [
                            [1761868800000, 2000.0, 1400.0, 500.0, 70.0, 4000.0],
                            [1764547200000, 2050.0, 1450.0, 520.0, 75.0, 4050.0],
                        ]
                    }
                },
            }
        }
    }
    _FakeClient.responses = {"holdings-chart2": _FakeResponse(payload=payload)}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_wgc_etf()
    assert result.ok, result.error
    holdings = [record for record in result.records if record["code"] == "ETF_GLOBAL_TONNES"]
    assert len(holdings) == 1
    assert holdings[0]["value"] == 2100.0 + 1500.0 + 540.0 + 80.0
    # 月流量仍按月频口径：4095 - 3970 = 125
    flows = [record for record in result.records if record["code"] == "ETF_FLOW_1M_TONNES"]
    assert flows and flows[-1]["value"] == pytest.approx(125.0)


def test_cftc_provider_ignores_micro_gold(monkeypatch):
    base = {
        "Market_and_Exchange_Names": "GOLD - COMMODITY EXCHANGE INC.",
        "Report_Date_as_YYYY-MM-DD": "2026-11-03",
        "Open_Interest_All": "399169",
        "Swap_Positions_Long_All": "19301",
        "Swap__Positions_Short_All": "215291",
        "M_Money_Positions_Long_All": "122283",
        "M_Money_Positions_Short_All": "18669",
    }
    micro = {
        **base,
        "Market_and_Exchange_Names": "MICRO GOLD - COMMODITY EXCHANGE INC.",
        "Open_Interest_All": "1000",
    }
    _FakeClient.responses = {"fut_disagg_txt_": _FakeResponse(content=_cftc_zip([base, micro]))}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    monkeypatch.setattr(providers, "_cftc_years", lambda: [2026])
    result = providers.fetch_cftc_cot()
    assert result.ok, result.error
    values = {record["code"]: record["value"] for record in result.records}
    assert values["COMEX_GOLD_OI"] == 399169
    assert values["COT_SWAP_NET"] == 19301 - 215291
    assert values["COT_MONEY_NET"] == 122283 - 18669


def test_eastmoney_provider_parses_reserves(monkeypatch):
    payload = {
        "success": True,
        "result": {
            "data": [
                {"REPORT_DATE": "2026-10-01 00:00:00", "GOLD_RESERVES": 3064.11, "TIME": "2026年10月份"},
                {"REPORT_DATE": "2026-09-01 00:00:00", "GOLD_RESERVES": 3235.17, "TIME": "2026年09月份"},
            ]
        },
    }
    _FakeClient.responses = {"RPT_ECONOMY_GOLD_CURRENCY": _FakeResponse(payload=payload)}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_china_gold_reserves()
    assert result.ok, result.error
    assert len(result.records) == 2
    assert result.records[0]["value"] == 3064.11


def test_wgc_cbd_provider_sums_countries_and_drops_partial_quarter(monkeypatch):
    def stamp(year: int, month: int, day: int) -> int:
        return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)

    payload = {
        "chartData": {
            "linechart": {
                "QTD_FULL": {
                    "gold_reserves_tns": {
                        "data": [
                            {
                                "name": "USA",
                                "data": [
                                    [stamp(2026, 3, 31), 8000.0],
                                    [stamp(2026, 6, 30), 8100.0],
                                    [stamp(2026, 9, 30), 8100.0],
                                ],
                            },
                            {
                                "name": "DEU",
                                "data": [
                                    [stamp(2026, 3, 31), 3000.0],
                                    [stamp(2026, 6, 30), 3010.0],
                                    [stamp(2026, 9, 30), None],
                                ],
                            },
                            {
                                "name": "CHN",
                                "data": [
                                    [stamp(2026, 3, 31), 2200.0],
                                    [stamp(2026, 6, 30), 2250.0],
                                ],
                            },
                        ]
                    }
                }
            }
        }
    }
    _FakeClient.responses = {"getPage": _FakeResponse(payload=payload)}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_wgc_central_banks()
    assert result.ok, result.error
    values = [round(record["value"], 1) for record in result.records]
    # 2026-09 只有 1 个国家上报，应被丢弃，避免总量假暴跌
    assert values == [13200.0, 13360.0]
    assert all(record["code"] == "CB_GOLD_GLOBAL_TONNES" for record in result.records)


def test_cftc_bpr_provider_parses_bank_net(monkeypatch):
    html = (
        "<html><body><div>REPORT DATE: 4/7/2026</div><table>"
        "<tr><td rowspan=\"3\">CMX GOLD</td><td>U.S.</td><td>5</td><td>13,092</td><td>3.7</td>"
        "<td>74,688</td><td>21.0</td><td>354,877</td></tr>"
        "<tr><td>NON U.S.</td><td>24</td><td>15,645</td><td>4.4</td><td>109,086</td><td>30.7</td><td>&nbsp;</td></tr>"
        "<tr><td>&nbsp;</td><td>29</td><td>28,737</td><td>8.1</td><td>183,774</td><td>51.8</td><td>&nbsp;</td></tr>"
        "</table></body></html>"
    )
    _FakeClient.responses = {"BankParticipation": _FakeResponse(text=html)}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    monkeypatch.setattr(providers, "_bpr_periods", lambda months=30: [(2026, 4)])
    result = providers.fetch_cftc_bank_participation()
    assert result.ok, result.error
    assert len(result.records) == 1
    record = result.records[0]
    assert record["code"] == "MM_BANK_GOLD_NET"
    assert record["value"] == 28_737 - 183_774
    assert record["as_of"].date().isoformat() == "2026-04-07"


def test_comex_inventory_provider_converts_oz_to_tonnes(monkeypatch):
    csv_text = (
        "week_start,metal,report_date,registered_oz,eligible_oz,total_oz\n"
        "2026-11-09,gold,2026-11-13,14220956.883,8683384.707,22904341.59\n"
        "2026-11-02,silver,2026-11-06,1,2,3\n"
    )
    _FakeClient.responses = {"comex-gold": _FakeResponse(text=csv_text)}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_comex_inventory()
    assert result.ok, result.error
    assert len(result.records) == 1
    assert result.records[0]["code"] == "COMEX_GOLD_INVENTORY_TONNES"
    assert result.records[0]["value"] == pytest.approx(22904341.59 * 31.1034768 / 1_000_000)


def test_sge_lease_provider_reads_3m_column(monkeypatch):
    class _FakeSheet:
        rows = [
            ["日期", "O/N", "1M", "3M", "6M", "9M", "1Y", "3Y"],
            ["2026-11-13", "0.4269", "0.4195", "0.4236", "0.4359", "0.4420", "0.4472", "0.4758"],
            ["2026-11-12", "0.4240", "0.4184", "0.4228", "0.4335", "0.4391", "0.4441", "0.4716"],
        ]
        nrows = len(rows)
        ncols = 8

        def cell_value(self, row: int, col: int):
            return self.rows[row][col]

    class _FakeBook:
        def sheet_by_index(self, index: int):
            return _FakeSheet()

    monkeypatch.setattr(xlrd, "open_workbook", lambda **kwargs: _FakeBook())
    _FakeClient.responses = {"rent/download/export": _FakeResponse(content=b"\xd0\xcf\x11\xe0fake-xls")}
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_sge_gold_lease()
    assert result.ok, result.error
    assert [record["code"] for record in result.records] == ["SGE_GOLD_LEASE_3M_PCT"] * 2
    assert result.records[0]["value"] == pytest.approx(0.4236)


def test_shfe_gold_stock_provider_parses_kilograms(monkeypatch):
    listing = {
        "dataList": "[20261112, 20261113]",
        "startDate": "20260815",
        "endDate": "20261113",
    }
    html = (
        "<html><table>"
        "<tr><th>地区</th><th>仓库</th><th>期货</th><th>增减</th></tr>"
        "<tr><td colspan=\"3\">黄金</td><td>单位：千克</td></tr>"
        "<tr><td colspan=\"2\">上期所指定交割金库</td><td>118,404</td><td>0</td></tr>"
        "</table></html>"
    )
    _FakeClient.responses = {
        "stock_data_list": _FakeResponse(payload=listing),
        "dailystock_": _FakeResponse(text=html),
    }
    monkeypatch.setattr(providers, "HttpClient", _FakeClient)
    result = providers.fetch_shfe_gold_stock()
    assert result.ok, result.error
    assert len(result.records) == 2
    assert result.records[0]["code"] == "SHFE_GOLD_STOCK_TONNES"
    assert result.records[0]["value"] == pytest.approx(118.404)
    assert result.records[-1]["as_of"].date().isoformat() == "2026-11-13"


def test_scoring_with_synthetic_metrics():
    init_db()
    with SessionLocal() as session:
        # 清理测试数据
        for row in session.query(GoldMetric).filter(GoldMetric.source == "test").all():
            session.delete(row)
        session.commit()
        base = datetime(2026, 10, 1, tzinfo=timezone.utc)
        rows = [
            ("ETF_GLOBAL_TONNES", 0, 4000.0),
            ("ETF_GLOBAL_TONNES", 31, 4100.0),
            ("US10Y_REAL", 0, 2.0),
            ("US10Y_REAL", 31, 1.5),
            ("CN_GOLD_RESERVES_USD", 0, 3000.0),
            ("CN_GOLD_RESERVES_USD", 31, 3060.0),
        ]
        for code, offset, value in rows:
            session.add(
                GoldMetric(
                    code=code,
                    as_of=base + __import__("datetime").timedelta(days=offset),
                    value=value,
                    source="test",
                )
            )
        session.commit()
        score = compute_gold_score(session)
        assert -100 <= score["score"] <= 100
        assert score["coverage"] >= 0
        factor_codes = {factor["code"] for factor in score["factors"]}
        assert "ETF_GLOBAL_TONNES" in factor_codes
        assert "SGE_GOLD_LEASE_3M_PCT" in factor_codes
        for row in session.query(GoldMetric).filter(GoldMetric.source == "test").all():
            session.delete(row)
        session.commit()


def test_gold_api_overview_and_manual_metric():
    with TestClient(app) as client:
        overview = client.get("/api/gold/overview")
        assert overview.status_code == 200
        payload = overview.json()
        assert set(payload) >= {"score", "series", "providers", "manual", "indicators", "categories"}
        expected_factors = sum(1 for item in INDICATORS.values() if item.weight > 0)
        assert len(payload["score"]["factors"]) == expected_factors
        assert payload["manual"], "manual indicator list should not be empty"

        series = client.get("/api/gold/series?code=COT_MONEY_NET&limit=5")
        assert series.status_code == 200
        assert series.json()["code"] == "COT_MONEY_NET"
        assert client.get("/api/gold/series?code=NOPE").status_code == 404

        saved = client.post(
            "/api/gold/metrics",
            json={"code": "BIS_GOLD_SWAP_USD", "value": 120.0, "as_of": "2026-11-01", "note": "test"},
        )
        assert saved.status_code == 200
        assert saved.json()["saved"] is True

        # 自动指标不允许手动写入
        rejected = client.post("/api/gold/metrics", json={"code": "ETF_GLOBAL_TONNES", "value": 1})
        assert rejected.status_code == 400
