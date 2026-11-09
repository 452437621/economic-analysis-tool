"""Monthly review report (M6 support)."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, func, select

from app.models.core import (
    Alert,
    AnalyticsResult,
    Brief,
    DataCheck,
    EconomicEvent,
    Outcome,
    Signal,
    TradePlan,
)
from app.platform.db import SessionLocal

KIND = "monthly"


def build_monthly_markdown(stats: dict, start: date, end: date) -> str:
    lines = [
        f"# {end.year} 年 {end.month} 月复盘（{start.isoformat()} ~ {end.isoformat()}）",
        "",
        "## 1. 运行与产出",
        f"- 简报 {stats['briefs']} 份；信号 {stats['signals']} 条；计划 {stats['plans']} 份",
        f"- 告警 {stats['alerts_total']} 条（严重 {stats['alerts_critical']} / 警告 {stats['alerts_warn']}）",
        f"- 已结算预测 {stats['resolved']} 条；Brier {stats['brier'] if stats['brier'] is not None else '—'}；"
        f"命中率 {stats['hit_rate'] if stats['hit_rate'] is not None else '—'}",
        f"- 论点 {stats['theses']} 条，方向命中率 {stats['thesis_hit_rate'] if stats['thesis_hit_rate'] is not None else '—'}",
        f"- 数据检查失败 {stats['data_checks_failed']} 项；财经日历事件 {stats['calendar_events']} 条",
        "",
        "## 2. 市场与风向",
        f"- 市场风向：{stats.get('wind_label', '—')}（{stats.get('wind_score', '—')}）",
    ]
    for mover in stats.get("movers", [])[:6]:
        lines.append(
            f"- {mover['symbol']}：20 日 {mover['change_20d']:+.2f}%，趋势 {mover.get('trend', '—')}"
        )
    lines += [
        "",
        "## 3. 本月校准清单",
        "- 对照周报，检查反复出现的判断偏差。",
        "- 复核论点命中率、计划采纳率与执行纪律。",
        "- 调整来源权重、周期参数、信号阈值、告警阈值。",
        "",
        "*自动生成，仅供个人研究，不构成投资建议。*",
    ]
    return "\n".join(lines)


def generate_monthly(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone().date()
    start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day)
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)

    with SessionLocal() as session:
        briefs = int(session.scalar(select(func.count()).select_from(Brief).where(Brief.created_at >= start_dt)) or 0)
        signals = int(session.scalar(select(func.count()).select_from(Signal).where(Signal.ts >= start_dt)) or 0)
        plans = int(session.scalar(select(func.count()).select_from(TradePlan).where(TradePlan.created_at >= start_dt)) or 0)
        alerts = session.execute(
            select(Alert.level, func.count()).where(Alert.created_at >= start_dt).group_by(Alert.level)
        ).all()
        alert_counts = {level: int(count) for level, count in alerts}
        resolved = int(
            session.scalar(select(func.count()).select_from(Outcome).where(Outcome.resolved_at >= start_dt)) or 0
        )
        brier = session.scalar(select(func.avg(Outcome.score)).where(Outcome.resolved_at >= start_dt))
        hit_rate = session.scalar(select(func.avg(Outcome.actual)).where(Outcome.resolved_at >= start_dt))
        checks_failed = int(
            session.scalar(
                select(func.count())
                .select_from(DataCheck)
                .where(DataCheck.check_date >= start_dt, DataCheck.passed.is_(False))
            )
            or 0
        )
        calendar_events = int(
            session.scalar(
                select(func.count())
                .select_from(EconomicEvent)
                .where(EconomicEvent.ts_utc >= start_dt, EconomicEvent.ts_utc <= end_dt)
            )
            or 0
        )
        wind_row = session.scalar(
            select(AnalyticsResult)
            .where(AnalyticsResult.kind == "wind", AnalyticsResult.subject == "market")
            .order_by(AnalyticsResult.asof.desc())
            .limit(1)
        )
        wind = wind_row.payload if wind_row else {}
        indicator_rows = session.scalars(
            select(AnalyticsResult).where(AnalyticsResult.kind == "indicator").order_by(
                AnalyticsResult.asof.desc()
            )
        ).all()
        latest: dict[str, dict] = {}
        for row in indicator_rows:
            latest.setdefault(row.subject, row.payload)
        movers = [
            {
                "symbol": symbol,
                "change_20d": payload.get("change_20d") or 0,
                "trend": payload.get("trend"),
            }
            for symbol, payload in latest.items()
            if payload.get("change_20d") is not None
        ]
        movers.sort(key=lambda item: abs(item["change_20d"]), reverse=True)

        from app.decision.thesis_review import review_theses

        thesis_review = review_theses()
        stats = {
            "briefs": briefs,
            "signals": signals,
            "plans": plans,
            "alerts_total": sum(alert_counts.values()),
            "alerts_critical": alert_counts.get("critical", 0),
            "alerts_warn": alert_counts.get("warn", 0),
            "resolved": resolved,
            "brier": round(float(brier), 4) if brier is not None else None,
            "hit_rate": round(float(hit_rate), 3) if hit_rate is not None else None,
            "theses": thesis_review["count"],
            "thesis_hit_rate": thesis_review["hit_rate"],
            "data_checks_failed": checks_failed,
            "calendar_events": calendar_events,
            "wind_label": wind.get("label"),
            "wind_score": wind.get("score"),
            "movers": movers[:8],
        }
        markdown = build_monthly_markdown(stats, start, end)
        session.execute(delete(Brief).where(Brief.kind == KIND, Brief.trade_date == end))
        brief = Brief(kind=KIND, trade_date=end, markdown=markdown, meta=stats)
        session.add(brief)
        session.commit()
        return {"id": brief.id, "trade_date": end.isoformat(), "chars": len(markdown)}
