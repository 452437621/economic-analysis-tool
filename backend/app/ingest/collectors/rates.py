"""Rates, yields and money-market collection."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.ingest import store
from app.ingest.failover import Candidate, run_chain
from app.ingest.http import HttpClient
from app.ingest.macro_meta import MACRO_SERIES_META
from app.ingest.providers import eastmoney_yield, ecb, fred, jgb, nyfed, nyfed_money, treasury
from app.ingest.sources import (
    SOURCE_ECB,
    SOURCE_EM,
    SOURCE_FRED,
    SOURCE_JGB,
    SOURCE_NYFED,
    SOURCE_TREASURY,
)
from app.models.core import MacroObs, MacroSeries
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def collect_rates() -> dict:
    """Fetch US Treasury nominal/real curves (5 rolling years)."""
    started = time.perf_counter()
    stats: dict = {"points": 0, "series": 0, "errors": []}

    current_year = datetime.now(timezone.utc).year
    years = list(range(current_year - 4, current_year + 1))

    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        treasury_source = store.get_source(session, **SOURCE_TREASURY)
        fred_source = store.get_source(session, **SOURCE_FRED) if settings.fred_enabled else None
        rate_codes = [
            "US2Y",
            "US5Y",
            "US10Y",
            "US30Y",
            "US5Y_REAL",
            "US10Y_REAL",
            "US5Y_BE",
            "US10Y_BE",
        ]
        candidates = [
            Candidate(
                SOURCE_TREASURY,
                lambda client: treasury.fetch_curves(client, years),
                "primary",
            )
        ]
        if fred_source is not None:
            candidates.append(
                Candidate(
                    SOURCE_FRED,
                    lambda client: fred.fetch_many(
                        client,
                        rate_codes,
                        start_date=datetime.now(timezone.utc).date() - timedelta(days=365 * 5),
                    ),
                    "backup",
                )
            )
        chain = run_chain(session, "rates.us_treasury", candidates, client, validator=bool)
        stats["us_rates_provider"] = chain.provider
        stats["us_rates_attempts"] = chain.attempts
        if chain.value:
            try:
                source_id = chain.source_id or treasury_source.id
                for code, points in chain.value.items():
                    meta = MACRO_SERIES_META.get(code, {})
                    n = store.upsert_macro(
                        session,
                        code,
                        points,
                        source_id=source_id,
                        name=meta.get("name"),
                        unit=meta.get("unit"),
                        country=meta.get("country"),
                        freq=meta.get("freq"),
                    )
                    stats["points"] += n
                    stats["series"] += 1
            except Exception as exc:  # noqa: BLE001 - one writer error must not skip other rate sources
                logger.exception("us rates persist failed")
                stats["errors"].append(f"us_rates persist: {exc}")
        else:
            detail = "; ".join(
                f"{item['source']}: {item.get('error')}" for item in chain.attempts if item.get("error")
            )
            logger.warning("us rates chain exhausted: %s", detail)
            stats["errors"].append(f"us_rates: {detail[:300]}")

        # Japan MOF JGB yields
        jgb_source = store.get_source(session, **SOURCE_JGB)
        try:
            curves = jgb.fetch_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=jgb_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                    freq=meta.get("freq"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, jgb_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("jgb rates failed")
            store.record_health(session, jgb_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"jgb: {exc}")

        # ECB Germany benchmark yields
        ecb_source = store.get_source(session, **SOURCE_ECB)
        try:
            curves = ecb.fetch_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=ecb_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                    freq=meta.get("freq"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, ecb_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ecb rates failed")
            store.record_health(session, ecb_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"ecb: {exc}")

        # France 10Y convergence rate (ECB IRS, monthly)
        try:
            curves = ecb.fetch_france_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=ecb_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                    freq=meta.get("freq"),
                )
                stats["points"] += n
                stats["series"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("ecb france rates failed")
            stats["errors"].append(f"ecb_fr: {exc}")

        # Eastmoney China (and US) treasury yields
        em_yield_source = store.get_source(session, **SOURCE_EM)
        try:
            curves = eastmoney_yield.fetch_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=em_yield_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                    freq=meta.get("freq"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, em_yield_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("eastmoney yields failed")
            store.record_health(session, em_yield_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"em_yield: {exc}")

        # NY Fed: SOFR / EFFR / spread
        nyfed_source = store.get_source(session, **SOURCE_NYFED)
        try:
            start = (datetime.now(timezone.utc).date() - timedelta(days=365 * 5))
            curves = nyfed.fetch_rates(client, start_date=start)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=nyfed_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                    freq=meta.get("freq"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, nyfed_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("nyfed rates failed")
            store.record_health(session, nyfed_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"nyfed: {exc}")
        # NY Fed 货币市场管道：TGCR / BGCR / OBFR / 隔夜逆回购规模
        try:
            start = datetime.now(timezone.utc).date() - timedelta(days=365 * 5)
            series = nyfed_money.fetch_money(client, start_date=start)
            for code, points in series.items():
                if not points:
                    stats["errors"].append(f"nyfed_money {code}: 无数据")
                    continue
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=nyfed_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                    freq=meta.get("freq"),
                )
                stats["points"] += n
                stats["series"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("nyfed money failed")
            stats["errors"].append(f"nyfed_money: {exc}")

        # FRED fallback: fill only the US series that are missing/stale after the
        # primary official endpoints. Never overwrite fresher primary data.
        if settings.fred_enabled and settings.env != "test":
            fred_source = store.get_source(session, **SOURCE_FRED)
            fallback_codes = [
                "US2Y",
                "US5Y",
                "US10Y",
                "US30Y",
                "US5Y_REAL",
                "US10Y_REAL",
                "US5Y_BE",
                "US10Y_BE",
                "SOFR",
                "EFFR",
            ]
            latest_rows = session.execute(
                select(MacroSeries.code, func.max(MacroObs.ts_utc))
                .join(MacroObs, MacroObs.series_id == MacroSeries.id, isouter=True)
                .where(MacroSeries.code.in_(fallback_codes))
                .group_by(MacroSeries.code)
            ).all()
            latest = {code: ts for code, ts in latest_rows}
            need = []
            for code in fallback_codes:
                ts = latest.get(code)
                if ts is None:
                    need.append(code)
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - ts).days > 5:
                    need.append(code)
            if need:
                try:
                    points_by_code = fred.fetch_many(
                        client,
                        need,
                        start_date=datetime.now(timezone.utc).date() - timedelta(days=365 * 5),
                    )
                    added = 0
                    for code, points in points_by_code.items():
                        meta = MACRO_SERIES_META.get(code, {})
                        added += store.upsert_macro(
                            session,
                            code,
                            points,
                            source_id=fred_source.id,
                            name=meta.get("name"),
                            unit=meta.get("unit"),
                            country=meta.get("country"),
                            freq=meta.get("freq"),
                        )
                    stats["fred_fallback"] = added
                    stats["fred_codes"] = sorted(points_by_code)
                    store.record_health(session, fred_source.id, ok=bool(points_by_code))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("fred rates fallback failed: %s", exc)
                    store.record_health(session, fred_source.id, ok=False, error=str(exc))
                    stats["errors"].append(f"fred: {exc}")

        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_rates: %s", stats)
    return stats
