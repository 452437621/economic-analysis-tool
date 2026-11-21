"""Cross-source reconciliation helpers.

When the same series is available from two providers, compare the latest common
observation and surface material divergence as a QC warning.  The primary value
is never silently replaced; the secondary value is kept in ``expected`` so a
human can inspect both.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.ingest import quality
from app.ingest.contracts import MacroPoint
from app.models.core import DataCheck


def _latest_by_day(points: list[MacroPoint]) -> dict[date, float]:
    out: dict[date, float] = {}
    for point in points:
        out[point.ts.date()] = float(point.value)
    return out


def compare_series(
    primary: list[MacroPoint],
    secondary: list[MacroPoint],
    *,
    tolerance: float = 0.005,
) -> dict | None:
    left = _latest_by_day(primary)
    right = _latest_by_day(secondary)
    common = sorted(set(left) & set(right))
    if not common:
        return None
    day = common[-1]
    expected = left[day]
    actual = right[day]
    if not expected:
        return None
    deviation = abs(actual - expected) / abs(expected)
    if deviation <= tolerance:
        return None
    return {
        "as_of": day.isoformat(),
        "expected": expected,
        "actual": actual,
        "deviation": deviation,
        "tolerance": tolerance,
    }


def record_divergence(
    session: Session,
    *,
    batch_id: str,
    dataset: str,
    symbol: str,
    finding: dict,
    action_job: str | None,
) -> DataCheck:
    return quality.add_check(
        session,
        batch_id,
        kind="reconcile",
        dataset=dataset,
        symbol=symbol,
        expected=finding["expected"],
        actual=finding["actual"],
        deviation=finding["deviation"],
        passed=False,
        severity="warn",
        detail=(
            f"{finding['as_of']}：主源 {finding['expected']:g} / 备源 {finding['actual']:g}，"
            f"偏差 {finding['deviation'] * 100:.2f}% > {finding['tolerance'] * 100:.1f}%"
        ),
        action_job=action_job,
    )
