"""Notification payloads."""

from __future__ import annotations

import pytest

from app.notify import build_serverchan_payload, build_wechat_payload, format_alert

pytestmark = pytest.mark.unit


def test_notify_payloads():
    alert = {"level": "critical", "title": "沪金 下跌 6%", "message": "最新 900"}
    text = format_alert(alert)
    assert "CRITICAL" in text
    assert "沪金" in text
    url, payload = build_serverchan_payload("KEY", text)
    assert url.endswith("/KEY.send")
    assert payload["desp"] == text
    url, payload = build_wechat_payload("https://example.com/hook", text)
    assert payload["text"]["content"] == text
