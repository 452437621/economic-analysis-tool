"""M4/M5 decision layer unit tests: position sizing and trade plans."""

from __future__ import annotations

import pytest

from app.decision.plans import build_plan, size_lots, size_position

pytestmark = pytest.mark.unit


def test_position_sizing():
    size = size_position(1_000_000, 0.25, price=100, stop_price=95)
    assert abs(size - 500) < 1e-6
    assert size_position(1_000_000, 0.25, 100, 100) == 0


def test_plan_construction_and_checks():
    signal = {
        "symbol": "AU",
        "type": "breakout",
        "direction": "long",
        "price": 500.0,
        "atr": 10.0,
        "strength": 0.8,
        "note": "test",
        "params": {},
    }
    plan = build_plan(signal, equity=1_000_000, risk_pct=0.25)
    assert plan["side"] == "long"
    assert plan["stop"] < plan["entry_low"]
    assert plan["targets"]["T1"] > plan["entry_high"]
    assert plan["targets"]["T2"] > plan["targets"]["T1"]
    assert all(check["passed"] for check in plan["checks"])
    assert plan["size"] > 0


def test_size_lots_contract_size():
    # 1000g/lot, 10 CNY stop -> 10,000 CNY risk per lot; 2500 risk budget -> 0.25 lot
    lots = size_lots(1_000_000, 0.25, price=500, stop_price=490, contract_size=1000)
    assert abs(lots - 0.25) < 1e-6


def test_build_plan_contract_checks():
    signal = {
        "symbol": "M",
        "type": "breakout",
        "direction": "long",
        "price": 3000.0,
        "atr": 20.0,
        "strength": 0.9,
        "note": "test",
        "params": {},
    }
    plan = build_plan(
        signal,
        spec={"contract_size": 10, "margin_pct": 0.08, "fee_per_lot": 1.5},
        equity=1_000_000,
        risk_pct=0.25,
    )
    assert plan["size"] >= 1
    assert plan["margin"] > 0
    assert plan["fee"] > 0
    assert all(check["passed"] for check in plan["checks"])
    assert plan["weight_pct"] > 0
    assert plan["stop_distance_pct"] > 0
    assert plan["risk_reward"] > 0


def test_build_plan_is_funding_agnostic():
    """昂贵合约只输出小数手，不再因「资金不足」被 0 手或拦截。"""
    signal = {
        "symbol": "AU",
        "type": "breakout",
        "direction": "long",
        "price": 900.0,
        "atr": 10.0,
        "strength": 0.9,
        "note": "test",
        "params": {},
    }
    expensive = build_plan(
        signal,
        spec={"contract_size": 1000, "margin_pct": 0.09, "fee_per_lot": 10},
        equity=1_000_000,
        risk_pct=0.25,
    )
    assert 0 < expensive["size"] < 1
    assert expensive["lots_int"] == 0
    assert "不足 1 整手" in expensive["sizing_note"]
    assert all(check["rule"] != "手数 ≥ 1" for check in expensive["checks"])
    assert all(check["passed"] for check in expensive["checks"])
    # 默认基准权益与显式权益只影响规模，不影响检查项语义
    default_plan = build_plan(signal, spec={"contract_size": 1000, "margin_pct": 0.09, "fee_per_lot": 10})
    assert default_plan["base_equity"] == 100_000.0
    assert default_plan["equity"] == default_plan["base_equity"]
    assert default_plan["size"] < expensive["size"]
    assert abs(default_plan["size"] * 10 - expensive["size"]) < 0.01
