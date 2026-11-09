"""M11 tests: thesis generation, evidence matching and thesis API."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.decision.theses import build_event_thesis, build_thesis, match_claims
from app.main import app

CLAIMS = [
    SimpleNamespace(id="c1", subject="美联储", predicate="维持利率不变", value=4.25, unit="%"),
    SimpleNamespace(id="c2", subject="黄金", predicate="现货价格上涨", value=2.1, unit="%"),
    SimpleNamespace(id="c3", subject="铜", predicate="库存下降", value=1.2, unit="万吨"),
]


def test_match_claims_by_keyword():
    matched = match_claims("AU", CLAIMS)
    assert {claim.id for claim in matched} == {"c1", "c2"}
    assert match_claims("CU", CLAIMS)[0].id == "c3"
    assert match_claims("SR", CLAIMS) == []


def test_build_thesis_from_signal():
    payload = build_thesis(
        {"symbol": "AU", "type": "momentum", "direction": "short", "strength": 0.9},
        "沪金",
        CLAIMS,
    )
    assert "看空" in payload["title"]
    assert payload["direction"] == "short"
    assert payload["prior"] == 0.9
    assert 0.5 <= payload["posterior"] <= 0.9
    assert len(payload["evidence"]) == 2
    assert len(payload["scenarios"]) == 2
    assert payload["scenarios"][0]["probability"] == 0.55
    assert "1.5×ATR" in payload["invalidation"]


def test_build_event_thesis_direction():
    payload = build_event_thesis(
        {"title": "USTR tariff action", "type": "trade"}, "AU", "沪金", "long"
    )
    assert "【事件】" in payload["title"]
    assert payload["direction"] == "long"
    assert payload["horizon_days"] == 5
    assert len(payload["scenarios"]) == 2


def test_theses_api_structure():
    with TestClient(app) as client:
        payload = client.get("/api/theses?limit=5").json()
    assert "data" in payload
    for thesis in payload["data"]:
        assert {"id", "title", "direction", "posterior", "status", "scenarios"} <= set(thesis)
