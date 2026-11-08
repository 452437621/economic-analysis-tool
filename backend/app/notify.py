"""Alert notification channels: Server 酱 / 企业微信 / SMTP (optional, env-driven)."""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText

import httpx

logger = logging.getLogger(__name__)


def format_alert(alert: dict) -> str:
    level = str(alert.get("level", "info")).upper()
    return f"[EPIC][{level}] {alert.get('title', '')}\n{alert.get('message', '')}".strip()


def channels() -> list[str]:
    raw = os.environ.get("EPIC_NOTIFY_CHANNELS", "").strip()
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_serverchan_payload(sendkey: str, text: str) -> tuple[str, dict]:
    return f"https://sctapi.ftqq.com/{sendkey}.send", {"title": "EPIC 市场告警", "desp": text}


def build_wechat_payload(webhook: str, text: str) -> tuple[str, dict]:
    return webhook, {"msgtype": "text", "text": {"content": text}}


@dataclass(slots=True)
class NotifyResult:
    channel: str
    ok: bool
    detail: str | None = None


def send_alert(alert: dict, enabled: list[str] | None = None) -> list[NotifyResult]:
    enabled = enabled if enabled is not None else channels()
    if not enabled:
        return []
    text = format_alert(alert)
    results: list[NotifyResult] = []
    for channel in enabled:
        try:
            if channel == "serverchan":
                key = os.environ.get("SERVERCHAN_SENDKEY", "")
                if not key:
                    results.append(NotifyResult(channel, False, "SERVERCHAN_SENDKEY missing"))
                    continue
                url, payload = build_serverchan_payload(key, text)
                with httpx.Client(timeout=10) as client:
                    resp = client.post(url, json=payload)
                results.append(NotifyResult(channel, resp.status_code < 300, str(resp.status_code)))
            elif channel == "wechat":
                webhook = os.environ.get("WECHAT_WEBHOOK", "")
                if not webhook:
                    results.append(NotifyResult(channel, False, "WECHAT_WEBHOOK missing"))
                    continue
                url, payload = build_wechat_payload(webhook, text)
                with httpx.Client(timeout=10) as client:
                    resp = client.post(url, json=payload)
                results.append(NotifyResult(channel, resp.status_code < 300, str(resp.status_code)))
            elif channel == "email":
                host = os.environ.get("SMTP_HOST", "")
                user = os.environ.get("SMTP_USER", "")
                password = os.environ.get("SMTP_PASSWORD", "")
                to_addr = os.environ.get("SMTP_TO", "")
                if not (host and user and password and to_addr):
                    results.append(NotifyResult(channel, False, "SMTP config incomplete"))
                    continue
                msg = MIMEText(text, "plain", "utf-8")
                msg["Subject"] = f"[EPIC] {alert.get('title', '告警')}"
                msg["From"] = os.environ.get("SMTP_FROM", user)
                msg["To"] = to_addr
                port = int(os.environ.get("SMTP_PORT", "465"))
                with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                    smtp.login(user, password)
                    smtp.sendmail(msg["From"], [to_addr], msg.as_string())
                results.append(NotifyResult(channel, True))
            else:
                results.append(NotifyResult(channel, False, "unknown channel"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("notify %s failed: %s", channel, exc)
            results.append(NotifyResult(channel, False, str(exc)))
    return results
