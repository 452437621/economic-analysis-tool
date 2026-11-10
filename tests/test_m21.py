"""M21: brief mainline emphasis + driver/watchlist tables."""

from __future__ import annotations

from app.init_db import seed_instruments, seed_watchlist
from app.narrative.brief import build_markdown
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
