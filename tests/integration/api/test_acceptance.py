"""System acceptance endpoint shape."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = [pytest.mark.integration, pytest.mark.api]


def test_acceptance_endpoint_structure():
    with TestClient(app) as client:
        payload = client.get("/api/system/acceptance").json()
    assert "checks" in payload and len(payload["checks"]) >= 10
    assert "counts" in payload
    assert isinstance(payload["passed"], bool)
    for check in payload["checks"]:
        assert {"name", "passed", "detail"} <= set(check)
