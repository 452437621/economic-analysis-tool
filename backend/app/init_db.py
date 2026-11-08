"""Initialize database schema and seed default instruments/jobs.

Usage:  python -m app.init_db
"""

from __future__ import annotations

import logging

import yaml
from sqlalchemy import select

from app.models.base import utcnow
from app.models.core import Instrument, Job
from app.platform.config import ROOT_DIR, settings
from app.platform.db import SessionLocal, init_db

logger = logging.getLogger(__name__)


def seed_instruments() -> int:
    """Seed instrument master data from config/default.yaml (idempotent)."""
    config_path = ROOT_DIR / "config" / "default.yaml"
    if not config_path.exists():
        logger.warning("config file not found: %s", config_path)
        return 0

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    groups = (config.get("market") or {}).get("instruments") or {}

    created = 0
    with SessionLocal() as session:
        for asset_class, items in groups.items():
            for item in items:
                symbol = str(item["symbol"])
                exists = session.scalar(
                    select(Instrument).where(Instrument.symbol == symbol)
                )
                if exists:
                    continue
                session.add(
                    Instrument(
                        symbol=symbol,
                        name=str(item.get("name", symbol)),
                        exchange=item.get("exchange"),
                        asset_class=str(item.get("asset_class", asset_class)),
                        currency=item.get("currency"),
                        active=True,
                    )
                )
                created += 1
        session.commit()
    logger.info("seeded %s instruments", created)
    return created


def seed_jobs() -> int:
    """Seed built-in job definitions (idempotent)."""
    defaults = [
        {"name": "heartbeat", "cron": "every 60s"},
        {"name": "collect_market", "cron": "every 60s (trading hours)"},
        {"name": "collect_news", "cron": "every 3m"},
        {"name": "brief_premarket", "cron": "07:30"},
        {"name": "brief_postmarket", "cron": "21:00"},
    ]
    created = 0
    with SessionLocal() as session:
        for item in defaults:
            exists = session.scalar(select(Job).where(Job.name == item["name"]))
            if exists:
                continue
            session.add(Job(name=item["name"], cron=item["cron"], enabled=item["name"] == "heartbeat"))
            created += 1
        session.commit()
    return created


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    created = seed_instruments()
    jobs = seed_jobs()
    print(f"database ready: {settings.db_url}")
    print(f"instruments seeded: {created}")
    print(f"jobs seeded: {jobs}")
    print(f"initialized at: {utcnow().isoformat()}")


if __name__ == "__main__":
    main()
