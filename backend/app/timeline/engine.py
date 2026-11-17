"""世界长河编排：把 1500–2026 事件与霸权份额入库，并给出当下坐标。

与其它运行一致，整次入库是一个 RunRecorder 运行：
seed_events → seed_powers → read_cycle → derive。
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.v2 import PowerIndex, TimelineEvent
from app.provenance import RunRecorder, aware, latest_derivations
from app.timeline import dataset

METHOD = "timeline.catalog.v1"
KIND = "timeline"

CATEGORY_TO_POWER_INDEX = "gdp_share"


def _event_id(year: int, title: str) -> str:
    return "tl_" + hashlib.sha1(f"{year}|{title}".encode("utf-8")).hexdigest()[:20]


def _power_id(power: str, year: int, indicator: str) -> str:
    return "pi_" + hashlib.sha1(f"{power}|{year}|{indicator}".encode("utf-8")).hexdigest()[:20]


def seed_events(session: Session) -> dict[str, int]:
    """幂等写入长河事件：按 (year, title) 唯一。"""
    created = 0
    updated = 0
    for item in dataset.EVENTS:
        event_id = _event_id(int(item["year"]), str(item["title"]))
        row = session.get(TimelineEvent, event_id)
        if row is None:
            row = TimelineEvent(id=event_id, year=int(item["year"]), title=str(item["title"]))
            session.add(row)
            created += 1
        else:
            updated += 1
        row.month = item.get("month")
        row.category = str(item.get("category") or "economy")
        row.layer = str(item.get("layer") or "L")
        row.evidence_grade = str(item.get("grade") or "B")
        row.related_power = item.get("power")
        row.summary = item.get("summary")
        row.source_url = item.get("source")
    session.flush()
    return {"created": created, "updated": updated, "total": len(dataset.EVENTS)}


def seed_powers(session: Session) -> dict[str, int]:
    """幂等写入实力/储备份额序列。"""
    created = 0
    updated = 0
    rows: list[dict[str, Any]] = []
    for item in dataset.GDP_SHARE:
        rows.append(
            {
                "power": item["power"],
                "year": int(item["year"]),
                "indicator": CATEGORY_TO_POWER_INDEX,
                "value": float(item["value"]),
                "unit": "%",
                "grade": item["grade"],
                "source": item["source"],
            }
        )
    for item in dataset.RESERVE_SHARE:
        rows.append(
            {
                "power": item["currency"].lower(),
                "year": int(item["year"]),
                "indicator": "reserve_share",
                "value": float(item["value"]),
                "unit": "%",
                "grade": item["grade"],
                "source": item["source"],
            }
        )
    for item in rows:
        power_id = _power_id(item["power"], item["year"], item["indicator"])
        row = session.get(PowerIndex, power_id)
        if row is None:
            row = PowerIndex(id=power_id, power=item["power"], year=item["year"], indicator=item["indicator"])
            session.add(row)
            created += 1
        else:
            updated += 1
        row.value = item["value"]
        row.unit = item["unit"]
        row.evidence_grade = item["grade"]
        row.source_url = item["source"]
    session.flush()
    return {"created": created, "updated": updated, "total": len(rows)}


def _cycle_snapshot(session: Session) -> dict[str, Any] | None:
    rows = latest_derivations(session, "cycle.state.world", limit=1)
    if not rows:
        return None
    value = rows[0].value or {}
    composites = value.get("composites") or {}
    long_cycle = value.get("long_cycle") or {}
    short_cycle = value.get("short_cycle") or {}
    return {
        "asof": value.get("asof"),
        "composites": composites,
        "phase": long_cycle.get("phase"),
        "phase_id": long_cycle.get("phase_id"),
        "short_state": short_cycle.get("state"),
        "liquidity": value.get("liquidity"),
    }


def _dimension_value(dimension: dict[str, Any], cycle: dict[str, Any] | None) -> Any:
    key = dimension.get("cycle_key")
    if not key or not cycle:
        return None
    composites = cycle.get("composites") or {}
    if key in composites:
        comp = composites[key] or {}
        return comp.get("value")
    mapping = {
        "reserve_share": 56.70,
        "debt_to_gdp": 133.0,
        "interest_to_revenue": 25.0,
        "r_minus_g": 0.9,
        "ICI": (composites.get("ICI") or {}).get("value"),
        "ECI": (composites.get("ECI") or {}).get("value"),
    }
    return mapping.get(key)


def run_timeline(session: Session, today: date | None = None) -> dict[str, Any]:
    asof = aware(today) if today else None
    with RunRecorder(
        session,
        kind=KIND,
        subject="world",
        method_id=METHOD,
        asof=asof,
    ) as rec:
        with rec.step("seed_events", kind="fetch", inputs={"source": "docs/23 + docs/research/history-1500-2026.md"}) as step:
            counts = seed_events(session)
            step.outputs = counts
        with rec.step("seed_powers", kind="fetch", inputs={"source": "Maddison 2023 / IMF COFER / Lindert 1969"}) as step:
            powers = seed_powers(session)
            step.outputs = powers
        with rec.step("read_cycle", kind="compute", inputs={"code": "cycle.state.world"}) as step:
            cycle = _cycle_snapshot(session)
            if cycle is None:
                rec.degrade("timeline.cycle_missing", "未找到周期引擎结果，五维对照使用文档静态值")
            step.outputs = {"found": cycle is not None, "phase": (cycle or {}).get("phase")}
        with rec.step("derive", kind="compute") as step:
            dimensions = []
            for item in dataset.DIMENSIONS:
                dimensions.append({**item, "value": _dimension_value(item, cycle)})
            rec.derive(
                code="timeline.position",
                claim=(
                    "当下坐标：储备货币衰落早期、债务高但未极端、利息/收入进警戒区、"
                    "内部极化高位、外部冲突处于经济战阶段"
                ),
                value={
                    "dimensions": dimensions,
                    "analogs": dataset.ANALOGS,
                    "cycle": cycle,
                },
                confidence=0.62,
                evidence_grade="E2",
                subject="world",
                method_id=METHOD,
                inputs=[item["dimension"] for item in dataset.DIMENSIONS],
                steps=[
                    {"name": "取周期引擎分量", "detail": "读取最新 cycle.state.world 的 DMI/ICI/ECI 与长短期阶段"},
                    {"name": "对齐历史锚点", "detail": "与 1913 英镑、1930s 美国、1970s 通胀期对照"},
                    {"name": "给出位置判断", "detail": "逐维判断早期/中期/晚期，并标注证据级"},
                    {"name": "列出历史类比", "detail": "1937 / 1971–73 / 1900–14 三个时刻，综合相似度"},
                ],
                rules_hit=[{"rule_id": "H2", "message": "实力转移领先储备货币转移"}, {"rule_id": "H4", "message": "储备货币衰落先慢后快"}] if cycle else [],
                caveats=[
                    "「早期/晚期」是叙事分期，不是统计检验结论",
                    "类比只用于启发，不用于预测；相似≠相同",
                    "早期份额（1500–1750）为 Maddison 估计，标 C 级",
                ],
                falsifiers=[
                    "美元储备份额连续两年回升超过 2pp，且全球支付份额同步回升",
                    "美国利息/收入回落至 20% 以下且 r−g 转负",
                    "中美关税与出口管制在 12 个月内实质取消",
                ],
                opposing=[
                    "美元份额在 2026Q1/Q2 回升（57.13% → 56.70% 前值 56.42%），「崩塌论」证据不足",
                    "全球贸易/GDP 仍高于 1970 年代，全球化没有逆转，只是在重组",
                ],
            )
            rec.derive(
                code="timeline.power.shift",
                claim="实力转移领先储备货币转移 30–50 年：1870/1900 美国总量超英国 → 1920s 市场换锚 → 1944 制度确认",
                value={
                    "gdp_share": dataset.GDP_SHARE,
                    "reserve_share": dataset.RESERVE_SHARE,
                    "gap_years": {"low": 30, "high": 50, "evidence": "B"},
                },
                confidence=0.70,
                evidence_grade="E1",
                subject="world",
                method_id=METHOD,
                inputs=["GDP_SHARE", "RESERVE_SHARE"],
                steps=[
                    {"name": "取 Maddison 份额", "detail": "1820/1870/1913/1950/2018 已核实点 + 早期估计"},
                    {"name": "取 COFER 份额", "detail": "1913 GBP、1945/1971/1999 估值、2025Q4/2026Q2 官表"},
                    {"name": "计算实力—货币时间差", "detail": "1870/1900 总量超越 → 1920s 市场换锚 → 1944 制度确认"},
                ],
                caveats=[
                    "1820 前份额为估计值（Maddison 反推），误差可达数个点",
                    "储备份额在 1945/1971/1999 三个点是估值，不是年度官表",
                ],
                falsifiers=[
                    "出现一个经济体实力份额超过美国 20 年以上而储备份额始终低于 5%",
                    "美元储备份额在 3 年内跌破 50% 而美国 GDP 份额未下降",
                ],
                opposing=["1950 年代美国实力与美元储备几乎同步达到峰值，时间差在霸权全盛期不明显"],
            )
            rec.derive(
                code="timeline.catalog",
                claim=f"世界长河收录 {len(dataset.EVENTS)} 条事件、{len(dataset.ERAS)} 个霸权时期、{len(dataset.LESSONS)} 条历史规律，覆盖 1500–2026",
                value={
                    "events": len(dataset.EVENTS),
                    "eras": len(dataset.ERAS),
                    "lessons": len(dataset.LESSONS),
                    "span": [1500, 2026],
                    "grade_counts": {
                        grade: sum(1 for item in dataset.EVENTS if item["grade"] == grade)
                        for grade in ("A", "B", "C")
                    },
                },
                confidence=0.85,
                evidence_grade="E1",
                subject="world",
                method_id=METHOD,
                inputs=["EVENTS", "ERAS", "LESSONS"],
                steps=[{"name": "读取数据集", "detail": "dataset.py 的 EVENTS/ERAS/LESSONS"}, {"name": "统计覆盖度", "detail": "按 A/B/C 证据级计数"}],
                caveats=["事件表是精选，不是全集；遗漏事件可能改变叙事权重"],
            )
            step.outputs = {"events": len(dataset.EVENTS), "eras": len(dataset.ERAS)}
        rec.finish(
            summary={
                "events": len(dataset.EVENTS),
                "eras": len(dataset.ERAS),
                "lessons": len(dataset.LESSONS),
                "cycle_found": cycle is not None,
                **counts,
            }
        )
    session.commit()
    return {
        "asof": asof.isoformat() if asof else None,
        "run_id": rec.run.id,
        "status": rec.run.status,
        "events": len(dataset.EVENTS),
        "eras": len(dataset.ERAS),
        "lessons": len(dataset.LESSONS),
        "cycle": cycle,
    }
