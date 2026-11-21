"""Shared pandas helpers for long-to-wide time-series frames.

Analytics and the cycle engine load different row shapes from SQLite but use
the same UTC-day normalisation.  Keeping that logic here prevents the two
pipelines from drifting on duplicate handling or timezone conversion.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def pivot_series_rows(
    rows: Sequence[tuple],
    *,
    key: str,
    ts: str,
    value: str,
    aggfunc: str = "last",
    drop_duplicates: bool = False,
) -> pd.DataFrame:
    """Pivot ``(key, ts, value)`` rows into a date-indexed wide frame.

    ``drop_duplicates`` keeps the last observation for a key/day before
    pivoting (analytics); otherwise ``aggfunc`` resolves duplicates (cycle).
    """
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows, columns=[key, ts, value])
    frame["date"] = (
        pd.to_datetime(frame[ts], utc=True).dt.tz_convert(None).dt.normalize()
    )
    if drop_duplicates:
        frame = frame.drop_duplicates(subset=[key, "date"], keep="last")
    return (
        frame.pivot_table(index="date", columns=key, values=value, aggfunc=aggfunc)
        .sort_index()
    )
