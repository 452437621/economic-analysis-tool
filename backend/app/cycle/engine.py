"""EPIC-C 2.0 cycle engine.

One run = one auditable analysis run: it records every step, every composite,
every phase decision and the forward scenarios, so the UI can answer
"这个结论是怎么算出来的" without any hidden state.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cycle import alerts as alert_rules
from app.cycle import analogs as analog_match
from app.cycle import history as history_mod
from app.cycle import scenarios as scenario_mod
from app.cycle.composite import all_composites
from app.cycle.config import load_config
from app.cycle.indicators import Reading, build_readings
from app.cycle.market import load_panel
from app.cycle.phases import (
    inventory_cycle,
    liquidity_state,
    long_cycle,
    political_calendar,
    short_cycle,
)
from app.platform.quality_gate import assess as assess_quality
from app.cycle.sustainability import sustainability
from app.cycle.world import world_state
from app.models.core import GoldMetric
from app.models.v2 import ScenarioRun
from app.models.base import new_id, utcnow
from app.provenance import RunRecorder, latest_derivations, record_observations

KIND = "cycle"
METHOD = "cycle.engine.v1"


def _reading_map(readings: list[Reading]) -> dict[str, Reading]:
    return {reading.id: reading for reading in readings}


def _previous_phase(session: Session, code: str) -> str | None:
    rows = latest_derivations(session, code=code, limit=1)
    if not rows:
        return None
    value = rows[0].value or {}
    phase = value.get("phase")
    return str(phase) if phase else None


def _previous_short(session: Session) -> tuple[str | None, str | None]:
    """返回上一次已确认的短周期状态与上一次的原始命中态（用于二次确认）。"""
    rows = latest_derivations(session, code="cycle.state.world", limit=1)
    if not rows:
        return None, None
    value = rows[0].value or {}
    short = value.get("short_cycle") or {}
    state = short.get("state")
    raw = short.get("raw_state")
    return (str(state) if state else None, str(raw) if raw else None)


def _rsi(series: pd.Series, window: int = 14) -> float | None:
    clean = series.dropna()
    if len(clean) < window + 1:
        return None
    delta = clean.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    last_gain = gain.dropna()
    last_loss = loss.dropna()
    if last_gain.empty or last_loss.empty:
        return None
    avg_loss = float(last_loss.iloc[-1])
    if avg_loss == 0:
        return 100.0
    rs = float(last_gain.iloc[-1]) / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 1)


def _cb_gold_flow(session: Session) -> dict | None:
    rows = session.execute(
        select(GoldMetric.as_of, GoldMetric.value)
        .where(GoldMetric.code == "CB_GOLD_GLOBAL_TONNES")
        .order_by(GoldMetric.as_of.desc())
        .limit(12)
    ).all()
    if len(rows) < 2:
        return None
    latest_asof, latest_value = rows[0]
    # 选最接近 365 天的观测，避免把 9 个月或 15 个月的差当成「12 个月流量」。
    candidates = [(abs((latest_asof - asof).days - 365), asof, value) for asof, value in rows[1:]]
    gap, base_asof, base_value = min(candidates, key=lambda item: item[0])
    if gap > 60:
        return None
    flow = float(latest_value or 0) - float(base_value or 0)
    return {
        "value": round(flow, 1),
        "unit": "吨（12 个月存量变化）",
        "asof": str(latest_asof)[:10],
        "base_asof": str(base_asof)[:10],
        "source": "本地 gold_metrics.CB_GOLD_GLOBAL_TONNES 存量差（WGC/IFS 口径）",
    }


def _alert_metrics(
    session: Session, readings: dict[str, Reading], panel, political: dict
) -> dict[str, dict]:
    metrics: dict[str, dict] = {}

    def add_reading(
        metric_id: str, reading: Reading | None, name: str | None = None, scale: float = 1.0
    ) -> None:
        if reading is None or reading.value is None:
            return
        metrics[metric_id] = {
            "value": round(float(reading.value) * scale, 4),
            "unit": reading.unit,
            "asof": reading.asof,
            "name": name or reading.name,
            "source": reading.source,
        }

    add_reading("us_30y", readings.get("us_30y"))
    add_reading("us_10y", readings.get("us_10y"))
    add_reading("us_sofr_spread", readings.get("us_sofr_spread"))
    # 预警阈值以百分数书写（8 = 8%），因此把比率放大 100 倍再比较。
    add_reading("gold_mom", readings.get("gold_mom"), scale=100.0)
    add_reading("oil_mom", readings.get("oil_mom"), scale=100.0)
    add_reading("us_reserve_share", readings.get("us_reserve_share"))
    add_reading("us_polarization", readings.get("us_polarization"))
    add_reading("cn_10y", readings.get("cn_credit_proxy"), name="中国 10 年期国债收益率")

    cn10y = panel.series("CN10Y")
    us10y = panel.series("US10Y")
    if not cn10y.empty and not us10y.empty:
        spread = (float(cn10y.iloc[-1]) - float(us10y.iloc[-1])) * 100.0
        metrics["cn_us_spread"] = {
            "value": round(spread, 1),
            "unit": "bp",
            "asof": max(cn10y.index[-1], us10y.index[-1]).strftime("%Y-%m-%d"),
            "name": "中美 10 年期利差",
            "source": "本地宏观序列",
        }

    gold_rsi = _rsi(panel.series("XAUUSD"))
    if gold_rsi is None:
        gold_rsi = _rsi(panel.series("GOLD_PRICE_USD"))
    if gold_rsi is not None:
        metrics["gold_rsi"] = {
            "value": gold_rsi,
            "unit": "index",
            "asof": panel.last,
            "name": "黄金 14 日 RSI",
            "source": "本地行情序列",
        }

    flow = _cb_gold_flow(session)
    if flow:
        metrics["cb_gold"] = {
            "value": flow["value"],
            "unit": flow["unit"],
            "asof": flow["asof"],
            "name": "央行购金 12 个月流量",
            "source": flow["source"],
        }

    nearest = political.get("nearest")
    if nearest:
        metrics["political_days"] = {
            "value": nearest["days"],
            "unit": "天",
            "asof": nearest["date"],
            "name": f"距「{nearest['name']}」",
            "source": "config/cycle.yaml political_calendar",
        }
    return metrics


def _state_value(
    composites: dict,
    long: dict,
    short: dict,
    liquidity: dict,
    inventory: dict,
    political: dict,
    readings: list[Reading],
) -> dict:
    return {
        "readings": [
            {
                "id": reading.id,
                "name": reading.name,
                "score": reading.score,
                "weight": reading.weight,
                "direction": reading.direction,
                "value": reading.value,
                "unit": reading.unit,
                "asof": reading.asof,
                "z": reading.z,
                "score_value": reading.score_value,
                "evidence": reading.evidence,
                "source": reading.source,
                "layer": reading.layer,
                "why": reading.why,
                "caveat": reading.caveat,
                "stale_days": reading.stale_days,
                "degraded": reading.degraded,
                "degrade_reason": reading.degrade_reason,
            }
            for reading in readings
        ],
        "composites": {
            key: {
                "name": item.get("name"),
                "value": item.get("value"),
                "coverage": item.get("coverage"),
                "confidence": item.get("confidence"),
                "evidence": item.get("evidence"),
                "degraded": item.get("degraded"),
                "degrade_reason": item.get("degrade_reason"),
            }
            for key, item in composites.items()
        },
        "long_cycle": {
            "phase": long.get("phase"),
            "phase_id": long.get("phase_id"),
            "score": long.get("score"),
            "band": long.get("band"),
            "position": long.get("position"),
            "meaning": long.get("meaning"),
            "asset": long.get("asset_implication"),
            "confidence": long.get("confidence"),
            "evidence": long.get("evidence"),
            "next_phase": long.get("next_phase"),
            "exit_condition": long.get("exit_condition"),
            "hysteresis_held": long.get("hysteresis_held"),
        },
        "short_cycle": {
            "state": short.get("state"),
            "raw_state": short.get("raw_state"),
            "hysteresis_held": short.get("hysteresis_held"),
            "variables": short.get("variables"),
            "meaning": short.get("meaning"),
            "confidence": short.get("confidence"),
            "growth_12m_change": short.get("growth_12m_change"),
        },
        "liquidity": liquidity,
        "inventory": {
            "state": inventory.get("state"),
            "degraded": inventory.get("degraded"),
            "degrade_reason": inventory.get("degrade_reason"),
            "meaning": inventory.get("meaning"),
            "asset": inventory.get("asset_implication"),
            "price_momentum_60d": inventory.get("price_momentum_60d"),
            "inventory_proxy_20d": inventory.get("inventory_proxy_20d"),
            "confidence": inventory.get("confidence"),
            "evidence": inventory.get("evidence"),
        },
        "political": {
            "window": political.get("window"),
            "nearest": political.get("nearest"),
            "days_to_nearest": political.get("days_to_nearest"),
            "events": political.get("events"),
        },
    }


def run_cycle(session: Session, today: date | None = None) -> dict:
    cfg = load_config()
    with RunRecorder(session, kind=KIND, subject="world", method_id=METHOD) as rec:
        quality = assess_quality(session, now=utcnow())
        if quality["status"] != "ok":
            rec.degrade(
                "quality.gate",
                quality.get("caveat") or f"数据质量门控：{quality['status']}",
                severity="critical" if quality["status"] == "blocked" else "warn",
            )
        with rec.step("load_panel", kind="fetch") as step:
            panel = load_panel(session)
            if panel.daily.empty:
                raise RuntimeError("no macro/market data available for cycle analysis")
            step.outputs = {"columns": len(panel.columns), "first": panel.first, "last": panel.last}

        with rec.step("read_indicators", kind="transform") as step:
            readings = build_readings(panel, cfg, session=session)
            by_id = _reading_map(readings)
            recorded = record_observations(
                session,
                [
                    {
                        "code": f"cycle.{reading.id}",
                        "asof": datetime.fromisoformat(reading.asof).replace(tzinfo=timezone.utc)
                        if reading.asof
                        else utcnow(),
                        "vintage_date": utcnow(),
                        "value": reading.value,
                        "unit": reading.unit,
                        "source": reading.source[:80] if reading.source else None,
                        "evidence_grade": reading.evidence,
                    }
                    for reading in readings
                    if reading.value is not None and reading.asof
                ],
            )
            step.outputs = {
                "readings": len(readings),
                "recorded": recorded,
                "missing": [reading.id for reading in readings if reading.value is None],
            }

        with rec.step("composite_scores", kind="compute") as step:
            composites = all_composites(readings, cfg)
            step.outputs = {key: item.get("value") for key, item in composites.items()}
            for key, item in composites.items():
                if item.get("value") is None:
                    rec.degrade(
                        f"cycle.composite.{key}",
                        item.get("degrade_reason") or f"{item.get('name', key)} 无可用指标",
                        severity="critical",
                    )
                elif item.get("coverage", 0) < 1.0:
                    rec.degrade(
                        f"cycle.coverage.{key}",
                        f"{item['name']}仅覆盖 {item['coverage'] * 100:.0f}% 权重：{item.get('degrade_reason') or ''}",
                    )

        with rec.step("history", kind="compute") as step:
            hist = history_mod.build_history(panel, cfg)
            growth_d12 = history_mod.momentum_12m(hist.scores, "GROWTH")
            step.outputs = {"months": hist.months, "growth_d12": growth_d12}

        with rec.step("phases", kind="compute") as step:
            previous_short_state, previous_short_raw = _previous_short(session)
            long = long_cycle(
                composites["DMI"],
                cfg,
                previous_phase=_previous_phase(session, "cycle.state.world"),
            )
            short = short_cycle(
                composites["GROWTH"],
                composites["INFLATION"],
                composites["LIQUIDITY"],
                growth_d12,
                cfg,
                previous_state=previous_short_state,
                previous_raw=previous_short_raw,
            )
            liquidity = liquidity_state(composites["LIQUIDITY"])
            inventory = inventory_cycle(panel, cfg)
            political = political_calendar(cfg, today)
            step.outputs = {
                "long": long.get("phase"),
                "short": short.get("state"),
                "liquidity": liquidity.get("state"),
                "inventory": inventory.get("state"),
            }

        with rec.step("sustainability", kind="compute") as step:
            sustain = sustainability(cfg, session=session)
            step.outputs = {"mode": sustain.get("mode")}

        with rec.step("world_order", kind="compute") as step:
            world = world_state(cfg)
            step.outputs = {"internal": (world.get("us_internal") or {}).get("stage_name")}

        with rec.step("analogs", kind="compute") as step:
            analogs = analog_match.find_cycle_analogs(hist.zscores, hist.scores)
            step.outputs = {"available": analogs.get("available"), "top": analogs.get("analogs", [])[:1]}

        with rec.step("scenarios", kind="compute") as step:
            scenario = scenario_mod.scenarios(
                composites["DMI"], composites["GROWTH"], composites["INFLATION"], composites["LIQUIDITY"], cfg
            )
            step.outputs = {item["id"]: item["probability"] for item in scenario.get("scenarios", [])}

        with rec.step("alerts", kind="compute") as step:
            metrics = _alert_metrics(session, by_id, panel, political)
            alert_state = alert_rules.evaluate(metrics, cfg)
            step.outputs = {"triggered": alert_state.get("triggered"), "unknown": alert_state.get("unknown")}

        # ---------- derivations (L1–L3) ----------
        input_ids = [reading.id for reading in readings if reading.score_value is not None]
        state_value = _state_value(composites, long, short, liquidity, inventory, political, readings)

        rec.derive(
            code="cycle.state.world",
            claim=(
                f"世界长债务周期：{long.get('phase') or '数据不足'}"
                f"（DMI {long.get('score')}）；短周期：{short.get('state') or '未知'}"
                f"；流动性：{liquidity.get('state') or '未知'}"
            ),
            value=state_value,
            confidence=round(
                min(
                    float(long.get("confidence") or 0.0),
                    float(short.get("confidence") or 0.0),
                ),
                2,
            ),
            evidence_grade="E3",
            inputs=input_ids,
            steps=[
                {"name": "读取指标", "detail": f"{len(readings)} 个指标（市场 E1 / 人工 E2–E4）"},
                {"name": "分量合成", "detail": "按配置权重加权，缺失权重不参与并降级覆盖率"},
                {"name": "阶段判定", "detail": f"长债务 7 阶段带 {cfg['long_cycle']['hysteresis']} 点滞回；短周期规则命中"},
            ],
            rules_hit=[
                {"rule_id": f"long_cycle.{long.get('phase_id')}", "message": f"DMI={long.get('score')} 落入 {long.get('band')}"},
                {"rule_id": f"short_cycle.{short.get('raw_state')}", "message": f"增长/通胀/动量：{short.get('variables')}"},
            ],
            caveats=[
                "结构性指标（BIS/IMF/WID）尚未自动化接入，部分分量以人工观测（E2–E4）参与，置信度已相应下调；",
                "库存周期无本地库存序列，用工业品价格动量代理（E1）；",
                "阶段滞回以「上一次推导的 phase」为状态，不依赖隐藏内存。",
            ],
            falsifiers=[
                "若 DMI 连续 2 个月回落至当前阶段下界 3 点以下，则阶段下移；",
                "若短周期规则与增长动量连续 2 个月矛盾，则短周期判定标记为不稳定。",
            ],
            opposing=[
                "长债务周期 75–100 年在实证上只有 n≈5 个观测，属于叙事分期而非统计检验结论（docs/23 已标注 C 级）；",
                "美国财政与 AI 生产率可能延长「顶部」阶段的持续时间。",
            ],
        )

        rec.derive(
            code="cycle.analogs",
            claim=(
                f"历史类比 {analogs.get('n') or 0} 个（样本内）"
                if analogs.get("available")
                else "历史类比不可用：样本不足"
            ),
            value=analogs,
            confidence=0.5 if analogs.get("available") else 0.2,
            evidence_grade="E1",
            inputs=input_ids,
            steps=[{"name": "相似度检索", "detail": "20 维状态向量余弦相似度 + 欧氏距离，剔除最近 12 个月"}],
            caveats=analogs.get("caveats"),
            falsifiers=["若类比样本的后续 6 个月与当前路径相关性为负，则类比失效。"],
            opposing=["相似≠相同；缺少政治与社会慢变量时，历史类比容易误导。"],
        )

        rec.derive(
            code="cycle.scenarios",
            claim="；".join(
                f"{item['id']} {item['name']} {item['probability'] * 100:.0f}%"
                for item in scenario.get("scenarios", [])
            ),
            value={
                "horizon": scenario.get("horizon"),
                "sum": scenario.get("sum"),
                "scenarios": scenario.get("scenarios"),
            },
            confidence=scenario.get("confidence"),
            evidence_grade="E3",
            inputs=["cycle.state.world"],
            steps=[{"name": "规则化先验", "detail": scenario.get("formula")}],
            caveats=scenario.get("caveats"),
            falsifiers=["样本外 Brier 分数劣于基准（历史频率先验）时，应下调情景权重。"],
            opposing=["情景概率尚未经过校准，不能当作精确概率使用。"],
        )

        rec.derive(
            code="cycle.sustainability.US",
            claim=f"美国债务可持续性模式：{sustain.get('mode')}（利息/收入 {sustain.get('interest_to_revenue')}%）",
            value=sustain,
            confidence=sustain.get("confidence"),
            evidence_grade="E2",
            inputs=["us_r_minus_g", "us_interest_revenue", "us_deficit_gdp", "us_debt_gdp"],
            steps=[{"name": "三模式判别", "detail": "r−g、利息/收入 20%/30%、赤字/GDP 5% 三条阈值"}],
            caveats=sustain.get("caveats"),
            falsifiers=["若 r−g 转负且赤字收缩至 3% 以下，模式判断应改为通缩化债/正常化。"],
        )

        rec.derive(
            code="cycle.world.order",
            claim=(
                f"美国内部秩序：{(world.get('us_internal') or {}).get('stage_name')}；"
                f"国际秩序：{(world.get('global_order') or {}).get('stage_name')}"
                f"（美元储备份额 {world.get('reserve_currency', {}).get('share')}%）"
            ),
            value=world,
            confidence=0.55,
            evidence_grade="E4",
            inputs=["world.judgment"],
            steps=[{"name": "阶段映射", "detail": "人工叙事映射（docs/23）"}],
            caveats=["阶段判定为 E4 叙事判断，不得单独构成交易信号（docs/19 证据规则）。"],
            falsifiers=["美元份额连续两季回升且极化指数下降，则阶段判断需下调。"],
        )

        rec.derive(
            code="cycle.alerts",
            claim=f"规则命中 {alert_state.get('triggered')}/{alert_state.get('total')} 条，未知 {alert_state.get('unknown')} 条",
            value=alert_state,
            confidence=0.6,
            evidence_grade="E3",
            inputs=["cycle.state.world"],
            steps=[{"name": "阈值规则评估", "detail": "逐条规则比较当前读数与阈值"}],
            caveats=["预警是规则命中，不是预测；触发后仍需人工复核与证伪。"],
        )

        months = [stamp.strftime("%Y-%m") for stamp in hist.scores.index][-60:]
        history_value = {
            "months": months,
            "series": {
                key: [None if pd.isna(v) else round(float(v), 1) for v in hist.scores[key].tail(len(months))]
                for key in ("DMI", "GROWTH", "INFLATION", "LIQUIDITY")
                if key in hist.scores.columns
            },
            "coverage": {
                key: [None if pd.isna(v) else float(v) for v in hist.coverage[key].tail(len(months))]
                for key in ("DMI", "GROWTH", "INFLATION", "LIQUIDITY")
                if key in hist.coverage.columns
            },
        }
        rec.derive(
            code="cycle.history",
            claim=f"近 {len(months)} 个月分量历史（仅市场指标，可回算）",
            value=history_value,
            confidence=0.8,
            evidence_grade="E1",
            inputs=input_ids,
            steps=[{"name": "月度重采样", "detail": "日频 z → 100×Φ(z) → 月末取值"}],
            caveats=["历史序列只含市场可回算指标，不含人工结构性读数；样本起点取决于各序列接入时间。"],
        )

        for item in scenario.get("scenarios", []):
            session.add(
                ScenarioRun(
                    id=new_id(),
                    run_id=rec.run.id if rec.run else None,
                    scenario_id=item["id"],
                    name=item["name"],
                    probability=float(item["probability"]),
                    horizon=scenario.get("horizon"),
                    drivers=item.get("triggers"),
                    assets={"summary": item.get("assets")},
                    asof=utcnow(),
                )
            )

        summary = {
            "long": long.get("phase"),
            "short": short.get("state"),
            "liquidity": liquidity.get("state"),
            "scenarios": {item["id"]: item["probability"] for item in scenario.get("scenarios", [])},
            "alerts_triggered": alert_state.get("triggered"),
            "months": hist.months,
        }
        rec.finish(summary=summary)

    session.commit()

    return {
        "asof": panel.last,
        "run_id": rec.run.id if rec.run else None,
        "status": rec.run.status if rec.run else None,
        "degraded_reasons": rec.run.degraded_reasons if rec.run else None,
        "generated_at": utcnow().isoformat(),
        "quality": quality,
        "composites": composites,
        "readings": [reading.dict() for reading in readings],
        "long_cycle": long,
        "short_cycle": short,
        "liquidity": liquidity,
        "inventory": inventory,
        "political": political,
        "sustainability": sustain,
        "world": world,
        "analogs": analogs,
        "scenarios": scenario,
        "alerts": alert_state,
        "history": {
            "months": months,
            "series": history_value["series"],
            "growth_12m_change": round(growth_d12, 1) if growth_d12 is not None else None,
        },
        "panel": {"first": panel.first, "last": panel.last, "columns": len(panel.columns)},
        "config_version": cfg.get("_meta", {}).get("version"),
    }
