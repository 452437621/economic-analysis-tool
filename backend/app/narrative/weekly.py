"""Weekly review: operational stats + decision ledger summary for M6."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.models.core import (
    Alert,
    AnalyticsResult,
    Brief,
    DataCheck,
    JournalEntry,
    Outcome,
    Signal,
    TradePlan,
)
from app.platform.db import SessionLocal

KIND = "weekly"


def build_weekly_markdown(stats: dict, start, end, journal: str | None = None) -> str:
    lines = [
        f"# {end.isoformat()} 周度复盘（{start.isoformat()} ~ {end.isoformat()}）",
        "",
        "## 1. 运行与产出",
        f"- 简报 {stats['briefs']} 份；信号 {stats['signals']} 条；计划 {stats['plans']} 份；告警 {stats['alerts_total']} 条"
        f"（严重 {stats['alerts_critical']} / 警告 {stats['alerts_warn']}）",
        f"- 已结算预测 {stats['resolved']} 条；Brier {stats['brier'] if stats['brier'] is not None else '—'}；"
        f"命中率 {stats['hit_rate'] if stats['hit_rate'] is not None else '—'}",
        f"- 数据检查失败 {stats['data_checks_failed']} 项；分析结果 {stats['analytics']} 条",
        "",
        "## 2. 市场与风向",
        f"- 市场风向：{stats.get('wind_label', '—')}（{stats.get('wind_score', '—')}）",
    ]
    for mover in stats.get("movers", [])[:5]:
        lines.append(
            f"- {mover['symbol']}：20 日 {mover['change_20d']:+.2f}%，趋势 {mover.get('trend', '—')}"
        )
    lines += ["", "## 3. 人工记录"]
    if journal:
        lines.append(journal.strip())
    else:
        lines.append("（本周无人工日志；可在看板「交易日志」区填写。）")
    lines += [
        "",
        "## 4. 下周校准清单",
        "- 核对系统主线与人工判断的差异，记录原因。",
        "- 检查告警误报/漏报，调整阈值。",
        "- 复核计划采纳率与执行纪律。",
        "",
        "*自动生成，仅供个人研究，不构成投资建议。*",
    ]
    return "\n".join(lines)


def generate_weekly(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    end = now.astimezone().date()
    start = end - timedelta(days=6)
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)

    with SessionLocal() as session:
        briefs = int(session.scalar(select(func.count()).select_from(Brief).where(Brief.created_at >= start_dt)) or 0)
        signals = int(session.scalar(select(func.count()).select_from(Signal).where(Signal.ts >= start_dt)) or 0)
        plans = int(session.scalar(select(func.count()).select_from(TradePlan).where(TradePlan.created_at >= start_dt)) or 0)
        alerts = session.execute(
            select(Alert.level, func.count()).where(Alert.created_at >= start_dt).group_by(Alert.level)
        ).all()
        alert_counts = {level: int(count) for level, count in alerts}
        resolved = int(
            session.scalar(
                select(func.count()).select_from(Outcome).where(Outcome.resolved_at >= start_dt)
            )
            or 0
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
        analytics = int(
            session.scalar(
                select(func.count()).select_from(AnalyticsResult).where(AnalyticsResult.asof >= start_dt)
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

        journal_row = session.scalar(
            select(JournalEntry).where(JournalEntry.entry_date >= start).order_by(JournalEntry.entry_date.desc()).limit(1)
        )

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
            "data_checks_failed": checks_failed,
            "analytics": analytics,
            "wind_label": wind.get("label"),
            "wind_score": wind.get("score"),
            "movers": movers[:6],
        }
        markdown = build_weekly_markdown(stats, start, end, journal_row.content if journal_row else None)
        session.execute(delete(Brief).where(Brief.kind == KIND, Brief.trade_date == end))
        brief = Brief(kind=KIND, trade_date=end, markdown=markdown, meta=stats)
        session.add(brief)
        session.commit()
        return {"id": brief.id, "trade_date": end.isoformat(), "chars": len(markdown)}
