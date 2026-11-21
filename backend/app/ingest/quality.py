"""Data-quality classification and remediation playbook.

``check_data_quality`` writes one batch of ``DataCheck`` rows per run.  This
module attaches a severity, a plain-language cause/impact and a concrete
remediation job to every row, and provides the helpers the API, acceptance
checker, alerts and repair job use to read the same latest batch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.base import new_id, utcnow
from app.models.core import DataCheck

BATCH_WINDOW = timedelta(minutes=5)


@dataclass(frozen=True)
class Finding:
    severity: str
    cause: str
    impact: str
    remediation: str
    action_job: str | None
    auto_repair: bool


def new_batch_id() -> str:
    return new_id()


def _finding(
    severity: str,
    cause: str,
    impact: str,
    remediation: str,
    action_job: str | None,
    *,
    auto_repair: bool = True,
) -> Finding:
    return Finding(severity, cause, impact, remediation, action_job, auto_repair)


def classify(
    *,
    kind: str,
    dataset: str,
    symbol: str | None = None,
    passed: bool = True,
    detail: str | None = None,
    expected: float | None = None,
    actual: float | None = None,
    deviation: float | None = None,
) -> Finding:
    """Map a check row onto the remediation playbook.

    ``passed`` rows still get a short classification so the UI can explain what
    the check covers; failed rows get a concrete action.
    """
    if passed:
        return _finding("info", "检查通过", "无", "无需处理", None, auto_repair=False)

    key = f"{kind}:{dataset}"
    if kind == "reconcile" and "CZCE" in dataset:
        return _finding(
            "error",
            "本地主力连续合约与交易所官方日行情偏差超过 0.2%，可能是换月、结算价口径或上游脏数据。",
            "白糖/棉花相关周期、信号与回测可能失真。",
            "重采日线并核对主力合约；若对账源本身不可用，先恢复数据源再复核。",
            "collect_daily_bars",
        )
    if kind == "reconcile":
        return _finding(
            "warn",
            "两个数据源的同一标的/序列出现偏差。",
            "单一源错误不易被发现，相关读数可能带偏。",
            "运行对应采集作业，并在数据源健康页核对主备源状态。",
            "collect_daily_bars",
        )
    if kind == "freshness" and dataset == "日线行情":
        return _finding(
            "error",
            "部分标的日线停更：上游不可达、节假日或端点风控。",
            "相关资产信号、透镜与预测结算会使用旧价格。",
            "运行 collect_daily_bars；备用链仍失败时检查数据源健康并稍后重试。",
            "collect_daily_bars",
        )
    if kind == "freshness" and dataset == "行情快照":
        return _finding(
            "warn",
            "行情快照超过新鲜度阈值：采集器失败或当前为非交易时段。",
            "总览、告警与盘前简报的价格可能陈旧。",
            "运行 collect_quotes，并确认新浪/东财/腾讯至少一条链可用。",
            "collect_quotes",
        )
    if kind == "freshness" and dataset == "宏观序列":
        critical = any(code in (detail or "") for code in ("US10Y", "US2Y", "EFFR", "SOFR"))
        return _finding(
            "error" if critical else "warn",
            "宏观序列超过发布窗口：上游发布滞后或数据源不可达。",
            "利率、流动性与宏观层读数会缺失或使用旧值。",
            "运行 collect_rates / collect_macro；确认世界银行/FRED 等备用链状态。",
            "collect_rates" if critical else "collect_macro",
        )
    if kind == "freshness" and dataset == "官方新闻":
        return _finding(
            "warn",
            "官方新闻超过 3 天没有更新。",
            "事件抽取与简报语料可能不足。",
            "运行 collect_news，并检查 RSS 源是否可达。",
            "collect_news",
        )
    if kind == "coverage" and "日线" in dataset:
        return _finding(
            "error",
            "启用标的没有日线数据或历史覆盖不足。",
            "该标的不参与趋势、信号与透镜计算。",
            "运行 collect_daily_bars；仍缺历史时运行 backfill_history。",
            "collect_daily_bars",
        )
    if kind == "coverage":
        return _finding(
            "warn",
            "宏观序列没有观测值。",
            "依赖该序列的读数会标记为 unknown。",
            "运行 collect_macro 并在数据源健康页确认来源。",
            "collect_macro",
        )
    if kind == "continuity" and "日线" in dataset:
        return _finding(
            "warn",
            "日线存在缺口、长时间断更、异常跳变或非法值。",
            "趋势斜率与回测结果可能错误。",
            "运行 backfill_history 修复历史缺口；异常点会优先用腾讯单根接口订正。",
            "backfill_history",
        )
    if kind == "continuity":
        return _finding(
            "warn",
            "宏观序列存在缺口或长间隔。",
            "同比、分位与比率读数可能失真。",
            "运行 collect_macro；确认上游发布日历。",
            "collect_macro",
        )
    if kind == "source":
        return _finding(
            "error",
            "数据源连续失败，主路径不可用。",
            "该源负责的行情/宏观数据可能停更或走备用路径。",
            "查看数据源健康与备用链，运行对应采集作业。",
            "collect_quotes",
        )
    return _finding(
        "warn",
        "未分类的数据质检失败，需要人工确认。",
        "相关结论可能降级或缺失。",
        "查看明细并在数据源健康页核对来源。",
        None,
        auto_repair=False,
    )


def add_check(
    session: Session,
    batch_id: str,
    *,
    kind: str,
    dataset: str,
    symbol: str | None = None,
    expected: float | None = None,
    actual: float | None = None,
    deviation: float | None = None,
    passed: bool = True,
    detail: str | None = None,
    check_date: datetime | None = None,
    action_job: str | None = None,
    severity: str | None = None,
    cause: str | None = None,
    impact: str | None = None,
    remediation: str | None = None,
) -> DataCheck:
    finding = classify(
        kind=kind,
        dataset=dataset,
        symbol=symbol,
        passed=passed,
        detail=detail,
        expected=expected,
        actual=actual,
        deviation=deviation,
    )
    row = DataCheck(
        kind=kind,
        dataset=dataset,
        symbol=symbol,
        check_date=check_date or utcnow(),
        expected=expected,
        actual=actual,
        deviation=deviation,
        passed=passed,
        detail=detail,
        batch_id=batch_id,
        severity=severity or finding.severity,
        cause=cause or finding.cause,
        impact=impact or finding.impact,
        remediation=remediation or finding.remediation,
        action_job=action_job or finding.action_job,
    )
    session.add(row)
    return row


def latest_batch(session: Session) -> tuple[str | None, list[DataCheck]]:
    """Return the newest QC batch, falling back to a 5-minute window for legacy rows."""
    newest = session.scalar(select(DataCheck).order_by(DataCheck.check_date.desc()).limit(1))
    if newest is None:
        return None, []
    if newest.batch_id:
        rows = session.scalars(
            select(DataCheck)
            .where(DataCheck.batch_id == newest.batch_id)
            .order_by(DataCheck.kind, DataCheck.dataset, DataCheck.symbol)
        ).all()
        return newest.batch_id, list(rows)
    cutoff = newest.check_date - BATCH_WINDOW
    rows = session.scalars(
        select(DataCheck)
        .where(DataCheck.check_date >= cutoff, DataCheck.check_date <= newest.check_date)
        .order_by(DataCheck.kind, DataCheck.dataset, DataCheck.symbol)
    ).all()
    return None, list(rows)


def latest_checks(session: Session) -> list[DataCheck]:
    return latest_batch(session)[1]


def failed_checks(session: Session) -> list[DataCheck]:
    return [row for row in latest_checks(session) if not row.passed]


def check_key(row: DataCheck) -> str:
    return f"{row.kind}:{row.dataset}:{row.symbol or '*'}"


def remediation_jobs(checks: list[DataCheck]) -> list[str]:
    jobs: list[str] = []
    for row in checks:
        if row.passed:
            continue
        action = row.action_job
        if not action:
            action = classify(
                kind=row.kind,
                dataset=row.dataset,
                symbol=row.symbol,
                passed=False,
                detail=row.detail,
                expected=row.expected,
                actual=row.actual,
                deviation=row.deviation,
            ).action_job
        if action and action not in jobs:
            jobs.append(action)
    return jobs


def batch_age_seconds(session: Session, now: datetime | None = None) -> float | None:
    newest = session.scalar(select(DataCheck).order_by(DataCheck.check_date.desc()).limit(1))
    if newest is None:
        return None
    current = now or datetime.now(timezone.utc)
    if newest.check_date.tzinfo is None:
        stamp = newest.check_date.replace(tzinfo=timezone.utc)
    else:
        stamp = newest.check_date
    return max(0.0, (current - stamp).total_seconds())


def severity_counts(checks: list[DataCheck]) -> dict[str, int]:
    counts = {"info": 0, "warn": 0, "error": 0, "critical": 0}
    for row in checks:
        key = (row.severity or "info").lower()
        counts[key] = counts.get(key, 0) + 1
    return counts


def prune_data_checks(session: Session, keep_days: int = 180) -> int:
    """Keep the QC history bounded; the current batch is never touched."""
    if keep_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    result = session.execute(delete(DataCheck).where(DataCheck.check_date < cutoff))
    return int(result.rowcount or 0)
