"""Load Luoyang topic datasets from SQLite into pandas frames."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.data import load_frames
from app.topics import storage


@dataclass
class LuoyangData:
    price: pd.DataFrame = field(default_factory=pd.DataFrame)
    valuation: pd.DataFrame = field(default_factory=pd.DataFrame)
    financials: pd.DataFrame = field(default_factory=pd.DataFrame)
    statements: pd.DataFrame = field(default_factory=pd.DataFrame)
    segments: pd.DataFrame = field(default_factory=pd.DataFrame)
    margin: pd.DataFrame = field(default_factory=pd.DataFrame)
    flows: pd.DataFrame = field(default_factory=pd.DataFrame)
    dividends: pd.DataFrame = field(default_factory=pd.DataFrame)
    announcements: pd.DataFrame = field(default_factory=pd.DataFrame)
    reports: pd.DataFrame = field(default_factory=pd.DataFrame)
    benchmarks: pd.DataFrame = field(default_factory=pd.DataFrame)
    market: pd.DataFrame = field(default_factory=pd.DataFrame)
    snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    panel: pd.DataFrame = field(default_factory=pd.DataFrame)
    catalog: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    status: str = "unknown"

    @property
    def latest_date(self) -> date | None:
        if self.price.empty:
            return None
        index = self.price.index[-1]
        return index.date() if hasattr(index, "date") else index

    @property
    def has_price(self) -> bool:
        return not self.price.empty and len(self.price) >= 30

    @property
    def latest_price(self) -> float | None:
        """Prefer the live A-share snapshot (unadjusted) over the adjusted bar."""
        snapshot = (self.snapshots.get("a") or {}).get("price")
        try:
            if snapshot:
                return float(snapshot)
        except (TypeError, ValueError):
            pass
        if not self.panel.empty and "close_raw" in self.panel.columns:
            return float(self.panel["close_raw"].iloc[-1])
        return None


def _frame(rows: list[dict[str, Any]], *, index_key: str = "as_of", row_filter: str | None = None) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        if row_filter and row.get("row_key") != row_filter:
            continue
        payload = row.get("payload") or {}
        record = {**payload, index_key: row.get("as_of")}
        records.append(record)
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records)
    frame[index_key] = pd.to_datetime(frame[index_key], errors="coerce")
    frame = frame.dropna(subset=[index_key]).drop_duplicates(subset=[index_key], keep="last")
    return frame.sort_values(index_key).set_index(index_key)


def _wide(rows: list[dict[str, Any]], value_key: str = "close") -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("payload") or {}
        records.append(
            {
                "date": row.get("as_of"),
                "symbol": row.get("row_key"),
                value_key: payload.get(value_key),
            }
        )
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", value_key])
    return frame.pivot_table(index="date", columns="symbol", values=value_key, aggfunc="last").sort_index()


def _doc_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records = [{**(row.get("payload") or {}), "as_of": row.get("as_of"), "row_key": row.get("row_key")} for row in rows]
    if not records:
        return pd.DataFrame()
    frame = pd.DataFrame(records)
    frame["as_of"] = pd.to_datetime(frame["as_of"], errors="coerce")
    return frame.dropna(subset=["as_of"]).sort_values("as_of")


def load_data(session: Session, topic_id: str = "luoyang") -> LuoyangData:
    data = LuoyangData()
    data.catalog = storage.load_dataset_catalog(session, topic_id)

    price_rows = storage.load_rows(session, topic_id, "price_daily")
    data.price = _frame(price_rows)
    data.valuation = _frame(storage.load_rows(session, topic_id, "valuation_daily"))
    data.financials = _frame(storage.load_rows(session, topic_id, "financials_quarterly"))
    data.statements = _frame(storage.load_rows(session, topic_id, "financial_statements"))
    segment_rows = storage.load_rows(session, topic_id, "segments")
    if segment_rows:
        records = [{**(row.get("payload") or {}), "as_of": row.get("as_of"), "row_key": row.get("row_key")} for row in segment_rows]
        frame = pd.DataFrame(records)
        frame["as_of"] = pd.to_datetime(frame["as_of"], errors="coerce")
        data.segments = frame.dropna(subset=["as_of"]).sort_values("as_of")
    data.margin = _frame(storage.load_rows(session, topic_id, "margin_daily"))
    data.flows = _frame(storage.load_rows(session, topic_id, "flows_daily"))
    data.dividends = _doc_frame(storage.load_rows(session, topic_id, "dividends"))
    data.announcements = _doc_frame(storage.load_rows(session, topic_id, "announcements"))
    data.reports = _doc_frame(storage.load_rows(session, topic_id, "research_reports"))

    bench_rows = storage.load_rows(session, topic_id, "benchmarks_daily")
    data.benchmarks = _wide(bench_rows)
    market_rows = storage.load_rows(session, topic_id, "market_daily")
    data.market = _wide(market_rows)

    for row in storage.load_rows(session, topic_id, "snapshots"):
        payload = dict(row.get("payload") or {})
        as_of = row.get("as_of")
        if as_of is not None:
            payload.setdefault("as_of", as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of))
        data.snapshots[str(row.get("row_key"))] = payload

    _fallback_from_system(session, data)

    if not data.price.empty:
        data.valuation = data.valuation.reindex(data.price.index).ffill()
        data.benchmarks = data.benchmarks.reindex(data.price.index).ffill()
        data.market = data.market.reindex(data.price.index).ffill()

    data.panel = _build_panel(data)
    data.status, data.notes = _assess(data)
    return data


def _fallback_from_system(session: Session, data: LuoyangData) -> None:
    """Use the system's own market library to fill the topic's missing series.

    The daily-bar collector already keeps 603993 / 000300 / CU / HG / DXY /
    USDCNH with real OHLC and volume.  Those bars are forward-adjusted
    (前复权), so the unadjusted close is unavailable; technicals and candles use
    the adjusted series, and the position block falls back to the live snapshot
    when present.
    """
    # Only require the series the analysis actually consumes.  Sector/sse may be
    # absent; treating them as mandatory made the fallback re-read every bar on
    # every overview request because they can never be satisfied.
    need_bench = data.benchmarks.empty or "hs300" not in data.benchmarks.columns
    need_market = data.market.empty or "shfe_cu" not in data.market.columns
    if not (data.price.empty or need_bench or need_market):
        return
    from app.topics import bars

    if data.price.empty:
        try:
            frame = bars.load_bar_frame(session, "603993")
        except Exception as exc:  # noqa: BLE001 - fallback must never break the page
            data.notes.append(f"系统行情库读取失败：{exc}")
            frame = pd.DataFrame()
        if len(frame) >= 30:
            data.price = frame
            data.notes.append(
                "主题日线端点不可达，使用系统行情库 603993 日线（前复权，含 OHLC/成交量；无不复权价）。"
            )
    if not (need_bench or need_market):
        return
    try:
        frames = load_frames(session).closes
    except Exception as exc:  # noqa: BLE001 - fallback must never break the page
        data.notes.append(f"系统行情库读取失败：{exc}")
        return
    if need_bench:
        mapping = {"hs300": "000300", "sse": "000001"}
        missing = {
            target: frames[source]
            for target, source in mapping.items()
            if source in frames.columns and (data.benchmarks.empty or target not in data.benchmarks.columns)
        }
        if missing:
            addition = pd.DataFrame(missing).dropna(how="all")
            addition.index = pd.to_datetime(addition.index)
            data.benchmarks = addition if data.benchmarks.empty else data.benchmarks.join(addition, how="outer")
            data.notes.append("主题基准端点不可达，使用系统行情库沪深300/上证指数；有色板块缺失。")
    if need_market:
        mapping = {"CU": "shfe_cu", "HG": "lme_cu", "DXY": "dxy", "USDCNH": "usdcnh"}
        missing = {
            target: frames[source]
            for source, target in mapping.items()
            if source in frames.columns and (data.market.empty or target not in data.market.columns)
        }
        if missing:
            addition = pd.DataFrame(missing).dropna(how="all")
            addition.index = pd.to_datetime(addition.index)
            data.market = addition if data.market.empty else data.market.join(addition, how="outer")
            data.notes.append("主题商品端点不可达，使用系统行情库沪铜/LME铜/美元/人民币；HKDCNH 缺失。")


def _build_panel(data: LuoyangData) -> pd.DataFrame:
    if data.price.empty:
        return pd.DataFrame()
    panel = data.price.copy()
    rename = {
        "total_market_cap": "total_market_cap",
        "total_shares": "total_shares",
    }
    if not data.valuation.empty:
        for column in ("total_market_cap", "total_shares", "pe_ttm", "pb_mrq", "ps_ttm", "close_price", "pe_lar"):
            if column in data.valuation.columns:
                panel[rename.get(column, column)] = data.valuation[column]
    if not data.benchmarks.empty:
        bench = data.benchmarks.rename(
            columns={"hs300": "hs300_close", "sse": "sse_close", "sector": "bk_nonferrous_close"}
        )
        for column in ("hs300_close", "sse_close", "bk_nonferrous_close"):
            if column in bench.columns:
                panel[column] = bench[column]
    if not data.market.empty:
        for column in ("shfe_cu", "lme_cu", "dxy", "usdcnh", "hkd_cny"):
            if column in data.market.columns:
                panel[column] = data.market[column]

    for column in ("high", "low", "close", "close_raw", "open", "volume", "amount", "total_market_cap"):
        if column in panel.columns:
            panel[column] = pd.to_numeric(panel[column], errors="coerce")
    if "close_raw" not in panel.columns:
        panel["close_raw"] = panel["close"]
    panel["close_raw"] = panel["close_raw"].fillna(panel["close"])

    panel["ret"] = panel["close"].pct_change()
    panel["ret_raw"] = panel["close_raw"].pct_change()
    for column, name in (
        ("hs300_close", "hs300_ret"),
        ("bk_nonferrous_close", "bk_ret"),
        ("shfe_cu", "cu_ret"),
        ("lme_cu", "lme_ret"),
        ("dxy", "dxy_ret"),
        ("usdcnh", "fx_ret"),
    ):
        if column in panel.columns:
            panel[name] = panel[column].pct_change()
    if "hs300_ret" in panel.columns:
        panel["excess_ret"] = panel["ret"] - panel["hs300_ret"]
    if "amount" in panel.columns:
        panel["amount_yi"] = panel["amount"] / 1e8
    if "total_market_cap" in panel.columns:
        panel["mcap_yi"] = panel["total_market_cap"] / 1e8
    return panel


def _assess(data: LuoyangData) -> tuple[str, list[str]]:
    notes: list[str] = []
    if not data.has_price:
        return "blocked", ["洛阳钼业日线不足 30 根，无法计算行情与技术面。"]
    if data.valuation.empty:
        notes.append("估值序列缺失：PE/PB 分位与估值打分为空。")
    if data.financials.empty:
        notes.append("财务主要指标缺失：TTM 与 ROE 退化。")
    if data.statements.empty:
        notes.append("三表关键科目缺失：EV/EBITDA 与 DCF 场景退化。")
    if data.segments.empty:
        notes.append("分部数据缺失：铜价敏感性使用配置兜底系数。")
    if data.margin.empty:
        notes.append("两融数据缺失：杠杆因子省略。")
    if data.flows.empty:
        notes.append("主力资金流缺失（东财接口通常仅覆盖约 120 个交易日）。")
    if data.reports.empty:
        notes.append("研报一致预期缺失：情景使用配置兜底 EPS。")
    status = "ok" if len(notes) <= 2 else "degraded"
    return status, notes
