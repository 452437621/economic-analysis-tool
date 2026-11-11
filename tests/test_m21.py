"""M21: brief mainline emphasis + driver/watchlist tables."""

from __future__ import annotations

from app.init_db import seed_instruments, seed_watchlist
from app.narrative.brief import build_markdown, order_rate_rows
from app.platform.db import SessionLocal, init_db


def test_brief_mainline_drivers_and_watchlist_are_tables():
    init_db()
    seed_instruments()
    seed_watchlist()
    with SessionLocal() as session:
        markdown, _meta = build_markdown(session, "manual")
    assert "> **一句话主线：" in markdown
    assert "| 动力 | 方向 | 强度 | 证据 |" in markdown
    assert "### 重点关注（自选）" in markdown or "### 重点关注" in markdown
    assert "| 品种 | 代码 | 最新 | 涨跌 | 20日 | 分组 |" in markdown
    assert "| 品种 | 代码 | 最新 | 涨跌幅 | 数据源 | 时点 |" in markdown


def test_rate_rows_order_by_country_and_maturity():
    rows = [
        {"code": "FR10Y", "name": "法国", "value": 4.4, "ts": None},
        {"code": "JP10Y", "name": "日本", "value": 2.8, "ts": None},
        {"code": "US10Y", "name": "美国10Y", "value": 4.8, "ts": None},
        {"code": "CN2Y", "name": "中国2Y", "value": 1.2, "ts": None},
        {"code": "US2Y", "name": "美国2Y", "value": 4.5, "ts": None},
        {"code": "DE10Y", "name": "德国", "value": 3.3, "ts": None},
    ]
    ordered = order_rate_rows(rows)
    assert [row["code"] for row in ordered] == [
        "US2Y",
        "US10Y",
        "CN2Y",
        "JP10Y",
        "DE10Y",
        "FR10Y",
    ]
    assert ordered[-1]["country"] == "法国"
