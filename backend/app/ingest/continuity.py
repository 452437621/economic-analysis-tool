"""历史数据连续性与完整性检查。

为什么不预置交易日历：中国/美国/英国/日本的节假日每年不同，维护一份硬编码
日历迟早会和交易所公告对不上，而且新增标的还要手工归类。这里改用「同业共识」：
同一市场组里**绝大多数标的都有数据的那一天**，就是这个市场的交易日；某个标的
在那天没数据，才是真缺口。周末、各国银行假日、LME 与美股的差异因此自动被排除。

三类问题分开报告，避免「一个异常值把整条序列判死」：

* ``gap``     同业共识日里缺少的交易日（趋势图会连出错误的斜率）
* ``silence`` 连续 N 天完全没有数据（不依赖共识，单标的也能发现长时间断更）
* ``outlier`` 相邻两根收盘价偏离超过阈值（多为上游返回了错误行情/股票误码）
* ``invalid`` 收盘价非正、最高价低于最低价这类非法值

所有函数都不写库，只返回 :class:`Finding`，便于单测与复用。
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import symbols as S
from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar

logger = logging.getLogger(__name__)

# 同一市场组：组内标的交易日历一致，可互为「共识」参照。
# 组内成员数 < 3 时无法形成共识，只做 silence（长间隔）检查。
# 分组按**交易日历**而不是资产类别：COMEX/NYMEX 在 Good Friday 照常交易，
# 而 ICE 布伦特与现货金（伦敦/OTC）休市——放在一组就会互相误报缺口。
# BZ/XAUUSD 因此不进共识组，只由 silence + outlier 兜住。
CALENDAR_GROUPS: dict[str, tuple[str, ...]] = {
    "国内期货": tuple(S.CN_FUTURES),
    "美股指数": ("SPX", "NDX", "DJIA"),
    "COMEX/NYMEX": ("GC", "SI", "CL"),
    "LME金属": ("HG", "AL_LME", "ZN_LME", "NI_LME"),
    "汇率": tuple(S.SINA_FX_DAILY) + ("EURUSD", "GBPUSD", "USDCAD", "USDCHF", "USDJPY", "USDSEK"),
    "A股": ("000300", "603993"),
    "港股": ("HSI",),
}

# 组内有这个比例的标的有数据，就算「共识交易日」（向下取整：n=3 时需要 2 个，
# 否则 3 个成员的组里任何单标的缺口都会把那天踢出共识，永远报不出来）。
CONSENSUS_SHARE = 0.75

# 已登记的「交易所暂停交易 / 全合约无成交」窗口：这几天没有数据不是采集问题。
# 与休市日不同，同一市场里别的品种照常交易，共识日历会把它们判成缺口，
# 所以必须显式登记，否则检查会一直报假警。
KNOWN_HOLDS: dict[str, tuple[tuple[date, date], ...]] = {
    # 沪镍 2022-03-10 全合约涨停无成交（同日 LME 镍已停牌，见下）
    "NI": ((date(2022, 3, 10), date(2022, 3, 10)),),
    # LME 镍 2022-03-08 逼空事件后暂停交易，03-16 复牌
    "NI_LME": ((date(2022, 3, 8), date(2022, 3, 16)),),
}

# 已登记的上游历史缺口：这些交易日上游接口本身就没有数据，且没有可回溯的官方
# 文件能补（大商所逐日行情页有瑞数反爬，必须浏览器执行 JS；上期所 kx 归档只保留
# 最近一批，2022 年之前的返回 404；新浪自己重拉仍然是这几天缺失）。逐条核实过
# 都是真实交易日，属于「数据源历史残缺」而不是采集故障，所以登记为已知缺口，
# 不让检查每轮都报同一批假警，同时在 detail 里如实说明还剩几个点。
KNOWN_GAPS: dict[str, frozenset[date]] = {
    # 铁矿石：2015 年春节后第一个交易日，新浪连续合约缺这一根。
    "I": frozenset({date(2015, 2, 25)}),
    # 棕榈油：新浪连续合约缺了 4 个「长假后第一个交易日」。
    "P": frozenset(
        {
            date(2015, 6, 23),
            date(2015, 10, 8),
            date(2016, 4, 5),
            date(2017, 10, 9),
        }
    ),
}

# 宏观序列里「按发布机构工作日」而非「按市场交易日」发布的序列：
# 纽约联储的 SOFR/EFFR 只在美国银行工作日发布（Good Friday 不发），
# 而美国国债收益率曲线在 Good Friday 仍会公布，两者不能互为共识参照。
MACRO_CONSENSUS_SKIP = frozenset({"SOFR", "SOFR_EFFR"})

# 日线：连续多少个自然日完全没有数据算「长时间断更」。
# 春节/国庆最长休市约 9 天，取 12 天留出余量。
MAX_SILENCE_DAYS = 12

# 相邻两根收盘价的偏离阈值（%）与只检查最近多少天。
# 只查最近一段：2020 年油价暴跌、2022 年镍逼空是真行情，不该永远报警。
OUTLIER_PCT = 25.0
OUTLIER_LOOKBACK_DAYS = 60


@dataclass(slots=True)
class Finding:
    """一条数据问题记录（不落库，由调用方决定怎么落）。"""

    dataset: str
    subject: str
    issue: str
    detail: str
    count: int = 1
    missing: list[date] = field(default_factory=list)

    def as_text(self) -> str:
        return f"{self.subject}:{self.detail}"


def _known_gap(symbol: str, day: date) -> bool:
    """该标的这一天是否已登记为「上游历史缺口」。"""
    return day in KNOWN_GAPS.get(symbol, frozenset())


def known_gap_points(dates_by_symbol: dict[str, set[date]]) -> int:
    """已登记缺口里、当前仍然确实缺着的点数（补上了就不再计数）。"""
    return sum(
        1
        for symbol, days in KNOWN_GAPS.items()
        for day in days
        if dates_by_symbol.get(symbol) is not None and day not in dates_by_symbol[symbol]
    )


def missing_known_gaps(session: Session) -> int:
    """查库：已登记的上游缺口里还有几个点确实缺着。"""
    if not KNOWN_GAPS:
        return 0
    rows = session.execute(
        select(Instrument.symbol, MarketBar.ts_utc)
        .join(MarketBar, MarketBar.instrument_id == Instrument.id)
        .where(
            MarketBar.timeframe == "1d",
            Instrument.symbol.in_(list(KNOWN_GAPS)),
        )
    ).all()
    seen: dict[str, set[date]] = defaultdict(set)
    for symbol, ts in rows:
        seen[symbol].add(ts.date())
    return known_gap_points(seen)


def _on_hold(symbol: str, day: date) -> bool:
    """该标的这一天是否落在已登记的停牌/无成交窗口里。"""
    for start, end in KNOWN_HOLDS.get(symbol, ()):
        if start <= day <= end:
            return True
    return False


def consensus_dates(
    dates_by_symbol: dict[str, set[date]],
    *,
    share: float = CONSENSUS_SHARE,
) -> set[date]:
    """由组内成员的日期集合推出「共识交易日」。"""
    members = [dates for dates in dates_by_symbol.values() if dates]
    if len(members) < 3:
        return set()
    need = max(2, math.floor(len(members) * share))
    counter: dict[date, int] = defaultdict(int)
    for dates in members:
        for day in dates:
            counter[day] += 1
    return {day for day, seen in counter.items() if seen >= need}


def group_gaps(
    dates_by_symbol: dict[str, set[date]],
    *,
    dataset: str,
    share: float = CONSENSUS_SHARE,
) -> list[Finding]:
    """组内「别人有、它没有」的日期。"""
    if len(dates_by_symbol) < 3:
        return []
    consensus = consensus_dates(dates_by_symbol, share=share)
    if not consensus:
        return []
    findings: list[Finding] = []
    for symbol, dates in sorted(dates_by_symbol.items()):
        if not dates:
            continue
        low, high = min(dates), max(dates)
        expected = {day for day in consensus if low <= day <= high}
        missing = sorted(expected - dates)
        missing = [day for day in missing if not _on_hold(symbol, day) and not _known_gap(symbol, day)]
        if not missing:
            continue
        head = ", ".join(day.isoformat() for day in missing[:6])
        if len(missing) > 6:
            head += f" 等{len(missing)}天"
        findings.append(
            Finding(
                dataset=dataset,
                subject=symbol,
                issue="gap",
                detail=f"缺{len(missing)}个交易日({head})",
                count=len(missing),
                missing=missing,
            )
        )
    return findings


def silences(
    dates_by_symbol: dict[str, set[date]],
    *,
    dataset: str,
    max_days: int = MAX_SILENCE_DAYS,
) -> list[Finding]:
    """相邻两个数据点间隔超过 ``max_days`` 自然日（不依赖共识，单标的也能查）。"""
    findings: list[Finding] = []
    for symbol, dates in sorted(dates_by_symbol.items()):
        if len(dates) < 2:
            continue
        ordered = sorted(dates)
        worst: tuple[int, date, date] | None = None
        for prev, nxt in zip(ordered, ordered[1:]):
            span = (nxt - prev).days
            if span > max_days and (worst is None or span > worst[0]):
                worst = (span, prev, nxt)
        if worst is None:
            continue
        span, prev, nxt = worst
        findings.append(
            Finding(
                dataset=dataset,
                subject=symbol,
                issue="silence",
                detail=f"{prev.isoformat()}→{nxt.isoformat()} 间隔{span}天",
                count=1,
            )
        )
    return findings


def anomalies(
    series_by_symbol: dict[str, list[tuple[date, float, float, float, float]]],
    *,
    dataset: str,
    pct: float = OUTLIER_PCT,
    lookback_days: int = OUTLIER_LOOKBACK_DAYS,
    today: date | None = None,
) -> list[Finding]:
    """非法 OHLC 与最近一段时间的异常跳变。

    ``series_by_symbol`` 的每个元素是 ``(date, open, high, low, close)`` 且按日期升序。
    """
    today = today or datetime.now(timezone.utc).date()
    horizon = today - timedelta(days=lookback_days)
    findings: list[Finding] = []
    for symbol, rows in sorted(series_by_symbol.items()):
        invalid = [
            day
            for day, _o, high, low, close in rows
            if not close or close <= 0 or (high and low and high < low)
        ]
        if invalid:
            findings.append(
                Finding(
                    dataset=dataset,
                    subject=symbol,
                    issue="invalid",
                    detail=f"{len(invalid)}根非法值({', '.join(d.isoformat() for d in invalid[:3])})",
                    count=len(invalid),
                    missing=invalid,
                )
            )
        jumps: list[str] = []
        for (prev_day, _po, _ph, _pl, prev_close), (day, _o, _h, _l, close) in zip(rows, rows[1:]):
            if day < horizon or not prev_close or not close:
                continue
            move = (close / prev_close - 1.0) * 100.0
            if abs(move) > pct:
                jumps.append(f"{day.isoformat()} {move:+.1f}%({prev_close:g}→{close:g})")
        if jumps:
            detail = f"{len(jumps)}处跳变(" + ", ".join(jumps[:3]) + ")"
            findings.append(
                Finding(
                    dataset=dataset,
                    subject=symbol,
                    issue="outlier",
                    detail=detail,
                    count=len(jumps),
                )
            )
    return findings


# ---------------------------------------------------------------- DB collectors


def load_daily_bars(session: Session) -> dict[str, list[tuple[date, float, float, float, float]]]:
    """读取全部日线，按标的分组、日期升序。"""
    rows = session.execute(
        select(Instrument.symbol, MarketBar.ts_utc, MarketBar.open, MarketBar.high,
               MarketBar.low, MarketBar.close)
        .join(MarketBar, MarketBar.instrument_id == Instrument.id)
        .where(MarketBar.timeframe == "1d")
        .order_by(Instrument.symbol, MarketBar.ts_utc)
    ).all()
    out: dict[str, list[tuple[date, float, float, float, float]]] = defaultdict(list)
    for symbol, ts, open_, high, low, close in rows:
        out[symbol].append((ts.date(), open_, high, low, close))
    return dict(out)


def daily_findings(session: Session, *, dataset: str = "日线行情") -> list[Finding]:
    """日线：组内共识缺口 + 长间隔 + 非法值/异常跳变。"""
    series = load_daily_bars(session)
    dates_by_symbol = {symbol: {row[0] for row in rows} for symbol, rows in series.items()}
    findings: list[Finding] = []
    for group, members in CALENDAR_GROUPS.items():
        subset = {symbol: dates_by_symbol[symbol] for symbol in members if symbol in dates_by_symbol}
        findings.extend(group_gaps(subset, dataset=dataset))
    findings.extend(silences(dates_by_symbol, dataset=dataset))
    findings.extend(anomalies(series, dataset=dataset))
    return findings


def macro_findings(session: Session, *, dataset: str = "宏观序列") -> list[Finding]:
    """宏观序列：同一国家/地区内同频序列互为参照（美国利率一组、中国收益率一组）。

    宏观数据只在发布日有观测，周末与假日天然没有点，所以不能整体按自然日判缺失；
    用同国同频序列的共识日来判断，才能区分「上游漏了某天」和「本来就不公布」。
    """
    rows = session.execute(
        select(MacroSeries.code, MacroSeries.country, MacroSeries.freq, MacroObs.ts_utc)
        .join(MacroObs, MacroObs.series_id == MacroSeries.id)
        .order_by(MacroSeries.code, MacroObs.ts_utc)
    ).all()
    dates_by_symbol: dict[str, set[date]] = defaultdict(set)
    freq_by_code: dict[str, str] = {}
    country_by_code: dict[str, str] = {}
    for code, country, freq, ts in rows:
        dates_by_symbol[code].add(ts.date())
        freq_by_code[code] = (freq or "d").lower()
        country_by_code[code] = (country or "") or "?"

    findings: list[Finding] = []
    # 按 (国家, 频率) 分组做共识，只对有 3 条以上序列的组启用（否则参照太少）。
    buckets: dict[tuple[str, str], dict[str, set[date]]] = defaultdict(dict)
    for code, dates in dates_by_symbol.items():
        buckets[(country_by_code[code], freq_by_code[code])][code] = dates
    for (_country, _freq), subset in buckets.items():
        # 发布日历不同的序列不参与共识（SOFR/EFFR 见 MACRO_CONSENSUS_SKIP）。
        reference = {code: dates for code, dates in subset.items() if code not in MACRO_CONSENSUS_SKIP}
        if len(reference) < 3:
            reference = subset
        findings.extend(group_gaps(reference, dataset=dataset))

    # 日频序列允许的最长空档：美国/中国长假 + 发布滞后，取 12 天；
    # 周/月/季频按频率放大（周 21 天、月 70 天、季 150 天）。
    limits = {"d": 12, "w": 21, "m": 70, "q": 150}
    for code, dates in dates_by_symbol.items():
        limit = limits.get(freq_by_code[code], 12)
        subset = {code: dates}
        findings.extend(silences(subset, dataset=dataset, max_days=limit))
    return findings


def summarize(
    findings: list[Finding], *, limit: int = 6, known_gaps: int = 0
) -> tuple[bool, int, str]:
    """把 findings 压成 ``(passed, 问题数, detail 文案)``。"""
    if not findings:
        detail = "历史数据连续，无缺口/异常值"
        if known_gaps:
            detail += f"（另有 {known_gaps} 个点属上游历史缺口，无法回溯补全，已登记）"
        return True, 0, detail
    total = sum(item.count for item in findings)
    parts = [f"{item.subject}:{item.issue}" for item in findings[:limit]]
    detail = f"问题{len(findings)}处(涉及{total}个点): " + ", ".join(parts)
    if len(findings) > limit:
        detail += f" 等{len(findings)}处"
    return False, len(findings), detail
