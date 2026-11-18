"""Coverage / freshness metrics shared by the system and cycle APIs.

The V2.0 UI shows one number for "how complete is the data right now". It must
be cheap to compute (a handful of aggregate queries, no full scan) and it must
never raise on an empty database: a fresh install should show 0%, not a 500.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Job, MacroObs, MacroSeries, MarketBar, Quote

#: A macro series counts as covered when its newest observation is this fresh.
SERIES_FRESH_DAYS = 45

#: Per-frequency freshness windows (days). Annual IMF/World Bank series would
#: otherwise be flagged stale for ~11 months of the year and drag the composite
#: score down, so the window follows the series' own publication cadence.
#: Annual = 800 days: World Bank / IMF annual values can lag 18~24 months behind
#: the reference year, so a 400-day window flags "upstream has not published yet".
FRESH_DAYS_BY_FREQ: dict[str, int] = {
    "d": 4,
    "w": 12,
    "m": 45,
    "q": 120,
    "y": 800,
}

#: Weights of the composite data-quality score (documented in ``QUALITY_METHOD``).
COVERAGE_WEIGHT = 0.6
JOBS_WEIGHT = 0.4

QUALITY_METHOD = (
    "data_quality_pct = 60% × 序列覆盖率 + 40% × 作业健康率；"
    f"序列覆盖率 = 最新观测仍在新发布窗口内的 macro_series 占比（"
    "窗口按序列频率取值：日 4 天 / 周 12 天 / 月 45 天 / 季 120 天 / 年 800 天，缺省 "
    f"{SERIES_FRESH_DAYS} 天；series_covered / series_total）；作业健康率 = jobs.last_status == "
    "'ok' 的占比（jobs_ok / jobs_total）；last_sync 取 quotes / macro_obs / market_bars 三张表"
    "最大 ts_utc；无数据时各项为 0/null 而不报错。"
)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def series_coverage(session: Session, now: datetime | None = None) -> tuple[int, int]:
    """Return ``(series_covered, series_total)`` for macro series freshness.

    Freshness is judged against each series' own publication frequency so that a
    quarterly IMF series or an annual World Bank series is not reported as stale
    just because it has not printed in 45 days.
    """
    rows = session.execute(
        select(MacroSeries.freq, func.max(MacroObs.ts_utc))
        .join(MacroObs, MacroObs.series_id == MacroSeries.id, isouter=True)
        .group_by(MacroSeries.id)
    ).all()
    total = len(rows)
    if total == 0:
        return 0, 0
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is not None:
        ref = ref.astimezone(timezone.utc).replace(tzinfo=None)
    covered = 0
    for freq, latest in rows:
        if latest is None:
            continue
        window = FRESH_DAYS_BY_FREQ.get((freq or "m").lower(), SERIES_FRESH_DAYS)
        if latest >= ref - timedelta(days=window):
            covered += 1
    return covered, total


def latest_sync(session: Session) -> str | None:
    """Newest write timestamp across quotes, macro observations and market bars."""
    stamps = [
        session.scalar(select(func.max(Quote.ts_utc))),
        session.scalar(select(func.max(MacroObs.ts_utc))),
        session.scalar(select(func.max(MarketBar.ts_utc))),
    ]
    present = [stamp for stamp in stamps if stamp is not None]
    if not present:
        return None
    return _iso(max(present))


def job_health(session: Session) -> tuple[int, int]:
    """Return ``(jobs_ok, jobs_total)`` where ok means ``last_status == "ok"``."""
    total = int(session.scalar(select(func.count()).select_from(Job)) or 0)
    ok = int(
        session.scalar(select(func.count()).select_from(Job).where(Job.last_status == "ok")) or 0
    )
    return ok, total


def data_quality_pct(
    series_covered: int, series_total: int, jobs_ok: int, jobs_total: int
) -> float:
    """Composite 0–100 score; empty datasets contribute 0 instead of failing."""
    coverage = series_covered / series_total if series_total else 0.0
    health = jobs_ok / jobs_total if jobs_total else 0.0
    return round(100.0 * (COVERAGE_WEIGHT * coverage + JOBS_WEIGHT * health), 1)
