"""M10 tests: calendar-triggered alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.alerts import calendar_alerts, compute_alerts

pytestmark = pytest.mark.unit


def test_calendar_alerts_levels():
    now = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
    events = [
        {"ts": now + timedelta(hours=2), "name": "中国:CPI:同比", "country": "中国", "importance": 3},
        {"ts": now + timedelta(minutes=45), "name": "美国:非农就业", "country": "美国", "importance": 3},
        {"ts": now + timedelta(hours=30), "name": "欧元区:GDP", "country": "欧盟", "importance": 3},
        {"ts": now + timedelta(hours=3), "name": "低重要性", "country": "美国", "importance": 2},
    ]
    alerts = calendar_alerts(events, now=now)
    assert len(alerts) == 2  # far future and low-importance filtered; merged per country/day
    levels = {alert["title"]: alert["level"] for alert in alerts}
    assert any("中国" in title and level == "warn" for title, level in levels.items())
    assert any("美国" in title and level == "critical" for title, level in levels.items())
    assert any("数据发布" in alert["title"] for alert in alerts)

    combined = compute_alerts([], [], [], now=now, calendar_events=events)
    assert any(alert["kind"] == "calendar" for alert in combined)
