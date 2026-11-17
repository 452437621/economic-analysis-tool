"""休市伪日线的识别与剔除。

新浪财经的「连续合约 / 外盘」历史接口在交易所休市日**不会留空**，而是塞一根
伪日线：开高低直接复制上一个交易日，收盘也常常照抄。实例（DB 实测）：

* CU 2015-09-03（抗战纪念日休市）：O/H/L 与 09-02 完全相同，volume=0
* M  2015-09-03：O/H/L 复制 09-02，close 取前一日开盘价 2675，volume 1689500
  （前一天 1689576，差 76 手）
* I  2015-09-03：O/H 与前一日相同，低点差 0.5，成交量 1734400 对 1734406
* GC 2016-12-26（圣诞休市）：O=H=L=C=1135.2，正好等于 12-23 的收盘价，volume=0
* XAUUSD 2018-12-25：O/H/L 与 12-24 完全相同

这些假数据不会让曲线断开，却会**污染「共识交易日」**：同组里别的标的没有这一天，
检查就会把正常标的（CF/SR/CL）误报成缺数据。所以要在落库前剔掉、并把历史里的
存量清掉。

判定必须**只打休市日、不碰真实交易日**——实测两个反例：

* GC 2023-01-17（马丁·路德·金日之后第一个交易日）：开盘价与最高价照抄了 01-16
  （1923.8 / 1931.8），但低点和收盘是真的，这是上游「复制前一日开高」的毛病，
  不是休市。删掉它反而让真实交易日缺一根。
* CL 2022-09-06（劳工节后第一个交易日）：同样复制了 09-05 的开盘价与最高价。

所以规则里「成交量」这一条只在**双方都有成交量**时才算证据（外盘/汇率源没有成交量，
0 对 0 不能算「成交量被复制」）；「单点报价」这条也只在**整条序列并不是天然单点**
的时候才用（新浪外汇日线是每天一个价的格式，O=H=L=C，按单点判会误删七成的行）。
"""

from __future__ import annotations

from datetime import date

from app.ingest.contracts import Bar

# 一根日线的 (open, high, low, close, volume)。
OHLCV = tuple[float | None, float | None, float | None, float | None, float | None]

# 成交量「几乎相同」的容差：绝对 1 手，或相对 0.1%。
VOLUME_ABS_TOLERANCE = 1.0
VOLUME_REL_TOLERANCE = 0.001
# 序列里「单点报价」占比超过该比例，就认为这是数据格式而非休市伪日线。
SINGLE_PRINT_SHARE = 0.5
# 单点报价判定的「收盘没动」容差：5bp。实测 GC 2018-12-25 存 1272.504，
# 前一交易日收 1272.503，只差 0.001，用全等判断会漏掉。
FLAT_CLOSE_TOLERANCE = 0.0005


def _same(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return abs(left - right) < 1e-9


def _positive(value: float | None) -> bool:
    return value is not None and value > 0


def _volume_same(left: float | None, right: float | None) -> bool:
    if not (_positive(left) and _positive(right)):
        return False
    tolerance = max(VOLUME_ABS_TOLERANCE, abs(right) * VOLUME_REL_TOLERANCE)  # type: ignore[arg-type]
    return abs(left - right) <= tolerance  # type: ignore[operator]


def is_holiday_stub(current: OHLCV, prev: OHLCV | None, *, series_is_single_print: bool = False) -> bool:
    """``current`` 是否看起来是休市日伪造出来的那根日线。

    ``series_is_single_print`` 为真时直接判定「不是」：整条序列每天只有一个价
    （新浪外汇日线）时，任何「重复前值」都可能只是行情没动，无从区分。
    """
    if prev is None or series_is_single_print:
        return False
    open_, high, low, close, volume = current
    prev_open, prev_high, prev_low, prev_close, prev_volume = prev
    if not prev_close or not close:
        return False
    # 规则 1：整根 OHLC 复制前一交易日（休市日直接拿前一日行情填充）。
    if _same(open_, prev_open) and _same(high, prev_high) and _same(low, prev_low):
        return True
    # 规则 1b：开、高相同，且双方都有成交量并几乎一致（伪造行把成交量也复制了）。
    if _same(open_, prev_open) and _same(high, prev_high) and _volume_same(volume, prev_volume):
        return True
    # 规则 2：单点报价 + 没有成交量 + 收盘与前一日几乎相同（拿前收填的新一天）。
    if (
        _same(high, low)
        and not _positive(volume)
        and abs(close / prev_close - 1.0) <= FLAT_CLOSE_TOLERANCE
    ):
        return True
    return False


def _ohlcv(bar: Bar) -> OHLCV:
    return (bar.open, bar.high, bar.low, bar.close, bar.volume)


def is_single_print_series(series: list[OHLCV]) -> bool:
    """整条序列是否「每天只有一个价格」（新浪外汇日线就是这种格式）。"""
    if not series:
        return False
    singles = sum(1 for open_, high, low, _close, _volume in series if _same(high, low) and _same(open_, high))
    return singles / len(series) >= SINGLE_PRINT_SHARE


def drop_holiday_stubs(bars: list[Bar]) -> list[Bar]:
    """按日期顺序剔除伪日线（保持输入顺序，O(n)）。"""
    rows = [_ohlcv(bar) for bar in bars]
    single_print = is_single_print_series(rows)
    kept: list[Bar] = []
    prev: OHLCV | None = None
    for bar, current in zip(bars, rows):
        if is_holiday_stub(current, prev, series_is_single_print=single_print):
            continue
        kept.append(bar)
        prev = current
    return kept


def stub_dates(series: list[tuple[date, float | None, float | None, float | None, float | None, float | None]]) -> list[date]:
    """从 ``(date, open, high, low, close, volume)`` 序列里找出伪日线日期。"""
    rows = [(open_, high, low, close, volume) for _day, open_, high, low, close, volume in series]
    single_print = is_single_print_series(rows)
    out: list[date] = []
    prev: OHLCV | None = None
    for (day, *_rest), current in zip(series, rows):
        if is_holiday_stub(current, prev, series_is_single_print=single_print):
            out.append(day)
            continue
        prev = current
    return out
