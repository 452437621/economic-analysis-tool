"""Gold monitoring tests: offline provider parsers, scoring and API contracts."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import openpyxl
import pytest
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
    assert "BIS_GOLD_LEASE_RATE" in manual_codes()
    assert "COMEX_GOLD_INVENTORY_TONNES" in manual_codes()
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
                "Monthly": {
                    "tonnes": {
                        "columns": ["Date", "North America", "Europe", "Asia", "Other", "Gold, US$/oz"],
                        "set": [
                            [1735689600000, 2000.0, 1400.0, 500.0, 70.0, 4000.0],
                            [1738368000000, 2010.0, 1410.0, 505.0, 72.0, 4100.0],
                        ],
                    }
                }
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
        assert "BIS_GOLD_LEASE_RATE" in factor_codes
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
            json={"code": "COMEX_GOLD_INVENTORY_TONNES", "value": 500.0, "as_of": "2026-11-01", "note": "test"},
        )
        assert saved.status_code == 200
        assert saved.json()["saved"] is True

        # 自动指标不允许手动写入
        rejected = client.post("/api/gold/metrics", json={"code": "ETF_GLOBAL_TONNES", "value": 1})
        assert rejected.status_code == 400
