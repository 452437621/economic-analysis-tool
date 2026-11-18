"""Resolve structural cycle readings from live macro series with manual fallback.

The structural layer used to be entirely hand-maintained in ``cycle.yaml``
(``manual:`` section): debt/GDP, deficit, interest burden and r−g were expert
observations updated a few times a year. Since the macro collector now persists
official first-hand series (IMF WEO, US Treasury Fiscal Data, World Bank) the
engine prefers those live values and only falls back to the YAML observation
when the series is missing or stale.

Evidence grades follow the project convention:

* ``E2`` – live official API series (first-hand, machine readable);
* YAML fallback keeps its own configured grade (``E1``/``E2``/``E3``), which
  documents the provenance of the hand-maintained observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select

from app.cycle.config import load_config
from app.models.core import MacroObs, MacroSeries

#: Freshness limits agreed with the data-quality job (``check_data_quality``).
ANNUAL_MAX_AGE_DAYS = 400
MONTHLY_MAX_AGE_DAYS = 120
QUARTERLY_MAX_AGE_DAYS = 150
DAILY_MAX_AGE_DAYS = 120
_MAX_AGE_BY_FREQ = {
    "d": DAILY_MAX_AGE_DAYS,
    "w": 30,
    "m": MONTHLY_MAX_AGE_DAYS,
    "q": QUARTERLY_MAX_AGE_DAYS,
    "y": ANNUAL_MAX_AGE_DAYS,
}
_EVIDENCE_LIVE = "E2"

_IMF_URL = "https://www.imf.org/external/datamapper/{indicator}@WEO/USA"
_TREASURY_DEBT_URL = "https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/"
_TREASURY_MTS_URL = "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/"
_WORLDBANK_GDP_URL = "https://data.worldbank.org/indicator/NY.GDP.MKTP.CD?locations=US"
_REAL_YIELD_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "TextView?type=daily_treasury_real_yield_curve"
)

#: Why a live path could not produce a value; surfaced through ``reason``.
_FALLBACK_REASONS = {
    "us_debt_gdp": "US_DEBT_GDP 与「财政部债务 ÷ 世界银行 GDP」组合序列均缺失或过期",
    "us_deficit_gdp": "US_NET_LENDING_GDP 与财政部月度收支序列均缺失或过期",
    "us_interest_revenue": "美国财政部月度利息/收入序列不足 12 个月或已过期",
    "us_r_minus_g": "US10Y_REAL 或 US_GDP_GROWTH 序列缺失/过期",
    "cn_debt_gdp": "CN_DEBT_GDP 序列缺失或过期",
    "cn_interest_revenue": "IMF 未提供「中国政府利息支出」的公开可比序列",
    "us_reserve_share": "IMF COFER 未接入（未确定稳定的美元储备份额 SDMX 取数键）",
}


@dataclass(slots=True)
class _Obs:
    value: float
    asof: date
    freq: str


@dataclass(slots=True)
class _LiveHit:
    value: float
    unit: str
    asof: date
    source: str
    url: str


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _fresh(asof: date | None, freq: str | None) -> bool:
    if asof is None:
        return False
    limit = _MAX_AGE_BY_FREQ.get((freq or "d").lower(), ANNUAL_MAX_AGE_DAYS)
    return (date.today() - asof).days <= limit


def _manual_item(config: dict, structural_id: str) -> dict | None:
    return next(
        (item for item in config.get("manual") or [] if item.get("id") == structural_id),
        None,
    )


def _latest(session, code: str) -> _Obs | None:
    if session is None:
        return None
    row = session.execute(
        select(MacroObs.value, MacroObs.ts_utc, MacroSeries.freq)
        .join(MacroSeries, MacroObs.series_id == MacroSeries.id)
        .where(MacroSeries.code == code)
        .order_by(MacroObs.ts_utc.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    asof = _as_date(row[1])
    if asof is None:
        return None
    return _Obs(value=float(row[0]), asof=asof, freq=str(row[2] or "d"))


def _latest_fresh(session, code: str) -> _Obs | None:
    obs = _latest(session, code)
    if obs is None or not _fresh(obs.asof, obs.freq):
        return None
    return obs


def _series(session, code: str, limit: int) -> list[_Obs]:
    if session is None:
        return []
    rows = session.execute(
        select(MacroObs.value, MacroObs.ts_utc, MacroSeries.freq)
        .join(MacroSeries, MacroObs.series_id == MacroSeries.id)
        .where(MacroSeries.code == code)
        .order_by(MacroObs.ts_utc.desc())
        .limit(limit)
    ).all()
    out: list[_Obs] = []
    for value, ts, freq in rows:
        asof = _as_date(ts)
        if asof is not None:
            out.append(_Obs(value=float(value), asof=asof, freq=str(freq or "d")))
    return out


def _month_sum(session, code: str, months: int = 12) -> tuple[float, date] | None:
    rows = _series(session, code, limit=months)
    if len(rows) < months or not _fresh(rows[0].asof, rows[0].freq or "m"):
        return None
    return sum(obs.value for obs in rows), rows[0].asof


def _annual_mean(session, code: str, years: int = 5) -> tuple[float, date] | None:
    rows = _series(session, code, limit=years)
    if len(rows) < years or not _fresh(rows[0].asof, rows[0].freq or "y"):
        return None
    return sum(obs.value for obs in rows) / years, rows[0].asof


def _resolve_us_debt_gdp(session) -> _LiveHit | None:
    obs = _latest_fresh(session, "US_DEBT_GDP")
    if obs is not None:
        return _LiveHit(
            value=obs.value,
            unit="%",
            asof=obs.asof,
            source="IMF WEO（GGXWDG_NGDP，一般政府债务/GDP）",
            url=_IMF_URL.format(indicator="GGXWDG_NGDP"),
        )
    debt = _latest_fresh(session, "US_FED_DEBT")
    gdp = _latest_fresh(session, "WB_US_GDP")
    if debt is None or gdp is None or gdp.value <= 0:
        return None
    ratio = debt.value / gdp.value * 100.0
    if not 0 < ratio < 500:
        return None
    return _LiveHit(
        value=ratio,
        unit="%",
        asof=min(debt.asof, gdp.asof),
        source="美国财政部 Debt to the Penny ÷ 世界银行名义 GDP（近似口径）",
        url=_TREASURY_DEBT_URL,
    )


def _resolve_us_deficit_gdp(session) -> _LiveHit | None:
    obs = _latest_fresh(session, "US_NET_LENDING_GDP")
    if obs is not None:
        return _LiveHit(
            value=-obs.value,
            unit="%",
            asof=obs.asof,
            source="IMF WEO（GGXCNL_NGDP，净贷出/借入取负 = 赤字率）",
            url=_IMF_URL.format(indicator="GGXCNL_NGDP"),
        )
    outlays = _month_sum(session, "US_MTS_OUTLAYS")
    receipts = _month_sum(session, "US_MTS_RECEIPTS")
    gdp = _latest_fresh(session, "WB_US_GDP")
    if outlays is None or receipts is None or gdp is None or gdp.value <= 0:
        return None
    deficit = (outlays[0] - receipts[0]) / gdp.value * 100.0
    return _LiveHit(
        value=deficit,
        unit="%",
        asof=min(outlays[1], receipts[1], gdp.asof),
        source="美国财政部 MTS（近 12 个月支出−收入）÷ 世界银行名义 GDP（近似口径）",
        url=_TREASURY_MTS_URL,
    )


def _resolve_us_interest_revenue(session) -> _LiveHit | None:
    interest = _month_sum(session, "US_MTS_INTEREST")
    receipts = _month_sum(session, "US_MTS_RECEIPTS")
    if interest is not None and receipts is not None and receipts[0] > 0:
        ratio = interest[0] / receipts[0] * 100.0
        return _LiveHit(
            value=ratio,
            unit="%",
            asof=min(interest[1], receipts[1]),
            source="美国财政部 MTS table 9（近 12 个月净利息 ÷ 近 12 个月财政收入）",
            url=_TREASURY_MTS_URL,
        )
    interest_gdp = _latest_fresh(session, "US_INTEREST_GDP")
    revenue_gdp = _latest_fresh(session, "US_GOV_REVENUE_GDP")
    if interest_gdp is None or revenue_gdp is None or revenue_gdp.value <= 0:
        return None
    return _LiveHit(
        value=interest_gdp.value / revenue_gdp.value * 100.0,
        unit="%",
        asof=min(interest_gdp.asof, revenue_gdp.asof),
        source="IMF WEO（利息支出/GDP ÷ 政府收入/GDP）",
        url=_IMF_URL.format(indicator="GGR_NGDP"),
    )


def _resolve_us_r_minus_g(session) -> _LiveHit | None:
    real_yield = _latest_fresh(session, "US10Y_REAL")
    growth = _annual_mean(session, "US_GDP_GROWTH", years=5)
    if real_yield is None or growth is None:
        return None
    return _LiveHit(
        value=real_yield.value - growth[0],
        unit="pp",
        asof=min(real_yield.asof, growth[1]),
        source="10Y 实际利率（财政部 TIPS）− 近 5 年实际 GDP 增速均值（IMF WEO）",
        url=_REAL_YIELD_URL,
    )


def _resolve_cn_debt_gdp(session) -> _LiveHit | None:
    obs = _latest_fresh(session, "CN_DEBT_GDP")
    if obs is None:
        return None
    return _LiveHit(
        value=obs.value,
        unit="%",
        asof=obs.asof,
        source="IMF WEO（GGXWDG_NGDP，一般政府债务/GDP）",
        url=_IMF_URL.format(indicator="GGXWDG_NGDP"),
    )


def _resolve_cn_interest_revenue(session) -> _LiveHit | None:
    interest_gdp = _latest_fresh(session, "CN_INTEREST_GDP")
    revenue_gdp = _latest_fresh(session, "CN_GOV_REVENUE_GDP")
    if interest_gdp is None or revenue_gdp is None or revenue_gdp.value <= 0:
        return None
    return _LiveHit(
        value=interest_gdp.value / revenue_gdp.value * 100.0,
        unit="%",
        asof=min(interest_gdp.asof, revenue_gdp.asof),
        source="IMF WEO（中国政府利息支出/GDP ÷ 政府收入/GDP）",
        url=_IMF_URL.format(indicator="GGR_NGDP"),
    )


def _resolve_us_reserve_share(session) -> _LiveHit | None:
    """IMF COFER 尚未接入（SDMX key 未稳定），只消费未来可能落库的序列。"""
    obs = _latest_fresh(session, "US_RESERVE_SHARE")
    if obs is None:
        return None
    return _LiveHit(
        value=obs.value,
        unit="%",
        asof=obs.asof,
        source="IMF COFER（美元在全球外汇储备中的占比）",
        url="https://data.imf.org/regular.aspx?key=41175",
    )


_RESOLVERS = {
    "us_debt_gdp": _resolve_us_debt_gdp,
    "us_deficit_gdp": _resolve_us_deficit_gdp,
    "us_interest_revenue": _resolve_us_interest_revenue,
    "us_r_minus_g": _resolve_us_r_minus_g,
    "cn_debt_gdp": _resolve_cn_debt_gdp,
    "cn_interest_revenue": _resolve_cn_interest_revenue,
    "us_reserve_share": _resolve_us_reserve_share,
}


def score_from_bands(value: float, bands: list) -> float:
    """Map a value onto the score bands declared in ``cycle.yaml``.

    ``bands`` is a list of ``[threshold, score]`` pairs, ordered however the YAML
    author likes; the value is linearly interpolated between the two adjacent
    thresholds, and clamped to the first/last score outside the range. This keeps
    the manual ``scale`` text and the machine-readable bands consistent.
    """
    points = sorted((float(pair[0]), float(pair[1])) for pair in bands or [])
    if not points:
        raise ValueError("bands must not be empty")
    if value <= points[0][0]:
        return round(points[0][1], 1)
    if value >= points[-1][0]:
        return round(points[-1][1], 1)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            if x1 == x0:
                return round(y0, 1)
            ratio = (value - x0) / (x1 - x0)
            return round(y0 + ratio * (y1 - y0), 1)
    return round(points[-1][1], 1)


def _live_payload(structural_id: str, hit: _LiveHit) -> dict:
    return {
        "id": structural_id,
        "value": round(hit.value, 4),
        "unit": hit.unit,
        "asof": hit.asof.isoformat(),
        "source": hit.source,
        "url": hit.url,
        "evidence": _EVIDENCE_LIVE,
        "live": True,
        "degraded": False,
        "reason": None,
    }


def _fallback_payload(item: dict, reason: str, *, degraded: bool) -> dict:
    value = item.get("value")
    return {
        "id": str(item.get("id")),
        "value": float(value) if value is not None else None,
        "unit": item.get("unit"),
        "asof": str(item.get("asof")) if item.get("asof") is not None else None,
        "source": str(item.get("source") or ""),
        "url": item.get("url"),
        "evidence": str(item.get("evidence", "E4")),
        "live": False,
        "degraded": degraded,
        "reason": f"{reason}，回落人工观测" if degraded else reason,
    }


def resolve(structural_id: str, session, config: dict | None = None) -> dict:
    """Return the best available value for one structural reading.

    Priority: live database series (fresh) → ``cycle.yaml`` manual observation.
    The returned dict always carries ``live``/``degraded``/``reason`` so callers
    (and the audit trail) can tell a live reading from a fallback.
    """
    cfg = config or load_config()
    item = _manual_item(cfg, structural_id)
    if item is None:
        return {
            "id": structural_id,
            "value": None,
            "unit": None,
            "asof": None,
            "source": "",
            "url": None,
            "evidence": _EVIDENCE_LIVE,
            "live": False,
            "degraded": True,
            "reason": f"cycle.yaml manual 段缺少 {structural_id}",
        }
    if not item.get("live_series"):
        return _fallback_payload(item, "该指标未配置可实时化序列（纯人工口径）", degraded=False)
    resolver = _RESOLVERS.get(structural_id)
    if resolver is None:
        return _fallback_payload(
            item,
            _FALLBACK_REASONS.get(structural_id, "未实现实时取数映射"),
            degraded=True,
        )
    hit: _LiveHit | None = None
    failure: str | None = None
    if session is None:
        failure = "未提供数据库会话，无法读取实时序列"
    else:
        try:
            hit = resolver(session)
        except Exception as exc:  # noqa: BLE001 - a broken series must not break the cycle run
            failure = f"实时序列读取失败：{exc}"
    if hit is not None:
        return _live_payload(structural_id, hit)
    reason = failure or _FALLBACK_REASONS.get(structural_id, "实时序列缺失或已过期")
    return _fallback_payload(item, reason, degraded=True)
