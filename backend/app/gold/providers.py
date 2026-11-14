"""Gold monitoring data providers.

Live sources (verified reachable from this workspace):
    - LBMA monthly London vault holdings (XLSX)
    - World Gold Council global gold ETF holdings (JSON chart API)
    - CFTC disaggregated Commitments of Traders, COMEX gold (annual ZIP/TXT)
    - Eastmoney China official gold reserves (JSON data-center API)
Derived sources:
    - Shanghai gold premium, COMEX basis / carry, real yield, DXY, 20d momentum

Not available publicly / blocked from this network (kept as manual indicators):
    - BIS gold lease / swap / storage, COMEX inventory, SGE inventory, global
      central-bank purchases, individual bank (JPM/HSBC) gold books.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone

import openpyxl
from sqlalchemy import select

from app.ingest.http import HttpClient
from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar, Quote
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

KOZ_TO_TONNE = 31.1034768 / 1_000  # 1,000 troy oz = 0.0311034768 t


def _utc(day: date | datetime) -> datetime:
    if isinstance(day, datetime):
        return day if day.tzinfo else day.replace(tzinfo=timezone.utc)
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def _record(code: str, as_of: datetime, value: float, source: str, **extra) -> dict:
    return {"code": code, "as_of": _utc(as_of), "value": float(value), "source": source, "extra": extra or None}


@dataclass
class ProviderResult:
    name: str
    ok: bool
    records: list[dict] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------- LBMA


def fetch_lbma_vault() -> ProviderResult:
    """London vault holdings, monthly (gold/silver in '000s troy oz)."""
    name = "lbma"
    try:
        with HttpClient(timeout=45, min_interval=1.0) as client:
            page = client.get("https://www.lbma.org.uk/prices-and-data/london-vault-data")
            if page.status_code != 200:
                raise RuntimeError(f"LBMA page HTTP {page.status_code}")
            match = re.search(
                r"https://cdn\.lbma\.org\.uk/downloads/LBMA-London-Vault-Holdings-Data-[A-Za-z]+-\d{4}\.xlsx",
                page.text,
            )
            if not match:
                raise RuntimeError("LBMA xlsx link not found")
            resp = client.get(match.group(0))
            if resp.status_code != 200:
                raise RuntimeError(f"LBMA xlsx HTTP {resp.status_code}")
        workbook = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
        sheet = workbook[workbook.sheetnames[0]]
        records: list[dict] = []
        for row in sheet.iter_rows(min_row=4, values_only=True):
            month, gold_koz, silver_koz = (row + (None, None, None))[:3]
            if not month or not isinstance(month, str):
                continue
            if not re.fullmatch(r"\d{4}-\d{2}", str(month).strip()):
                continue
            year, mon = (int(part) for part in str(month).strip().split("-"))
            as_of = _utc(date(year, mon, 1))
            if isinstance(gold_koz, (int, float)):
                records.append(_record("LBMA_GOLD_TONNES", as_of, gold_koz * KOZ_TO_TONNE, "lbma"))
            if isinstance(silver_koz, (int, float)):
                records.append(_record("LBMA_SILVER_TONNES", as_of, silver_koz * KOZ_TO_TONNE, "lbma"))
        workbook.close()
        if not records:
            raise RuntimeError("LBMA xlsx contained no rows")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001 - provider failures must not break the run
        logger.warning("gold provider lbma failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- WGC ETF


WGC_ETF_HOLDINGS = "https://fsapi.gold.org/api/v11/charts/etfv2/revised/holdings-chart2"


def fetch_wgc_etf() -> ProviderResult:
    """Global gold ETF holdings (monthly, tonnes) + monthly flow."""
    name = "wgc_etf"
    try:
        with HttpClient(timeout=60) as client:
            resp = client.get(WGC_ETF_HOLDINGS)
        if resp.status_code != 200:
            raise RuntimeError(f"WGC ETF HTTP {resp.status_code}")
        payload = resp.json()
        monthly = payload["chartData"]["data"]["Monthly"]["tonnes"]
        rows = monthly.get("set") or []
        records: list[dict] = []
        totals: list[tuple[datetime, float]] = []
        for row in rows:
            if not row or len(row) < 5:
                continue
            stamp = row[0]
            regions = [value for value in row[1:5] if isinstance(value, (int, float))]
            if not regions:
                continue
            total = float(sum(regions))
            as_of = _utc(datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).date())
            totals.append((as_of, total))
            records.append(_record("ETF_GLOBAL_TONNES", as_of, total, "wgc", **{"regions": row[1:5]}))
        if len(totals) >= 2:
            last_as_of, last = totals[-1]
            _, previous = totals[-2]
            records.append(_record("ETF_FLOW_1M_TONNES", last_as_of, last - previous, "wgc"))
        if not records:
            raise RuntimeError("WGC ETF returned no rows")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider wgc_etf failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- CFTC COT


CFTC_ZIP = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"


def _cftc_years() -> list[int]:
    current = datetime.now(timezone.utc).year
    return [current - 2, current - 1, current]


def fetch_cftc_cot() -> ProviderResult:
    """COMEX gold disaggregated COT (weekly): OI, swap dealer & managed money net."""
    name = "cftc"
    records: list[dict] = []
    errors: list[str] = []
    try:
        with HttpClient(timeout=180, min_interval=1.5) as client:
            for year in _cftc_years():
                resp = client.get(CFTC_ZIP.format(year=year))
                if resp.status_code != 200:
                    errors.append(f"{year}: HTTP {resp.status_code}")
                    continue
                try:
                    archive = zipfile.ZipFile(io.BytesIO(resp.content))
                    text = archive.read(archive.namelist()[0]).decode("utf-8", errors="replace")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{year}: {exc}")
                    continue
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    market = (row.get("Market_and_Exchange_Names") or "").upper()
                    # 仅取 COMEX 标准黄金合约，排除 MICRO GOLD 等子合约
                    if not market.startswith("GOLD - COMMODITY EXCHANGE"):
                        continue
                    try:
                        as_of = _utc(date.fromisoformat(row["Report_Date_as_YYYY-MM-DD"]))
                        oi = float(row["Open_Interest_All"])
                        swap_net = float(row["Swap_Positions_Long_All"]) - float(row["Swap__Positions_Short_All"])
                        money_net = float(row["M_Money_Positions_Long_All"]) - float(row["M_Money_Positions_Short_All"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    records.append(_record("COMEX_GOLD_OI", as_of, oi, "cftc"))
                    records.append(_record("COT_SWAP_NET", as_of, swap_net, "cftc"))
                    records.append(_record("COT_MONEY_NET", as_of, money_net, "cftc"))
        if not records:
            raise RuntimeError("; ".join(errors) or "no gold COT rows")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider cftc failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- China reserves


EASTMONEY_GOLD = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName=RPT_ECONOMY_GOLD_CURRENCY&columns=ALL&pageSize=48"
    "&sortColumns=REPORT_DATE&sortTypes=-1"
)


def fetch_china_gold_reserves() -> ProviderResult:
    """China official gold reserves (USD 100m) and forex reserves, monthly."""
    name = "eastmoney"
    try:
        with HttpClient(timeout=45) as client:
            resp = client.get(EASTMONEY_GOLD)
        if resp.status_code != 200:
            raise RuntimeError(f"Eastmoney HTTP {resp.status_code}")
        payload = resp.json()
        if not payload.get("success"):
            raise RuntimeError(f"Eastmoney error: {payload.get('message')}")
        records: list[dict] = []
        for row in (payload.get("result") or {}).get("data") or []:
            report_date = str(row.get("REPORT_DATE") or "")[:10]
            if not report_date:
                continue
            try:
                as_of = _utc(date.fromisoformat(report_date))
            except ValueError:
                continue
            gold = row.get("GOLD_RESERVES")
            if isinstance(gold, (int, float)):
                records.append(_record("CN_GOLD_RESERVES_USD", as_of, gold, "eastmoney", **{"time": row.get("TIME")}))
        if not records:
            raise RuntimeError("Eastmoney returned no gold reserve rows")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider eastmoney failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- derived


def fetch_derived() -> ProviderResult:
    """Market-implied gold indicators derived from locally stored quotes/bars/rates."""
    name = "derived"
    records: list[dict] = []
    try:
        with SessionLocal() as session:
            instruments = {
                row.symbol: row for row in session.scalars(select(Instrument)).all()
            }
            latest: dict[str, Quote] = {}
            for quote in session.scalars(select(Quote).order_by(Quote.ts_utc.desc()).limit(3000)).all():
                symbol = next((s for s, inst in instruments.items() if inst.id == quote.instrument_id), None)
                if symbol and symbol not in latest:
                    latest[symbol] = quote

            def price(symbol: str) -> float | None:
                quote = latest.get(symbol)
                return float(quote.price) if quote and quote.price else None

            au, xau, usdcnh, gc, dxy = price("AU"), price("XAUUSD"), price("USDCNH"), price("GC"), price("DXY")
            now = _utc(datetime.now(timezone.utc).date())
            if xau:
                records.append(_record("GOLD_PRICE_USD", now, xau, "derived", **{"proxy": "XAUUSD"}))
            if au and xau and usdcnh:
                implied = xau * usdcnh / 31.1034768
                if implied > 0:
                    premium = (au / implied - 1) * 100
                    records.append(_record("CN_GOLD_PREMIUM_PCT", now, premium, "derived"))
            basis_pct = None
            if gc and xau and xau > 0:
                basis_pct = (gc - xau) / xau * 100
                records.append(_record("COMEX_GOLD_BASIS_PCT", now, basis_pct, "derived"))
            if dxy:
                records.append(_record("DXY", now, dxy, "derived"))
            # 租赁利率代理：短端利率 - 年化期现基差（假设近月 90 天）
            real_series = session.scalar(select(MacroSeries).where(MacroSeries.code == "US10Y_REAL"))
            short_series = session.scalar(select(MacroSeries).where(MacroSeries.code == "US2Y"))
            real_value = _latest_macro(session, real_series.id) if real_series else None
            short_value = _latest_macro(session, short_series.id) if short_series else None
            if real_value is not None:
                records.append(_record("US10Y_REAL", now, real_value, "treasury"))
            if short_value is not None and basis_pct is not None:
                lease = -basis_pct * 365 / 90  # 贴水（负基差）→ 租赁紧张度上升
                records.append(_record("GOLD_LEASE_PROXY_PCT", now, lease, "derived", **{"basis_pct": basis_pct}))
            au_bar_count = 0
            if "AU" in instruments:
                closes = session.scalars(
                    select(MarketBar.close)
                    .where(MarketBar.instrument_id == instruments["AU"].id, MarketBar.timeframe == "1d")
                    .order_by(MarketBar.ts_utc.desc())
                    .limit(21)
                ).all()
                closes = [float(value) for value in reversed(closes) if value is not None]
                au_bar_count = len(closes)
                if len(closes) >= 21 and closes[0] > 0:
                    momentum = (closes[-1] / closes[0] - 1) * 100
                    records.append(_record("GOLD_MOM_20D_PCT", now, momentum, "derived"))
            # 溢价/基差历史：用日线收盘价回填（AU、XAUUSD、USDCNH、GC）
            bar_maps: dict[str, dict] = {}
            for symbol in ("AU", "XAUUSD", "USDCNH", "GC"):
                inst = instruments.get(symbol)
                if inst is None:
                    continue
                bars = session.scalars(
                    select(MarketBar)
                    .where(MarketBar.instrument_id == inst.id, MarketBar.timeframe == "1d")
                    .order_by(MarketBar.ts_utc.desc())
                    .limit(260)
                ).all()
                bar_maps[symbol] = {
                    _utc(bar.ts_utc).date(): float(bar.close)
                    for bar in bars
                    if bar.close is not None
                }
            au_map, xau_map, fx_map, gc_map = (
                bar_maps.get("AU", {}),
                bar_maps.get("XAUUSD", {}),
                bar_maps.get("USDCNH", {}),
                bar_maps.get("GC", {}),
            )
            for day in sorted(set(au_map) & set(xau_map) & set(fx_map))[-180:]:
                implied = xau_map[day] * fx_map[day] / 31.1034768
                if implied > 0:
                    records.append(_record("CN_GOLD_PREMIUM_PCT", _utc(day), (au_map[day] / implied - 1) * 100, "derived"))
            for day in sorted(set(gc_map) & set(xau_map))[-180:]:
                if xau_map[day] > 0:
                    records.append(_record("COMEX_GOLD_BASIS_PCT", _utc(day), (gc_map[day] - xau_map[day]) / xau_map[day] * 100, "derived"))
            # 历史序列回填（供图表与因子变化）
            for symbol, code in (("XAUUSD", "GOLD_PRICE_USD"), ("DXY", "DXY")):
                inst = instruments.get(symbol)
                if inst is None:
                    continue
                bars = session.scalars(
                    select(MarketBar)
                    .where(MarketBar.instrument_id == inst.id, MarketBar.timeframe == "1d")
                    .order_by(MarketBar.ts_utc.desc())
                    .limit(180)
                ).all()
                for bar in reversed(bars):
                    if bar.close:
                        records.append(_record(code, bar.ts_utc, float(bar.close), "derived", **{"history": True}))
            if real_series is not None:
                observations = session.scalars(
                    select(MacroObs)
                    .where(MacroObs.series_id == real_series.id)
                    .order_by(MacroObs.ts_utc.desc())
                    .limit(250)
                ).all()
                for observation in reversed(observations):
                    if observation.value is not None:
                        records.append(_record("US10Y_REAL", observation.ts_utc, float(observation.value), "treasury"))
            logger.info("gold derived: %s records (AU bars=%s)", len(records), au_bar_count)
        if not records:
            raise RuntimeError("no local market data for derived gold indicators")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider derived failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))



def _latest_macro(session, series_id: str) -> float | None:
    row = session.scalar(
        select(MacroObs)
        .where(MacroObs.series_id == series_id)
        .order_by(MacroObs.ts_utc.desc())
        .limit(1)
    )
    return float(row.value) if row and row.value is not None else None


PROVIDERS = [
    ("lbma", fetch_lbma_vault),
    ("wgc_etf", fetch_wgc_etf),
    ("cftc", fetch_cftc_cot),
    ("eastmoney", fetch_china_gold_reserves),
    ("derived", fetch_derived),
]
