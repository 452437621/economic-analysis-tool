"""落库前的行情护栏（`pipeline._guard_tail_bar`）与脏点订正（`backfill.repair_outliers`）。

两处都在处理同一类上游故障：腾讯原始端点 `us.NDX` 会把某一天的纳斯达克100
行情写成 close=10.0。护栏负责「不让它进库」，订正负责「已经进库的改回来」。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.ingest import backfill, pipeline
from app.ingest.contracts import Bar


def _bar(day: str, close: float, *, open_=None, high=None, low=None, volume=100.0) -> Bar:
    ts = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    return Bar(
        ts=ts,
        open=open_ if open_ is not None else close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=volume,
    )


@pytest.fixture()
def fetched(monkeypatch):
    """记录 `tencent.fetch_daily_kline` 的调用，并返回预设结果。"""
    calls: list[tuple[str, bool]] = []
    responses: dict[str, list[Bar]] = {}

    def fake_fetch(client, code, count=320, *, adjust=True):  # noqa: ANN001
        calls.append((code, adjust))
        return responses.get(code, [])

    monkeypatch.setattr(pipeline.tencent, "fetch_daily_kline", fake_fetch)
    return SimpleNamespace(calls=calls, responses=responses)


# ---------------------------------------------------------------- 落库前护栏


def test_guard_keeps_normal_tail(fetched):
    """正常波动直接返回，且不额外发请求。"""
    bars = [_bar("2026-11-13", 27943.74), _bar("2026-11-16", 27197.15)]
    kept = pipeline._guard_tail_bar(object(), "NDX", bars)
    assert [bar.close for bar in kept] == [27943.74, 27197.15]
    assert fetched.calls == []


def test_guard_corrects_corrupt_tail_from_single_bar(fetched):
    """串码｜−100%｜：用单根接口拿到当日正确收盘后就地订正，时间戳不变。"""
    fetched.responses["usNDX"] = [_bar("2026-11-16", 27197.15, open_=27543.64, high=27594.67, low=27401.2)]
    bars = [_bar("2026-11-13", 27943.74), _bar("2026-11-16", 10.0)]
    kept = pipeline._guard_tail_bar(object(), "NDX", bars)
    assert len(kept) == 2
    assert kept[-1].close == 27197.15
    assert kept[-1].ts == bars[-1].ts
    assert (kept[-1].open, kept[-1].high, kept[-1].low) == (27543.64, 27594.67, 27401.2)
    assert fetched.calls == [("usNDX", True)]


def test_guard_drops_tail_when_single_bar_is_for_another_day(fetched):
    """单根接口只给当日一根：日期对不上就不能拿去写历史（宁可留缺口）。"""
    fetched.responses["usNDX"] = [_bar("2026-11-17", 27000.0)]
    bars = [_bar("2026-11-13", 27943.74), _bar("2026-11-16", 10.0)]
    kept = pipeline._guard_tail_bar(object(), "NDX", bars)
    assert [bar.close for bar in kept] == [27943.74]


def test_guard_drops_tail_when_single_bar_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline.tencent, "fetch_daily_kline", boom)
    bars = [_bar("2026-11-13", 27943.74), _bar("2026-11-16", 10.0)]
    kept = pipeline._guard_tail_bar(object(), "NDX", bars)
    assert [bar.close for bar in kept] == [27943.74]


def test_guard_drops_tail_when_no_single_bar_mapping(fetched):
    """没有单根接口的标的（如 A股）只能丢弃，不能拿错源的数据凑。"""
    bars = [_bar("2026-11-13", 4000.0), _bar("2026-11-16", 100.0)]
    kept = pipeline._guard_tail_bar(object(), "000300", bars)
    assert [bar.close for bar in kept] == [4000.0]
    assert fetched.calls == []


def test_guard_ignores_single_bar_that_is_still_extreme(fetched):
    """单根接口自己也可能给错：偏离仍超阈值就丢弃。"""
    fetched.responses["usNDX"] = [_bar("2026-11-16", 9.0)]
    bars = [_bar("2026-11-13", 27943.74), _bar("2026-11-16", 10.0)]
    kept = pipeline._guard_tail_bar(object(), "NDX", bars)
    assert [bar.close for bar in kept] == [27943.74]


def test_guard_needs_two_bars(fetched):
    bars = [_bar("2026-11-16", 10.0)]
    assert pipeline._guard_tail_bar(object(), "NDX", bars) == bars


# ---------------------------------------------------------------- 已入库脏点订正


class _FakeSession:
    def __init__(self) -> None:
        self.deleted: list[object] = []
        self.commits = 0

    def scalar(self, _stmt):  # noqa: ANN001
        return SimpleNamespace(id="inst-ndx")

    def execute(self, stmt):  # noqa: ANN001
        self.deleted.append(stmt)

    def commit(self) -> None:
        self.commits += 1


@pytest.fixture()
def repair_env(monkeypatch):
    session = _FakeSession()
    upserts: list[list[Bar]] = []

    monkeypatch.setattr(
        backfill.continuity, "load_daily_bars",
        lambda _session: {"NDX": [
            (date(2026, 11, 13), 27800.0, 28000.0, 27700.0, 27943.74),
            (date(2026, 11, 16), 10.09, 10.14, 9.88, 10.0),
        ]},
    )
    monkeypatch.setattr(
        backfill.store, "get_source",
        lambda _session, **_kw: SimpleNamespace(id="src-tencent"),
    )
    monkeypatch.setattr(
        backfill.store, "upsert_bars",
        lambda _session, _iid, _tf, bars, _sid: (upserts.append(list(bars)) or len(bars)),
    )
    return SimpleNamespace(session=session, upserts=upserts)


def test_repair_outliers_rewrites_matching_day(repair_env, monkeypatch):
    monkeypatch.setattr(
        backfill.tencent, "fetch_daily_kline",
        lambda client, code, count=320, adjust=True: [_bar("2026-11-16", 27197.15)],
    )
    stats = backfill.repair_outliers(repair_env.session, object())
    assert stats["repaired"] == 1 and stats["dropped"] == 0
    assert repair_env.upserts[0][0].close == 27197.15
    assert repair_env.upserts[0][0].ts == datetime(2026, 11, 16, tzinfo=timezone.utc)


def test_repair_outliers_drops_point_when_single_bar_is_another_day(repair_env, monkeypatch):
    """单根接口给的是今天：不能把今天的价格写进 11-16，只能删掉这根脏数据。"""
    monkeypatch.setattr(
        backfill.tencent, "fetch_daily_kline",
        lambda client, code, count=320, adjust=True: [_bar("2026-11-17", 27000.0)],
    )
    stats = backfill.repair_outliers(repair_env.session, object())
    assert stats["repaired"] == 0 and stats["dropped"] == 1
    assert repair_env.upserts == []
    assert repair_env.session.deleted


def test_repair_outliers_ignores_normal_series(repair_env, monkeypatch):
    monkeypatch.setattr(
        backfill.continuity, "load_daily_bars",
        lambda _session: {"NDX": [
            (date(2026, 11, 13), 27800.0, 28000.0, 27700.0, 27943.74),
            (date(2026, 11, 16), 27900.0, 28100.0, 27800.0, 28000.0),
        ]},
    )
    calls: list[str] = []
    monkeypatch.setattr(
        backfill.tencent, "fetch_daily_kline",
        lambda *args, **kwargs: calls.append("called") or [],
    )
    stats = backfill.repair_outliers(repair_env.session, object())
    assert stats == {"repaired": 0, "dropped": 0, "checked": 0, "errors": []}
    assert calls == []
