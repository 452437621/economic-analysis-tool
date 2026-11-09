"""M10 tests: calendar-triggered alerts and calendar event study."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.alerts import calendar_alerts, compute_alerts
from app.analytics.calendar_study import build_calendar_study, categorize


def test_calendar_alerts_levels():
    now = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
    events = [
        {"ts": now + timedelta(hours=2), "name": "中国:CPI:同比", "country": "中国", "importance": 3},
        {"ts": now + timedelta(minutes=45), "name": "美国:非农就业", "country": "美国", "importance": 3},
        {"ts": now + timedelta(hours=30), "name": "欧元区:GDP", "country": "欧盟", "importance": 3},
        {"ts": now + timedelta(hours=3), "name": "低重要性", "country": "美国", "importance": 2},
    ]
    alerts = calendar_alerts(events, now=now)
    assert len(alerts) == 2  # far future and low-importance filtered
    levels = {alert["title"]: alert["level"] for alert in alerts}
    assert levels["中国:CPI:同比 即将发布"] == "warn"
    assert levels["美国:非农就业 即将发布"] == "critical"

    combined = compute_alerts([], [], [], now=now, calendar_events=events)
    assert any(alert["kind"] == "calendar" for alert in combined)


def test_calendar_study_forward_returns():
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    closes = pd.DataFrame(
        {
            "AU": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "CU": [200, 202, 204, 206, 208, 210, 212, 214, 216, 218],
            "SC": [80, 81, 82, 83, 84, 85, 86, 87, 88, 89],
            "000300": [300, 301, 302, 303, 304, 305, 306, 307, 308, 309],
            "DXY": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
            "SPX": [400, 402, 404, 406, 408, 410, 412, 414, 416, 418],
        },
        index=dates,
    )
    events = [
        {"ts": "2026-01-03", "name": "美国:CPI:同比", "country": "美国", "importance": 3},
    ]
    payload = build_calendar_study(closes, events)
    assert payload["events"] == 1
    group = payload["groups"][0]
    assert group["country"] == "美国"
    assert group["category"] == "通胀"
    au = group["assets"]["AU"]
    # 2026-01-03 base 102; +1d 103 => +0.98%; +3d 105 => +2.94%
    assert au["1d"] == 0.98
    assert au["3d"] == 2.94
    assert au["1d_hit"] == 1.0


def test_categorize():
    assert categorize("中国:CPI:同比") == "通胀"
    assert categorize("美国:非农就业人口") == "就业"
    assert categorize("某行业会议") == "其他"
