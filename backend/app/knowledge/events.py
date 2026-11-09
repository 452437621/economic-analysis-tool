"""Rule-based event extraction from official news (trade/geopolitical/policy/data)."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.models.core import Document, DocumentBody, Event, EventInstrument, Instrument
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "trade",
        (
            "tariff",
            "关税",
            "trade war",
            "贸易战",
            "export control",
            "出口管制",
            "section 301",
            "ustr",
            "wto",
            "贸易代表",
        ),
    ),
    (
        "geopolitical",
        (
            "sanction",
            "制裁",
            "war",
            "战争",
            "conflict",
            "冲突",
            "military",
            "军事",
            "hormuz",
            "red sea",
            "红海",
            "geopolitical",
        ),
    ),
    (
        "monetary_policy",
        (
            "federal reserve",
            "美联储",
            "rate cut",
            "降息",
            "rate hike",
            "加息",
            "european central bank",
            "欧洲央行",
            "bank of japan",
            "日本央行",
            "monetary policy",
            "货币政策",
        ),
    ),
    (
        "supply",
        (
            "opec",
            "supply cut",
            "production cut",
            "减产",
            "原油库存",
            "crude stocks",
            "eia",
            "inventory",
        ),
    ),
    (
        "data_release",
        (
            "cpi",
            "ppi",
            "pmi",
            "gdp",
            "nonfarm",
            "非农",
            "unemployment",
            "失业率",
            "inflation",
            "通胀",
        ),
    ),
]

INSTRUMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AU": ("gold", "黄金", "fed", "美联储", "利率", "美元", "inflation", "通胀"),
    "AG": ("silver", "白银", "gold", "黄金"),
    "CU": ("copper", "铜", "smelter", "冶炼"),
    "AL": ("aluminum", "铝", "alumina"),
    "SC": ("oil", "原油", "opec", "crude", "能源"),
    "000300": ("china", "中国", "stock", "股市", "a股"),
    "603993": ("molybdenum", "钼", "cobalt", "钴", "copper", "铜"),
}


def classify_document(title: str, body: str) -> dict | None:
    text = f"{title}\n{body[:3000]}".lower()
    for event_type, keywords in RULES:
        hits = [keyword for keyword in keywords if keyword in text]
        if hits:
            return {"type": event_type, "hits": hits[:6], "subtype": hits[0]}
    return None


def match_instruments(text: str) -> list[str]:
    lowered = text.lower()
    return [
        symbol
        for symbol, keywords in INSTRUMENT_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]


def extract_events(limit: int = 25) -> dict:
    stats = {"documents": 0, "events": 0, "links": 0, "errors": []}
    with SessionLocal() as session:
        instruments = {row.symbol: row.id for row in session.scalars(select(Instrument)).all()}
        documents = session.scalars(
            select(Document)
            .where(Document.body_status.in_(["extracted", "claims_extracted"]))
            .order_by(Document.fetched_at.desc())
            .limit(limit * 4)
        ).all()
        processed = 0
        for document in documents:
            if processed >= limit:
                break
            meta = dict(document.meta or {})
            if meta.get("event_extracted"):
                continue
            body = session.scalar(
                select(DocumentBody).where(DocumentBody.document_id == document.id)
            )
            if body is None:
                continue
            try:
                payload = classify_document(document.title, body.text)
                if payload:
                    event = Event(
                        type=payload["type"],
                        subtype=payload["subtype"],
                        event_date=document.published_at or document.fetched_at,
                        title=document.title[:500],
                        summary=body.text[:400],
                        impact=0.3,
                        source_ids=[document.id],
                        meta={"hits": payload["hits"]},
                    )
                    session.add(event)
                    session.flush()
                    stats["events"] += 1
                    for symbol in match_instruments(f"{document.title} {body.text[:2000]}"):
                        instrument_id = instruments.get(symbol)
                        if instrument_id:
                            session.add(EventInstrument(event_id=event.id, instrument_id=instrument_id))
                            stats["links"] += 1
                meta["event_extracted"] = True
                document.meta = meta
                session.commit()
                stats["documents"] += 1
                processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("event extraction failed for %s: %s", document.id, exc)
                session.rollback()
                stats["errors"].append(f"{document.id}: {exc}")
    logger.info("extract_events: %s", stats)
    return stats
