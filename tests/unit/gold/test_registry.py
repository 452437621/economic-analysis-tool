"""Gold monitoring tests: indicator registry consistency."""

from __future__ import annotations

import pytest

from app.gold.registry import INDICATORS, manual_codes

pytestmark = pytest.mark.unit


def test_registry_is_consistent():
    assert len(INDICATORS) >= 19
    assert "LBMA_GOLD_TONNES" in INDICATORS
    assert "ETF_GLOBAL_TONNES" in INDICATORS
    assert "COT_MONEY_NET" in INDICATORS
    manual = manual_codes()
    # 已找到自动数据源的手动指标应转入自动采集
    assert "CB_GOLD_GLOBAL_TONNES" not in manual
    assert "COMEX_GOLD_INVENTORY_TONNES" not in manual
    assert "MM_BANK_GOLD_NET" not in manual
    # BIS 官方无公开序列，仍保留手动录入
    assert "BIS_GOLD_LEASE_RATE" in manual or "BIS_GOLD_SWAP_USD" in manual
    for item in INDICATORS.values():
        assert item.weight >= 0
        assert item.direction in (1, -1)
        assert item.category
