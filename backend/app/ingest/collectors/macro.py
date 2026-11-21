"""Structural macro collection (IMF, Treasury, World Bank, Fed, FRED)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.ingest import store
from app.ingest.collectors.support import (
    _annual_points,
    _imf_years,
    _month_end,
    _parse_day,
    _store_macro_points,
    _to_float,
)
from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient
from app.ingest.macro_meta import (
    IMF_ANNUAL_SERIES,
    MACRO_SERIES_META,
    MTS_LINE_SERIES,
    WORLDBANK_ANNUAL_SERIES,
)
from app.ingest.providers import fed_h41, fed_h6, fred, imf_datamapper, treasury_fiscal, worldbank
from app.ingest.sources import (
    SOURCE_FED_RESEARCH,
    SOURCE_FRED,
    SOURCE_IMF,
    SOURCE_TREASURY_FISCAL,
    SOURCE_WORLDBANK,
)
from app.models.core import MacroObs, MacroSeries
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def collect_macro(fed_history_weeks: int = 0) -> dict:
    """Collect structural macro series: IMF WEO, Treasury Fiscal Data, World Bank.

    这是「数据缺失补数据源」的结构性读数来源：IMF 提供债务/GDP、赤字、增速等
    年频序列；财政部提供日频债务与月频收支（可算利息/收入比与赤字率）；世界银行
    作 IMF 不可达时的年频兜底，并补储蓄/投资/货币化/经常账户口径；美联储 H.4.1
    与 H.6 提供周频资产负债表与月频货币供应（净流动性与 M2 的本体读数）。
    任一源失败只记 degraded，不影响其它源。

    ``fed_history_weeks`` > 0 时对 H.4.1 做历史回补（每周一个归档页，成本较高），
    仅供一次性补采使用；默认 0 只取当前周快照。
    """
    started = time.perf_counter()
    stats: dict = {"series": 0, "obs": 0, "degraded_reasons": []}

    with SessionLocal() as session:
        # 1) IMF WEO 年频（7 个指标 × 美国/中国）
        imf_source = store.get_source(session, **SOURCE_IMF)
        imf_errors: list[str] = []
        imf_ok = False
        for indicator, code_by_country in IMF_ANNUAL_SERIES.items():
            try:
                data = imf_datamapper.fetch(indicator, list(code_by_country))
            except Exception as exc:  # noqa: BLE001
                logger.warning("imf datamapper %s failed: %s", indicator, exc)
                imf_errors.append(f"imf {indicator}: {exc}")
                continue
            imf_ok = True
            for iso3, code in code_by_country.items():
                points = _annual_points(code, _imf_years(data, iso3))
                if not points:
                    stats["degraded_reasons"].append(f"imf {indicator}/{iso3}: 无观测值")
                    continue
                _store_macro_points(session, code, points, imf_source.id, stats)
        if imf_ok:
            store.record_health(session, imf_source.id, ok=True)
        else:
            store.record_health(
                session, imf_source.id, ok=False, error="; ".join(imf_errors[-3:]) or "no data"
            )
            stats["degraded_reasons"].extend(imf_errors)

        # 2) 美国财政部 Fiscal Data：日频债务 + 月频收支/利息
        treasury_source = store.get_source(session, **SOURCE_TREASURY_FISCAL)
        try:
            debt_points: list[MacroPoint] = []
            for row in treasury_fiscal.fetch_debt_to_penny(limit=1800):
                ts = _parse_day(row.get("record_date"))
                value = _to_float(row.get("tot_pub_debt_out_amt"))
                if ts is None or value is None:
                    continue
                debt_points.append(MacroPoint(code="US_FED_DEBT", ts=ts, value=value))
            _store_macro_points(session, "US_FED_DEBT", debt_points, treasury_source.id, stats)

            by_month: dict[str, dict[str, float]] = {}
            for row in treasury_fiscal.fetch_mts(table=9, page_size=3600):
                code = MTS_LINE_SERIES.get(str(row.get("line_code_nbr") or "").strip())
                month = str(row.get("record_date") or "")[:7]
                value = _to_float(row.get("current_month_rcpt_outly_amt"))
                if code is None or len(month) != 7 or value is None:
                    continue
                by_month.setdefault(month, {})[code] = value
            monthly: dict[str, dict[str, float]] = {}
            for month, values in by_month.items():
                receipts = values.get("US_MTS_RECEIPTS")
                outlays = values.get("US_MTS_OUTLAYS")
                interest = values.get("US_MTS_INTEREST")
                if receipts is not None:
                    monthly.setdefault("US_MTS_RECEIPTS", {})[month] = receipts
                if outlays is not None:
                    monthly.setdefault("US_MTS_OUTLAYS", {})[month] = outlays
                if interest is not None:
                    monthly.setdefault("US_MTS_INTEREST", {})[month] = interest
                if receipts is not None and outlays is not None:
                    monthly.setdefault("US_MTS_DEFICIT", {})[month] = outlays - receipts
            for code, by_ts in monthly.items():
                points = []
                for month, value in by_ts.items():
                    day = _parse_day(f"{month}-01")
                    if day is not None:
                        points.append(MacroPoint(code=code, ts=_month_end(day), value=value))
                _store_macro_points(session, code, points, treasury_source.id, stats)
            store.record_health(session, treasury_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("treasury fiscal data failed")
            store.record_health(session, treasury_source.id, ok=False, error=str(exc))
            stats["degraded_reasons"].append(f"treasury_fiscal: {exc}")

        # 3) 世界银行年频兜底（IMF 403/不可达时仍能给出债务与增长口径）
        wb_source = store.get_source(session, **SOURCE_WORLDBANK)
        wb_errors: list[str] = []
        wb_ok = False
        for indicator, code_by_country in WORLDBANK_ANNUAL_SERIES.items():
            for iso3, code in code_by_country.items():
                try:
                    years = worldbank.fetch(indicator, iso3)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("worldbank %s/%s failed: %s", indicator, iso3, exc)
                    wb_errors.append(f"worldbank {indicator}/{iso3}: {exc}")
                    continue
                wb_ok = True
                points = _annual_points(code, years)
                if not points:
                    stats["degraded_reasons"].append(f"worldbank {indicator}/{iso3}: 无观测值")
                    continue
                _store_macro_points(session, code, points, wb_source.id, stats)
        if wb_ok:
            store.record_health(session, wb_source.id, ok=True)
        else:
            store.record_health(
                session, wb_source.id, ok=False, error="; ".join(wb_errors[-3:]) or "no data"
            )
            stats["degraded_reasons"].extend(wb_errors)

        # 4) 美联储 H.4.1 周频资产负债表：总资产/国债/MBS/准备金/TGA/流通现金。
        #    这是「净流动性 = 央行资产 − TGA − RRP」的本体，此前完全缺失。
        fed_source = store.get_source(session, **SOURCE_FED_RESEARCH)
        try:
            if fed_history_weeks > 0:
                series = fed_h41.fetch_history(weeks=fed_history_weeks)
            else:
                snapshot = fed_h41.fetch_current()
                ts = datetime(snapshot["asof"].year, snapshot["asof"].month, snapshot["asof"].day,
                              tzinfo=timezone.utc)
                series = {
                    code: [MacroPoint(code=code, ts=ts, value=value)]
                    for code, value in snapshot["values"].items()
                }
            for code, points in series.items():
                if points:
                    _store_macro_points(session, code, points, fed_source.id, stats)
            store.record_health(session, fed_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("fed h41 balance sheet failed")
            store.record_health(session, fed_source.id, ok=False, error=str(exc))
            stats["degraded_reasons"].append(f"fed_h41: {exc}")

        # 5) 美联储 H.6 月频货币供应：M1 / M2 / 货币基础（季节调整）。
        #    M2 此前是透镜的已知缺口，H.6 当前页一次给出约 17 个月。
        try:
            if fed_history_weeks > 0:
                h6_series = fed_h6.fetch_history(months=max(12, fed_history_weeks // 4))
            else:
                snapshot = fed_h6.fetch_current()
                h6_series = {
                    code: [
                        MacroPoint(
                            code=code,
                            ts=datetime(month.year, month.month, 1, tzinfo=timezone.utc),
                            value=value,
                        )
                        for month, value in sorted(obs.items())
                    ]
                    for code, obs in snapshot.items()
                }
            for code, points in h6_series.items():
                if points:
                    _store_macro_points(session, code, points, fed_source.id, stats)
        except Exception as exc:  # noqa: BLE001
            logger.exception("fed h6 money supply failed")
            stats["degraded_reasons"].append(f"fed_h6: {exc}")

        # FRED fallback for Fed balance sheet / money supply. Only missing or
        # stale series are fetched; fresh H.4.1/H.6 data always wins.
        if settings.fred_enabled and settings.env != "test":
            fred_source = store.get_source(session, **SOURCE_FRED)
            fallback_codes = [
                "US_FED_ASSETS",
                "US_FED_TREASURY",
                "US_FED_MBS",
                "US_FED_RESERVES",
                "US_TGA",
                "US_CURRENCY",
                "US_M1",
                "US_M2",
                "US_MONETARY_BASE",
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
                limit_days = 70 if code in {"US_M1", "US_M2", "US_MONETARY_BASE"} else 14
                if (datetime.now(timezone.utc) - ts).days > limit_days:
                    need.append(code)
            if need:
                try:
                    with HttpClient() as client:
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
                    logger.warning("fred macro fallback failed: %s", exc)
                    store.record_health(session, fred_source.id, ok=False, error=str(exc))
                    stats["degraded_reasons"].append(f"fred: {exc}")

        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_macro: %s", stats)
    return stats
