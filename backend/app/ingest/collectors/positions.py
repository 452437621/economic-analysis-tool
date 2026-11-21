"""Exchange member position rankings (SHFE / CZCE / Sina)."""

from __future__ import annotations

import logging
import time

from sqlalchemy import delete, select

from app.ingest import store
from app.ingest.http import HttpClient
from app.ingest.providers import czce_positions, shfe_positions, sina_positions
from app.ingest.sources import SOURCE_CZCE, SOURCE_SHFE, SOURCE_SINA
from app.models.core import MemberPosition, PositionSnapshot
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def collect_positions() -> dict:
    """Fetch SHFE + CZCE member position rankings (top-20 long/short)."""
    started = time.perf_counter()
    stats: dict = {"trade_date": None, "products": 0, "errors": []}
    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        for label, fetcher, source_conf in (
            ("shfe", shfe_positions.fetch_latest, SOURCE_SHFE),
            ("czce", czce_positions.fetch_latest, SOURCE_CZCE),
            ("sina", sina_positions.fetch_latest, SOURCE_SINA),
        ):
            source = store.get_source(session, **source_conf)
            try:
                report_date, rows = fetcher(client)
                if not report_date or not rows:
                    raise RuntimeError(f"no {label} position report available")
                for item in rows:
                    existing = session.scalar(
                        select(PositionSnapshot).where(
                            PositionSnapshot.trade_date == report_date,
                            PositionSnapshot.product == item["product"],
                        )
                    )
                    if existing is None:
                        existing = PositionSnapshot(
                            trade_date=report_date,
                            product=item["product"],
                            name=item["name"],
                        )
                        session.add(existing)
                    existing.name = item["name"]
                    existing.long_pos = item["long_pos"]
                    existing.short_pos = item["short_pos"]
                    existing.net_pos = item["net_pos"]
                    existing.net_ratio = item["net_ratio"]
                    existing.long_chg = item["long_chg"]
                    existing.short_chg = item["short_chg"]
                    session.execute(
                        delete(MemberPosition).where(
                            MemberPosition.trade_date == report_date,
                            MemberPosition.product == item["product"],
                        )
                    )
                    for member in item.get("members") or []:
                        if not member.get("member") or not member.get("rank"):
                            continue
                        session.add(
                            MemberPosition(
                                trade_date=report_date,
                                product=item["product"],
                                name=item["name"],
                                side=member["side"],
                                rank=int(member["rank"]),
                                member=str(member["member"]),
                                position=int(member.get("position") or 0),
                                change=int(member.get("change") or 0),
                            )
                        )
                session.commit()
                stats["products"] += len(rows)
                date_str = report_date.isoformat()
                stats["trade_date"] = max(stats["trade_date"], date_str) if stats["trade_date"] else date_str
                store.record_health(session, source.id, ok=True)
            except Exception as exc:  # noqa: BLE001
                logger.exception("%s positions failed", label)
                store.record_health(session, source.id, ok=False, error=str(exc))
                stats["errors"].append(f"{label}: {exc}")
    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_positions: %s", stats)
    return stats
