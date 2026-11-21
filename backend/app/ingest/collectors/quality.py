"""Cross-source data-quality checks."""

from __future__ import annotations

import logging
import time
from datetime import timedelta, timezone

from sqlalchemy import func, select

from app.ingest import continuity, quality, reconcile, store
from app.ingest.collectors.support import _now
from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient
from app.ingest.providers import czce, fred
from app.ingest.sources import NEWS_FEEDS, NEWS_FEEDS_SLOW
from app.models.core import (
    DataCheck,
    Document,
    Instrument,
    MacroObs,
    MacroSeries,
    MarketBar,
    Quote as QuoteRow,
    Source,
    SourceHealth,
)
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def check_data_quality() -> dict:
    """Cross-check official CZCE quotes and dataset freshness.

    Every run gets one ``batch_id``.  Failures carry a severity, cause, impact
    and a concrete remediation job, so the API/acceptance checker/repair job
    all agree on what is wrong and what to run next.
    """
    started = time.perf_counter()
    batch_id = quality.new_batch_id()
    now = _now()
    stats: dict = {
        "checks": 0,
        "failed": 0,
        "errors": [],
        "batch_id": batch_id,
    }
    written: list[DataCheck] = []

    def add(**kwargs) -> DataCheck:
        kwargs.setdefault("check_date", now)
        row = quality.add_check(session, batch_id, **kwargs)
        written.append(row)
        stats["checks"] += 1
        if not kwargs.get("passed", True):
            stats["failed"] += 1
        return row

    with HttpClient(min_interval=0.8) as client, SessionLocal() as session:
        for symbol in ("SR", "CF"):
            instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
            if instrument is None:
                add(
                    kind="reconcile",
                    dataset="CZCE官方日行情",
                    symbol=symbol,
                    passed=False,
                    detail="本地缺少该标的，无法与交易所对账",
                )
                continue
            bar = session.scalar(
                select(MarketBar)
                .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == "1d")
                .order_by(MarketBar.ts_utc.desc())
                .limit(1)
            )
            if bar is None:
                add(
                    kind="reconcile",
                    dataset="CZCE官方日行情",
                    symbol=symbol,
                    passed=False,
                    detail="本地无日线，无法与交易所对账",
                )
                continue
            try:
                rows = czce.fetch_daily(client, bar.ts_utc.date())
                main_contract = czce.main_contract(rows.get(symbol, []))
                expected = main_contract.close if main_contract else None
                actual = bar.close
                deviation = abs(actual - expected) / expected if expected else None
                passed = deviation is not None and deviation <= 0.002
                add(
                    kind="reconcile",
                    dataset="CZCE官方日行情",
                    symbol=symbol,
                    expected=expected,
                    actual=actual,
                    deviation=deviation,
                    passed=passed,
                    detail=main_contract.code if main_contract else "未找到主力合约",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("quality check failed %s: %s", symbol, exc)
                stats["errors"].append(f"{symbol}: {exc}")
                add(
                    kind="reconcile",
                    dataset="CZCE官方日行情",
                    symbol=symbol,
                    passed=False,
                    detail=f"官方对账失败: {exc}",
                )
            session.commit()

        def freshness(dataset: str, latest, max_age_days: int, note: str | None = None) -> None:
            if latest is not None and latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            age = (now - latest).days if latest is not None else None
            if age is not None and age < 0:
                # 个别新闻源会给出「未来」时间戳（时区换算/预告稿），按当日算。
                age = 0
            passed = age is not None and age <= max_age_days
            detail = f"最新={latest.date() if latest else '无'}"
            if age is not None:
                detail += f", 距今{age}天"
            if not passed:
                detail += f", 超过{max_age_days}天阈值"
            if note:
                detail += f" ({note})"
            add(
                kind="freshness",
                dataset=dataset,
                passed=passed,
                detail=detail,
            )

        # 日线：按标的逐条比对，避免"某个标的停更被全表最大值掩盖"。
        bar_max_age_days = 5
        bar_latest = session.execute(
            select(Instrument.symbol, func.max(MarketBar.ts_utc))
            .join(MarketBar, MarketBar.instrument_id == Instrument.id)
            .where(MarketBar.timeframe == "1d")
            .group_by(Instrument.id)
        ).all()
        if bar_latest:
            def _age(value):
                if value is None:
                    return None
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return (now - value).days

            pairs = [(symbol, ts, _age(ts)) for symbol, ts in bar_latest]
            latest_ts = max((ts for _, ts, _ in pairs if ts is not None), default=None)
            stale = sorted(
                [
                    (symbol, ts, age)
                    for symbol, ts, age in pairs
                    if age is None or age > bar_max_age_days
                ],
                key=lambda item: (item[2] is not None, -(item[2] or 0)),
            )
            detail = f"最新={latest_ts.date() if latest_ts else '无'}, 标的{len(pairs)}个"
            if stale:
                detail += "; 滞后: " + ", ".join(
                    f"{symbol}:{ts.date() if ts else '无'}({age}天)" for symbol, ts, age in stale[:6]
                )
                if len(stale) > 6:
                    detail += f" 等{len(stale)}个"
            add(
                kind="freshness",
                dataset="日线行情",
                passed=not stale,
                detail=detail,
            )

        # 宏观序列：按序列频率给阈值（日频 5 天 / 周频 10 天 / 月频 70 天 / 季频 150 天 / 年频 800 天），
        # 逐条检查——全表最大值会把"日债停在 10-30"这类单序列断更完全掩盖。
        freq_days = {"d": 5, "w": 10, "m": 70, "q": 150, "y": 800}
        macro_rows = session.execute(
            select(MacroSeries.code, MacroSeries.freq, func.max(MacroObs.ts_utc))
            .outerjoin(MacroObs, MacroObs.series_id == MacroSeries.id)
            .group_by(MacroSeries.id)
        ).all()
        if macro_rows:
            stale_macro: list[str] = []
            oldest = None
            for code, freq, ts in macro_rows:
                age = None
                if ts is not None:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age = (now - ts).days
                limit = freq_days.get((freq or "d").lower(), 5)
                if age is None or age > limit:
                    stale_macro.append(f"{code}:{ts.date() if ts else '无'}({age}天, {freq}频)")
                if ts is not None and (oldest is None or ts < oldest):
                    oldest = ts
            detail = f"序列{len(macro_rows)}条, 最旧={oldest.date() if oldest else '无'}"
            if stale_macro:
                detail += "; 滞后: " + ", ".join(stale_macro[:8])
                if len(stale_macro) > 8:
                    detail += f" 等{len(stale_macro)}条"
            add(
                kind="freshness",
                dataset="宏观序列",
                passed=not stale_macro,
                detail=detail,
            )

        freshness("行情快照", session.scalar(select(func.max(QuoteRow.ts_utc))), 1)
        freshness(
            "官方新闻",
            session.scalar(select(func.max(func.coalesce(Document.published_at, Document.fetched_at)))),
            3,
        )

        coverage = session.execute(
            select(Instrument.symbol, func.count(MarketBar.id))
            .outerjoin(
                MarketBar,
                (MarketBar.instrument_id == Instrument.id) & (MarketBar.timeframe == "1d"),
            )
            .where(Instrument.active.is_(True))
            .group_by(Instrument.id)
        ).all()
        missing = [symbol for symbol, count in coverage if count == 0]
        add(
            kind="coverage",
            dataset="启用标的日线覆盖",
            expected=len(coverage),
            actual=len(coverage) - len(missing),
            deviation=len(missing),
            passed=not missing,
            detail="缺失: " + ", ".join(missing) if missing else "全部启用标的均有日线",
        )

        macro_coverage = session.execute(
            select(MacroSeries.code, func.count(MacroObs.id))
            .outerjoin(MacroObs, MacroObs.series_id == MacroSeries.id)
            .group_by(MacroSeries.id)
        ).all()
        missing_macro = [code for code, count in macro_coverage if count == 0]
        add(
            kind="coverage",
            dataset="宏观序列覆盖",
            expected=len(macro_coverage),
            actual=len(macro_coverage) - len(missing_macro),
            deviation=len(missing_macro),
            passed=not missing_macro,
            detail="缺失: " + ", ".join(missing_macro) if missing_macro else "全部宏观序列均有观测",
        )

        # 历史连续性：不预置交易日历，用「同业共识」判断某个标的漏了哪天
        # （休市日不会被误判），趋势图缺一根或出现错误行情都会在这里暴露。
        for dataset, findings in (
            ("日线行情", continuity.daily_findings(session)),
            ("宏观序列", continuity.macro_findings(session)),
        ):
            known = continuity.missing_known_gaps(session) if dataset == "日线行情" else 0
            passed, problems, detail = continuity.summarize(findings, known_gaps=known)
            add(
                kind="continuity",
                dataset=f"{dataset}连续性",
                expected=len({item.subject for item in findings}),
                actual=0,
                deviation=problems,
                passed=passed,
                detail=detail,
            )

        # FRED spot-check: compare a few key US series with the official primary.
        # Only runs outside the test environment; failures are warnings, not
        # silent passes.
        if settings.fred_enabled and settings.env != "test":
            for code in ("US10Y", "US2Y", "US_M2"):
                action = "collect_macro" if code == "US_M2" else "collect_rates"
                try:
                    remote = fred.fetch_series(
                        client, code, start_date=(now - timedelta(days=45)).date()
                    )
                except Exception as exc:  # noqa: BLE001
                    add(
                        kind="reconcile",
                        dataset="FRED抽样对账",
                        symbol=code,
                        passed=False,
                        severity="warn",
                        detail=f"FRED 对账源不可用: {exc}",
                        action_job=action,
                    )
                    continue
                local_row = session.scalar(
                    select(MacroObs)
                    .join(MacroSeries, MacroSeries.id == MacroObs.series_id)
                    .where(MacroSeries.code == code)
                    .order_by(MacroObs.ts_utc.desc())
                    .limit(1)
                )
                if local_row is None:
                    continue
                finding = reconcile.compare_series(
                    [
                        MacroPoint(
                            code=code,
                            ts=local_row.ts_utc.replace(tzinfo=timezone.utc)
                            if local_row.ts_utc.tzinfo is None
                            else local_row.ts_utc,
                            value=float(local_row.value),
                        )
                    ],
                    remote,
                )
                if finding:
                    reconcile.record_divergence(
                        session,
                        batch_id=batch_id,
                        dataset="FRED抽样对账",
                        symbol=code,
                        finding=finding,
                        action_job=action,
                    )

        # 数据源健康：连续失败 >= 3 的源进入质检批次，避免「采集失败但质检全绿」。
        source_rows = session.scalars(select(Source).order_by(Source.name)).all()
        health_rows = session.scalars(
            select(SourceHealth).order_by(SourceHealth.ts.desc()).limit(500)
        ).all()
        latest_health: dict[str, SourceHealth] = {}
        recent_health: dict[str, list[SourceHealth]] = {}
        for row in health_rows:
            latest_health.setdefault(row.source_id, row)
            recent_health.setdefault(row.source_id, []).append(row)
        # 源 → 修复作业：优先从备用链注册表推导（链主作业），再补不在链里的
        # 新闻/日历/持仓源，避免未映射源被误派给 collect_quotes。
        from app.ingest.chains import CHAINS

        action_by_source: dict[str, str] = {}
        for chain in CHAINS.values():
            for conf in chain.sources:
                action_by_source.setdefault(conf["name"], chain.action_job)
        action_by_source.update(
            {
                "IMF DataMapper": "collect_macro",
                "世界银行": "collect_macro",
                "美国财政部FiscalData": "collect_macro",
                "FRED": "collect_rates",
                "日本财务省": "collect_rates",
                "欧洲央行": "collect_rates",
                "上海期货交易所": "collect_positions",
                "郑州商品交易所": "collect_positions",
                "国家统计局": "collect_news",
                "美国能源信息署": "collect_news",
                "美国贸易代表办公室": "collect_news",
            }
        )
        for feed in NEWS_FEEDS + NEWS_FEEDS_SLOW:
            action_by_source.setdefault(feed["name"], "collect_news")
        flagged = 0
        for source in source_rows:
            records = recent_health.get(source.id) or []
            consecutive = 0
            for record in records:
                if record.ok:
                    break
                consecutive += 1
            if consecutive < 3 or flagged >= 20:
                continue
            latest = latest_health.get(source.id)
            add(
                kind="source",
                dataset=source.name,
                passed=False,
                detail=(
                    f"连续失败 {consecutive} 次；最近错误："
                    f"{(latest.error if latest else None) or '无'}"
                ),
                action_job=action_by_source.get(source.name),
            )
            flagged += 1

        if not written:
            add(
                kind="quality",
                dataset="质检自身",
                passed=False,
                detail="本轮未生成任何检查项，质检流程可能未正确执行",
                action_job="check_data_quality",
            )

        stats["by_severity"] = quality.severity_counts(written)
        stats["status"] = "degraded" if stats["failed"] else "ok"
        stats["checks_pruned"] = quality.prune_data_checks(session)

        # 分钟级行情快照只保留最近 N 天（EPIC_QUOTES_RETENTION_DAYS），
        # 一天清理一次把 SQLite 文件大小压回稳态。
        stats["quotes_pruned"] = store.prune_quotes(session)
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("check_data_quality: %s", stats)
    return stats
