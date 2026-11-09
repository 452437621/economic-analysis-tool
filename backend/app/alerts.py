"""Alert engine: price moves, stale data, failed checks, plan risk."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.core import Alert, DataCheck, EconomicEvent, PlanCheck, Quote, TradePlan
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

MOVE_WARN_PCT = 3.0
MOVE_CRITICAL_PCT = 5.0
STALE_SECONDS = 6 * 3600
DEDUPE_HOURS = 6
CN_MARKET_TZ = timezone(timedelta(hours=8))


def _cn_futures_open(now: datetime) -> bool:
    local = now.astimezone(CN_MARKET_TZ)
    if local.weekday() >= 5:
        return False
    minutes = local.hour * 60 + local.minute
    return (9 * 60 <= minutes <= 15 * 60) or minutes >= 21 * 60 or minutes <= 2 * 60 + 30


def _should_check_stale(asset_class: str | None, now: datetime) -> bool:
    if asset_class == "fx":
        return now.astimezone(CN_MARKET_TZ).weekday() < 5
    if asset_class in {"metal", "energy", "black", "agri"}:
        return _cn_futures_open(now)
    return True


def calendar_alerts(events: list[dict], now: datetime | None = None) -> list[dict]:
    """Upcoming high-impact calendar events within 24 hours, merged per country/day."""
    now = now or datetime.now(timezone.utc)
    groups: dict[tuple[str, str], list[dict]] = {}
    for event in events:
        ts = event.get("ts")
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        hours = (ts - now).total_seconds() / 3600
        if hours < -0.1 or hours > 24 or int(event.get("importance") or 0) < 3:
            continue
        local = ts.astimezone(CN_MARKET_TZ)
        key = (str(event.get("country") or "全球"), local.strftime("%m-%d"))
        groups.setdefault(key, []).append(
            {
                "name": str(event.get("name") or ""),
                "time": local.strftime("%H:%M"),
                "hours": hours,
            }
        )

    alerts: list[dict] = []
    for (country, day), items in groups.items():
        items.sort(key=lambda item: item["hours"])
        nearest = items[0]["hours"]
        level = "critical" if nearest <= 1.5 else "warn"
        names = []
        for item in items[:5]:
            short = item["name"].split("(报告期")[0]
            names.append(f"{item['time']} {short}")
        suffix = " 等" if len(items) > 5 else ""
        alerts.append(
            {
                "level": level,
                "kind": "calendar",
                "title": f"{country} {day} 数据发布 {len(items)} 项",
                "message": f"{'；'.join(names)}{suffix}；最近一项约 {nearest:.1f} 小时后",
            }
        )
    return alerts


def compute_alerts(
    quotes: list[dict],
    data_checks: list[dict],
    plan_checks: list[dict],
    now: datetime | None = None,
    calendar_events: list[dict] | None = None,
) -> list[dict]:
    """Pure alert generator (testable)."""
    now = now or datetime.now(timezone.utc)
    alerts: list[dict] = []
    for quote in quotes:
        change = quote.get("change_pct")
        if change is not None and abs(change) >= MOVE_WARN_PCT:
            level = "critical" if abs(change) >= MOVE_CRITICAL_PCT else "warn"
            direction = "上涨" if change > 0 else "下跌"
            alerts.append(
                {
                    "level": level,
                    "kind": "price_move",
                    "title": f"{quote.get('symbol')} {direction} {abs(change):.1f}%",
                    "message": f"{quote.get('name')} 最新 {quote.get('price')}，日变动 {change:.2f}%",
                }
            )
        stale = quote.get("stale_sec")
        delay = quote.get("delay_sec") or 0
        if (
            stale is not None
            and stale > STALE_SECONDS
            and delay < 900
            and _should_check_stale(quote.get("asset_class"), now)
        ):
            alerts.append(
                {
                    "level": "warn",
                    "kind": "stale_quote",
                    "title": f"{quote.get('symbol')} 行情陈旧",
                    "message": f"最近快照 {stale // 3600} 小时前，请检查采集任务",
                }
            )
    for check in data_checks:
        if not check.get("passed"):
            alerts.append(
                {
                    "level": "critical",
                    "kind": "data_check",
                    "title": f"数据检查失败：{check.get('dataset')}",
                    "message": str(check.get("detail") or ""),
                }
            )
    for check in plan_checks:
        if not check.get("passed"):
            alerts.append(
                {
                    "level": "warn",
                    "kind": "plan_risk",
                    "title": f"计划风控拦截：{check.get('rule')}",
                    "message": str(check.get("detail") or ""),
                }
            )
    alerts.extend(calendar_alerts(calendar_events or [], now))
    return alerts


def _recent_exists(session, kind: str, title: str, since: datetime) -> bool:
    return (
        session.scalar(
            select(Alert.id).where(
                Alert.kind == kind, Alert.title == title, Alert.created_at >= since
            )
        )
        is not None
    )


def scan_alerts() -> dict:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=DEDUPE_HOURS)
    created = 0
    skipped = 0

    with SessionLocal() as session:
        latest_quotes: dict[str, Quote] = {}
        for row in session.scalars(select(Quote).order_by(Quote.ts_utc.desc()).limit(500)).all():
            latest_quotes.setdefault(row.instrument_id, row)
        from app.models.core import Instrument

        instruments = {row.id: row for row in session.scalars(select(Instrument)).all()}
        quotes = []
        for instrument_id, quote in latest_quotes.items():
            instrument = instruments.get(instrument_id)
            if instrument is None:
                continue
            ts = quote.ts_utc
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            quotes.append(
                {
                    "symbol": instrument.symbol,
                    "name": instrument.name,
                    "asset_class": instrument.asset_class,
                    "price": quote.price,
                    "change_pct": quote.change_pct,
                    "stale_sec": int((now - ts).total_seconds()),
                    "delay_sec": quote.delay_sec,
                }
            )

        latest_checks: dict[str, DataCheck] = {}
        for row in session.scalars(select(DataCheck).order_by(DataCheck.check_date.desc()).limit(100)).all():
            latest_checks.setdefault(f"{row.kind}:{row.dataset}", row)
        data_checks = [
            {"dataset": row.dataset, "passed": row.passed, "detail": row.detail}
            for row in latest_checks.values()
        ]

        plan_checks = [
            {"rule": row.rule, "passed": row.passed, "detail": row.detail}
            for row in session.scalars(
                select(PlanCheck)
                .join(TradePlan, TradePlan.id == PlanCheck.plan_id)
                .where(TradePlan.status.in_(["draft", "confirmed", "executed"]))
            ).all()
        ]

        created_alerts: list[dict] = []
        now_naive = now.replace(tzinfo=None)
        upcoming = session.scalars(
            select(EconomicEvent)
            .where(
                EconomicEvent.ts_utc >= now_naive - timedelta(minutes=10),
                EconomicEvent.ts_utc <= now_naive + timedelta(hours=24),
                EconomicEvent.importance >= 3,
            )
            .order_by(EconomicEvent.ts_utc.asc())
        ).all()
        calendar_events = [
            {
                "ts": row.ts_utc.replace(tzinfo=timezone.utc),
                "name": row.name,
                "country": row.country,
                "importance": row.importance,
            }
            for row in upcoming
        ]
        for alert in compute_alerts(
            quotes, data_checks, plan_checks, now=now, calendar_events=calendar_events
        ):
            if _recent_exists(session, alert["kind"], alert["title"], since):
                skipped += 1
                continue
            session.add(
                Alert(
                    level=alert["level"],
                    kind=alert["kind"],
                    title=alert["title"],
                    message=alert["message"],
                )
            )
            created_alerts.append(alert)
            created += 1
        session.commit()

    if created_alerts:
        from app.notify import send_alert

        for alert in created_alerts:
            if alert["level"] != "critical":
                continue
            for result in send_alert(alert):
                if not result.ok:
                    logger.warning("notify %s failed: %s", result.channel, result.detail)

    logger.info("scan_alerts: created=%s skipped=%s", created, skipped)
    return {"created": created, "skipped": skipped, "notified": len(created_alerts)}
