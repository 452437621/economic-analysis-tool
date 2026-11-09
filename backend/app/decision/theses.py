"""Thesis & scenario management: turn signals and events into falsifiable theses."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.models.core import (
    Claim,
    Event,
    EventInstrument,
    Instrument,
    Scenario,
    Signal,
    Thesis,
    ThesisEvidence,
)
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

KEYWORDS: dict[str, tuple[str, ...]] = {
    "AU": ("黄金", "金价", "美联储", "实际利率", "央行", "利率", "通胀", "CPI", "美元"),
    "AG": ("白银", "银价", "黄金", "央行", "利率", "通胀", "美元"),
    "CU": ("铜", "铜价", "冶炼", "制造业", "PMI", "库存", "美元"),
    "AL": ("铝", "电解铝", "制造业", "PMI", "库存"),
    "ZN": ("锌", "库存", "制造业"),
    "NI": ("镍", "库存", "制造业"),
    "SC": ("原油", "油价", "OPEC", "库存", "能源"),
    "M": ("豆粕", "大豆", "农产品"),
    "P": ("棕榈", "油脂", "农产品"),
    "SR": ("白糖", "食糖", "农产品"),
    "CF": ("棉花", "农产品"),
    "I": ("铁矿", "钢铁", "库存"),
    "603993": ("洛阳钼业", "钼", "钴", "铜"),
    "000300": ("沪深300", "A股", "股市", "沪指"),
}
DRIVER_TEXT = {
    "breakout": "区间突破后的趋势延续",
    "momentum": "中期动量与均线结构",
    "mean_reversion": "偏离均值后的回归",
}


def match_claims(symbol: str, claims: list[Claim], limit: int = 3) -> list[Claim]:
    keywords = KEYWORDS.get(symbol, ())
    matched = [
        claim
        for claim in claims
        if any(
            keyword in (claim.subject or "") or keyword in (claim.predicate or "")
            for keyword in keywords
        )
    ]
    return matched[:limit]


def build_thesis(signal: dict, instrument_name: str, claims: list[Claim]) -> dict:
    direction = "long" if signal.get("direction") == "long" else "short"
    label = "看多" if direction == "long" else "看空"
    strength = float(signal.get("strength") or 0.5)
    matched = match_claims(signal.get("symbol", ""), claims)
    evidence_weight = min(0.75, 0.45 + 0.1 * len(matched))
    confidence = round(min(0.9, strength * 0.7 + evidence_weight * 0.3), 2)
    return {
        "title": f"【信号】{instrument_name}（{signal.get('symbol')}）{label}：{signal.get('type')}",
        "direction": direction,
        "prior": round(strength, 2),
        "posterior": confidence,
        "horizon_days": 10,
        "status": "watch",
        "invalidation": (
            f"{instrument_name} 收盘反向突破 1.5×ATR，或 {signal.get('type')} 条件消失；"
            "或在 10 个交易日内未兑现方向性收益。"
        ),
        "main_driver": DRIVER_TEXT.get(signal.get("type"), "技术信号"),
        "evidence": [
            {
                "claim_id": claim.id,
                "weight": 0.6,
                "note": f"{claim.subject}: {claim.predicate} {(claim.value if claim.value is not None else '')}{claim.unit or ''}".strip(),
            }
            for claim in matched
        ],
        "scenarios": [
            {
                "name": "基准情景",
                "probability": 0.55,
                "triggers": "信号延续，关键价位不破",
                "impacts": {"direction": label, "horizon": "10d"},
            },
            {
                "name": "反向情景",
                "probability": 0.45,
                "triggers": "止损触发或驱动因素反转",
                "impacts": {"direction": "看空" if direction == "long" else "看多", "horizon": "10d"},
            },
        ],
        "evidence_note": f"匹配 {len(matched)} 条断言",
    }


EVENT_DIRECTION: dict[str, dict[str, tuple[str, ...]]] = {
    "trade": {"long": ("AU", "AG"), "short": ("000300", "CU")},
    "geopolitical": {"long": ("AU", "SC"), "short": ("000300",)},
    "supply": {"long": ("SC",)},
    "monetary_policy": {"long": ("AU",), "short": ("000300",)},
}


def build_event_thesis(event: dict, symbol: str, instrument_name: str, direction: str) -> dict:
    label = "看多" if direction == "long" else "看空"
    return {
        "title": f"【事件】{event.get('title', '')[:40]} · {instrument_name}{label}",
        "direction": direction,
        "prior": 0.5,
        "posterior": 0.5,
        "horizon_days": 5,
        "status": "watch",
        "invalidation": (
            f"事件影响消退后 {instrument_name} 未在 5 个交易日内兑现方向；"
            "或出现相反政策/官方澄清。"
        ),
        "main_driver": f"{event.get('type')} 事件驱动（规则识别，需人工核实）",
        "evidence": [],
        "scenarios": [
            {
                "name": "基准情景",
                "probability": 0.5,
                "triggers": "事件持续发酵，市场按风险方向定价",
                "impacts": {"direction": label, "horizon": "5d"},
            },
            {
                "name": "反向情景",
                "probability": 0.5,
                "triggers": "事件被证伪/迅速缓和",
                "impacts": {"direction": "看空" if direction == "long" else "看多", "horizon": "5d"},
            },
        ],
    }


def generate_event_theses(
    session,
    instruments: dict,
    claims: list[Claim],
    limit: int = 3,
) -> dict:
    counts = {"theses": 0, "scenarios": 0, "evidence": 0}
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
    events = session.scalars(
        select(Event)
        .where(Event.event_date >= cutoff, Event.type.in_(tuple(EVENT_DIRECTION)))
        .order_by(Event.event_date.desc())
        .limit(limit)
    ).all()
    for event in events:
        linked = session.scalars(
            select(EventInstrument.instrument_id).where(EventInstrument.event_id == event.id)
        ).all()
        source_claims: list[Claim] = []
        if event.source_ids:
            source_claims = session.scalars(
                select(Claim).where(Claim.document_id == event.source_ids[0]).limit(2)
            ).all()
        for instrument_id in linked:
            instrument = instruments.get(instrument_id)
            if instrument is None:
                continue
            directions = EVENT_DIRECTION.get(event.type) or {}
            direction = None
            for candidate, symbols in directions.items():
                if instrument.symbol in symbols:
                    direction = candidate
                    break
            if direction is None:
                continue
            payload = build_event_thesis(
                {"title": event.title, "type": event.type}, instrument.symbol, instrument.name, direction
            )
            thesis = Thesis(
                title=payload["title"],
                asset_ids=[instrument.id],
                direction=payload["direction"],
                prior=payload["prior"],
                posterior=payload["posterior"],
                horizon_days=payload["horizon_days"],
                status=payload["status"],
                invalidation=payload["invalidation"],
                main_driver=payload["main_driver"],
            )
            session.add(thesis)
            session.flush()
            counts["theses"] += 1
            for claim in source_claims:
                session.add(
                    ThesisEvidence(
                        thesis_id=thesis.id,
                        claim_id=claim.id,
                        weight=0.4,
                        note=f"事件来源断言：{claim.subject} {claim.predicate}",
                    )
                )
                counts["evidence"] += 1
            for scenario in payload["scenarios"]:
                session.add(
                    Scenario(
                        thesis_id=thesis.id,
                        name=scenario["name"],
                        probability=scenario["probability"],
                        triggers=scenario["triggers"],
                        impacts=scenario["impacts"],
                    )
                )
                counts["scenarios"] += 1
    return counts


def generate_theses(limit: int = 4) -> dict:
    counts = {"theses": 0, "scenarios": 0, "evidence": 0}
    with SessionLocal() as session:
        session.execute(delete(Thesis).where(Thesis.title.like("【信号】%")))
        session.execute(delete(Thesis).where(Thesis.title.like("【事件】%")))
        signals = session.scalars(
            select(Signal).order_by(Signal.strength.desc()).limit(limit)
        ).all()
        instruments = {row.id: row for row in session.scalars(select(Instrument)).all()}
        claims = session.scalars(
            select(Claim).order_by(Claim.created_at.desc()).limit(200)
        ).all()
        for signal in signals:
            instrument = instruments.get(signal.instrument_id)
            if instrument is None:
                continue
            payload = build_thesis(
                {
                    "symbol": instrument.symbol,
                    "type": signal.type,
                    "direction": signal.direction,
                    "strength": signal.strength,
                },
                instrument.name,
                claims,
            )
            thesis = Thesis(
                title=payload["title"],
                asset_ids=[instrument.id],
                direction=payload["direction"],
                prior=payload["prior"],
                posterior=payload["posterior"],
                horizon_days=payload["horizon_days"],
                status=payload["status"],
                invalidation=payload["invalidation"],
                main_driver=payload["main_driver"],
            )
            session.add(thesis)
            session.flush()
            counts["theses"] += 1
            for evidence in payload["evidence"]:
                session.add(
                    ThesisEvidence(
                        thesis_id=thesis.id,
                        claim_id=evidence["claim_id"],
                        weight=evidence["weight"],
                        note=evidence["note"],
                    )
                )
                counts["evidence"] += 1
            for scenario in payload["scenarios"]:
                session.add(
                    Scenario(
                        thesis_id=thesis.id,
                        name=scenario["name"],
                        probability=scenario["probability"],
                        triggers=scenario["triggers"],
                        impacts=scenario["impacts"],
                    )
                )
                counts["scenarios"] += 1
        event_counts = generate_event_theses(session, instruments, claims)
        for key in counts:
            counts[key] += event_counts[key]
        session.commit()
    logger.info("generate_theses: %s", counts)
    return counts
