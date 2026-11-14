"""Gold composite score: turn monitored indicators into a -100..100 view."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gold.registry import CATEGORY_LABELS, INDICATORS, Indicator
from app.models.core import GoldMetric, Instrument, MarketBar

HISTORY_LIMIT = 400
WEIGHT_TOTAL = sum(item.weight for item in INDICATORS.values() if item.weight > 0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def history(session: Session, code: str, limit: int = HISTORY_LIMIT) -> list[tuple[datetime, float]]:
    rows = session.scalars(
        select(GoldMetric)
        .where(GoldMetric.code == code)
        .order_by(GoldMetric.as_of.desc())
        .limit(limit)
    ).all()
    return [(_aware(row.as_of), float(row.value)) for row in reversed(rows)]


def _baseline(obs: list[tuple[datetime, float]], days: int) -> float | None:
    """Observation closest to (but not after) ``last - days``."""
    if len(obs) < 2:
        return None
    target = obs[-1][0] - timedelta(days=days)
    candidates = [value for as_of, value in obs if as_of <= target]
    if candidates:
        return candidates[-1]
    return obs[0][1]


def _pct_change(obs: list[tuple[datetime, float]], days: int) -> float | None:
    base = _baseline(obs, days)
    if base is None or base == 0:
        return None
    return (obs[-1][1] / base - 1) * 100


def _percentile(obs: list[tuple[datetime, float]]) -> float | None:
    if len(obs) < 8:
        return None
    values = [value for _, value in obs[-104:]]
    current = values[-1]
    below = sum(1 for value in values if value <= current)
    return below / len(values) * 100


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _normalize(item: Indicator, obs: list[tuple[datetime, float]]) -> tuple[float, float | None, str]:
    """Return (raw_score -1..1, change for display, note). Higher raw value = positive."""
    value = obs[-1][1]
    if item.transform == "pct_change_1m":
        change = _pct_change(obs, 30)
        if change is None:
            return 0.0, None, "历史样本不足"
        return _clip(change / item.scale), change, f"近 30 天 {change:+.2f}%"
    if item.transform == "pct_change_3m":
        change = _pct_change(obs, 90)
        if change is None:
            return 0.0, None, "历史样本不足"
        return _clip(change / item.scale), change, f"近 90 天 {change:+.2f}%"
    if item.transform == "percentile":
        percentile = _percentile(obs)
        if percentile is None:
            return 0.0, None, "样本不足（至少 8 期）"
        return _clip((percentile - 50) / 50), percentile, f"历史分位 {percentile:.0f}%"
    if item.transform == "level_and_change":
        change = _pct_change(obs, 30)
        if change is None:
            return 0.0, None, "历史样本不足"
        raw = (value - 2.0) / item.scale * 0.6 + (change / 0.5) * 0.4
        return _clip(raw), change, f"水平 {value:.2f}，近 30 天 {change:+.1f}%"
    # level: 相对中性基准 0 归一化
    return _clip(value / item.scale), value, f"水平 {value:.2f}"


def _factor_signal(score: float) -> str:
    if score >= 0.15:
        return "bullish"
    if score <= -0.15:
        return "bearish"
    return "neutral"


def _label(score: float) -> str:
    if score >= 50:
        return "强多"
    if score >= 18:
        return "偏多"
    if score <= -50:
        return "强空"
    if score <= -18:
        return "偏空"
    return "中性"


def compute_gold_score(session: Session) -> dict:
    weighted = 0.0
    total_weight = 0.0
    available_weight = 0.0
    factors: list[dict] = []
    for code, item in INDICATORS.items():
        if item.weight <= 0:
            continue
        obs = history(session, code)
        raw_value = obs[-1][1] if obs else None
        raw_score, change, note = _normalize(item, obs) if obs else (0.0, None, "尚未采集")
        if obs and code == "CN_GOLD_RESERVES_USD":
            # 中国黄金储备以美元计价：剔除金价重估后近似“净购金”
            gold_return = _gold_price_return(session, 30)
            if change is not None and gold_return is not None:
                adjusted = change - gold_return
                raw_score = _clip(adjusted / item.scale)
                note = f"储备变动 {change:+.2f}% − 金价 {gold_return:+.2f}% ≈ 购金代理 {adjusted:+.2f}%"
                change = adjusted
        factor_score = raw_score * item.direction
        available = bool(obs)
        if available:
            total_weight += item.weight
            available_weight += item.weight
            weighted += item.weight * factor_score
        factors.append(
            {
                "code": code,
                "name": item.name,
                "category": item.category,
                "category_label": CATEGORY_LABELS.get(item.category, item.category),
                "unit": item.unit,
                "freq": item.freq,
                "source": item.source,
                "weight": item.weight,
                "direction": item.direction,
                "value": round(raw_value, 4) if raw_value is not None else None,
                "change": round(change, 4) if change is not None else None,
                "score": round(factor_score * 100, 1),
                "contribution": round(item.weight * factor_score, 2),
                "signal": _factor_signal(factor_score) if available else "unavailable",
                "available": available,
                "manual": item.manual,
                "note": item.note,
                "explain": note,
                "as_of": obs[-1][0].isoformat() if obs else None,
            }
        )
    # GOLD_MOM_20D_PCT 由日线直接计算（覆盖“首次运行样本不足”）
    momentum = _momentum_from_bars(session)
    for factor in factors:
        if factor["code"] != "GOLD_MOM_20D_PCT" or momentum is None:
            continue
        norm = max(-1.0, min(1.0, momentum / 8))
        if factor["available"]:
            weighted -= factor["weight"] * (factor["score"] / 100)
        else:
            total_weight += factor["weight"]
            available_weight += factor["weight"]
        weighted += factor["weight"] * norm
        factor.update(
            {
                "available": True,
                "value": round(momentum, 3),
                "change": round(momentum, 3),
                "score": round(norm * 100, 1),
                "signal": _factor_signal(norm),
                "explain": f"AU 近 20 个交易日 {momentum:+.2f}%",
            }
        )
    score = round(weighted / total_weight * 100, 1) if total_weight else 0.0
    coverage = round(available_weight / WEIGHT_TOTAL * 100, 0) if WEIGHT_TOTAL else 0.0
    return {
        "score": score,
        "label": _label(score),
        "coverage": coverage,
        "available_weight": round(available_weight, 1),
        "total_weight": round(WEIGHT_TOTAL, 1),
        "factors": factors,
        "categories": [
            {"key": key, "label": label, "count": sum(1 for f in factors if f["category"] == key)}
            for key, label in CATEGORY_LABELS.items()
        ],
        "generated_at": _utcnow().isoformat(),
        "methodology": (
            "综合评分 = Σ(指标权重 × 标准化得分 × 方向) / 已获取权重；"
            "权重按可得数据重新归一。方向：实际利率/美元/库存/投机持仓逆向，"
            "央行购金/ETF/上海溢价/租赁紧张正向。CFTC 分类持仓与银行参与报告是"
            "公开可得的最佳代理，不等同于摩根大通/汇丰等个体做市商账簿。"
        ),
    }


def _momentum_from_bars(session: Session) -> float | None:
    try:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == "AU"))
        if instrument is None:
            return None
        closes = session.scalars(
            select(MarketBar.close)
            .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == "1d")
            .order_by(MarketBar.ts_utc.desc())
            .limit(21)
        ).all()
        values = [float(value) for value in reversed(closes) if value is not None]
        if len(values) < 21 or values[0] <= 0:
            return None
        return (values[-1] / values[0] - 1) * 100
    except Exception:  # pragma: no cover - defensive
        return None


def _gold_price_return(session: Session, days: int) -> float | None:
    """伦敦金现（XAUUSD，缺失时用沪金 AU）近 N 天涨跌幅，用于央行储备的价格重估剔除。"""
    try:
        for symbol in ("XAUUSD", "AU"):
            instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
            if instrument is None:
                continue
            rows = session.execute(
                select(MarketBar.ts_utc, MarketBar.close)
                .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == "1d")
                .order_by(MarketBar.ts_utc.desc())
                .limit(days + 15)
            ).all()
            points = [(as_of, float(close)) for as_of, close in reversed(rows) if close is not None]
            if len(points) < 2:
                continue
            last_date = points[-1][0]
            if last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)
            target = last_date - timedelta(days=days)
            baseline = next((value for as_of, value in points if _aware(as_of) <= target), points[0][1])
            if baseline:
                return (points[-1][1] / baseline - 1) * 100
    except Exception:  # pragma: no cover - defensive
        return None
    return None
