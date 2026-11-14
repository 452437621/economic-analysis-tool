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
from app.platform.instrument_units import UNIT_BY_SYMBOL

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
                extra = dict(exists.extra or {})
                if spec:
                    exists.contract_size = spec["contract_size"]
                    exists.margin_pct = spec["margin_pct"]
                    extra.update(
                        {key: value for key, value in spec.items() if key not in ("contract_size", "margin_pct")}
                    )
                if symbol in UNIT_BY_SYMBOL:
                    extra["unit"] = UNIT_BY_SYMBOL[symbol]
                if extra:
                    exists.extra = extra
        session.commit()
    logger.info("seeded/updated %s instruments", created)
    return created


JOBS_DEFAULT: dict[str, str] = {
    "heartbeat": "every 60s",
    "collect_quotes": "every 5m",
    "collect_news": "every 3m",
    "collect_news_slow": "08:15",
    "collect_rates": "every 6h",
    "collect_calendar": "every 6h",
    "collect_positions": "15:45",
    "collect_bodies": "every 10m",
    "collect_daily_bars": "15:40 / 06:30",
    "extract_claims": "every 15m",
    "extract_events": "every 30m",
    "extract_claims_llm": "every 20m (需 LLM Key)",
    "check_data_quality": "15:50",
    "analyze": "16:10",
    "decide": "16:30",
    "theses": "16:35",
    "scan_alerts": "every 5m",
    "score_predictions": "17:00",
    "brief_premarket": "07:30",
    "brief_postmarket": "21:00",
    "weekly_review": "周日 10:00",
    "monthly_review": "每月 1 日 10:00",
    "brief_manual": "manual",
}


def seed_jobs() -> int:
    """Seed the full built-in job registry (idempotent; never overrides user flags)."""
    created = 0
    with SessionLocal() as session:
        legacy = session.scalar(select(Job).where(Job.name == "collect_market"))
        if legacy is not None:
            session.delete(legacy)
        for name, cron in JOBS_DEFAULT.items():
            exists = session.scalar(select(Job).where(Job.name == name))
            if exists is not None:
                # Keep operator-toggled enabled flag; refresh stale/blank labels.
                if not exists.cron or exists.cron == "manual" and name != "brief_manual":
                    exists.cron = cron
                continue
            session.add(Job(name=name, cron=cron, enabled=True))
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
        for index, item in enumerate(items):
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
                    sort_order=index,
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
