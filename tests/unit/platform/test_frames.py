"""Shared long-to-wide frame helper."""

from __future__ import annotations

import pytest

from datetime import datetime, timezone

import pandas as pd

from app.platform.frames import pivot_series_rows

pytestmark = pytest.mark.unit


def test_pivot_keeps_last_duplicate_per_key_day() -> None:
    day = datetime(2026, 1, 2, tzinfo=timezone.utc)
    rows = [
        ("AU", day, 1.0),
        ("AU", day, 2.0),
        ("CU", day, 3.0),
    ]
    frame = pivot_series_rows(rows, key="key", ts="ts", value="value", drop_duplicates=True)
    assert list(frame.columns) == ["AU", "CU"]
    assert frame.loc[pd.Timestamp("2026-01-02"), "AU"] == 2.0
    assert frame.loc[pd.Timestamp("2026-01-02"), "CU"] == 3.0


def test_pivot_aggregates_duplicates_when_requested() -> None:
    rows = [
        ("US10Y", datetime(2026, 1, 2, tzinfo=timezone.utc), 4.0),
        ("US10Y", datetime(2026, 1, 2, tzinfo=timezone.utc), 4.4),
    ]
    frame = pivot_series_rows(rows, key="code", ts="ts", value="value", aggfunc="last")
    assert frame.iloc[0, 0] == 4.4


def test_pivot_empty_rows_returns_empty_frame() -> None:
    frame = pivot_series_rows([], key="key", ts="ts", value="value")
    assert frame.empty


def test_pivot_normalises_utc_dates() -> None:
    rows = [
        ("AU", datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc), 1.0),
        ("AU", datetime(2026, 1, 2, 1, 0, tzinfo=timezone.utc), 2.0),
    ]
    frame = pivot_series_rows(rows, key="key", ts="ts", value="value", drop_duplicates=True)
    assert list(frame.index) == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")]
    assert frame.index[1] - frame.index[0] == pd.Timedelta(days=1)
