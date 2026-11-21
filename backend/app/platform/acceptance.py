"""Structured acceptance / DoD checks with actionable failure explanations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.alerts import Alert
from app.ingest import quality
from app.jobs.supervisor import assess_readiness, schedule_status
from app.models.core import (
    AnalyticsResult,
    Brief,
    Claim,
    Document,
    DocumentBody,
    EconomicEvent,
    Instrument,
    Job,
    MacroObs,
    MarketBar,
    Quote,
    ScheduleCheck,
    Signal,
    Thesis,
    TradePlan,
)
from app.platform.quality_gate import assess as assess_quality

ERROR = "error"
WARN = "warn"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _job_hint(session: Session, name: str | None) -> str | None:
    if not name:
        return None
    if name == "schedule_check":
        row = session.scalar(select(ScheduleCheck).order_by(ScheduleCheck.started_at.desc()).limit(1))
        if row is None:
            return "调度自检从未运行。"
        return (
            f"调度自检最近一次 {_iso(row.started_at)} 状态 {row.status}"
            f"{'：' + str(row.error) if row.error else ''}"
        )
    job = session.scalar(select(Job).where(Job.name == name))
    if job is None:
        return f"作业 {name} 尚未注册。"
    hint = f"作业 {name} 最近 {_iso(job.last_run_at) or '从未'} 状态 {job.last_status or '未知'}"
    if job.last_error:
        hint += f"，错误：{job.last_error[:300]}"
    return hint


def _check(
    *,
    check_id: str,
    name: str,
    category: str,
    status: str,
    severity: str,
    actual,
    required=None,
    detail=None,
    reason=None,
    impact=None,
    remediation=None,
    action_job=None,
) -> dict:
    return {
        "id": check_id,
        "name": name,
        "category": category,
        "status": status,
        "severity": severity,
        "passed": status != "fail",
        "required": required,
        "actual": actual,
        "detail": detail if detail is not None else str(actual if actual is not None else "—"),
        "reason": reason,
        "impact": impact,
        "remediation": remediation,
        "action_job": action_job,
    }


def _count_check(
    *,
    check_id: str,
    name: str,
    category: str,
    actual: int,
    required: int,
    impact: str,
    remediation: str,
    action_job: str | None,
    session: Session,
) -> dict:
    passed = actual >= required
    reason = None
    if not passed:
        reason = f"当前 {actual}，要求 ≥ {required}，差 {required - actual}。"
        hint = _job_hint(session, action_job)
        if hint:
            reason += hint
    return _check(
        check_id=check_id,
        name=name,
        category=category,
        status="pass" if passed else "fail",
        severity="error",
        actual=actual,
        required=required,
        reason=reason,
        impact=None if passed else impact,
        remediation=None if passed else remediation,
        action_job=action_job,
    )


def build_acceptance(session: Session, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    counts = {
        "instruments": int(session.scalar(select(func.count()).select_from(Instrument)) or 0),
        "market_bars": int(session.scalar(select(func.count()).select_from(MarketBar)) or 0),
        "quotes": int(session.scalar(select(func.count()).select_from(Quote)) or 0),
        "macro": int(session.scalar(select(func.count()).select_from(MacroObs)) or 0),
        "calendar": int(session.scalar(select(func.count()).select_from(EconomicEvent)) or 0),
        "documents": int(session.scalar(select(func.count()).select_from(Document)) or 0),
        "bodies": int(session.scalar(select(func.count()).select_from(DocumentBody)) or 0),
        "claims": int(session.scalar(select(func.count()).select_from(Claim)) or 0),
        "briefs": int(session.scalar(select(func.count()).select_from(Brief)) or 0),
        "analytics": int(session.scalar(select(func.count()).select_from(AnalyticsResult)) or 0),
        "signals": int(session.scalar(select(func.count()).select_from(Signal)) or 0),
        "plans": int(session.scalar(select(func.count()).select_from(TradePlan)) or 0),
        "theses": int(session.scalar(select(func.count()).select_from(Thesis)) or 0),
        "alerts": int(session.scalar(select(func.count()).select_from(Alert)) or 0),
    }

    checks: list[dict] = [
        _count_check(
            check_id="data.instruments",
            name="行情标的 ≥ 20",
            category="data",
            actual=counts["instruments"],
            required=20,
            impact="标的太少，市场覆盖不足。",
            remediation="运行 seed_instruments 或检查 config/default.yaml。",
            action_job=None,
            session=session,
        ),
        _count_check(
            check_id="data.market_bars",
            name="日线 ≥ 10,000",
            category="data",
            actual=counts["market_bars"],
            required=10000,
            impact="趋势、信号与回测样本不足。",
            remediation="运行 collect_daily_bars；历史缺口再运行 backfill_history。",
            action_job="collect_daily_bars",
            session=session,
        ),
        _count_check(
            check_id="data.quotes",
            name="行情快照 ≥ 20",
            category="data",
            actual=counts["quotes"],
            required=20,
            impact="总览、告警与盘前简报缺少实时价。",
            remediation="运行 collect_quotes 并检查数据源备用链。",
            action_job="collect_quotes",
            session=session,
        ),
        _count_check(
            check_id="data.macro",
            name="宏观观测 ≥ 1,000",
            category="data",
            actual=counts["macro"],
            required=1000,
            impact="宏观层、透镜与周期读数不足。",
            remediation="运行 collect_rates / collect_macro。",
            action_job="collect_macro",
            session=session,
        ),
        _count_check(
            check_id="data.calendar",
            name="财经日历 ≥ 20",
            category="data",
            actual=counts["calendar"],
            required=20,
            impact="事件驱动研判与预警缺少日历。",
            remediation="运行 collect_calendar。",
            action_job="collect_calendar",
            session=session,
        ),
        _count_check(
            check_id="knowledge.documents",
            name="新闻 ≥ 10",
            category="knowledge",
            actual=counts["documents"],
            required=10,
            impact="事件抽取与简报语料不足。",
            remediation="运行 collect_news。",
            action_job="collect_news",
            session=session,
        ),
        _count_check(
            check_id="knowledge.bodies",
            name="正文 ≥ 10",
            category="knowledge",
            actual=counts["bodies"],
            required=10,
            impact="证据链无法引用原文。",
            remediation="运行 collect_bodies。",
            action_job="collect_bodies",
            session=session,
        ),
        _count_check(
            check_id="knowledge.claims",
            name="断言 ≥ 50",
            category="knowledge",
            actual=counts["claims"],
            required=50,
            impact="证据与论点缺少可验证断言。",
            remediation="运行 extract_claims；配置 LLM Key 后可运行 extract_claims_llm。",
            action_job="extract_claims",
            session=session,
        ),
        _count_check(
            check_id="output.briefs",
            name="简报 ≥ 1",
            category="output",
            actual=counts["briefs"],
            required=1,
            impact="没有可读的盘前/盘后输出。",
            remediation="运行 brief_premarket 或 brief_postmarket。",
            action_job="brief_premarket",
            session=session,
        ),
        _count_check(
            check_id="output.analytics",
            name="分析结果 ≥ 10",
            category="output",
            actual=counts["analytics"],
            required=10,
            impact="分析引擎没有产出。",
            remediation="运行 analyze，并先确认数据就绪。",
            action_job="analyze",
            session=session,
        ),
        _count_check(
            check_id="output.signals",
            name="信号 ≥ 1",
            category="output",
            actual=counts["signals"],
            required=1,
            impact="没有可执行的交易信号。",
            remediation="运行 decide，并检查数据质量门控。",
            action_job="decide",
            session=session,
        ),
        _count_check(
            check_id="output.plans",
            name="计划 ≥ 1",
            category="output",
            actual=counts["plans"],
            required=1,
            impact="没有交易计划草案。",
            remediation="运行 decide；若质量门控阻断，先修复数据。",
            action_job="decide",
            session=session,
        ),
        _count_check(
            check_id="output.theses",
            name="论点 ≥ 1",
            category="output",
            actual=counts["theses"],
            required=1,
            impact="分析依据页没有论点。",
            remediation="运行 theses。",
            action_job="theses",
            session=session,
        ),
    ]

    batch_id, qc_rows = quality.latest_batch(session)
    age = quality.batch_age_seconds(session, current)
    failed_qc = [row for row in qc_rows if not row.passed]
    critical_qc = [
        row for row in failed_qc if (row.severity or "warn").lower() in {"error", "critical"}
    ]
    if not qc_rows:
        checks.append(
            _check(
                check_id="quality.latest_batch",
                name="数据质检最新批次",
                category="quality",
                status="fail",
                severity=ERROR,
                actual="无批次",
                required="≤36h 且存在",
                reason="尚未运行数据质检，无法证明当前数据可用。",
                impact="周期/透镜/决策可能使用过期或缺失数据。",
                remediation="运行 check_data_quality，再运行 repair_data。",
                action_job="check_data_quality",
            )
        )
    else:
        stale = age is None or age > 36 * 3600
        checks.append(
            _check(
                check_id="quality.latest_batch",
                name="数据质检最新批次",
                category="quality",
                status="fail" if stale else "pass",
                severity=ERROR if stale else "info",
                actual=f"{age / 3600:.1f}h" if age is not None else "未知",
                required="≤36h",
                reason=(
                    f"最近批次 {batch_id or 'legacy'} 已过期 {age / 3600:.1f} 小时。"
                    if stale and age is not None
                    else None
                ),
                impact="质检结论失效，系统按降级处理。" if stale else None,
                remediation="运行 check_data_quality。" if stale else None,
                action_job="check_data_quality" if stale else None,
            )
        )
        checks.append(
            _check(
                check_id="quality.failed",
                name="数据质检全部通过",
                category="quality",
                status="fail" if critical_qc else ("warn" if failed_qc else "pass"),
                severity=ERROR if critical_qc else (WARN if failed_qc else "info"),
                actual=len(failed_qc),
                required=0,
                reason=(
                    f"最新批次有 {len(failed_qc)} 项失败，其中 {len(critical_qc)} 项为关键失败。"
                    if failed_qc
                    else None
                ),
                impact="相关研判可能使用偏差/过期数据。" if failed_qc else None,
                remediation="查看失败项的 cause/remediation，运行 repair_data。" if failed_qc else None,
                action_job="repair_data" if failed_qc else None,
            )
        )

    schedule = schedule_status(session, current)
    overdue = [row for row in schedule["jobs"] if row["overdue"]]
    critical_overdue = [row for row in overdue if row["critical"]]
    checks.append(
        _check(
            check_id="scheduler.overdue",
            name="无逾期关键作业",
            category="schedule",
            status="fail" if critical_overdue else ("warn" if overdue else "pass"),
            severity=ERROR if critical_overdue else (WARN if overdue else "info"),
            actual=len(overdue),
            required=0,
            reason=(
                f"{len(overdue)} 个作业逾期，其中关键作业 {len(critical_overdue)} 个："
                + ", ".join(row["name"] for row in (critical_overdue or overdue)[:5])
                if overdue
                else None
            ),
            impact="逾期作业对应的数据/结论停留在旧时点。" if overdue else None,
            remediation="运行调度自检触发补跑；查看 job_runs 失败原因。" if overdue else None,
            action_job="schedule_check" if overdue else None,
        )
    )
    last_check = session.scalar(
        select(ScheduleCheck).order_by(ScheduleCheck.started_at.desc()).limit(1)
    )
    check_stale = (
        last_check is None
        or last_check.finished_at is None
        or (current - last_check.finished_at.replace(tzinfo=timezone.utc)
            if last_check.finished_at.tzinfo is None
            else current - last_check.finished_at) > timedelta(hours=26)
    )
    check_status = last_check.status if last_check else None
    check_failed_status = check_status in {"blocked", "error", "interrupted"}
    checks.append(
        _check(
            check_id="scheduler.last_check",
            name="调度自检最近 26h 内完成",
            category="schedule",
            status=(
                "fail"
                if check_stale or check_failed_status
                else ("warn" if check_status in {"degraded", "running"} else "pass")
            ),
            severity=ERROR if check_stale or check_failed_status else (WARN if check_status == "degraded" else "info"),
            actual=check_status or "无",
            required="ok/degraded 且 ≤26h",
            reason=(
                "调度自检从未完成或已超过 26 小时。"
                if check_stale
                else (
                    f"最近自检状态 {check_status}，未能完成补跑。"
                    if check_failed_status
                    else None
                )
            ),
            impact="无法确认停机期间错过的作业已补跑。",
            remediation="运行调度自检（schedule_check）。",
            action_job="schedule_check",
        )
    )

    from app.ingest.chains import chain_summaries

    chains = chain_summaries(session, current)
    critical_chains = [chain for chain in chains if chain["critical"]]
    down = [chain for chain in critical_chains if chain["status"] == "down"]
    degraded = [
        chain for chain in critical_chains if chain["status"] in {"degraded", "unknown"}
    ]
    checks.append(
        _check(
            check_id="sources.critical_chains",
            name="关键数据域至少一条可用链",
            category="source",
            status="fail" if down else ("warn" if degraded else "pass"),
            severity=ERROR if down else (WARN if degraded else "info"),
            actual=f"{len(critical_chains) - len(down)}/{len(critical_chains)}",
            required="全部可用",
            reason=(
                "以下关键链全部候选不可用："
                + ", ".join(chain["id"] for chain in down[:5])
                if down
                else (
                    "以下关键链主源失败/冷却或尚未检查，备用可用："
                    + ", ".join(chain["id"] for chain in degraded[:5])
                    if degraded
                    else None
                )
            ),
            impact="对应行情/利率/宏观数据可能停更。" if down or degraded else None,
            remediation="查看数据源健康与备用链，运行对应采集作业。"
            if down or degraded
            else None,
            action_job=down[0]["action_job"] if down else None,
        )
    )

    readiness = assess_readiness(session, current)
    checks.append(
        _check(
            check_id="freshness.readiness",
            name="关键数据就绪",
            category="freshness",
            status="fail" if readiness.blocked else ("warn" if readiness.status == "degraded" else "pass"),
            severity=ERROR if readiness.blocked else (WARN if readiness.status == "degraded" else "info"),
            actual=readiness.status,
            required="ok/degraded",
            reason="；".join(reason["message"] for reason in readiness.reasons) or None,
            impact="数据不完整时不能生成可信的研判结论。"
            if readiness.status != "ok"
            else None,
            remediation="运行 collect_daily_bars / collect_macro / collect_quotes。"
            if readiness.status != "ok"
            else None,
            action_job=next(
                (reason.get("action_job") for reason in readiness.reasons if reason.get("action_job")),
                None,
            ),
        )
    )

    gate = assess_quality(session, now=current)
    coverage_ratio = gate["components"]["coverage"]["ratio"]
    checks.append(
        _check(
            check_id="coverage.series",
            name="宏观序列覆盖 ≥ 80%",
            category="freshness",
            status="fail" if coverage_ratio < 0.5 else ("warn" if coverage_ratio < 0.8 else "pass"),
            severity=ERROR if coverage_ratio < 0.5 else (WARN if coverage_ratio < 0.8 else "info"),
            actual=f"{coverage_ratio * 100:.1f}%",
            required="80%",
            reason=f"当前覆盖 {coverage_ratio * 100:.1f}%，低于 80%。" if coverage_ratio < 0.8 else None,
            impact="宏观层与人物透镜可用读数不足。" if coverage_ratio < 0.8 else None,
            remediation="运行 collect_macro / collect_rates，并检查备用源。"
            if coverage_ratio < 0.8
            else None,
            action_job="collect_macro" if coverage_ratio < 0.8 else None,
        )
    )

    failed = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]
    hints: list[str] = []
    for check in failed[:8]:
        hint = _job_hint(session, check.get("action_job"))
        if hint:
            hints.append(f"{check['name']}：{hint}")
    return {
        "status": "fail" if failed else ("warn" if warnings else "pass"),
        "passed": not failed,
        "checks": checks,
        "counts": counts,
        "failed_summary": {
            "count": len(failed),
            "failed": [
                {
                    "id": check["id"],
                    "name": check["name"],
                    "severity": check["severity"],
                    "actual": check["actual"],
                    "required": check["required"],
                    "reason": check["reason"],
                    "impact": check["impact"],
                    "remediation": check["remediation"],
                    "action_job": check["action_job"],
                }
                for check in failed
            ],
            "hints": hints,
        },
        "warnings_summary": {
            "count": len(warnings),
            "warnings": [check["name"] for check in warnings],
        },
        "generated_at": _iso(current),
    }
