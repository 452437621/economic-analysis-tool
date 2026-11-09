"""Initialize database schema and seed default instruments/jobs.

Usage:  python -m app.init_db
"""

from __future__ import annotations

import logging

import yaml
from sqlalchemy import select

from app.models.base import utcnow
from app.models.core import Instrument, Job, WatchItem
from app.platform.config import ROOT_DIR, settings
from app.platform.db import SessionLocal, init_db

logger = logging.getLogger(__name__)

# 交易所标准合约参数（近似值，用户应按期货公司实际标准覆写 extra/margin）
CONTRACT_SPECS: dict[str, dict] = {
    "AU": {"contract_size": 1000, "margin_pct": 0.09, "fee_per_lot": 10.0, "tick_size": 0.02},
    "AG": {"contract_size": 15, "margin_pct": 0.10, "fee_per_lot": 3.0, "tick_size": 1.0},
    "CU": {"contract_size": 5, "margin_pct": 0.10, "fee_per_lot": 15.0, "tick_size": 10.0},
    "AL": {"contract_size": 5, "margin_pct": 0.10, "fee_per_lot": 3.0, "tick_size": 5.0},
    "ZN": {"contract_size": 5, "margin_pct": 0.10, "fee_per_lot": 3.0, "tick_size": 5.0},
    "NI": {"contract_size": 1, "margin_pct": 0.12, "fee_per_lot": 3.0, "tick_size": 10.0},
    "SC": {"contract_size": 1000, "margin_pct": 0.12, "fee_per_lot": 20.0, "tick_size": 0.1},
    "M": {"contract_size": 10, "margin_pct": 0.08, "fee_per_lot": 1.5, "tick_size": 1.0},
    "I": {"contract_size": 100, "margin_pct": 0.10, "fee_per_lot": 2.0, "tick_size": 0.5},
    "SR": {"contract_size": 10, "margin_pct": 0.07, "fee_per_lot": 3.0, "tick_size": 1.0},
    "CF": {"contract_size": 5, "margin_pct": 0.07, "fee_per_lot": 4.3, "tick_size": 5.0},
    "P": {"contract_size": 10, "margin_pct": 0.09, "fee_per_lot": 2.5, "tick_size": 2.0},
    "603993": {
        "contract_size": 1,
        "margin_pct": 1.0,
        "fee_per_lot": 0.0,
        "commission_rate": 0.0003,
        "tick_size": 0.01,
    },
}


def seed_instruments() -> int:
    """Seed/update instrument master data from config/default.yaml (idempotent)."""
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
                if exists is None:
                    exists = Instrument(
                        symbol=symbol,
                        name=str(item.get("name", symbol)),
                        exchange=item.get("exchange"),
                        asset_class=str(item.get("asset_class", asset_class)),
                        currency=item.get("currency"),
                        active=True,
                    )
                    session.add(exists)
                    created += 1
                spec = CONTRACT_SPECS.get(symbol)
                if spec:
                    exists.contract_size = spec["contract_size"]
                    exists.margin_pct = spec["margin_pct"]
                    extra = dict(exists.extra or {})
                    extra.update(
                        {key: value for key, value in spec.items() if key not in ("contract_size", "margin_pct")}
                    )
                    exists.extra = extra
        session.commit()
    logger.info("seeded/updated %s instruments", created)
    return created


def seed_jobs() -> int:
    """Seed built-in job definitions (idempotent)."""
    defaults = [
        {"name": "heartbeat", "cron": "every 60s"},
        {"name": "collect_quotes", "cron": "every 60s (trading hours)"},
        {"name": "collect_news", "cron": "every 3m"},
        {"name": "collect_rates", "cron": "every 6h"},
        {"name": "collect_daily_bars", "cron": "15:40 / 06:30"},
        {"name": "brief_premarket", "cron": "07:30"},
        {"name": "brief_postmarket", "cron": "21:00"},
    ]
    created = 0
    with SessionLocal() as session:
        legacy = session.scalar(select(Job).where(Job.name == "collect_market"))
        if legacy is not None:
            session.delete(legacy)
        for item in defaults:
            exists = session.scalar(select(Job).where(Job.name == item["name"]))
            if exists:
                continue
            session.add(
                Job(
                    name=item["name"],
                    cron=item["cron"],
                    enabled=item["name"] in {"heartbeat", "collect_quotes", "collect_news"},
                )
            )
            created += 1
        session.commit()
    return created


def seed_watchlist() -> int:
    """Seed default watchlist from config (only missing symbols; user edits kept)."""
    config_path = ROOT_DIR / "config" / "default.yaml"
    if not config_path.exists():
        return 0
    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    items = (config.get("market") or {}).get("watchlist") or []
    created = 0
    with SessionLocal() as session:
        instruments = {
            row.symbol: row.id for row in session.scalars(select(Instrument)).all()
        }
        for item in items:
            symbol = str(item.get("symbol"))
            instrument_id = instruments.get(symbol)
            if not instrument_id:
                logger.warning("watchlist symbol not found: %s", symbol)
                continue
            exists = session.scalar(
                select(WatchItem).where(WatchItem.instrument_id == instrument_id)
            )
            if exists is not None:
                continue
            session.add(
                WatchItem(
                    instrument_id=instrument_id,
                    group=item.get("group"),
                    priority=int(item.get("priority") or 3),
                    note=item.get("note"),
                )
            )
            created += 1
        session.commit()
    return created


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    created = seed_instruments()
    watch = seed_watchlist()
    jobs = seed_jobs()
    print(f"database ready: {settings.db_url}")
    print(f"instruments seeded: {created}")
    print(f"watchlist seeded: {watch}")
    print(f"jobs seeded: {jobs}")
    print(f"initialized at: {utcnow().isoformat()}")


if __name__ == "__main__":
    main()
