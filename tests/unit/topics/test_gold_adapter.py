"""Gold topic adapter helpers."""

from __future__ import annotations

import pytest

from app.topics.gold import _chart

pytestmark = pytest.mark.unit


def test_chart_uses_a_union_date_axis_for_mixed_frequencies():
    series_map = {
        "DAILY": [{"t": "2026-01-02", "v": 1.0}, {"t": "2026-01-05", "v": 2.0}],
        "MONTHLY": [{"t": "2026-01-31", "v": 10.0}],
    }
    chart = _chart("mixed", "混合", "吨", series_map, [("DAILY", "日频"), ("MONTHLY", "月频")])
    assert chart["dates"] == ["2026-01-02", "2026-01-05", "2026-01-31"]
    assert chart["series"][1]["values"] == [None, None, 10.0]
    assert chart["hasData"] is True
