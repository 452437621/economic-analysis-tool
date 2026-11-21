"""Shared helpers used by the ingest collector modules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.ingest import store
from app.ingest.contracts import MacroPoint
from app.ingest.macro_meta import MACRO_SERIES_META


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_float(value) -> float | None:
    """Fiscal Data / World Bank 的金额是字符串，且空值可能是 "null"。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"null", "none", "nan", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None

def _parse_day(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def _month_end(day: datetime) -> datetime:
    """返回该日所在月份的月末 UTC 零点（月频观测的时间戳口径）。"""
    first = day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (first + timedelta(days=32)).replace(day=1)
    return next_month - timedelta(days=1)

def _annual_points(code: str, years: dict[str, float]) -> list[MacroPoint]:
    """年频观测按 12-31 落库；WEO 的预测年份（> 当前年）不落库。"""
    current = datetime.now(timezone.utc).year
    points: list[MacroPoint] = []
    for year, value in years.items():
        try:
            number = int(str(year)[:4])
        except (TypeError, ValueError):
            continue
        if number > current:
            continue
        points.append(
            MacroPoint(code=code, ts=datetime(number, 12, 31, tzinfo=timezone.utc), value=float(value))
        )
    return points

def _imf_years(data: dict[str, dict[str, float]], iso3: str) -> dict[str, float]:
    """IMF 返回键可能是 ISO3（USA）或两位代码（US），两种都接受。"""
    for key in (iso3.upper(), iso3[:2].upper()):
        if key in data:
            return data[key]
    return {}

def _store_macro_points(session, code: str, points: list[MacroPoint], source_id: str, stats: dict) -> int:
    """按 (series_id, ts_utc) 幂等 upsert；同一时间点重复出现时保留最后一条。"""
    if not points:
        return 0
    unique: dict[datetime, float] = {}
    for point in points:
        unique[point.ts] = point.value
    ordered = [MacroPoint(code=code, ts=ts, value=value) for ts, value in sorted(unique.items())]
    meta = MACRO_SERIES_META.get(code, {})
    n = store.upsert_macro(
        session,
        code,
        ordered,
        source_id=source_id,
        name=meta.get("name"),
        unit=meta.get("unit"),
        country=meta.get("country"),
        freq=meta.get("freq"),
    )
    if n:
        stats["obs"] += n
        stats["series"] += 1
    return n
