"""Positions API structure."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.unit


def test_positions_api_structure():
    with TestClient(app) as client:
        payload = client.get("/api/positions").json()
    assert "data" in payload
    assert "trade_date" in payload
