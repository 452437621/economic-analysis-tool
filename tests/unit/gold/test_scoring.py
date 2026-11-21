"""Gold monitoring tests: score computation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.gold.scoring import compute_gold_score
from app.models.core import GoldMetric
from app.platform.db import SessionLocal, init_db

pytestmark = pytest.mark.unit


def test_scoring_with_synthetic_metrics():
    init_db()
    with SessionLocal() as session:
        # 清理测试数据
        for row in session.query(GoldMetric).filter(GoldMetric.source == "test").all():
            session.delete(row)
        session.commit()
        base = datetime(2026, 10, 1, tzinfo=timezone.utc)
        rows = [
            ("ETF_GLOBAL_TONNES", 0, 4000.0),
            ("ETF_GLOBAL_TONNES", 31, 4100.0),
            ("US10Y_REAL", 0, 2.0),
            ("US10Y_REAL", 31, 1.5),
            ("CN_GOLD_RESERVES_USD", 0, 3000.0),
            ("CN_GOLD_RESERVES_USD", 31, 3060.0),
        ]
        for code, offset, value in rows:
            session.add(
                GoldMetric(
                    code=code,
                    as_of=base + __import__("datetime").timedelta(days=offset),
                    value=value,
                    source="test",
                )
            )
        session.commit()
        score = compute_gold_score(session)
        assert -100 <= score["score"] <= 100
        assert score["coverage"] >= 0
        factor_codes = {factor["code"] for factor in score["factors"]}
        assert "ETF_GLOBAL_TONNES" in factor_codes
        assert "SGE_GOLD_LEASE_3M_PCT" in factor_codes
        for row in session.query(GoldMetric).filter(GoldMetric.source == "test").all():
            session.delete(row)
        session.commit()
