"""Shared topic scoring primitives."""

from __future__ import annotations

import pytest

from app.topics.scoring import (
    clip,
    combine_factors,
    factor,
    label_for_score,
    norm_pct,
    score_0_100,
    signal_of,
)

pytestmark = pytest.mark.unit


def _item(weight: float, score: float, available: bool = True) -> dict:
    return {"weight": weight, "score": score, "available": available}


def test_combine_factors_normalises_available_weight_only():
    result = combine_factors([_item(10, 50), _item(10, -50, available=False), _item(20, 25)])
    assert result["total_weight"] == 40
    assert result["available_weight"] == 30
    assert result["coverage"] == 75.0
    # Numerator: 10*0.5 + 20*0.25 = 10; /30*100 = 33.3
    assert result["score"] == pytest.approx(33.3, abs=0.1)
    assert result["available_count"] == 2
    assert result["total_count"] == 3


def test_combine_factors_handles_no_available_data():
    result = combine_factors([_item(10, 50, available=False)])
    assert result["score"] == 0.0
    assert result["coverage"] == 0.0
    assert result["label"] == "中性"


def test_zero_weight_items_do_not_count():
    result = combine_factors([_item(0, 100), _item(10, 20)])
    assert result["total_weight"] == 10
    assert result["total_count"] == 1


def test_score_is_clipped():
    result = combine_factors([_item(10, 400)])
    assert result["score"] == 100.0


def test_factor_applies_direction_and_contribution():
    item = factor(
        code="X",
        name="测试",
        category="price",
        category_label="价格",
        weight=10,
        direction=-1,
        score=0.5,
        available=True,
    )
    assert item["score"] == -50.0
    assert item["signal"] == "bearish"
    assert item["contribution"] == -5.0


def test_label_boundaries():
    assert label_for_score(50) == "强多"
    assert label_for_score(18) == "偏多"
    assert label_for_score(17.9) == "中性"
    assert label_for_score(-18) == "偏空"
    assert label_for_score(-50) == "强空"


def test_small_helpers():
    assert clip(3) == 1
    assert norm_pct(100) == 1
    assert norm_pct(0) == -1
    assert norm_pct(None) == 0
    assert signal_of(0.2) == "bullish"
    assert signal_of(-0.2) == "bearish"
    assert score_0_100(-100) == 0.0
    assert score_0_100(100) == 100.0
