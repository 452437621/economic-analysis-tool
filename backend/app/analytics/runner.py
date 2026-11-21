"""Analytics runner: compute all M3 results and persist snapshots.

V2.0 起，每次运行都写入 ``analysis_runs`` / ``analysis_steps`` / ``derivations``，
使每个结果都能回答「谁算的、用了哪些输入、哪些规则命中、置信度多少」。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.analytics.analogs import build_state, find_analogs
from app.analytics.attribution import build_drivers, decompose
from app.analytics.calendar_study import build_calendar_study
from app.analytics.correlation import correlation_snapshot
from app.analytics.data import aligned, load_frames
from app.analytics.events import build_event_study
from app.analytics.indicators import compute_indicators
from app.analytics.leadlag import leadlag_pairs
from app.analytics.regime import compute_regimes
from app.analytics.wind import compute_wind
from app.models.core import AnalyticsResult
from app.platform.db import SessionLocal
from app.platform.quality_gate import assess as assess_quality
from app.provenance import RunRecorder

logger = logging.getLogger(__name__)

ATTRIBUTION_SYMBOLS = ["AU", "AG", "CU", "SC", "603993", "000300"]

# 周期象限用到的输入（用于谱系追踪；缺失的会自动过滤）
REGIME_INPUTS = {
    "US": ["US10Y", "US2Y", "US10Y_BE", "US10Y_REAL"],
    "CN": ["000300", "CU", "I", "SC", "M", "P"],
}
REGIME_ASSETS = {"US": ["CU", "AU", "SC"], "CN": ["CU", "I", "000300", "SC", "M", "P"]}


def _asof(closes) -> datetime:  # noqa: ANN001
    latest = closes.index[-1].to_pydatetime()
    if latest.tzinfo is None:
        return latest.replace(tzinfo=timezone.utc)
    return latest


def _save(session, kind: str, subject: str, asof: datetime, payload: dict) -> None:  # noqa: ANN001
    # 每类结果只保留最新快照，避免旧的 asof 覆盖新计算结果
    session.execute(
        delete(AnalyticsResult).where(
            AnalyticsResult.kind == kind, AnalyticsResult.subject == subject
        )
    )
    session.add(
        AnalyticsResult(kind=kind, subject=subject, asof=asof, payload=payload, code_version="m3.0")
    )


def _regime_inputs(country: str, closes, macro) -> list[str]:  # noqa: ANN001
    candidates = REGIME_INPUTS.get(country, []) + REGIME_ASSETS.get(country, [])
    available = set(closes.columns) | set(macro.columns)
    return [code for code in candidates if code in available]


def _derive_regime(rec: RunRecorder, country: str, payload: dict, inputs: list[str]):  # noqa: ANN001
    confidence = payload.get("confidence")
    return rec.derive(
        code=f"regime.{country}",
        subject=country,
        claim=f"{country} 市场隐含周期象限：{payload.get('quadrant')}",
        value={
            "quadrant": payload.get("quadrant"),
            "growth_score": payload.get("growth_score"),
            "inflation_score": payload.get("inflation_score"),
            "liquidity_score": payload.get("liquidity_score"),
        },
        confidence=confidence,
        evidence_grade="E3",
        method_id="analytics.regime.v1",
        inputs=inputs,
        steps=[
            {"name": "计算增长/通胀 z 分数", "detail": "250 日滚动 z-score，按权重合成"},
            {"name": "映射到 0–100 分", "detail": "50 + 50·tanh(z/1.5)"},
            {"name": "判定象限", "detail": "增长/通胀阈值 ±0.15 决定 过热/复苏/滞胀/衰退/过渡"},
        ],
        caveats=[
            "增长与通胀均为市场隐含代理，官方 CPI/GDP 尚未接入",
            f"置信度 {confidence}：单一指标集，缺少宏观基本面交叉验证",
        ],
        falsifiers=[
            "官方增长/通胀数据接入后，象限若翻转则本条推导失效",
            "同一象限在 20 个交易日内反复切换，说明信号噪声大于信息",
        ],
        opposing=[
            "收益率曲线斜率可能由期限溢价驱动，而非增长预期",
            "铜金比同时受供给扰动影响",
        ],
    )


def _derive_wind(rec: RunRecorder, wind: dict):  # noqa: ANN001
    components = wind.get("components") or {}
    return rec.derive(
        code="wind.market",
        subject="market",
        claim=f"市场风向：{wind.get('label')}（{wind.get('score')}）",
        value=wind,
        confidence=0.55,
        evidence_grade="E3",
        method_id="analytics.wind.v1",
        inputs=["risk_asset_breadth", "momentum_20d", "US10Y"],
        steps=[
            {"name": "广度", "detail": "风险资产站上 60 日均线比例，权重 40%"},
            {"name": "动量", "detail": "20 日平均涨幅 tanh 压缩，权重 35%"},
            {"name": "利率", "detail": "10Y 20 日变化反向，权重 25%"},
        ],
        caveats=[
            "合成权重为经验设定，未经样本外优化",
            f"风险资产样本 {len(components.get('risk_assets') or [])} 个，广度代表性有限",
        ],
        falsifiers=[
            "风向分与后续 20 日风险资产收益相关性为负，说明方向定反",
            "广度与动量背离超过 30 个交易日，合成结果不可用",
        ],
        opposing=["利率上行也可能反映增长预期改善，而非风险偏好下降"],
    )


def run_analytics() -> dict:
    counts = {
        "indicators": 0,
        "regimes": 0,
        "attribution": 0,
        "correlation": 0,
        "wind": 0,
        "analogs": 0,
        "leadlag": 0,
        "events": 0,
    }
    with SessionLocal() as session:
        rec = RunRecorder(
            session, kind="analytics", subject="market", method_id="analytics.run.v1"
        )
        try:
            rec.start()
            quality = assess_quality(session)
            if quality["status"] == "blocked":
                raise RuntimeError(
                    "data quality gate blocked analytics: "
                    + "; ".join(reason["message"] for reason in quality["reasons"][:3])
                )
            if quality["status"] != "ok":
                rec.degrade(
                    "quality.gate",
                    quality.get("caveat") or f"数据质量门控：{quality['status']}",
                    severity="warn",
                )
            with rec.step("load_bars", kind="fetch") as step:
                frames = load_frames(session)
                step.outputs = {
                    "assets": int(len(frames.closes.columns)),
                    "macro_series": int(len(frames.macro.columns)),
                }

            with rec.step("align_calendar", kind="transform") as step:
                closes, macro = aligned(frames)
                if closes.empty or macro.empty:
                    raise RuntimeError("no daily bars or macro data available for analytics")
                step.outputs = {
                    "days": int(len(closes)),
                    "assets": int(len(closes.columns)),
                    "macro": int(len(macro.columns)),
                }

            asof = _asof(closes)
            rec.asof = asof
            if rec.run is not None:
                rec.run.asof = asof

            with rec.step("indicators", kind="compute") as step:
                for symbol in closes.columns:
                    oi = (
                        frames.open_interest[symbol]
                        if symbol in frames.open_interest.columns
                        else None
                    )
                    payload = compute_indicators(symbol, closes[symbol], oi)
                    if payload:
                        _save(session, "indicator", symbol, asof, payload)
                        counts["indicators"] += 1
                step.outputs = {"count": counts["indicators"]}

            with rec.step("regimes", kind="compute") as step:
                regimes = compute_regimes(closes, macro)
                for country, payload in regimes.items():
                    _save(session, "regime", country, asof, payload)
                    counts["regimes"] += 1
                    _derive_regime(rec, country, payload, _regime_inputs(country, closes, macro))
                step.outputs = {"countries": sorted(regimes)}

            with rec.step("wind", kind="compute") as step:
                wind = compute_wind(closes, macro)
                if wind:
                    _save(session, "wind", "market", asof, wind)
                    counts["wind"] = 1
                    _derive_wind(rec, wind)
                step.outputs = {"score": (wind or {}).get("score")}

            with rec.step("correlation", kind="compute") as step:
                correlation = correlation_snapshot(closes)
                if correlation:
                    _save(session, "correlation", "matrix", asof, correlation)
                    counts["correlation"] = 1
                step.outputs = {"avg_abs_corr": (correlation or {}).get("avg_abs_corr")}

            with rec.step("attribution", kind="compute") as step:
                drivers = build_drivers(macro)
                if "DXY" in closes.columns:
                    drivers["dxy_chg"] = closes["DXY"].pct_change()
                if not drivers.empty:
                    for symbol in ATTRIBUTION_SYMBOLS:
                        if symbol not in closes.columns:
                            continue
                        payload = decompose(closes[symbol].pct_change(), drivers)
                        if payload:
                            _save(session, "attribution", symbol, asof, payload)
                            counts["attribution"] += 1
                step.outputs = {"count": counts["attribution"]}

            with rec.step("analogs", kind="compute") as step:
                state = build_state(closes, macro)
                analogs = find_analogs(state, closes)
                if analogs:
                    _save(session, "analogs", "current", asof, analogs)
                    counts["analogs"] = 1
                step.outputs = {"count": len((analogs or {}).get("analogs") or [])}

            with rec.step("leadlag", kind="compute") as step:
                leadlag = leadlag_pairs(closes)
                if leadlag:
                    _save(session, "leadlag", "pairs", asof, leadlag)
                    counts["leadlag"] = 1
                step.outputs = {"pairs": len((leadlag or {}).get("pairs") or [])}

            with rec.step("events", kind="compute") as step:
                events = build_event_study(closes)
                if events:
                    _save(session, "event_study", "library", asof, events)
                    counts["events"] = 1
                step.outputs = {"count": counts["events"]}

            with rec.step("calendar_study", kind="compute") as step:
                from app.models.core import EconomicEvent

                calendar_rows = session.scalars(
                    select(EconomicEvent)
                    .where(
                        EconomicEvent.ts_utc >= asof - timedelta(days=365),
                        EconomicEvent.ts_utc <= asof,
                        EconomicEvent.importance >= 3,
                    )
                    .order_by(EconomicEvent.ts_utc.asc())
                ).all()
                calendar_payload = build_calendar_study(
                    closes,
                    [
                        {
                            "ts": row.ts_utc,
                            "name": row.name,
                            "country": row.country,
                            "importance": row.importance,
                        }
                        for row in calendar_rows
                    ],
                )
                if calendar_payload.get("groups"):
                    _save(session, "calendar_study", "market", asof, calendar_payload)
                    counts["calendar_study"] = 1
                step.outputs = {"events": len(calendar_rows)}

            counts["asof"] = asof.date().isoformat()
            rec.finish(summary=counts)
            session.commit()
        except Exception as exc:
            rec.fail(exc)
            session.commit()
            logger.exception("run_analytics failed")
            raise

    logger.info("run_analytics: %s", counts)
    return counts
