"""休市伪日线判定（用例全部来自 DB 实测的历史脏数据）。"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from app.ingest import bars_quality
from app.ingest.contracts import Bar


def _bar(day: date, values: tuple[float, float, float, float, float | None]) -> Bar:
    open_, high, low, close, volume = values
    return Bar(
        ts=datetime.combine(day, time.min, tzinfo=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


# 2015-09-03 抗战胜利纪念日休市，新浪给国内期货补了假 K 线。
CU_0902 = (39020.0, 39450.0, 38930.0, 39210.0, 30904.0)
CU_0903 = (39020.0, 39450.0, 38930.0, 39000.0, 0.0)
M_0902 = (2698.0, 2716.0, 2679.0, 2690.0, 1689576.0)
M_0903 = (2698.0, 2716.0, 2656.0, 2675.0, 1689500.0)
I_0902 = (388.0, 393.0, 385.5, 390.0, 1734406.0)
I_0903 = (388.0, 393.0, 386.0, 389.0, 1734400.0)
P_0902 = (4300.0, 4314.0, 4234.0, 4286.0, 0.0)
P_0903 = (4300.0, 4314.0, 4234.0, 4274.0, 0.0)


def test_repeated_ohlc_is_stub():
    assert bars_quality.is_holiday_stub(CU_0903, CU_0902) is True
    assert bars_quality.is_holiday_stub(M_0903, M_0902) is True
    assert bars_quality.is_holiday_stub(P_0903, P_0902) is True


def test_slightly_different_low_with_copied_volume_is_stub():
    # 新浪没把开高低全抄，但把成交量复制了（只差几十手）。
    assert bars_quality.is_holiday_stub(I_0903, I_0902) is True


def test_single_print_at_previous_close_is_stub():
    # GC 2016-12-26 圣诞休市：O=H=L=C=1135.2，正好等于 12-23 收盘价。
    prev = (1129.9, 1137.3, 1129.5, 1135.2, 0.0)
    stub = (1135.2, 1135.2, 1135.2, 1135.2, 0.0)
    assert bars_quality.is_holiday_stub(stub, prev) is True


def test_single_print_at_previous_close_tolerates_rounding():
    # GC 2018-12-25 实际存 1272.504，前一交易日收 1272.503（差 0.001）。
    prev = (1260.7, 1273.9, 1259.1, 1272.503, 0.0)
    stub = (1272.504, 1272.5, 1272.5, 1272.504, 0.0)
    assert bars_quality.is_holiday_stub(stub, prev) is True


def test_repeated_ohlcv_row_is_stub():
    # HG 2018-12-25：整根 OHLCV 与 12-24 完全相同。
    prev = (2.6835, 2.7115, 2.6675, 2.7035, 41616.0)
    assert bars_quality.is_holiday_stub(prev, prev) is True


def test_copied_open_high_on_real_trading_day_is_kept():
    # GC 2023-01-17（马丁·路德·金日后的第一个交易日）：开、高照抄 01-16，
    # 低点和收盘是真的。这不是休市，删掉会让真实交易日出现缺口。
    prev = (1923.8, 1931.8, 1913.9, 1918.2, 0.0)
    current = (1923.8, 1931.8, 1906.2, 1911.1, 0.0)
    assert bars_quality.is_holiday_stub(current, prev) is False


def test_copied_open_high_on_real_trading_day_is_kept_even_with_same_volume_zero():
    # CL 2022-09-06（劳工节后第一个交易日）：开、高照抄 09-05。
    prev = (86.84, 90.39, 86.81, 88.87, 0.0)
    current = (86.84, 90.39, 86.18, 86.93, 0.0)
    assert bars_quality.is_holiday_stub(current, prev) is False


def test_flat_placeholder_with_different_close_is_kept():
    # NI 2016-04-05：单点报价 + 零成交，但收盘与前一日不同，属于「真实交易日
    # 上游只给了一个价」，不能当休市删掉（删了就是缺口）。
    prev = (66070.0, 66830.0, 66010.0, 66340.0, 472770.0)
    current = (66100.0, 66100.0, 66100.0, 66100.0, 0.0)
    assert bars_quality.is_holiday_stub(current, prev) is False


def test_real_trading_day_after_holiday_is_kept():
    cu_0907 = (39260.0, 39560.0, 39100.0, 39440.0, 18500.0)
    assert bars_quality.is_holiday_stub(cu_0907, CU_0902) is False
    # 铁矿石 2015-09-07 一字涨停：high == low，但有成交量，属于真行情。
    i_0907 = (467.0, 467.0, 467.0, 467.0, 467.0)
    assert bars_quality.is_holiday_stub(i_0907, I_0902) is False


def test_first_bar_is_never_a_stub():
    assert bars_quality.is_holiday_stub(CU_0903, None) is False


def test_fx_single_print_series_is_not_cleaned():
    """新浪外汇日线每天只有一个价（O=H=L=C），按单点规则会误删大半行。"""
    series = [
        (date(2021, 11, 10), 1.1595, 1.1595, 1.1595, 1.1595, None),
        (date(2021, 11, 11), 1.1595, 1.1595, 1.1595, 1.1595, None),
        (date(2021, 11, 12), 1.1448, 1.1448, 1.1448, 1.1448, None),
        (date(2021, 11, 15), 1.1444, 1.1444, 1.1444, 1.1444, None),
        (date(2021, 11, 16), 1.1382, 1.1382, 1.1382, 1.1382, None),
    ]
    assert bars_quality.stub_dates(series) == []


def test_drop_holiday_stubs_keeps_order_and_real_bars():
    bars = [
        _bar(date(2015, 9, 2), CU_0902),
        _bar(date(2015, 9, 3), CU_0903),  # 伪日线，剔除
        _bar(date(2015, 9, 7), (39260.0, 39560.0, 39100.0, 39440.0, 18500.0)),
    ]
    kept = bars_quality.drop_holiday_stubs(bars)
    assert [item.ts.date() for item in kept] == [date(2015, 9, 2), date(2015, 9, 7)]


def test_stub_dates_reports_removed_days():
    series = [
        (date(2015, 9, 2), *CU_0902),
        (date(2015, 9, 3), *CU_0903),
        (date(2015, 9, 7), 39260.0, 39560.0, 39100.0, 39440.0, 18500.0),
    ]
    assert bars_quality.stub_dates(series) == [date(2015, 9, 3)]


def test_is_single_print_series():
    single = [(1.0, 1.0, 1.0, 1.0, None), (2.0, 2.0, 2.0, 2.0, None)]
    ranged = [(1.0, 1.5, 0.5, 1.2, 10.0), (2.0, 2.5, 1.5, 2.2, 20.0)]
    assert bars_quality.is_single_print_series(single) is True
    assert bars_quality.is_single_print_series(ranged) is False
    assert bars_quality.is_single_print_series([]) is False
