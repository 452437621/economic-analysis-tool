"""Event alerts."""

from __future__ import annotations

import pytest

from app.alerts import event_alerts

pytestmark = pytest.mark.unit


def test_event_alerts():
    alerts = event_alerts(
        [
            {"type": "trade", "title": "USTR tariff action", "instruments": ["AU", "CU"]},
            {"type": "data_release", "title": "CPI", "instruments": []},
        ]
    )
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "event"
    assert "USTR" in alerts[0]["title"]
