"""连续性检查（`app.ingest.continuity`）的纯函数测试。

这套检查不预置交易日历，靠「同业共识」区分真缺口和休市日，所以测试重点是把
这几个边界钉住：共识阈值、组内人数不足、已登记停牌、长间隔阈值、异常值只看
最近一段。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.ingest import continuity


def _days(*values: str) -> set[date]:
    return {date.fromisoformat(value) for value in values}


# ---------------------------------------------------------------- consensus


def test_consensus_requires_share_of_group():
    """4 个成员里 3 个有数据（75%）= 共识日；只有 2 个有数据的日期不算。"""
    dates = {
        "A": _days("2026-11-02", "2026-11-03"),
        "B": _days("2026-11-02", "2026-11-03"),
        "C": _days("2026-11-02", "2026-11-03"),
        "D": _days("2026-11-02"),
    }
    assert continuity.consensus_dates(dates) == _days("2026-11-02", "2026-11-03")


def test_consensus_needs_at_least_three_members():
    """两个标的无法形成共识（可能是同一个源的同一缺口）。"""
    assert continuity.consensus_dates({"A": _days("2026-11-02"), "B": _days("2026-11-02")}) == set()


def test_consensus_three_members_needs_two_of_three():
    """n=3 时 floor(2.25)=2：只要有 2 个标的有数据就算交易日，
    否则 3 个成员的组里任何单标的缺口都会把那天踢出共识、永远报不出来。"""
    dates = {
        "A": _days("2026-11-02", "2026-11-03"),
        "B": _days("2026-11-02", "2026-11-03"),
        "C": _days("2026-11-02"),
    }
    assert continuity.consensus_dates(dates) == _days("2026-11-02", "2026-11-03")


# ---------------------------------------------------------------- gaps


def test_group_gaps_reports_missing_consensus_day():
    dates = {
        "A": _days("2026-11-02", "2026-11-03", "2026-11-04"),
        "B": _days("2026-11-02", "2026-11-03", "2026-11-04"),
        "C": _days("2026-11-02", "2026-11-04"),
    }
    findings = continuity.group_gaps(dates, dataset="日线行情")
    assert len(findings) == 1
    finding = findings[0]
    assert (finding.subject, finding.issue, finding.count) == ("C", "gap", 1)
    assert finding.missing == [date(2026, 11, 3)]
    assert "缺1个交易日(2026-11-03)" in finding.detail


def test_group_gaps_ignores_holiday_everyone_misses():
    """全体都没数据的日期（周末/假日）不是缺口。"""
    dates = {
        "A": _days("2026-11-02", "2026-11-04"),
        "B": _days("2026-11-02", "2026-11-04"),
        "C": _days("2026-11-02", "2026-11-04"),
    }
    assert continuity.group_gaps(dates, dataset="日线行情") == []


def test_group_gaps_ignores_dates_outside_symbol_range():
    """只检查标的自身覆盖区间：上市前/退市后的日期不算缺口。"""
    dates = {
        "A": _days("2026-11-02", "2026-11-03", "2026-11-04"),
        "B": _days("2026-11-02", "2026-11-03", "2026-11-04"),
        "C": _days("2026-11-04"),
    }
    assert continuity.group_gaps(dates, dataset="日线行情") == []


def test_group_gaps_honours_known_holds():
    """已登记的停牌窗口不算缺口（LME 镍 2022-03 停牌）。"""
    dates = {
        "HG": _days("2022-03-08", "2022-03-09", "2022-03-10"),
        "AL_LME": _days("2022-03-08", "2022-03-09", "2022-03-10"),
        "ZN_LME": _days("2022-03-08", "2022-03-09", "2022-03-10"),
        "NI_LME": _days("2022-03-08", "2022-03-10"),
    }
    assert continuity.KNOWN_HOLDS["NI_LME"]
    assert continuity.group_gaps(dates, dataset="日线行情") == []


def test_group_gaps_skipped_when_group_too_small():
    dates = {"A": _days("2026-11-02"), "B": _days("2026-11-02", "2026-11-03")}
    assert continuity.group_gaps(dates, dataset="日线行情") == []


def test_calendar_groups_follow_trading_calendar():
    """分组按交易日历：COMEX/NYMEX 与 ICE 布伦特/现货金不能放在同一共识组，
    否则 Good Friday（前者交易、后者休市）会被反复误报成缺口。"""
    groups = continuity.CALENDAR_GROUPS
    assert groups["COMEX/NYMEX"] == ("GC", "SI", "CL")
    members_of_others = {symbol for name, members in groups.items() if name != "COMEX/NYMEX" for symbol in members}
    assert "BZ" not in members_of_others
    assert "XAUUSD" not in members_of_others


# ---------------------------------------------------------------- silences


def test_silences_flags_long_gap():
    start = date(2026, 1, 1)
    dates = {"A": {start, start + timedelta(days=20)}}
    findings = continuity.silences(dates, dataset="宏观序列", max_days=12)
    assert len(findings) == 1
    assert findings[0].issue == "silence"
    assert "间隔20天" in findings[0].detail


def test_silences_ignores_gap_within_limit():
    start = date(2026, 1, 1)
    dates = {"A": {start, start + timedelta(days=10)}}
    assert continuity.silences(dates, dataset="宏观序列", max_days=12) == []


def test_silences_reports_worst_gap_only():
    start = date(2026, 1, 1)
    dates = {"A": {start, start + timedelta(days=15), start + timedelta(days=60)}}
    findings = continuity.silences(dates, dataset="宏观序列", max_days=12)
    assert len(findings) == 1
    assert "间隔45天" in findings[0].detail


# ---------------------------------------------------------------- anomalies


def _series(*rows: tuple[str, float, float, float, float]):
    return [(date.fromisoformat(day), o, h, l, c) for day, o, h, l, c in rows]


def test_anomalies_flags_recent_jump():
    series = {
        "NDX": _series(
            ("2026-11-13", 27900.0, 28000.0, 27800.0, 27943.74),
            ("2026-11-16", 10.09, 10.14, 9.88, 10.0),
        )
    }
    findings = continuity.anomalies(series, dataset="日线行情", today=date(2026, 11, 17))
    assert len(findings) == 1
    assert findings[0].issue == "outlier"
    assert "2026-11-16" in findings[0].detail


def test_anomalies_ignores_old_jump():
    """历史真实暴跌（2020 年油价）不该永远报警：只看最近 60 天。"""
    series = {
        "CL": _series(
            ("2020-04-20", 20.0, 21.0, 10.0, 20.0),
            ("2020-04-21", 10.0, 11.0, 9.0, 10.0),
        )
    }
    assert continuity.anomalies(series, dataset="日线行情", today=date(2026, 11, 17)) == []


def test_anomalies_flags_invalid_values():
    series = {
        "SR": _series(
            ("2026-11-16", 5343.0, 5300.0, 5400.0, 5343.0),  # high < low
            ("2026-11-17", 5343.0, 5300.0, 5400.0, 0.0),  # close <= 0
        )
    }
    findings = continuity.anomalies(series, dataset="日线行情", today=date(2026, 11, 17))
    assert len(findings) == 1
    assert findings[0].issue == "invalid"
    assert findings[0].count == 2


# ---------------------------------------------------------------- summarize


def test_summarize_clean():
    assert continuity.summarize([]) == (True, 0, "历史数据连续，无缺口/异常值")


def test_summarize_clean_mentions_registered_known_gaps():
    passed, problems, detail = continuity.summarize([], known_gaps=5)
    assert (passed, problems) == (True, 0)
    assert "5 个点属上游历史缺口" in detail


# ---------------------------------------------------------------- known gaps


def test_registered_known_gaps_are_not_reported_as_gaps():
    """已登记的上游历史缺口不再当缺口报（I 2015-02-25 就是这种）。"""
    dates = {
        "A": _days("2015-02-16", "2015-02-17", "2015-02-25", "2015-02-26"),
        "B": _days("2015-02-16", "2015-02-17", "2015-02-25", "2015-02-26"),
        "C": _days("2015-02-16", "2015-02-17", "2015-02-25", "2015-02-26"),
        "I": _days("2015-02-16", "2015-02-17", "2015-02-26"),
    }
    findings = continuity.group_gaps(dates, dataset="日线行情")
    assert findings == []


def test_known_gap_points_counts_only_still_missing_days():
    assert continuity.KNOWN_GAPS["I"] == frozenset({date(2015, 2, 25)})
    # I 补上了、P 只剩 3 天还缺（2017-10-09 已补）→ 只计 3 点。
    seen = {
        "I": _days("2015-02-25"),
        "P": _days("2017-10-09"),
    }
    assert continuity.known_gap_points(seen) == 3
    # 没采到的标的（不在 seen 里）不计入。
    assert continuity.known_gap_points({}) == 0


def test_summarize_lists_issues_and_counts_points():
    findings = [
        continuity.Finding(dataset="日线行情", subject="CF", issue="gap", detail="缺3天", count=3),
        continuity.Finding(dataset="日线行情", subject="NDX", issue="outlier", detail="1处跳变", count=1),
    ]
    passed, problems, detail = continuity.summarize(findings)
    assert (passed, problems) == (False, 2)
    assert "问题2处(涉及4个点)" in detail
    assert "CF:gap" in detail and "NDX:outlier" in detail


@pytest.mark.parametrize("limit", [1, 2])
def test_summarize_truncates_long_list(limit: int):
    findings = [
        continuity.Finding(dataset="d", subject=f"S{i}", issue="gap", detail="x", count=1)
        for i in range(5)
    ]
    _passed, _problems, detail = continuity.summarize(findings, limit=limit)
    assert "等5处" in detail
