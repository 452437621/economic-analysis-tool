"""需求 8/9：会员持仓 pipe 表格、英文标题中文对照、周/月报三节。

覆盖点：
- 日报的「会员持仓」是标准 Markdown 表格（表头 + 分隔行 + 数据行 + 表脚日期）；
- 事件/新闻的英文标题后带「（中文：…）」，且 `[D:xxx]` 证据标记仍在中文之后；
- 周报/月报含「会员持仓」节，并复用同一套取数/渲染 helper；
- ``zh_pairs`` 去重且不因未知文本抛异常。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.core import Document, Event, PositionSnapshot, Source
from app.narrative.brief import (
    build_markdown,
    pick_position_rows,
    position_rows,
    position_table_lines,
)
from app.narrative.monthly import build_monthly_markdown
from app.narrative.weekly import build_weekly_markdown
from app.narrative.zh import zh_pairs

KNOWN_TITLE = "PJM, ERCOT, and SWPP all set peak load records this summer"
POSITION_HEADER = "| 品种 | 多头(手) | 空头(手) | 净持仓(手) | 净占比 |"
POSITION_DATE = date(2026, 11, 17)

# product, name, long_pos, short_pos, net_pos, net_ratio（净占比从高到低排列）
_POSITIONS = [
    ("rb", "螺纹钢", 32000, 29000, 3000, 0.42),
    ("au", "沪金", 18000, 12000, 6000, 0.31),
    ("cu", "沪铜", 21000, 19000, 2000, 0.18),
    ("al", "沪铝", 15000, 17000, -2000, -0.15),
    ("ag", "沪银", 22000, 27000, -5000, -0.27),
    ("zn", "沪锌", 9000, 13000, -4000, -0.38),
    ("ni", "沪镍", 6000, 6000, 0, None),
]


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with maker() as handle:
        source = Source(name="TestWire", kind="news")
        handle.add(source)
        handle.flush()
        handle.add(
            Document(
                source_id=source.id,
                url_hash="test-brief-zh-hash",
                url="https://example.com/brief-zh",
                title=KNOWN_TITLE,
                published_at=datetime(2026, 11, 18, 9, 0),
            )
        )
        handle.add(
            Event(
                type="supply",
                title=KNOWN_TITLE,
                event_date=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
            )
        )
        for product, name, long_pos, short_pos, net_pos, net_ratio in _POSITIONS:
            handle.add(
                PositionSnapshot(
                    trade_date=POSITION_DATE,
                    product=product,
                    name=name,
                    long_pos=long_pos,
                    short_pos=short_pos,
                    net_pos=net_pos,
                    net_ratio=net_ratio,
                )
            )
        handle.commit()
        yield handle


def test_position_rows_picks_head_and_tail():
    """按 net_ratio 排序取头尾各 3、同品种去重；net_ratio 为空的品种不入选。"""
    rows = [
        {"product": f"p{i}", "name": f"品种{i}", "net_ratio": ratio, "trade_date": POSITION_DATE}
        for i, ratio in enumerate([0.5, 0.4, 0.3, 0.2, 0.1, 0.0, -0.1, -0.2, -0.3])
    ]
    picked = pick_position_rows(rows)
    assert [row["product"] for row in picked] == ["p0", "p1", "p2", "p6", "p7", "p8"]
    # 只有 3 条时不重复取；net_ratio=None 不参与排序
    assert len(pick_position_rows(rows[:3] + [{"product": "x", "name": "X", "net_ratio": None}])) == 3


def test_daily_brief_position_table_and_chinese_titles(session):
    markdown, _meta = build_markdown(session, "manual")

    # 1) 会员持仓：标准 pipe 表格 + 表脚日期
    assert POSITION_HEADER in markdown
    assert "|---|---|---|---|---|" in markdown
    assert "| **螺纹钢** | 32,000 | 29,000 | +3,000 | +42.0% |" in markdown
    assert "| **沪锌** | 9,000 | 13,000 | -4,000 | -38.0% |" in markdown
    assert "- 数据日期：2026-11-17（上期所/郑商所）" in markdown
    # 净占比为空的品种不进表格；头尾各 3 共 6 行
    assert "沪镍" not in markdown
    assert len(re.findall(r"^\| \*\*.+?\| \d", markdown, flags=re.M)) >= 6
    assert {row["product"] for row in position_rows(session)} == {
        "rb",
        "au",
        "cu",
        "al",
        "ag",
        "zn",
        "ni",
    }

    # 2) 事件/新闻：英文标题后带「（中文：…）」
    assert "事件驱动" in markdown and "新闻与政策" in markdown
    assert markdown.count("（中文：") >= 2
    assert re.search(r"^- \[[^\]]+\] .*?（中文：.+?）（关联 ", markdown, flags=re.M)
    assert re.search(r"^- \[[^\]]+\] .*?（中文：.+?）（.+?）`\[D:[0-9a-f]{32}\]`$", markdown, flags=re.M)

    # 3) [D:xxx] 证据标记仍是 32 位 hex，且在中文对照之后
    doc = session.scalar(select(Document))
    match = re.search(r"`\[D:([0-9a-f]{32})\]`", markdown)
    assert match is not None and match.group(1) == doc.id
    assert markdown.index("（中文：") < match.start()


def test_weekly_and_monthly_have_position_section():
    stats = {
        "briefs": 12,
        "signals": 20,
        "plans": 8,
        "alerts_total": 30,
        "alerts_critical": 4,
        "alerts_warn": 12,
        "resolved": 0,
        "brier": None,
        "hit_rate": None,
        "theses": 4,
        "thesis_hit_rate": 0.5,
        "data_checks_failed": 0,
        "calendar_events": 180,
        "analytics": 30,
        "wind_label": "避险",
        "wind_score": -54.7,
        "movers": [{"symbol": "AU", "change_20d": -4.2, "trend": "down"}],
    }
    rows = position_rows_cache()
    events = [{"id": "e" * 32, "type": "supply", "title": KNOWN_TITLE, "symbols": ["AU"]}]
    news = [
        {
            "id": "a" * 32,
            "title": KNOWN_TITLE,
            "source": "TestWire",
            "published_at": "2026-11-18T09:00:00+00:00",
        }
    ]
    zh_map = zh_pairs([KNOWN_TITLE], allow_llm=False)
    assert zh_map.get(KNOWN_TITLE)

    weekly = build_weekly_markdown(
        stats,
        date(2026, 11, 3),
        date(2026, 11, 9),
        "今日没有追高。",
        positions=rows,
        events=events,
        news=news,
        zh_map=zh_map,
    )
    assert "## 3. 会员持仓" in weekly
    assert POSITION_HEADER in weekly
    assert "- 数据日期：2026-11-17" in weekly
    assert "## 4. 事件驱动" in weekly and "## 5. 新闻与政策" in weekly
    assert weekly.count("（中文：") >= 2

    monthly = build_monthly_markdown(
        stats,
        date(2026, 11, 1),
        date(2026, 11, 30),
        positions=rows,
        events=events,
        news=news,
        zh_map=zh_map,
    )
    assert "## 3. 会员持仓" in monthly
    assert POSITION_HEADER in monthly
    assert "## 4. 事件驱动" in monthly and "## 5. 新闻与政策" in monthly
    assert "本月校准清单" in monthly
    assert monthly.count("（中文：") >= 2


def position_rows_cache() -> list[dict]:
    """不依赖数据库的持仓行，供纯函数 builder 测试使用。"""
    return [
        {
            "trade_date": POSITION_DATE,
            "product": product,
            "name": name,
            "long_pos": long_pos,
            "short_pos": short_pos,
            "net_pos": net_pos,
            "net_ratio": net_ratio,
        }
        for product, name, long_pos, short_pos, net_pos, net_ratio in _POSITIONS
    ]


def test_position_table_lines_empty_and_md_cell_escape():
    assert position_table_lines([]) == ["- 暂无会员持仓数据"]
    escaped = position_table_lines(
        [
            {
                "trade_date": POSITION_DATE,
                "product": "rb",
                "name": "螺纹|钢",
                "long_pos": 1,
                "short_pos": 0,
                "net_pos": 1,
                "net_ratio": 0.5,
            }
        ]
    )
    # 单元格里的 `|` 会被 _md_cell 换成全角，表格不会被拆列
    assert "| **螺纹｜钢** |" in escaped[2]


def test_zh_pairs_dedupes_without_raising():
    pairs = zh_pairs([KNOWN_TITLE, KNOWN_TITLE, "   ", "Unseen english headline"], allow_llm=False)
    assert "峰值负荷" in pairs[KNOWN_TITLE]
    assert "" not in pairs
    assert zh_pairs([], allow_llm=False) == {}
