"""Global data-quality gate used by analysis/decision engines.

The gate answers one question: *should we present this conclusion as
actionable right now?*  It combines the latest QC batch with direct freshness
queries, so an old batch cannot silently keep the system green.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingest import quality
from app.models.core import MacroObs, MacroSeries, MarketBar, Quote
from app.platform.coverage import FRESH_DAYS_BY_FREQ, series_coverage

BATCH_MAX_AGE_SECONDS = 36 * 3600
BAR_MAX_AGE_DAYS = 10
QUOTE_MAX_AGE_DAYS = 3
CRITICAL_SEVERITIES = {"error", "critical"}


def _age_days(ts: datetime | None, now: datetime) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 86400.0)


def assess(session: Session, *, now: datetime | None = None, domains=None) -> dict:  # noqa: ARG001
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    batch_id, checks = quality.latest_batch(session)
    age_seconds = quality.batch_age_seconds(session, current)
    passed = sum(1 for check in checks if check.passed)
    failed = [check for check in checks if not check.passed]
    critical_failed = [
        check for check in failed if (check.severity or "warn").lower() in CRITICAL_SEVERITIES
    ]
    qc_ratio = passed / len(checks) if checks else 0.0

    quote_latest = session.scalar(select(func.max(Quote.ts_utc)))
    bar_latest = session.scalar(select(func.max(MarketBar.ts_utc)))
    quote_age = _age_days(quote_latest, current)
    bar_age = _age_days(bar_latest, current)

    macro_rows = session.execute(
        select(MacroSeries.freq, func.max(MacroObs.ts_utc))
        .outerjoin(MacroObs, MacroObs.series_id == MacroSeries.id)
        .group_by(MacroSeries.id)
    ).all()
    fresh_macro = 0
    for freq, ts in macro_rows:
        age = _age_days(ts, current)
        window = FRESH_DAYS_BY_FREQ.get((freq or "m").lower(), 45)
        if age is not None and age <= window:
            fresh_macro += 1
    macro_ratio = fresh_macro / len(macro_rows) if macro_rows else 0.0

    covered, total = series_coverage(session, current)
    coverage_ratio = covered / total if total else 0.0

    freshness_parts = [
        1.0 if quote_age is not None and quote_age <= QUOTE_MAX_AGE_DAYS else 0.0,
        1.0 if bar_age is not None and bar_age <= BAR_MAX_AGE_DAYS else 0.0,
        macro_ratio,
    ]
    freshness_score = sum(freshness_parts) / len(freshness_parts)

    reasons: list[dict] = []
    for check in failed[:8]:
        reasons.append(
            {
                "code": f"qc.{check.kind}.{check.dataset}",
                "severity": check.severity or "warn",
                "message": check.detail or f"{check.dataset} 未通过",
                "impact": check.impact,
                "remediation": check.remediation,
                "action_job": check.action_job,
            }
        )
    if age_seconds is None:
        reasons.insert(
            0,
            {
                "code": "qc.missing",
                "severity": "warn",
                "message": "尚未运行数据质检，无法证明数据可用。",
                "impact": "所有研判结论按降级处理。",
                "remediation": "运行 check_data_quality。",
                "action_job": "check_data_quality",
            },
        )
    elif age_seconds > BATCH_MAX_AGE_SECONDS:
        reasons.insert(
            0,
            {
                "code": "qc.stale",
                "severity": "warn",
                "message": f"最新质检批次已过期 {age_seconds / 3600:.1f} 小时。",
                "impact": "数据状态可能已变化，结论按降级处理。",
                "remediation": "运行 check_data_quality。",
                "action_job": "check_data_quality",
            },
        )

    stale_datasets: list[str] = []
    if quote_age is None or quote_age > QUOTE_MAX_AGE_DAYS:
        stale_datasets.append("行情快照")
    if bar_age is None or bar_age > BAR_MAX_AGE_DAYS:
        stale_datasets.append("日线行情")
    if macro_rows and macro_ratio < 0.8:
        stale_datasets.append("宏观序列")

    if not checks:
        status = "unknown"
    elif critical_failed or (bar_age is not None and bar_age > BAR_MAX_AGE_DAYS) or (
        macro_rows and macro_ratio < 0.5
    ):
        status = "blocked"
    elif failed or age_seconds is None or age_seconds > BATCH_MAX_AGE_SECONDS or coverage_ratio < 0.8:
        status = "degraded"
    else:
        status = "ok"

    score = round(0.5 * qc_ratio + 0.3 * freshness_score + 0.2 * coverage_ratio, 3)
    factor = round(max(0.5, min(1.0, 0.70 + 0.30 * score)), 3)
    allow_action = status in {"ok", "degraded"}
    caveat = None
    if status == "blocked":
        caveat = "数据质量门控：阻断。相关结论只作研究，不生成可执行计划。"
    elif status == "degraded":
        caveat = "数据质量门控：降级。置信度已下调，执行前请核对失败项。"
    elif status == "unknown":
        caveat = "数据质量门控：未知。尚未完成质检，结论按降级处理。"

    return {
        "status": status,
        "score": score,
        "factor": factor,
        "allow_action": allow_action,
        "caveat": caveat,
        "batch_id": batch_id,
        "batch_age_seconds": int(age_seconds) if age_seconds is not None else None,
        "reasons": reasons,
        "stale_datasets": stale_datasets,
        "components": {
            "qc": {
                "status": "missing" if not checks else ("fail" if critical_failed else "pass"),
                "total": len(checks),
                "passed": passed,
                "failed": len(failed),
                "critical_failed": len(critical_failed),
            },
            "freshness": {
                "quotes_age_days": round(quote_age, 2) if quote_age is not None else None,
                "bars_age_days": round(bar_age, 2) if bar_age is not None else None,
                "macro_fresh_ratio": round(macro_ratio, 3),
            },
            "coverage": {"covered": covered, "total": total, "ratio": round(coverage_ratio, 3)},
        },
    }


def confidence_factor(quality_payload: dict) -> float:
    return float(quality_payload.get("factor") or 1.0)
