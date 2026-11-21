"""Single source of truth for job schedules, groups and dependencies.

APScheduler triggers, the ``jobs.cron`` display labels and the startup
supervisor all read the same registry, so a job's real cadence cannot drift
away from what the system status page advertises.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.platform.config import settings

CST = ZoneInfo(settings.timezone)


@dataclass(frozen=True)
class TriggerSpec:
    """One APScheduler trigger.

    ``kind="cron"`` uses ``hour/minute`` plus optional ``day_of_week`` or
    ``day``; ``kind="interval"`` uses ``seconds``.
    """

    kind: str
    hour: int | None = None
    minute: int | None = None
    day_of_week: str | None = None
    day: int | None = None
    seconds: int | None = None
    first_run_delay_seconds: int | None = None
    label: str = ""


@dataclass(frozen=True)
class JobPlan:
    name: str
    group: str
    triggers: tuple[TriggerSpec, ...]
    period_seconds: int | None = None
    depends_on: tuple[str, ...] = ()
    data_requirements: tuple[str, ...] = ()
    critical: bool = False
    max_lag_hours: float | None = None
    manual: bool = False
    startup: bool = True
    order: int = 0

    @property
    def cron_label(self) -> str:
        labels = [trigger.label for trigger in self.triggers if trigger.label]
        return " / ".join(labels) if labels else ("manual" if self.manual else "")

    @property
    def fixed_time(self) -> bool:
        return any(trigger.kind == "cron" for trigger in self.triggers)


@dataclass
class DueInfo:
    name: str
    group: str
    due_at: datetime | None
    overdue: bool
    action: str
    reason: str | None = None
    late_seconds: int = 0


def _at(day: date, trigger: TriggerSpec) -> datetime:
    return datetime.combine(day, time(int(trigger.hour or 0), int(trigger.minute or 0)), tzinfo=CST)


def _latest_daily(trigger: TriggerSpec, now: datetime) -> datetime:
    candidate = _at(now.date(), trigger)
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def _latest_weekly(trigger: TriggerSpec, now: datetime) -> datetime:
    target = (trigger.day_of_week or "sun").lower()
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    index = names.index(target) if target in names else 6
    candidate = _at(now.date(), trigger)
    delta = (candidate.weekday() - index) % 7
    candidate -= timedelta(days=delta)
    if candidate > now:
        candidate -= timedelta(days=7)
    return candidate


def _latest_monthly(trigger: TriggerSpec, now: datetime) -> datetime:
    def candidate_for(year: int, month: int) -> datetime:
        import calendar

        day = min(int(trigger.day or 1), calendar.monthrange(year, month)[1])
        return _at(date(year, month, day), trigger)

    candidate = candidate_for(now.year, now.month)
    if candidate > now:
        year, month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
        candidate = candidate_for(year, month)
    return candidate


def latest_occurrence(plan: JobPlan, now: datetime) -> datetime | None:
    """Latest scheduled occurrence at or before ``now`` (CST-aware)."""
    candidates: list[datetime] = []
    for trigger in plan.triggers:
        if trigger.kind != "cron":
            continue
        if trigger.day_of_week:
            candidates.append(_latest_weekly(trigger, now))
        elif trigger.day:
            candidates.append(_latest_monthly(trigger, now))
        else:
            candidates.append(_latest_daily(trigger, now))
    return max(candidates) if candidates else None


def _as_cst(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(CST)


def due_info(
    plan: JobPlan,
    last_run_at: datetime | None,
    now: datetime,
    *,
    enabled: bool = True,
    running: bool = False,
    force: bool = False,
) -> DueInfo:
    """Decide whether a job is overdue and what the supervisor should do."""
    if plan.manual:
        return DueInfo(plan.name, plan.group, None, False, "skip_manual", "手动作业不参与自动补跑")
    if not enabled:
        return DueInfo(plan.name, plan.group, None, False, "skip_disabled", "任务已禁用")
    if running:
        return DueInfo(plan.name, plan.group, None, False, "skip_running", "同名作业仍在运行")
    if force:
        due_at = latest_occurrence(plan, now) if plan.fixed_time else None
        return DueInfo(plan.name, plan.group, due_at, True, "run", "强制补跑", 0)

    last = _as_cst(last_run_at)
    if plan.fixed_time:
        due_at = latest_occurrence(plan, now)
        if due_at is None:
            return DueInfo(plan.name, plan.group, None, False, "skip_no_trigger", "未配置触发器")
        if last is not None and last >= due_at:
            return DueInfo(plan.name, plan.group, due_at, False, "none")
        late = max(0, int((now - due_at).total_seconds()))
        if not force and plan.max_lag_hours is not None:
            if late > plan.max_lag_hours * 3600:
                return DueInfo(
                    plan.name,
                    plan.group,
                    due_at,
                    False,
                    "skip_window",
                    f"错过计划窗口 {late / 3600:.1f}h，超过 {plan.max_lag_hours:g}h",
                    late,
                )
        return DueInfo(plan.name, plan.group, due_at, True, "run", "错过计划时点", late)

    period = plan.period_seconds
    if not period:
        return DueInfo(plan.name, plan.group, None, False, "skip_no_trigger", "未配置周期")
    grace = min(600, max(60, int(period * 0.1)))
    if last is None:
        return DueInfo(plan.name, plan.group, None, True, "run", "从未运行", 0)
    due_at = last + timedelta(seconds=period + grace)
    if now <= due_at:
        return DueInfo(plan.name, plan.group, due_at, False, "none")
    late = int((now - due_at).total_seconds())
    if not force and plan.max_lag_hours is not None and late > plan.max_lag_hours * 3600:
        return DueInfo(
            plan.name,
            plan.group,
            due_at,
            False,
            "skip_window",
            f"逾期 {late / 3600:.1f}h，超过 {plan.max_lag_hours:g}h",
            late,
        )
    return DueInfo(plan.name, plan.group, due_at, True, "run", "超过计划周期", late)


def _daily(hour: int, minute: int, *, delay: int | None = None) -> TriggerSpec:
    return TriggerSpec(
        "cron",
        hour=hour,
        minute=minute,
        first_run_delay_seconds=delay,
        label=f"{hour:02d}:{minute:02d}",
    )


def _interval(seconds: int, label: str, *, delay: int | None = None) -> TriggerSpec:
    return TriggerSpec("interval", seconds=seconds, first_run_delay_seconds=delay, label=label)


def _weekly(day: str, hour: int, minute: int) -> TriggerSpec:
    return TriggerSpec(
        "cron",
        hour=hour,
        minute=minute,
        day_of_week=day,
        label=f"{day} {hour:02d}:{minute:02d}",
    )


def _monthly(day: int, hour: int, minute: int) -> TriggerSpec:
    return TriggerSpec(
        "cron",
        hour=hour,
        minute=minute,
        day=day,
        label=f"每月{day}日 {hour:02d}:{minute:02d}",
    )


JOB_PLANS: dict[str, JobPlan] = {
    "heartbeat": JobPlan(
        "heartbeat",
        "system",
        (_interval(60, "every 60s"),),
        period_seconds=60,
        order=0,
    ),
    "collect_quotes": JobPlan(
        "collect_quotes",
        "data",
        (_interval(60, "every 60s", delay=3),),
        period_seconds=60,
        data_requirements=("quotes",),
        critical=True,
        max_lag_hours=2,
        order=10,
    ),
    "collect_daily_bars": JobPlan(
        "collect_daily_bars",
        "data",
        (_daily(15, 40), _daily(6, 30)),
        data_requirements=("daily_bars",),
        critical=True,
        max_lag_hours=36,
        order=20,
    ),
    "collect_rates": JobPlan(
        "collect_rates",
        "data",
        (_interval(3600, "every 1h", delay=15),),
        period_seconds=3600,
        data_requirements=("rates",),
        critical=True,
        max_lag_hours=12,
        order=30,
    ),
    "collect_macro": JobPlan(
        "collect_macro",
        "data",
        (_daily(8, 5),),
        data_requirements=("macro",),
        critical=True,
        max_lag_hours=36,
        order=40,
    ),
    "collect_calendar": JobPlan(
        "collect_calendar",
        "data",
        (_interval(21600, "every 6h", delay=20),),
        period_seconds=21600,
        order=50,
    ),
    "collect_positions": JobPlan(
        "collect_positions",
        "data",
        (_daily(15, 45),),
        max_lag_hours=36,
        order=60,
    ),
    "collect_gold": JobPlan(
        "collect_gold",
        "data",
        (_daily(16, 40),),
        data_requirements=("daily_bars",),
        critical=True,
        max_lag_hours=36,
        order=70,
    ),
    "collect_luoyang": JobPlan(
        "collect_luoyang",
        "data",
        (_daily(16, 50),),
        depends_on=("collect_daily_bars",),
        data_requirements=("daily_bars",),
        max_lag_hours=48,
        order=75,
    ),
    "collect_news": JobPlan(
        "collect_news",
        "data",
        (_interval(180, "every 3m", delay=8),),
        period_seconds=180,
        order=80,
    ),
    "collect_news_slow": JobPlan(
        "collect_news_slow",
        "data",
        (_daily(8, 15),),
        max_lag_hours=36,
        order=90,
    ),
    "collect_bodies": JobPlan(
        "collect_bodies",
        "data",
        (_interval(600, "every 10m", delay=60),),
        period_seconds=600,
        order=100,
    ),
    "extract_claims": JobPlan(
        "extract_claims",
        "derive",
        (_interval(900, "every 15m", delay=120),),
        period_seconds=900,
        depends_on=("collect_bodies",),
        order=110,
    ),
    "extract_events": JobPlan(
        "extract_events",
        "derive",
        (_interval(1800, "every 30m", delay=130),),
        period_seconds=1800,
        depends_on=("extract_claims",),
        order=120,
    ),
    "extract_claims_llm": JobPlan(
        "extract_claims_llm",
        "derive",
        (_interval(1200, "every 20m", delay=180),),
        period_seconds=1200,
        depends_on=("collect_bodies",),
        order=130,
    ),
    "check_data_quality": JobPlan(
        "check_data_quality",
        "quality",
        (_daily(15, 50),),
        depends_on=("collect_daily_bars", "collect_rates", "collect_macro"),
        data_requirements=("daily_bars", "macro", "quotes"),
        critical=True,
        max_lag_hours=36,
        order=200,
    ),
    "repair_data": JobPlan(
        "repair_data",
        "quality",
        (_daily(15, 55),),
        depends_on=("check_data_quality",),
        data_requirements=("daily_bars", "macro", "quotes"),
        max_lag_hours=36,
        order=210,
    ),
    "analyze": JobPlan(
        "analyze",
        "analysis",
        (_daily(16, 10),),
        depends_on=("check_data_quality",),
        data_requirements=("daily_bars", "macro"),
        critical=True,
        max_lag_hours=36,
        order=300,
    ),
    "cycle": JobPlan(
        "cycle",
        "analysis",
        (_daily(16, 20),),
        depends_on=("analyze",),
        data_requirements=("daily_bars", "macro"),
        critical=True,
        max_lag_hours=36,
        order=310,
    ),
    "lenses": JobPlan(
        "lenses",
        "analysis",
        (_daily(16, 25),),
        depends_on=("cycle",),
        data_requirements=("daily_bars", "macro"),
        critical=True,
        max_lag_hours=36,
        order=320,
    ),
    "decide": JobPlan(
        "decide",
        "decision",
        (_daily(16, 30),),
        depends_on=("analyze", "cycle", "lenses"),
        data_requirements=("daily_bars",),
        critical=True,
        max_lag_hours=36,
        order=400,
    ),
    "theses": JobPlan(
        "theses",
        "decision",
        (_daily(16, 35),),
        depends_on=("analyze", "cycle"),
        max_lag_hours=36,
        order=410,
    ),
    "ledger": JobPlan(
        "ledger",
        "decision",
        (_daily(16, 45),),
        depends_on=("lenses", "decide"),
        max_lag_hours=36,
        order=420,
    ),
    "score_predictions": JobPlan(
        "score_predictions",
        "report",
        (_daily(17, 0),),
        depends_on=("decide",),
        max_lag_hours=36,
        order=500,
    ),
    "scan_alerts": JobPlan(
        "scan_alerts",
        "report",
        (_interval(300, "every 5m", delay=45),),
        period_seconds=300,
        depends_on=("collect_quotes",),
        order=510,
    ),
    "brief_premarket": JobPlan(
        "brief_premarket",
        "report",
        (_daily(7, 30),),
        depends_on=("collect_daily_bars", "collect_macro", "analyze"),
        max_lag_hours=36,
        order=520,
    ),
    "brief_postmarket": JobPlan(
        "brief_postmarket",
        "report",
        (_daily(21, 0),),
        depends_on=("collect_daily_bars", "analyze"),
        max_lag_hours=36,
        order=530,
    ),
    "weekly_review": JobPlan(
        "weekly_review",
        "report",
        (_weekly("sun", 10, 0),),
        depends_on=("analyze", "cycle", "ledger"),
        max_lag_hours=96,
        order=540,
    ),
    "monthly_review": JobPlan(
        "monthly_review",
        "report",
        (_monthly(1, 10, 0),),
        depends_on=("analyze", "cycle", "ledger"),
        max_lag_hours=120,
        order=550,
    ),
    "timeline": JobPlan(
        "timeline",
        "system",
        (_weekly("sun", 9, 30),),
        max_lag_hours=96,
        startup=False,
        order=600,
    ),
    "backfill_history": JobPlan(
        "backfill_history",
        "data",
        (_weekly("sun", 9, 0),),
        data_requirements=("daily_bars",),
        max_lag_hours=96,
        startup=False,
        order=610,
    ),
    "brief_manual": JobPlan(
        "brief_manual",
        "report",
        (),
        manual=True,
        order=999,
    ),
}

#: Execution buckets. The supervisor runs these in order, respecting deps.
GROUP_ORDER = {
    "data": 0,
    "derive": 1,
    "quality": 2,
    "analysis": 3,
    "decision": 4,
    "report": 5,
    "system": 6,
}

#: Jobs the supervisor must never run directly.
SUPERVISOR_SKIP = frozenset({"heartbeat", "brief_manual"})


def ordered_jobs(group: str | None = None) -> list[JobPlan]:
    """Topologically ordered plans (dependencies first, then registry order)."""
    plans = [plan for plan in JOB_PLANS.values() if group is None or plan.group == group]
    selected_names = {plan.name for plan in plans}
    plans.sort(key=lambda plan: (GROUP_ORDER.get(plan.group, 99), plan.order, plan.name))
    resolved: list[JobPlan] = []
    remaining = list(plans)
    while remaining:
        progressed = False
        for plan in list(remaining):
            deps = [dep for dep in plan.depends_on if dep in selected_names]
            if all(any(dep == done.name for done in resolved) for dep in deps):
                resolved.append(plan)
                remaining.remove(plan)
                progressed = True
        if not progressed:
            # Dependency cycle or missing node: keep registry order so the
            # supervisor still makes progress and reports the anomaly.
            resolved.extend(sorted(remaining, key=lambda plan: (plan.order, plan.name)))
            break
    return resolved


def validate_registry() -> list[str]:
    """Return human-readable problems (empty means the registry is consistent)."""
    from app.jobs.runner import JOBS

    problems: list[str] = []
    expected = set(JOBS) | {"heartbeat"}
    missing = expected - set(JOB_PLANS)
    extra = set(JOB_PLANS) - expected
    if missing:
        problems.append(f"missing plans: {sorted(missing)}")
    if extra:
        problems.append(f"unknown plans: {sorted(extra)}")
    for plan in JOB_PLANS.values():
        for dep in plan.depends_on:
            if dep not in JOB_PLANS:
                problems.append(f"{plan.name} depends on unknown {dep}")
    return problems
