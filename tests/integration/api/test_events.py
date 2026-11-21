"""Events API shape."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = [pytest.mark.integration, pytest.mark.api]


def test_events_api_structure():
    with TestClient(app) as client:
        payload = client.get("/api/events?limit=5").json()
    assert "data" in payload
    for event in payload["data"]:
        assert {"id", "type", "title", "event_date", "instruments"} <= set(event)
