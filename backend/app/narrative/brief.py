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
from app.ingest import quality
from app.models.core import (
    AnalyticsResult,
    Brief,
    Claim,
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
from app.platform.quality_gate import assess as assess_quality

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


def local_time(ts: datetime) -> datetime:
    """Render a stored timestamp in local time.

    SQLite returns naive datetimes that are **UTC**; calling ``astimezone()``
    on them directly would treat them as local and shift the clock by the
    timezone offset (8h in Asia/Shanghai).
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone()


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


RATE_ORDER = [
    "SOFR",
    "EFFR",
    "SOFR_EFFR",
    "US2Y",
    "US5Y",
    "US10Y",
    "US30Y",
    "US5Y_REAL",
    "US10Y_REAL",
    "US5Y_BE",
    "US10Y_BE",
    "CN2Y",
    "CN5Y",
    "CN10Y",
    "CN30Y",
    "CN10Y2Y",
    "JP2Y",
    "JP10Y",
    "JP30Y",
    "DE2Y",
    "DE10Y",
    "FR10Y",
]
COUNTRY_BY_CODE = {
    "SOFR": "美国",
    "EFFR": "美国",
    "SOFR_EFFR": "美国",
    "FR10Y": "法国",
}
COUNTRY_PREFIX = {"US": "美国", "CN": "中国", "JP": "日本", "DE": "德国", "FR": "法国"}


def order_rate_rows(rows: list[dict]) -> list[dict]:
    """Order rates by country (US→CN→JP→DE→FR→others) and maturity ascending."""
    by_code = {row["code"]: row for row in rows}
    ordered_codes = [code for code in RATE_ORDER if code in by_code]
    ordered_codes += [code for code in by_code if code not in ordered_codes]
    result = []
    for code in ordered_codes:
        row = dict(by_code[code])
        row["country"] = COUNTRY_BY_CODE.get(code) or COUNTRY_PREFIX.get(code[:2], "其他")
        result.append(row)
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


def position_rows(session: Session) -> list[dict]:
    """最新一期会员持仓（上期所/郑商所），日报/周报/月报共用。

    字段与 ``PositionSnapshot`` 对齐；没有数据时返回空列表。
    """
    latest = session.scalar(select(func.max(PositionSnapshot.trade_date)))
    if latest is None:
        return []
    return [
        {
            "trade_date": latest,
            "product": row.product,
            "name": row.name,
            "net_pos": row.net_pos,
            "net_ratio": row.net_ratio,
            "long_pos": row.long_pos,
            "short_pos": row.short_pos,
        }
        for row in session.scalars(
            select(PositionSnapshot).where(PositionSnapshot.trade_date == latest)
        ).all()
    ]


def pick_position_rows(rows: list[dict], per_side: int = 3) -> list[dict]:
    """按净占比排序取头尾各 ``per_side`` 个品种（同品种只保留一次）。"""
    ranked = sorted(
        (row for row in rows if row.get("net_ratio") is not None),
        key=lambda row: row["net_ratio"],
        reverse=True,
    )
    picks = ranked[:per_side] + ranked[-per_side:] if len(ranked) > per_side else ranked
    seen: set[str] = set()
    picked: list[dict] = []
    for row in picks:
        product = row["product"]
        if product in seen:
            continue
        seen.add(product)
        picked.append(row)
    return picked


POSITION_TABLE_HEADER = "| 品种 | 多头(手) | 空头(手) | 净持仓(手) | 净占比 |"


def position_table_lines(rows: list[dict]) -> list[str]:
    """会员持仓 Markdown pipe 表格，表脚保留数据日期；无数据时返回缺口提示。"""
    picks = pick_position_rows(rows)
    if not picks:
        return ["- 暂无会员持仓数据"]
    lines = [POSITION_TABLE_HEADER, "|---|---|---|---|---|"]
    for row in picks:
        name = _md_cell(row["name"])
        long_pos = _md_cell(f"{row['long_pos']:,}")
        short_pos = _md_cell(f"{row['short_pos']:,}")
        net_pos = _md_cell(f"{row['net_pos']:+,}")
        ratio = "—" if row["net_ratio"] is None else _md_cell(f"{row['net_ratio'] * 100:+.1f}%")
        lines.append(f"| **{name}** | {long_pos} | {short_pos} | {net_pos} | {ratio} |")
    trade_date = picks[0]["trade_date"]
    lines.append("")
    lines.append(f"- 数据日期：{trade_date.isoformat()}（上期所/郑商所）")
    return lines


def recent_event_rows(
    session: Session,
    now: datetime | None = None,
    *,
    days: int = 3,
    limit: int = 5,
) -> list[dict]:
    """最近事件 + 关联品种，日报/周报/月报共用（周/月报传更大的 days/limit）。"""
    now = now or datetime.now(timezone.utc)
    events = session.scalars(
        select(Event)
        .where(Event.event_date >= now.replace(tzinfo=None) - timedelta(days=days))
        .order_by(Event.event_date.desc())
        .limit(limit)
    ).all()
    if not events:
        return []
    link_rows = session.execute(
        select(EventInstrument.event_id, Instrument.symbol)
        .join(Instrument, Instrument.id == EventInstrument.instrument_id)
        .where(EventInstrument.event_id.in_([row.id for row in events]))
    ).all()
    symbols_by_event: dict[str, list[str]] = {}
    for event_id, symbol in link_rows:
        symbols_by_event.setdefault(event_id, []).append(symbol)
    return [
        {
            "id": row.id,
            "type": row.type,
            "title": row.title or "",
            "event_date": row.event_date,
            "symbols": symbols_by_event.get(row.id, []),
        }
        for row in events
    ]


def _zh_map(texts: list[str], allow_llm: bool = True) -> dict[str, str]:
    """批量取中文对照；翻译层任何异常都退化成空映射。"""
    try:
        from app.narrative.zh import zh_pairs

        return zh_pairs(texts, allow_llm=allow_llm)
    except Exception:  # pragma: no cover - 翻译缺失不能影响简报生成
        return {}


def _zh_suffix(text: str, zh_map: dict[str, str] | None) -> str:
    """英文标题后的「（中文：…）」；已是中文或没有译文时返回空串。"""
    if not zh_map or not isinstance(text, str):
        return ""
    zh = (zh_map.get(text) or "").strip()
    if not zh or zh == text.strip():
        return ""
    return f"（中文：{zh}）"


def event_lines(events: list[dict], zh_map: dict[str, str] | None = None) -> list[str]:
    """「事件驱动」节的 bullet 行（英文标题后带中文对照）。"""
    if not events:
        return ["- 暂无规则识别事件"]
    lines = []
    for row in events:
        title = row.get("title") or ""
        symbols = "/".join(row.get("symbols") or []) or "—"
        lines.append(
            f"- [{row.get('type') or '—'}] {title[:90]}{_zh_suffix(title, zh_map)}（关联 {symbols}）"
        )
    return lines


def news_lines(news: list[dict], zh_map: dict[str, str] | None = None) -> list[str]:
    """「新闻与政策」节的 bullet 行；保留 ``[D:xxx]`` 证据标记在中文对照之后。"""
    if not news:
        return ["- 暂无最新新闻"]
    lines = []
    for item in news:
        title = item.get("title") or ""
        published = (item.get("published_at") or "")[:16].replace("T", " ")
        lines.append(
            f"- [{item.get('source') or '未知来源'}] {title}{_zh_suffix(title, zh_map)}"
            f"（{published}）`[D:{item.get('id')}]`"
        )
    return lines


def _freshness(session: Session) -> list[dict]:
    """One row per dataset from the latest QC batch (never old runs)."""
    latest: dict[str, dict] = {}
    for check in quality.latest_checks(session):
        if check.kind != "freshness":
            continue
        latest[check.dataset] = {
            "dataset": check.dataset,
            "passed": check.passed,
            "detail": check.detail,
            "remediation": check.remediation,
            "action_job": check.action_job,
        }
    return list(latest.values())


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
    positions = position_rows(session)
    driver_events = recent_event_rows(session, now, days=7, limit=10)
    driver_list = rank_drivers(
        wind=wind_row.payload if wind_row else None,
        indicators=indicator_map,
        positions=positions,
        events=[{"type": row["type"], "title": row["title"]} for row in driver_events],
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
                f"| **{_md_cell(instrument.name)}** | {_md_cell(instrument.symbol)} | {price} "
                f"| {change} | {change_20d_text} | {_md_cell(item.group or '未分组')} |"
            )
        lines.append("")

    lines.append("## 2. 市场快照（按波动排序，Top 5）")
    lines.append("| 品种 | 代码 | 最新 | 涨跌幅 | 数据源 | 时点 |")
    lines.append("|---|---|---|---|---|---|")
    for row in top:
        ts = local_time(row["ts"]).strftime("%m-%d %H:%M")
        pct = "—" if row["change_pct"] is None else f"{row['change_pct']:+.2f}%"
        lines.append(
            f"| **{row['name']}** | {row['symbol']} | {_fmt_num(row['price'], 2)} | {pct} | {row['source'] or '—'} | {ts} |"
        )
    lines.append("")

    lines.append("## 3. 利率与流动性（按国家/期限排序）")
    lines.append("| 国家 | 序列 | 最新 | 时点 |")
    lines.append("|---|---|---|---|")
    for row in order_rate_rows(macro):
        row_local = local_time(row["ts"])
        age_days = (trade_date - row_local.date()).days
        # 周末/当地收盘前没有当日数据是常态，把"几天前"显式写出来，
        # 避免一条 11-13 的海外利率被读成"数据源挂了"。
        cell = f"{row_local.strftime('%m-%d')}" + (f"（{age_days} 天前）" if age_days > 0 else "（当日）")
        lines.append(f"| {row['country']} | {row['name']}（{row['code']}） | {row['value']:.2f}% | {cell} |")
    lines.append("")
    lines.append(
        "- 口径：美债/德债/日债/法债为各市场**最近一个已发布交易日**的数据，"
        "周末与当地收盘前不会有当日值，时点早于中债属正常；SOFR/EFFR 于美东 08:00/09:00 发布前一日值。"
    )
    lines.append("")

    lines.append("## 4. 关注品种（净占比头尾各 3；净持仓 = 多 − 空）")
    lines.extend(position_table_lines(positions))
    lines.append("")

    lines.append("## 5. 事件驱动（近 3 天）")
    recent = recent_event_rows(session, now, days=3, limit=5)
    section_zh = _zh_map(
        [row["title"] for row in recent] + [item["title"] for item in news if item.get("title")],
        allow_llm=True,
    )
    lines.extend(event_lines(recent, section_zh))
    lines.append("")

    lines.append("## 6. 新闻与政策（官方来源）")
    lines.extend(news_lines(news, section_zh))
    lines.append("")

    lines.append("## 7. 数据与信息缺口")
    lines.append(f"- 已入库原文 {bodies_count} 篇、断言 {claims_count} 条；新闻条目 {len(news)} 条（Top 10 展示）")
    gate = assess_quality(session)
    lines.append(
        f"- 数据质量门控：{gate['status']}"
        + (f"（{gate['caveat']}）" if gate.get("caveat") else "")
    )
    for check in _freshness(session):
        status = "正常" if check["passed"] else "异常"
        lines.append(f"- 数据检查：{check['dataset']} = {status}（{check['detail'] or ''}）")
        if not check["passed"] and check.get("remediation"):
            lines.append(f"  - 处置：{check['remediation']}")
            if check.get("action_job"):
                lines.append(f"  - 建议运行：{check['action_job']}")
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
