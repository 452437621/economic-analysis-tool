"""Deterministic daily brief generation.

Uses only structured data already collected: latest quotes, US Treasury yields,
official news documents and data-source health. No LLM is required for v1; the
brief is the baseline that the LLM editor will polish once an API key exists.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analytics.drivers import rank_drivers
from app.models.core import (
    AnalyticsResult,
    Brief,
    Claim,
    DataCheck,
    Document,
    DocumentBody,
    Event,
    EventInstrument,
    Instrument,
    MacroObs,
    MacroSeries,
    PositionSnapshot,
    Quote,
    Source,
    WatchItem,
)
from app.platform.config import settings
from app.platform.db import SessionLocal

KIND_LABEL = {"premarket": "盘前简报", "postmarket": "盘后简报", "manual": "手动简报"}
ASSET_LABEL = {
    "metal": "贵金属/工业金属",
    "energy": "能源",
    "black": "黑色系",
    "agri": "农产品",
    "fx": "汇率",
    "equity": "股指/个股",
}


def _fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}"


def _md_cell(value: object) -> str:
    """Escape table-breaking characters in markdown table cells."""
    return str(value).replace("|", "｜").replace("\n", " ").strip()


def _latest_quotes(session: Session) -> list[dict]:
    instruments = session.scalars(select(Instrument).where(Instrument.active.is_(True))).all()
    rows = session.scalars(select(Quote).order_by(Quote.ts_utc.desc()).limit(3000)).all()
    latest: dict[str, Quote] = {}
    for row in rows:
        latest.setdefault(row.instrument_id, row)
    source_names = {row.id: row.name for row in session.scalars(select(Source)).all()}
    result = []
    for instrument in instruments:
        quote = latest.get(instrument.id)
        if quote is None:
            continue
        result.append(
            {
                "symbol": instrument.symbol,
                "name": instrument.name,
                "asset_class": instrument.asset_class,
                "price": quote.price,
                "change_pct": quote.change_pct,
                "ts": quote.ts_utc,
                "delay_sec": quote.delay_sec,
                "source": source_names.get(quote.source_id),
            }
        )
    return result


def _latest_macro(session: Session) -> list[dict]:
    result = []
    for series in session.scalars(select(MacroSeries).order_by(MacroSeries.code)).all():
        obs = session.scalar(
            select(MacroObs).where(MacroObs.series_id == series.id).order_by(MacroObs.ts_utc.desc()).limit(1)
        )
        if obs is not None:
            result.append({"code": series.code, "name": series.name, "value": obs.value, "ts": obs.ts_utc})
    return result


def _latest_news(session: Session, limit: int = 10) -> list[dict]:
    rows = session.execute(
        select(Document, Source)
        .join(Source, Document.source_id == Source.id, isouter=True)
        .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": document.id,
            "title": document.title,
            "url": document.url,
            "published_at": (document.published_at or document.fetched_at).isoformat(),
            "source": source.name if source else "未知来源",
        }
        for document, source in rows
    ]


def _freshness(session: Session) -> list[dict]:
    checks = session.scalars(
        select(DataCheck).where(DataCheck.kind == "freshness").order_by(DataCheck.dataset)
    ).all()
    return [
        {"dataset": check.dataset, "passed": check.passed, "detail": check.detail}
        for check in checks[-12:]
    ]


def build_markdown(session: Session, kind: str, now: datetime | None = None) -> tuple[str, dict]:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone()
    trade_date = local.date()

    quotes = _latest_quotes(session)
    macro = _latest_macro(session)
    news = _latest_news(session)
    claims_count = int(session.scalar(select(func.count()).select_from(Claim)) or 0)
    bodies_count = int(session.scalar(select(func.count()).select_from(DocumentBody)) or 0)

    movers = sorted(
        [row for row in quotes if row["change_pct"] is not None],
        key=lambda row: abs(row["change_pct"]),
        reverse=True,
    )
    top = movers[:5]
    us10y = next((row for row in macro if row["code"] == "US10Y"), None)
    real10y = next((row for row in macro if row["code"] == "US10Y_REAL"), None)

    lines: list[str] = []
    lines.append(f"# {trade_date.isoformat()} {KIND_LABEL.get(kind, '简报')}（自动生成 {local.strftime('%H:%M')}）")
    lines.append("")
    lines.append("## 0. 一句话主线")
    if top:
        direction = "上涨" if (top[0]["change_pct"] or 0) >= 0 else "下跌"
        mainline = f"**{top[0]['name']}** {direction} {abs(top[0]['change_pct']):.2f}% 领跑波动"
        if us10y:
            mainline += f"；10Y 美债 {us10y['value']:.2f}%"
        if real10y:
            mainline += f"、10Y 实际利率 {real10y['value']:.2f}%"
    else:
        mainline = "行情数据尚未就绪，等待采集任务完成"
    lines.append(f"> **一句话主线：** {mainline}（自动摘要，置信度标注待 M2 证据链完善）")
    lines.append("")

    wind_row = session.scalar(
        select(AnalyticsResult)
        .where(AnalyticsResult.kind == "wind", AnalyticsResult.subject == "market")
        .order_by(AnalyticsResult.asof.desc())
        .limit(1)
    )
    indicator_map: dict[str, dict] = {}
    for row in session.scalars(
        select(AnalyticsResult).where(AnalyticsResult.kind == "indicator").order_by(AnalyticsResult.asof.desc())
    ).all():
        indicator_map.setdefault(row.subject, row.payload or {})
    regime_map: dict[str, dict] = {}
    for row in session.scalars(
        select(AnalyticsResult).where(AnalyticsResult.kind == "regime").order_by(AnalyticsResult.asof.desc())
    ).all():
        regime_map.setdefault(row.subject, row.payload or {})
    latest_position_date = session.scalar(select(func.max(PositionSnapshot.trade_date)))
    position_rows = []
    if latest_position_date is not None:
        position_rows = [
            {"product": row.product, "name": row.name, "net_ratio": row.net_ratio}
            for row in session.scalars(
                select(PositionSnapshot).where(PositionSnapshot.trade_date == latest_position_date)
            ).all()
        ]
    recent_events = session.scalars(
        select(Event)
        .where(Event.event_date >= now.replace(tzinfo=None) - timedelta(days=7))
        .order_by(Event.event_date.desc())
        .limit(10)
    ).all()
    driver_list = rank_drivers(
        wind=wind_row.payload if wind_row else None,
        indicators=indicator_map,
        positions=position_rows,
        events=[{"type": row.type, "title": row.title} for row in recent_events],
        regimes=regime_map,
    )

    lines.append("## 1. 主次动力（规则合成，非预测）")
    lines.append("| 动力 | 方向 | 强度 | 证据 |")
    lines.append("|---|---|---|---|")
    if driver_list:
        for driver in driver_list:
            lines.append(
                f"| **{_md_cell(driver['name'])}** | {_md_cell(driver['direction'])} "
                f"| {driver['strength']:.0%} | {_md_cell(driver['evidence'])} |"
            )
    else:
        lines.append("| — | 数据不足 | — | 等待分析任务完成后生成 |")
    lines.append("")

    watch_rows = session.execute(
        select(WatchItem, Instrument)
        .join(Instrument, Instrument.id == WatchItem.instrument_id)
        .order_by(
            WatchItem.sort_order.asc(),
            WatchItem.priority.asc(),
            Instrument.symbol.asc(),
        )
    ).all()
    if watch_rows:
        quote_map = {row["symbol"]: row for row in quotes}
        lines.append("### 重点关注（自选）")
        lines.append("| 品种 | 代码 | 最新 | 涨跌 | 20日 | 分组 |")
        lines.append("|---|---|---|---|---|---|")
        for item, instrument in watch_rows:
            quote = quote_map.get(instrument.symbol)
            price = _fmt_num(quote["price"], 2) if quote else "—"
            change = "—" if not quote or quote["change_pct"] is None else f"{quote['change_pct']:+.2f}%"
            change_20d = (indicator_map.get(instrument.symbol) or {}).get("change_20d")
            change_20d_text = f"{change_20d:+.2f}%" if change_20d is not None else "—"
            lines.append(
                f"| **{_md_cell(instrument.name)}** | **{_md_cell(instrument.symbol)}** | {price} "
                f"| {change} | {change_20d_text} | {_md_cell(item.group or '未分组')} |"
            )
        lines.append("")

    lines.append("## 2. 市场快照（按波动排序，Top 5）")
    lines.append("| 品种 | 名称 | 最新 | 涨跌幅 | 数据源 | 时点 |")
    lines.append("|---|---|---|---|---|---|")
    for row in top:
        ts = row["ts"].astimezone().strftime("%m-%d %H:%M")
        pct = "—" if row["change_pct"] is None else f"{row['change_pct']:+.2f}%"
        lines.append(
            f"| **{row['symbol']}** | **{row['name']}** | {_fmt_num(row['price'], 2)} | {pct} | {row['source'] or '—'} | {ts} |"
        )
    lines.append("")

    lines.append("## 3. 美债利率与流动性")
    lines.append("| 序列 | 最新 | 时点 |")
    lines.append("|---|---|---|")
    for row in macro:
        ts = row["ts"].astimezone().strftime("%m-%d")
        lines.append(f"| {row['name']}（{row['code']}） | {row['value']:.2f}% | {ts} |")
    lines.append("")

    lines.append("## 4. 会员持仓（Top20，净持仓 = 多 − 空）")
    latest_position_date = session.scalar(select(func.max(PositionSnapshot.trade_date)))
    positions = []
    if latest_position_date is not None:
        positions = session.scalars(
            select(PositionSnapshot).where(PositionSnapshot.trade_date == latest_position_date)
        ).all()
    if positions:
        ranked = sorted(
            (row for row in positions if row.net_ratio is not None),
            key=lambda row: row.net_ratio,
            reverse=True,
        )
        picks = ranked[:3] + ranked[-3:] if len(ranked) > 3 else ranked
        seen = set()
        for row in picks:
            if row.product in seen:
                continue
            seen.add(row.product)
            lines.append(
                f"- {row.name}：净持仓 {row.net_pos:+,} 手，净占比 {row.net_ratio * 100:+.1f}%"
                f"（多 {row.long_pos:,} / 空 {row.short_pos:,}）"
            )
        lines.append(f"- 数据日期：{latest_position_date.isoformat()}（上期所/郑商所）")
    else:
        lines.append("- 暂无会员持仓数据")
    lines.append("")

    lines.append("## 5. 事件驱动（近 3 天）")
    recent_events = session.scalars(
        select(Event)
        .where(Event.event_date >= now.replace(tzinfo=None) - timedelta(days=3))
        .order_by(Event.event_date.desc())
        .limit(5)
    ).all()
    if recent_events:
        event_ids = [row.id for row in recent_events]
        link_rows = session.execute(
            select(EventInstrument.event_id, Instrument.symbol)
            .join(Instrument, Instrument.id == EventInstrument.instrument_id)
            .where(EventInstrument.event_id.in_(event_ids))
        ).all()
        symbols_by_event: dict[str, list[str]] = {}
        for event_id, symbol in link_rows:
            symbols_by_event.setdefault(event_id, []).append(symbol)
        for row in recent_events:
            symbols = "/".join(symbols_by_event.get(row.id, [])) or "—"
            lines.append(f"- [{row.type}] {row.title[:90]}（关联 {symbols}）")
    else:
        lines.append("- 暂无规则识别事件")
    lines.append("")

    lines.append("## 6. 新闻与政策（官方来源）")
    for item in news:
        doc_id = item["id"]
        lines.append(f"- [{item['source']}] {item['title']}（{item['published_at'][:16].replace('T', ' ')}）`[D:{doc_id}]`")
    lines.append("")

    lines.append("## 7. 数据与信息缺口")
    lines.append(f"- 已入库原文 {bodies_count} 篇、断言 {claims_count} 条；新闻条目 {len(news)} 条（Top 10 展示）")
    for check in _freshness(session):
        status = "正常" if check["passed"] else "异常"
        lines.append(f"- 数据检查：{check['dataset']} = {status}（{check['detail'] or ''}）")
    lines.append("")

    lines.append("## 8. 免责声明")
    lines.append("- 本简报由系统基于公开数据自动生成，仅供个人研究，不构成投资建议。")
    lines.append("- 外盘数据存在约 15 分钟延迟，国内期货盘后数据为最近收盘；引用前请核对时点。")

    meta = {
        "generated_at": now.isoformat(),
        "quotes": len(quotes),
        "macro": len(macro),
        "news": len(news),
        "claims": claims_count,
        "bodies": bodies_count,
    }
    return "\n".join(lines), meta


def generate(kind: str = "manual", now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone()
    trade_date = local.date()
    with SessionLocal() as session:
        markdown, meta = build_markdown(session, kind, now)
        if settings.llm_available:
            from app.narrative.llm_edit import enhance_brief

            markdown, llm_meta = enhance_brief(markdown)
            meta["llm"] = llm_meta
        session.execute(
            delete(Brief).where(Brief.kind == kind, Brief.trade_date == trade_date)
        )
        brief = Brief(kind=kind, trade_date=trade_date, markdown=markdown, meta=meta)
        session.add(brief)
        session.commit()
        return {"id": brief.id, "kind": kind, "trade_date": trade_date.isoformat(), "chars": len(markdown)}
