"""Topic collectors: self-contained Eastmoney ingestion for the Luoyang topic.

Every dataset is fetched and upserted independently; one failing endpoint never
aborts the rest of the run.  The collector is scheduled by ``collect_luoyang``
and can also be triggered from the topic page's refresh button.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Callable

from app.ingest.providers import eastmoney_fundamentals as em
from app.ingest.providers import sina
from app.ingest.http import HttpClient
from app.platform.db import SessionLocal
from app.topics import config as topic_config
from app.topics import storage

logger = logging.getLogger(__name__)

TOPIC_ID = "luoyang"


def _spec():
    spec = topic_config.get_topic(TOPIC_ID)
    if spec is None:
        raise RuntimeError("luoyang topic is not configured")
    return spec


def _dataset_meta(spec, dataset: str) -> dict[str, Any]:
    raw = ((spec.params or {}).get("datasets") or {}).get(dataset) or {}
    return {
        "name": raw.get("label") or dataset,
        "source": raw.get("source"),
        "freq": raw.get("freq"),
        "primary_key": raw.get("primary_key"),
    }


def _upsert(session, spec, dataset: str, rows: list[dict[str, Any]], *, prune_before=None) -> int:
    meta = _dataset_meta(spec, dataset)
    catalog = storage.ensure_dataset(session, topic_id=spec.id, dataset=dataset, **meta)
    return storage.upsert_rows(session, catalog, rows, prune_before=prune_before)


def _benchmark_rows(client: HttpClient, secid: str, symbol: str) -> list[dict[str, Any]]:
    rows = em.fetch_kline(client, secid)
    return [{"as_of": item["as_of"], "row_key": symbol, "payload": item["payload"]} for item in rows]


def _market_rows(client: HttpClient) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol, secid in (
        ("shfe_cu", em.SECIDS["shfe_cu"]),
        ("dxy", em.SECIDS["dxy"]),
        ("usdcnh", em.SECIDS["usdcnh"]),
        ("hkd_cny", em.SECIDS["hkd_cnh"]),
    ):
        try:
            rows.extend(_benchmark_rows(client, secid, symbol))
        except Exception as exc:  # noqa: BLE001 - per-symbol isolation
            logger.warning("luoyang market series %s failed: %s", symbol, exc)
    try:
        lme = sina.fetch_global_daily(client, "CAD")
        rows.extend(
            {
                "as_of": bar.ts.date(),
                "row_key": "lme_cu",
                "payload": {"open": bar.open, "close": bar.close, "high": bar.high, "low": bar.low, "volume": bar.volume},
            }
            for bar in lme
            if bar.close is not None
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("luoyang LME copper failed: %s", exc)
    return rows


def _statement_rows(client: HttpClient) -> list[dict[str, Any]]:
    reports = {
        "income": ("RPT_F10_FINANCE_GINCOME", "REPORT_DATE"),
        "cashflow": ("RPT_F10_FINANCE_GCASHFLOW", "REPORT_DATE"),
        "balance": ("RPT_F10_FINANCE_GBALANCE", "REPORT_DATE"),
    }
    data: dict[str, list[dict[str, Any]]] = {}
    for key, (report_name, sort_column) in reports.items():
        data[key] = em.fetch_datacenter(
            client,
            report_name,
            filter_='(SECUCODE="603993.SH")',
            sort_columns=sort_column,
            max_pages=4,
        )
    return em.merge_statements(data["income"], data["cashflow"], data["balance"])


def _seed_from_system(session, spec, dataset: str) -> list[dict[str, Any]]:
    """Fallback to the system's own daily bars when the topic kline endpoint fails.

    Uses the real OHLC/volume stored in ``market_bars``; duplicating the close
    into open/high/low would render as flat candles with no body or shadows.
    """
    from app.topics import bars

    mapping: dict[str, list[tuple[str, str]]] = {
        "price_daily": [("default", "603993")],
        "benchmarks_daily": [("hs300", "000300"), ("sse", "000001")],
        "market_daily": [("shfe_cu", "CU"), ("lme_cu", "HG"), ("dxy", "DXY"), ("usdcnh", "USDCNH")],
    }
    rows: list[dict[str, Any]] = []
    for row_key, symbol in mapping.get(dataset) or []:
        for item in bars.load_bar_rows(session, symbol):
            rows.append({"as_of": item["as_of"], "row_key": row_key, "payload": item["payload"]})
    return rows


def collect_luoyang() -> dict[str, Any]:
    """Fetch every Luoyang dataset, upsert and report per-dataset status."""
    started = time.perf_counter()
    spec = _spec()
    summary: dict[str, Any] = {"datasets": {}, "records": 0, "errors": []}

    jobs: list[tuple[str, Callable[[HttpClient], list[dict[str, Any]]], str]] = []

    def price_rows(client: HttpClient) -> list[dict[str, Any]]:
        adjusted = em.fetch_kline(client, em.SECIDS["a"], fqt=1)
        raw = em.fetch_kline(client, em.SECIDS["a"], fqt=0)
        return em.merge_raw_close(adjusted, raw)

    def valuation_rows(client: HttpClient) -> list[dict[str, Any]]:
        return em.normalize_valuation(
            em.fetch_datacenter(
                client,
                "RPT_VALUEANALYSIS_DET",
                filter_='(SECURITY_CODE="603993")',
                sort_columns="TRADE_DATE",
                max_pages=10,
            )
        )

    def financial_rows(client: HttpClient) -> list[dict[str, Any]]:
        return em.normalize_financials(
            em.fetch_datacenter(
                client,
                "RPT_F10_FINANCE_MAINFINADATA",
                filter_='(SECUCODE="603993.SH")',
                sort_columns="REPORT_DATE",
                max_pages=6,
            )
        )

    def segment_rows(client: HttpClient) -> list[dict[str, Any]]:
        return em.normalize_segments(
            em.fetch_datacenter(
                client,
                "RPT_F10_FN_MAINOP",
                filter_='(SECUCODE="603993.SH")',
                sort_columns="REPORT_DATE",
                max_pages=4,
            )
        )

    def margin_rows(client: HttpClient) -> list[dict[str, Any]]:
        return em.normalize_margin(
            em.fetch_datacenter(
                client,
                "RPTA_WEB_RZRQ_GGMX",
                filter_='(SCODE="603993")',
                sort_columns="DATE",
                max_pages=8,
            )
        )

    def dividend_rows(client: HttpClient) -> list[dict[str, Any]]:
        return em.normalize_dividends(
            em.fetch_datacenter(
                client,
                "RPT_SHAREBONUS_DET",
                filter_='(SECURITY_CODE="603993")',
                sort_columns="REPORT_DATE",
                max_pages=2,
            )
        )

    jobs.extend(
        [
            ("price_daily", price_rows, "eastmoney_push2his"),
            ("h_price_daily", lambda client: _benchmark_rows(client, em.SECIDS["h"], "default"), "eastmoney_push2his"),
            (
                "benchmarks_daily",
                lambda client: [
                    * _benchmark_rows(client, em.SECIDS["hs300"], "hs300"),
                    * _benchmark_rows(client, em.SECIDS["sse"], "sse"),
                    * _benchmark_rows(client, em.SECIDS["sector"], "sector"),
                ],
                "eastmoney_push2his",
            ),
            ("market_daily", _market_rows, "eastmoney+sina"),
            ("valuation_daily", valuation_rows, "eastmoney_datacenter"),
            ("financials_quarterly", financial_rows, "eastmoney_datacenter"),
            ("financial_statements", _statement_rows, "eastmoney_datacenter"),
            ("segments", segment_rows, "eastmoney_datacenter"),
            ("margin_daily", margin_rows, "eastmoney_datacenter"),
            ("flows_daily", lambda client: em.fetch_flows(client), "eastmoney_fflow"),
            ("dividends", dividend_rows, "eastmoney_datacenter"),
            ("announcements", lambda client: em.fetch_announcements(client), "eastmoney_notice"),
            ("research_reports", lambda client: em.fetch_reports(client), "eastmoney_report"),
        ]
    )

    def snapshot_rows(client: HttpClient) -> list[dict[str, Any]]:
        peers = (spec.params or {}).get("peers") or []
        secids = {"a": em.SECIDS["a"], "h": em.SECIDS["h"], "sector": em.SECIDS["sector"]}
        for peer in peers:
            if peer.get("code") and peer.get("secid"):
                secids[str(peer["code"])] = str(peer["secid"])
        rows = em.fetch_quotes(client, secids)
        for row in rows:
            code = str((row.get("payload") or {}).get("code") or "")
            if code == "603993":
                row["row_key"] = "a"
            elif code == "03993":
                row["row_key"] = "h"
            elif code == "BK0478":
                row["row_key"] = "sector"
        return rows

    jobs.append(("snapshots", snapshot_rows, "eastmoney_quote"))

    with HttpClient(min_interval=0.35) as client, SessionLocal() as session:
        for dataset, fetcher, provider in jobs:
            try:
                rows = fetcher(client)
                if not rows and dataset in {"price_daily", "benchmarks_daily", "market_daily"}:
                    rows = _seed_from_system(session, spec, dataset)
                    provider = f"{provider}+system_bars"
                elif not rows:
                    # A silent empty vendor response is a failure, not a healthy run.
                    raise RuntimeError("上游返回 0 行")
                if not rows:
                    raise RuntimeError("上游返回 0 行且系统行情库无兜底")
                prune_before = storage.today_local() - timedelta(days=30) if dataset == "snapshots" else None
                written = _upsert(session, spec, dataset, rows, prune_before=prune_before)
                storage.record_source_run(
                    session,
                    topic_id=spec.id,
                    dataset=dataset,
                    provider=provider,
                    ok=True,
                    records=written,
                )
                summary["datasets"][dataset] = {"ok": True, "records": written}
                summary["records"] += written
                session.commit()
            except Exception as exc:  # noqa: BLE001 - dataset isolation
                session.rollback()
                logger.exception("luoyang dataset %s failed", dataset)
                seeded = 0
                if dataset in {"price_daily", "benchmarks_daily", "market_daily"}:
                    try:
                        seeded = _upsert(session, spec, dataset, _seed_from_system(session, spec, dataset))
                        session.commit()
                    except Exception:  # noqa: BLE001 - fallback is best effort
                        session.rollback()
                        seeded = 0
                storage.record_source_run(
                    session,
                    topic_id=spec.id,
                    dataset=dataset,
                    provider=provider,
                    ok=seeded > 0,
                    records=seeded,
                    error=str(exc) if not seeded else f"{exc}（已用系统行情库兜底 {seeded} 行）",
                )
                session.commit()
                summary["datasets"][dataset] = {
                    "ok": seeded > 0,
                    "records": seeded,
                    "error": str(exc),
                    "fallback": seeded > 0,
                }
                summary["errors"].append(f"{dataset}: {exc}")
                if seeded:
                    summary["records"] += seeded
        storage.prune_source_runs(session)
        session.commit()

    summary["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_luoyang: %s", summary)
    return summary
