"""台账引擎：原则库核对 + 预测对账与校准。

一次运行 = 一个 ``RunRecorder``：读周期快照 → 同步原则 → 核对原则 →
对账到期预测 → 派生总结。原则与核对结果落库，预测结果写
``forecast_outcomes``，让「当时怎么说、后来对不对」可回看。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger.principles import CATEGORY_LABELS, PRINCIPLES
from app.models.base import new_id
from app.models.core import AnalyticsResult, Instrument, MacroObs, MacroSeries, MarketBar
from app.models.v2 import (
    AnalysisRun,
    AnalysisStep,
    Derivation,
    Forecast,
    ForecastOutcome,
    Principle,
    PrincipleCheck,
)
from app.provenance import RunRecorder, aware, latest_derivations

METHOD = "ledger.review.v1"
KIND = "ledger"

# 外部结构性读数（不在本地面板内，显式标注来源，避免静默使用）
EXTERNAL_METRICS: dict[str, tuple[float, str]] = {
    "global_debt_gdp": (311.0, "IIF 2026H1：全球债务 365 万亿美元 / 全球 GDP"),
}

FORECAST_CODES = {
    "cycle.dmi": "DMI（债务货币压力）",
    "cycle.ici": "ICI（内部秩序压力）",
    "cycle.eci": "ECI（外部秩序压力）",
    "cycle.growth": "GROWTH 增长分量",
    "cycle.inflation": "INFLATION 通胀分量",
    "cycle.liquidity": "LIQUIDITY 流动性分量",
    "gold.score": "黄金综合评分",
    "xauusd": "XAUUSD 收盘价",
    "us10y": "美国 10 年期国债收益率",
    "us30y": "美国 30 年期国债收益率",
    "cn10y": "中国 10 年期国债收益率",
    "usdcnh": "USDCNH 汇率",
}

DIRECTION_LABELS = {"up": "上行", "down": "下行", "flat": "持平"}


def _asof_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.today()


def _eval(value: float, op: str | None, threshold: float | None, near: float | None) -> tuple[str, str]:
    """返回 (status, note)。status ∈ hit / near / miss / unknown。"""
    if op is None or threshold is None:
        return "unknown", "该原则为定性判断，未设自动阈值，需人工复盘"
    compare = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
    }.get(op)
    if compare is None:
        return "unknown", f"不支持的比较符 {op}"
    if compare(value, threshold):
        return "hit", f"{value:.2f} 满足 {op} {threshold:g}"
    if near is not None and compare(value, near):
        return "near", f"{value:.2f} 接近 {op} {threshold:g}（观察线 {near:g}）"
    return "miss", f"{value:.2f} 未满足 {op} {threshold:g}"


# ── 周期快照 → 指标字典 ──────────────────────────────────────────────


def _cycle_snapshot(session: Session) -> tuple[dict | None, dict | None, str | None]:
    state = latest_derivations(session, "cycle.state.world", limit=1)
    alerts = latest_derivations(session, "cycle.alerts", limit=1)
    state_row = state[0] if state else None
    alerts_row = alerts[0] if alerts else None
    asof = None
    if state_row is not None and state_row.asof is not None:
        asof = aware(state_row.asof).date().isoformat()
    return (
        (state_row.value or None) if state_row else None,
        (alerts_row.value or None) if alerts_row else None,
        asof,
    )


def build_metrics(state_value: dict | None, alerts_value: dict | None) -> dict[str, float]:
    metrics: dict[str, float] = {}
    if state_value:
        for reading in state_value.get("readings") or []:
            value = reading.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                metrics[str(reading.get("id"))] = float(value)
        for key in ("gold_mom", "oil_mom", "us_sofr_spread"):
            if key in metrics and key in {"gold_mom", "oil_mom"}:
                metrics[key] *= 100.0
        for name, composite in (state_value.get("composites") or {}).items():
            value = composite.get("value") if isinstance(composite, dict) else composite
            if isinstance(value, (int, float)):
                metrics[name.lower()] = float(value)
        long_cycle = state_value.get("long_cycle") or {}
        position = long_cycle.get("position")
        if isinstance(position, (int, float)):
            metrics["long_position"] = float(position)
    if alerts_value:
        for item in alerts_value.get("alerts") or []:
            metric = item.get("metric")
            value = item.get("value")
            if metric and isinstance(value, (int, float)):
                metrics[str(metric)] = float(value)
    for key, (value, _source) in EXTERNAL_METRICS.items():
        metrics.setdefault(key, value)
    # 面板指标 id 带国家/主题前缀，原则用短名引用；补别名，避免静默变 unknown
    for alias, source_key in (
        ("polarization", "us_polarization"),
        ("sofr_spread", "us_sofr_spread"),
        ("inequality", "us_inequality"),
        ("tariffs", "us_tariffs"),
    ):
        if source_key in metrics:
            metrics.setdefault(alias, metrics[source_key])
    return metrics


# ── 原则库 ───────────────────────────────────────────────────────────


def sync_principles(session: Session) -> dict[str, int]:
    existing = {row.id: row for row in session.scalars(select(Principle)).all()}
    created = 0
    updated = 0
    for item in PRINCIPLES:
        payload = {
            "category": item["category"],
            "name": item["name"],
            "statement": item["statement"],
            "evidence": item["evidence"],
            "observable": item.get("observable", ""),
            "signal": item.get("signal", ""),
            "falsifier": item.get("falsifier", ""),
            "grade": item["grade"],
            "metric": item.get("metric"),
            "op": item.get("op"),
            "threshold": item.get("threshold"),
            "near": item.get("near"),
        }
        row = existing.get(item["id"])
        if row is None:
            session.add(Principle(id=item["id"], **payload))
            created += 1
        else:
            changed = False
            for key, value in payload.items():
                if getattr(row, key) != value:
                    setattr(row, key, value)
                    changed = True
            if changed:
                updated += 1
    session.flush()
    return {"created": created, "updated": updated, "total": len(PRINCIPLES)}


def check_principles(
    session: Session, metrics: dict[str, float], asof: date, run_id: str
) -> list[dict]:
    rows = session.scalars(select(Principle).order_by(Principle.id)).all()
    out: list[dict] = []
    asof_dt = datetime.combine(asof, datetime.min.time())
    existing = {
        (row.principle_id, _asof_date(row.asof)): row
        for row in session.scalars(
            select(PrincipleCheck).where(PrincipleCheck.asof == asof_dt)
        ).all()
    }
    for row in rows:
        metric = row.metric
        value = metrics.get(metric) if metric else None
        if metric is None:
            status, note = "unknown", "该原则为定性判断，未设自动阈值，需人工复盘"
        elif value is None:
            status, note = "unknown", f"缺少指标 {metric} 的读数"
        else:
            status, note = _eval(float(value), row.op, row.threshold, row.near)
        key = (row.id, asof)
        check = existing.get(key)
        if check is None:
            check = PrincipleCheck(
                id=new_id(),
                principle_id=row.id,
                run_id=run_id,
                asof=asof_dt,
                status=status,
                value=float(value) if isinstance(value, (int, float)) else None,
                note=note,
            )
            session.add(check)
        else:
            check.status = status
            check.value = float(value) if isinstance(value, (int, float)) else None
            check.note = note
            check.run_id = run_id
        out.append(
            {
                "id": row.id,
                "category": row.category,
                "category_label": CATEGORY_LABELS.get(row.category, row.category),
                "name": row.name,
                "statement": row.statement,
                "evidence": row.evidence,
                "observable": row.observable,
                "signal": row.signal,
                "falsifier": row.falsifier,
                "grade": row.grade,
                "metric": row.metric,
                "op": row.op,
                "threshold": row.threshold,
                "near": row.near,
                "status": status,
                "value": float(value) if isinstance(value, (int, float)) else None,
                "note": note,
            }
        )
    session.flush()
    return out


# ── 预测台账 ─────────────────────────────────────────────────────────


# 自动登记的预测范围（其余 FORECAST_CODES 仅手工登记时出现）。
AUTO_FORECAST_CODES = (
    "cycle.dmi",
    "cycle.ici",
    "cycle.eci",
    "cycle.growth",
    "cycle.inflation",
    "cycle.liquidity",
    "gold.score",
    "xauusd",
    "us10y",
)
AUTO_FORECAST_HORIZONS = (30, 90)

# 方向判定：把窗口内首末日度观测的斜率线性折算成「60 天变化幅度」，再与阈值比较。
SLOPE_WINDOW_DAYS = 60
# 历史跨度不足 5 天不判方向（几小时的噪声不足以支撑 30/90 天前瞻，判 flat 更诚实）。
SLOPE_MIN_SPAN_DAYS = 5
# 60 天变化幅度阈值：分数类用「分」，收益率用 bp（百分点），价格类用相对幅度。
SLOPE_THRESHOLDS: dict[str, float] = {
    "cycle.dmi": 2.0,
    "cycle.ici": 2.0,
    "cycle.eci": 2.0,
    "cycle.growth": 2.0,
    "cycle.inflation": 2.0,
    "cycle.liquidity": 2.0,
    "gold.score": 2.0,
    "xauusd": 0.015,
    "us10y": 0.10,
}
RELATIVE_SLOPE_CODES = frozenset({"xauusd"})
# 概率标定：|Δ60| 达到阈值的 3 倍时方向判断给到最高置信度 0.85。
PROBABILITY_FULL_RATIO = 3.0


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _composite_history(session: Session, name: str, cutoff: datetime) -> list[tuple]:
    """周期合成分的本地历史：analysis_steps 的 composite_scores + derivations 快照。"""
    points: list[tuple] = []
    rows = session.execute(
        select(AnalysisStep.started_at, AnalysisStep.outputs)
        .join(AnalysisRun, AnalysisRun.id == AnalysisStep.run_id)
        .where(AnalysisRun.kind == "cycle", AnalysisStep.name == "composite_scores")
        .where(AnalysisStep.started_at >= cutoff)
    ).all()
    for started, outputs in rows:
        value = outputs.get(name) if isinstance(outputs, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool) and started is not None:
            points.append((started, float(value)))
    snapshots = session.execute(
        select(Derivation.asof, Derivation.value)
        .where(Derivation.code == "cycle.state.world", Derivation.asof >= cutoff)
    ).all()
    for asof, payload in snapshots:
        composite = ((payload or {}).get("composites") or {}).get(name)
        value = composite.get("value") if isinstance(composite, dict) else composite
        if isinstance(value, (int, float)) and not isinstance(value, bool) and asof is not None:
            points.append((asof, float(value)))
    return points


def _history_points(session: Session, code: str, cutoff: datetime) -> list[tuple]:
    """取该 code 在窗口内的本地历史点 [(时间, 值)]，与 ``actual_value`` 的口径一致。"""
    if code.startswith("cycle."):
        return _composite_history(session, code.split(".", 1)[1].upper(), cutoff)
    if code == "gold.score":
        rows = session.execute(
            select(AnalyticsResult.asof, AnalyticsResult.payload)
            .where(AnalyticsResult.kind == "gold", AnalyticsResult.asof >= cutoff)
            .order_by(AnalyticsResult.asof)
        ).all()
        return [
            (asof, float(payload["score"]))
            for asof, payload in rows
            if isinstance(payload, dict)
            and isinstance(payload.get("score"), (int, float))
            and not isinstance(payload.get("score"), bool)
        ]
    if code in {"xauusd", "usdcnh"}:
        rows = session.execute(
            select(MarketBar.ts_utc, MarketBar.close)
            .join(Instrument, Instrument.id == MarketBar.instrument_id)
            .where(Instrument.symbol == code.upper())
            .where(MarketBar.timeframe == "1d", MarketBar.ts_utc >= cutoff)
            .order_by(MarketBar.ts_utc)
        ).all()
        return [(ts, float(close)) for ts, close in rows if close is not None]
    if code in {"us10y", "us30y", "cn10y"}:
        rows = session.execute(
            select(MacroObs.ts_utc, MacroObs.value)
            .join(MacroSeries, MacroSeries.id == MacroObs.series_id)
            .where(MacroSeries.code == code.upper(), MacroObs.ts_utc >= cutoff)
            .order_by(MacroObs.ts_utc)
        ).all()
        return [(ts, float(value)) for ts, value in rows if value is not None]
    return []


def _slope_60d(session: Session, code: str, today: date) -> float | None:
    """窗口内首末日度值的斜率，线性折算成 60 天变化幅度；历史不足返回 None。"""
    cutoff = datetime.combine(
        today - timedelta(days=SLOPE_WINDOW_DAYS), datetime.min.time(), tzinfo=timezone.utc
    )
    points = sorted(_history_points(session, code, cutoff), key=lambda item: _as_utc(item[0]))
    daily: dict[date, float] = {}
    for ts, value in points:
        daily[_as_utc(ts).date()] = value  # 同日多条取最后一条（points 已按时间升序）
    ordered = sorted(daily.items())
    if len(ordered) < 2:
        return None
    span = (ordered[-1][0] - ordered[0][0]).days
    if span < SLOPE_MIN_SPAN_DAYS:
        return None
    return (ordered[-1][1] - ordered[0][1]) * SLOPE_WINDOW_DAYS / span


def _classify_direction(
    code: str, change_60d: float | None, baseline: float
) -> tuple[str, float]:
    """确定式方向 + 概率（0.5–0.85，无随机数）。

    - 归一化幅度 = |Δ60|（价格类再除以当前值换成相对幅度）；
    - 幅度 > 阈值 → up/down，概率 ``0.5 + 0.35 * min(1, 幅度/(阈值×3))``；
    - 否则 flat，概率 ``0.5 + 0.35 * (1 - min(1, 幅度/阈值))``（越平越确信）；
    - 历史不足（``change_60d is None``）→ flat，概率 0.5（不给虚假置信度）。
    """
    if change_60d is None:
        return "flat", 0.5
    threshold = SLOPE_THRESHOLDS[code]
    magnitude = abs(change_60d)
    if code in RELATIVE_SLOPE_CODES and baseline:
        magnitude = magnitude / abs(baseline)
    if magnitude > threshold:
        ratio = min(1.0, magnitude / (threshold * PROBABILITY_FULL_RATIO))
        direction = "up" if change_60d > 0 else "down"
        return direction, round(0.5 + 0.35 * ratio, 4)
    ratio = min(1.0, magnitude / threshold)
    return "flat", round(0.5 + 0.35 * (1.0 - ratio), 4)


def _open_forecast_exists(session: Session, code: str, subject: str, target: date) -> bool:
    start = datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    found = session.scalar(
        select(Forecast.id)
        .where(
            Forecast.code == code,
            Forecast.subject == subject,
            Forecast.status == "open",
            Forecast.target_date >= start,
            Forecast.target_date < end,
        )
        .limit(1)
    )
    return found is not None


def auto_register_forecasts(
    session: Session,
    state_value: dict | None,
    *,
    run_id: str | None = None,
    today: date | None = None,
) -> int:
    """从最新周期快照自动登记 30/90 天前瞻预测，返回新增条数（幂等）。

    方向规则（简单、可解释、无随机数）：
    1. 对每个 code 取最近 60 天本地历史：周期合成分来自 ``analysis_steps`` 的
       ``composite_scores`` 输出与 ``cycle.state.world`` 历史快照，黄金评分来自
       ``analytics_results``，价格/收益率来自 ``market_bars`` / ``macro_obs``；
    2. 每个 UTC 日只保留最后一条，用首末两日的差值 ÷ 跨度天数得到日均斜率，
       再乘 60 折算成「60 天变化幅度」；历史跨度 < 5 天视为样本不足，判 ``flat``；
    3. 阈值见 ``SLOPE_THRESHOLDS``（分数 ±2 分、US10Y ±10bp、XAUUSD ±1.5%）：
       幅度超阈值按符号判 ``up``/``down``，否则 ``flat``；
    4. 概率见 ``_classify_direction``（0.5–0.85 的确定式映射）；
    5. ``point`` 按日均斜率线性外推到 30/90 天，``baseline_value`` 填当前值。

    幂等键为 ``code + subject + target_date``：已有同目标日的 open 预测就跳过，
    所以一天内多次运行只新增一轮。

    旧版 ``predictions`` 表不桥接：它只有 thesis/plan/概率/期限，没有 code、方向、
    目标日与基线，语义对不上 v2 ``Forecast``；且 v1 的 ``score_predictions`` 仍在
    结算它，硬塞会让同一判断被计两次。
    """
    if not state_value:
        return 0
    today = today or date.today()
    metrics = build_metrics(state_value, None)
    added = 0
    for code in AUTO_FORECAST_CODES:
        baseline = actual_value(session, code, metrics)
        if baseline is None:
            continue
        change_60d = _slope_60d(session, code, today)
        direction, probability = _classify_direction(code, change_60d, baseline)
        slope_per_day = (change_60d or 0.0) / SLOPE_WINDOW_DAYS
        for horizon in AUTO_FORECAST_HORIZONS:
            target = today + timedelta(days=horizon)
            if _open_forecast_exists(session, code, "all", target):
                continue
            register_forecast(
                session,
                code=code,
                direction=direction,
                horizon_days=horizon,
                probability=probability,
                point=round(baseline + slope_per_day * horizon, 4),
                baseline_value=round(baseline, 4),
                target_date=target,
                run_id=run_id,
                notes=(
                    f"自动登记：60 天斜率折算 {change_60d:+.2f}"
                    if change_60d is not None
                    else "自动登记：历史跨度不足，方向判 flat"
                )
                + f"，{DIRECTION_LABELS[direction]}，概率 {probability:.2f}",
            )
            added += 1
    session.flush()
    return added


def register_forecast(
    session: Session,
    *,
    code: str,
    direction: str,
    horizon_days: int,
    probability: float | None = None,
    point: float | None = None,
    baseline_value: float | None = None,
    subject: str = "all",
    notes: str | None = None,
    run_id: str | None = None,
    target_date: date | None = None,
) -> Forecast:
    if code not in FORECAST_CODES:
        raise ValueError(f"unsupported forecast code: {code}")
    if direction not in DIRECTION_LABELS:
        raise ValueError(f"unsupported direction: {direction}")
    now = datetime.now(timezone.utc)
    target = (
        datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        if target_date is not None
        else now + timedelta(days=max(1, int(horizon_days)))
    )
    row = Forecast(
        id=new_id(),
        run_id=run_id,
        code=code,
        subject=subject,
        direction=direction,
        horizon_days=max(1, min(int(horizon_days), 365)),
        made_at=now,
        target_date=target,
        point=point,
        probability=probability,
        baseline_value=baseline_value,
        status="open",
        notes=notes,
        method_id=METHOD,
    )
    session.add(row)
    session.flush()
    return row


def _latest_market_value(session: Session, code: str) -> float | None:
    row = session.execute(
        select(MarketBar.close)
        .join(Instrument, Instrument.id == MarketBar.instrument_id)
        .where(Instrument.symbol == code.upper())
        .where(MarketBar.timeframe == "1d")
        .order_by(MarketBar.ts_utc.desc())
        .limit(1)
    ).scalar_one_or_none()
    return float(row) if row is not None else None


def _latest_macro_value(session: Session, code: str) -> float | None:
    row = session.execute(
        select(MacroObs.value)
        .join(MacroSeries, MacroSeries.id == MacroObs.series_id)
        .where(MacroSeries.code == code.upper())
        .order_by(MacroObs.ts_utc.desc())
        .limit(1)
    ).scalar_one_or_none()
    return float(row) if row is not None else None


def _latest_gold_score(session: Session) -> float | None:
    row = session.execute(
        select(AnalyticsResult)
        .where(AnalyticsResult.kind == "gold")
        .order_by(AnalyticsResult.asof.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None or not isinstance(row.payload, dict):
        return None
    score = row.payload.get("score")
    return float(score) if isinstance(score, (int, float)) else None


LENS_ACTUALS: dict[str, tuple[str, str]] = {
    "lens.us_equity": ("bar", "SPX"),
    "lens.gold": ("bar", "XAUUSD"),
    "lens.silver": ("bar", "SI"),
    "lens.usd": ("bar", "DXY"),
    "lens.cn_equity": ("bar", "000300"),
    "lens.commodities": ("bar", "BZ"),
    "lens.long_bond": ("macro", "US30Y"),
}


def actual_value(session: Session, code: str, metrics: dict[str, float]) -> float | None:
    if code.startswith("cycle."):
        return metrics.get(code.split(".", 1)[1])
    if code in LENS_ACTUALS:
        kind, target = LENS_ACTUALS[code]
        return _latest_market_value(session, target) if kind == "bar" else _latest_macro_value(session, target)
    if code == "gold.score":
        return _latest_gold_score(session)
    if code in {"xauusd", "usdcnh"}:
        return _latest_market_value(session, code)
    if code in {"us10y", "us30y", "cn10y"}:
        value = _latest_macro_value(session, code)
        return value
    return None


def score_forecasts(
    session: Session,
    metrics: dict[str, float],
    today: date | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    open_rows = session.scalars(
        select(Forecast).where(Forecast.status == "open").order_by(Forecast.target_date)
    ).all()
    resolved = 0
    pending = 0
    rows: list[dict] = []
    for row in open_rows:
        target = aware(row.target_date).date()
        if target > today:
            pending += 1
            continue
        actual = actual_value(session, row.code, metrics)
        if actual is None:
            pending += 1
            continue
        reference = row.baseline_value if row.baseline_value is not None else row.point
        if reference is None:
            pending += 1
            continue
        if row.direction == "up":
            hit = actual > reference
        elif row.direction == "down":
            hit = actual < reference
        else:
            hit = abs(actual - reference) <= max(abs(reference) * 0.02, 0.01)
        probability = row.probability if row.probability is not None else (0.6 if row.direction != "flat" else 0.5)
        brier = (probability - 1.0) ** 2 if hit else probability**2
        row.status = "resolved"
        outcome = session.scalar(
            select(ForecastOutcome).where(ForecastOutcome.forecast_id == row.id)
        )
        if outcome is None:
            outcome = ForecastOutcome(id=new_id())
            outcome.forecast_id = row.id
            session.add(outcome)
        outcome.actual = actual
        outcome.hit = bool(hit)
        outcome.brier = float(brier)
        outcome.resolved_at = datetime.now(timezone.utc)
        outcome.notes = f"基线 {reference}，实际 {actual}，方向 {DIRECTION_LABELS[row.direction]}"
        resolved += 1
        rows.append(
            {
                "id": row.id,
                "code": row.code,
                "direction": row.direction,
                "hit": bool(hit),
                "actual": float(actual),
                "brier": float(brier),
            }
        )
    session.flush()
    return {"resolved": resolved, "pending": pending, "rows": rows}


def calibration_summary(session: Session) -> dict[str, Any]:
    outcomes = session.execute(
        select(ForecastOutcome, Forecast)
        .join(Forecast, Forecast.id == ForecastOutcome.forecast_id)
        .order_by(ForecastOutcome.resolved_at.desc())
    ).all()
    if not outcomes:
        return {
            "n": 0,
            "brier": None,
            "hit_rate": None,
            "by_horizon": [],
            "note": "尚无已结预测；登记需要时间，先积累样本再谈校准",
        }
    brier = sum(float(outcome.brier or 0.0) for outcome, _forecast in outcomes) / len(outcomes)
    hit_rate = sum(1 for outcome, _forecast in outcomes if outcome.hit) / len(outcomes)
    buckets: dict[int, list[float]] = {}
    for outcome, forecast in outcomes:
        bucket = "≤20 天" if forecast.horizon_days <= 20 else "21–60 天" if forecast.horizon_days <= 60 else ">60 天"
        buckets.setdefault(bucket, []).append(float(outcome.brier or 0.0))
    by_horizon = [
        {"bucket": key, "n": len(values), "brier": round(sum(values) / len(values), 4)}
        for key, values in sorted(buckets.items())
    ]
    return {
        "n": len(outcomes),
        "brier": round(brier, 4),
        "hit_rate": round(hit_rate, 4),
        "by_horizon": by_horizon,
        "note": "Brier 越低越好；<0.25 优于随机猜测，<0.15 说明概率有信息量。样本 <20 条时仅作参考。",
    }


# ── 编排 ─────────────────────────────────────────────────────────────


def run_ledger(session: Session, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    with RunRecorder(
        session, kind=KIND, subject="world", method_id=METHOD
    ) as rec:
        with rec.step("load_cycle", kind="fetch", inputs={"source": "cycle.state.world"}) as step:
            state_value, alerts_value, cycle_asof = _cycle_snapshot(session)
            step.outputs = {"found": state_value is not None, "asof": cycle_asof}
            if state_value is None:
                rec.degrade("ledger.cycle_missing", "尚未运行周期引擎，原则核对只能给出 unknown")
        metrics = build_metrics(state_value, alerts_value)
        asof = date.fromisoformat(cycle_asof) if cycle_asof else today
        asof_dt = datetime.combine(asof, datetime.min.time(), tzinfo=timezone.utc)

        with rec.step("sync_principles", kind="transform", inputs={"count": len(PRINCIPLES)}) as step:
            step.outputs = sync_principles(session)

        with rec.step("check_principles", kind="compute", inputs={"metrics": len(metrics)}) as step:
            checks = check_principles(session, metrics, asof, rec.run.id)
            counts: dict[str, int] = {"hit": 0, "near": 0, "miss": 0, "unknown": 0}
            for item in checks:
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            counts["total"] = len(checks)
            step.outputs = counts

        with rec.step(
            "register_forecasts", kind="compute", inputs={"today": today.isoformat()}
        ) as step:
            added = auto_register_forecasts(session, state_value, run_id=rec.run.id, today=today)
            step.outputs = {"added": added, "horizons": list(AUTO_FORECAST_HORIZONS)}

        with rec.step("score_forecasts", kind="compute", inputs={"today": today.isoformat()}) as step:
            scored = score_forecasts(session, metrics, today=today, run_id=rec.run.id)
            step.outputs = {"resolved": scored["resolved"], "pending": scored["pending"]}

        with rec.step("derive", kind="derive", inputs={"checks": len(checks)}) as step:
            calibration = calibration_summary(session)
            open_rows = session.scalars(
                select(Forecast).where(Forecast.status == "open")
            ).all()
            next_due = min((aware(row.target_date).date() for row in open_rows), default=None)
            rec.derive(
                code="ledger.principles",
                claim=(
                    f"原则库 {len(checks)} 条：命中 {counts['hit']}、接近 {counts['near']}、"
                    f"不成立 {counts['miss']}、缺数据 {counts['unknown']}"
                ),
                value={
                    "counts": counts,
                    "items": [
                        {
                            "id": item["id"],
                            "name": item["name"],
                            "category": item["category"],
                            "status": item["status"],
                            "value": item["value"],
                            "note": item["note"],
                        }
                        for item in checks
                    ],
                    "categories": CATEGORY_LABELS,
                },
                confidence=0.55,
                evidence_grade="E2",
                inputs=[{"code": "cycle.state.world", "asof": cycle_asof}],
                steps=[
                    {"name": "同步原则库", "detail": f"{len(PRINCIPLES)} 条"},
                    {"name": "按读数核对", "detail": "阈值比较，缺数据记 unknown"},
                ],
                rules_hit=[
                    {"id": item["id"], "name": item["name"]}
                    for item in checks
                    if item["status"] == "hit"
                ],
                caveats=[
                    "自动核对只覆盖有阈值的原则；定性原则保持 unknown，需人工复盘。",
                    "规模与结构性读数为人工观测 + 来源，存在更新滞后。",
                ],
                falsifiers=[
                    "命中项在未来 2 个季度内逆转且无对应事件冲击。",
                    "unknown 占比长期过半，说明自动核对覆盖不足。",
                ],
                opposing=["原则之间可能互相矛盾（如 A2 与 A4 同时成立时，政策选择取决于政治约束）。"],
                asof=asof_dt,
            )
            rec.derive(
                code="ledger.calibration",
                claim=(
                    f"已结预测 {calibration['n']} 条，Brier {calibration['brier']}，"
                    f"命中率 {calibration['hit_rate']}"
                    if calibration["n"]
                    else "尚无已结预测，校准曲线待样本"
                ),
                value=calibration,
                confidence=0.6 if calibration["n"] >= 20 else 0.4,
                evidence_grade="E2",
                inputs=[{"code": "forecasts", "asof": asof.isoformat()}],
                caveats=[
                    calibration.get("note", ""),
                    "样本内与事后叙事选择偏差会高估长期胜率。",
                ],
                falsifiers=["后续 20 条预测的 Brier 显著高于当前水平。"],
                opposing=[],
                asof=asof_dt,
            )
            rec.derive(
                code="ledger.forecasts",
                claim=(
                    f"未结预测 {len(open_rows)} 条（本轮自动登记新增 {added} 条），"
                    f"最近到期 {next_due.isoformat() if next_due else '—'}"
                ),
                value={
                    "open": len(open_rows),
                    "resolved": calibration["n"],
                    "added": added,
                    "next_due": next_due.isoformat() if next_due else None,
                    "open_items": [
                        {
                            "id": row.id,
                            "code": row.code,
                            "direction": row.direction,
                            "target": aware(row.target_date).date().isoformat(),
                        }
                        for row in open_rows[-10:]
                    ],
                },
                confidence=0.7,
                evidence_grade="E1",
                inputs=[{"code": "forecasts", "asof": asof.isoformat()}],
                asof=asof_dt,
            )
            step.outputs = {
                "principles": len(checks),
                "calibration_n": calibration["n"],
                "forecasts_added": added,
            }

        counter = session.scalars(select(Forecast)).all()
        rec.finish(
            summary={
                "principles": len(checks),
                "hits": counts["hit"],
                "forecasts": len(counter),
                "open": len(open_rows),
                "forecasts_added": added,
            }
        )
        session.commit()
        return {
            "asof": (cycle_asof or today.isoformat()),
            "run_id": rec.run.id,
            "status": rec.run.status,
            "degraded_reasons": rec.run.degraded_reasons or [],
            "principles": checks,
            "counts": counts,
            "calibration": calibration,
            "forecasts": [
                {
                    "id": row.id,
                    "code": row.code,
                    "subject": row.subject,
                    "direction": row.direction,
                    "horizon_days": row.horizon_days,
                    "probability": row.probability,
                    "point": row.point,
                    "baseline_value": row.baseline_value,
                    "status": row.status,
                    "made_at": aware(row.made_at).isoformat() if row.made_at else None,
                    "target_date": aware(row.target_date).date().isoformat(),
                    "notes": row.notes,
                }
                for row in sorted(counter, key=lambda item: aware(item.target_date))
            ],
        }
