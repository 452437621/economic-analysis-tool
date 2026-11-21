"""M3 analytics unit tests: regime quadrant classification."""

from __future__ import annotations

import pytest

from app.analytics.regime import classify_quadrant

pytestmark = pytest.mark.unit


def test_quadrant_classification():
    assert classify_quadrant(1.0, 1.0) == "过热"
    assert classify_quadrant(1.0, -1.0) == "复苏"
    assert classify_quadrant(-1.0, 1.0) == "滞胀"
    assert classify_quadrant(-1.0, -1.0) == "衰退"
    assert classify_quadrant(0.0, 0.0) == "过渡"
