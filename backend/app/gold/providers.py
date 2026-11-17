"""Gold monitoring data providers.

Live sources (verified reachable from this workspace):
    - LBMA monthly London vault holdings (XLSX)
    - World Gold Council global gold ETF holdings (JSON chart API)
    - World Gold Council Central Banks Dashboard: quarterly gold reserves by
      country, summed into a global total (same IMF IFS basis as gold.org)
    - CFTC disaggregated Commitments of Traders, COMEX gold (annual ZIP/TXT)
    - CFTC Bank Participation Report, monthly CMX gold bank long/short
    - COMEX warehouse inventories (free weekly CSV mirrored by metalcharts.org,
      because cmegroup.com itself is unreachable from this network)
    - Eastmoney China official gold reserves (JSON data-center API)
Derived sources:
    - Shanghai gold premium, COMEX basis / carry, real yield, DXY, 20d momentum

Not available publicly / blocked from this network (kept as manual indicators):
    - BIS gold swap / storage balances (BIS publishes no machine-readable series),
      SGE exchange inventory, individual bank (JPM/HSBC) gold books.
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
#: 派生序列回填天数（对上/金价/美元等日线），支撑黄金研判图表的 1 年～全部时间范围
DERIVED_HISTORY_BARS = 2000


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


def _wgc_etf_totals(payload: dict, freq: str) -> list[tuple]:
    """[("as_of", total_tonnes, regions)] from the WGC ETF holdings payload."""
    node = ((payload.get("chartData") or {}).get("data") or {}).get(freq) or {}
    totals: list[tuple] = []
    for row in (node.get("tonnes") or {}).get("set") or []:
        if not row or len(row) < 5:
            continue
        regions = [value for value in row[1:5] if isinstance(value, (int, float))]
        if not regions:
            continue
        as_of = _utc(datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc).date())
        totals.append((as_of, float(sum(regions)), row[1:5]))
    return totals


def fetch_wgc_etf() -> ProviderResult:
    """Global gold ETF holdings (weekly tonnes) + monthly flow."""
    name = "wgc_etf"
    try:
        with HttpClient(timeout=60) as client:
            resp = client.get(WGC_ETF_HOLDINGS)
        if resp.status_code != 200:
            raise RuntimeError(f"WGC ETF HTTP {resp.status_code}")
        payload = resp.json()
        # 持仓总量取周度序列（上游每周四更新，滞后 3~10 天）；
        # 早先误取 Monthly，导致该指标永远比上游慢一个月。
        weekly = _wgc_etf_totals(payload, "Weekly")
        totals = weekly or _wgc_etf_totals(payload, "Monthly")
        records: list[dict] = []
        for as_of, total, regions in totals:
            records.append(
                _record("ETF_GLOBAL_TONNES", as_of, total, "wgc", **{"regions": regions})
            )
        # 1 个月净流量仍是月度口径（月度末值同比上一个月）
        monthly = _wgc_etf_totals(payload, "Monthly")
        if len(monthly) >= 2:
            last_as_of, last, _ = monthly[-1]
            _, previous, _ = monthly[-2]
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


# ---------------------------------------------------------------- WGC central banks


WGC_CBD_PAGE = "https://fsapi.gold.org/api/cbd/v11/charts/getPage"


def _cbd_quarter_totals(series: list[dict]) -> list[tuple[datetime, float, int]]:
    """Sum reported tonnes by quarter and drop partial trailing quarters.

    The IMF/WGC dashboard publishes country by country, so the newest quarter
    usually has only a handful of reporters.  Summing it raw would show a fake
    collapse in global reserves, hence the completeness guard.
    """
    totals: dict[datetime, tuple[float, int]] = {}
    for country in series:
        for stamp, value in country.get("data") or []:
            if value is None:
                continue
            try:
                as_of = _utc(datetime.fromtimestamp(float(stamp) / 1000, tz=timezone.utc))
            except (TypeError, ValueError, OverflowError):
                continue
            total, count = totals.get(as_of, (0.0, 0))
            totals[as_of] = (total + float(value), count + 1)
    points = [(as_of, total, count) for as_of, (total, count) in sorted(totals.items())]
    while len(points) >= 2 and points[-1][2] < 0.85 * points[-2][2]:
        points.pop()
    return points


def fetch_wgc_central_banks() -> ProviderResult:
    """Global central-bank gold reserves (quarterly, tonnes), summed over countries."""
    name = "wgc_cbd"
    try:
        now = datetime.now(timezone.utc)
        params = {
            "page": "date_range",
            "periodicity": "QTD_FULL",
            "startDate": f"{now.year - 8}-01-01",
            "endDate": now.date().isoformat(),
        }
        with HttpClient(timeout=90) as client:
            resp = client.get(WGC_CBD_PAGE, params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"WGC CBD HTTP {resp.status_code}")
        payload = resp.json()
        series = payload["chartData"]["linechart"]["QTD_FULL"]["gold_reserves_tns"]["data"]
        points = _cbd_quarter_totals(series)
        if not points:
            raise RuntimeError("WGC CBD returned no gold reserve rows")
        records = [
            _record("CB_GOLD_GLOBAL_TONNES", as_of, total, "wgc_cbd", **{"countries": count})
            for as_of, total, count in points
        ]
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider wgc_cbd failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- CFTC bank participation


CFTC_BPR = "https://www.cftc.gov/MarketReports/BankParticipation/dea{mon}{yy}f"
BPR_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
BPR_LOOKBACK_MONTHS = 30


def _bpr_numbers(cells: list[str]) -> list[float]:
    values: list[float] = []
    for cell in cells:
        cleaned = cell.replace(",", "").replace("%", "").strip()
        if not cleaned:
            continue
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values


def _parse_bpr_gold(html: str) -> tuple[date, int, float, float] | None:
    """Return (report date, bank count, bank long, bank short) for CMX GOLD."""
    date_match = re.search(r"REPORT DATE:\s*(\d{1,2})/(\d{1,2})/(\d{4})", html)
    if not date_match:
        return None
    as_of = date(int(date_match.group(3)), int(date_match.group(1)), int(date_match.group(2)))
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", html, re.S | re.I)
    cells_by_row: list[list[str]] = []
    for row in rows:
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)
        cleaned = [re.sub(r"<[^>]+>", " ", cell).replace("\xa0", " ").strip() for cell in cells]
        cells_by_row.append(cleaned)
    for index, cells in enumerate(cells_by_row):
        label = next((cell.upper() for cell in cells if cell.upper() == "CMX GOLD"), None)
        if label is None:
            continue
        try:
            us_row = cells_by_row[index]
            us_start = next(i for i, cell in enumerate(us_row) if cell.upper() == "U.S.")
            us_numbers = _bpr_numbers(us_row[us_start + 1:])
            non_us_numbers = _bpr_numbers(cells_by_row[index + 1])
            total_numbers = _bpr_numbers(cells_by_row[index + 2])
        except (IndexError, StopIteration):
            continue
        if len(total_numbers) < 4:
            continue
        # 汇总行：银行数、多头、多头占比、空头、空头占比
        bank_count = int(total_numbers[0])
        bank_long = float(total_numbers[1])
        bank_short = float(total_numbers[3])
        if not us_numbers or not non_us_numbers:
            continue
        return as_of, bank_count, bank_long, bank_short
    return None


def _bpr_periods(months: int = BPR_LOOKBACK_MONTHS) -> list[tuple[int, int]]:
    today = datetime.now(timezone.utc).date()
    year, month = today.year, today.month
    periods: list[tuple[int, int]] = []
    for _ in range(months):
        periods.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return periods


def fetch_cftc_bank_participation() -> ProviderResult:
    """Monthly CMX gold bank participation: aggregate bank long/short contracts."""
    name = "cftc_bpr"
    records: list[dict] = []
    errors: list[str] = []
    try:
        with HttpClient(timeout=60, min_interval=0.8) as client:
            for year, month in _bpr_periods():
                url = CFTC_BPR.format(mon=BPR_MONTHS[month - 1], yy=f"{year % 100:02d}")
                try:
                    resp = client.get(url)
                except Exception as exc:  # noqa: BLE001 - keep walking older months
                    errors.append(f"{year}-{month:02d}: {exc}")
                    continue
                if resp.status_code == 404:
                    continue
                if resp.status_code != 200:
                    errors.append(f"{year}-{month:02d}: HTTP {resp.status_code}")
                    continue
                parsed = _parse_bpr_gold(resp.text)
                if parsed is None:
                    errors.append(f"{year}-{month:02d}: CMX GOLD row not found")
                    continue
                as_of, bank_count, bank_long, bank_short = parsed
                records.append(
                    _record(
                        "MM_BANK_GOLD_NET",
                        as_of,
                        bank_long - bank_short,
                        "cftc_bpr",
                        **{"banks": bank_count, "long": bank_long, "short": bank_short},
                    )
                )
        if not records:
            raise RuntimeError("; ".join(errors) or "no CMX gold bank participation rows")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider cftc_bpr failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- COMEX inventory


COMEX_INVENTORY_CSV = "https://metalcharts.org/data/comex-gold-silver-registered-eligible-weekly.csv"
OZ_TO_TONNE = 31.1034768 / 1_000_000


def fetch_comex_inventory() -> ProviderResult:
    """COMEX gold warehouse stocks (weekly): registered + eligible, tonnes.

    cmegroup.com is unreachable from this network, so we read the free CME
    warehouse-stock mirror that metalcharts.org publishes as a weekly CSV.
    """
    name = "metalcharts"
    try:
        with HttpClient(timeout=60) as client:
            resp = client.get(COMEX_INVENTORY_CSV)
        if resp.status_code != 200:
            raise RuntimeError(f"metalcharts COMEX CSV HTTP {resp.status_code}")
        reader = csv.DictReader(io.StringIO(resp.text))
        records: list[dict] = []
        for row in reader:
            if str(row.get("metal") or "").strip().lower() != "gold":
                continue
            try:
                as_of = _utc(date.fromisoformat(str(row["report_date"]).strip()))
                total_oz = float(row["total_oz"])
            except (KeyError, TypeError, ValueError):
                continue
            records.append(
                _record(
                    "COMEX_GOLD_INVENTORY_TONNES",
                    as_of,
                    total_oz * OZ_TO_TONNE,
                    "metalcharts",
                    **{
                        "registered_oz": float(row.get("registered_oz") or 0) or None,
                        "eligible_oz": float(row.get("eligible_oz") or 0) or None,
                    },
                )
            )
        if not records:
            raise RuntimeError("metalcharts COMEX CSV returned no gold rows")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider metalcharts failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- SGE gold lease


SGE_LEASE_EXPORT = "https://www.sge.com.cn/rent/download/export"
SGE_LEASE_TENOR = "3M"


def _parse_sge_lease_xls(payload: bytes, tenor: str) -> list[tuple[date, float]]:
    """Read SGE's all-string .xls lease-rate export (日期 / O/N / 1M / 3M ... / 3Y)."""
    import xlrd

    book = xlrd.open_workbook(file_contents=payload)
    sheet = book.sheet_by_index(0)
    header = [str(sheet.cell_value(0, column)).strip() for column in range(sheet.ncols)]
    if tenor not in header:
        raise RuntimeError(f"SGE lease XLS missing {tenor} column: {header}")
    column = header.index(tenor)
    points: list[tuple[date, float]] = []
    for row in range(1, sheet.nrows):
        raw_date = str(sheet.cell_value(row, 0)).strip()
        raw_value = str(sheet.cell_value(row, column)).strip()
        if not raw_date or not raw_value:
            continue
        try:
            points.append((date.fromisoformat(raw_date[:10]), float(raw_value)))
        except ValueError:
            continue
    return points


def fetch_sge_gold_lease() -> ProviderResult:
    """SGE gold lease benchmark rate (daily, 3M tenor, %).

    The BIS publishes no machine-readable gold lease series, so the Shanghai
    Gold Exchange's official lease benchmark rate is used as the lease-stress
    proxy (CNY market, same direction as the USD gold lease rate).
    """
    name = "sge_lease"
    try:
        with HttpClient(timeout=90) as client:
            resp = client.get(
                SGE_LEASE_EXPORT,
                headers={"Referer": "https://www.sge.com.cn/sjzx/zjjzll"},
            )
        if resp.status_code != 200:
            raise RuntimeError(f"SGE lease export HTTP {resp.status_code}")
        if not resp.content.startswith(b"\xd0\xcf\x11\xe0"):
            raise RuntimeError("SGE lease export is not an OLE2 XLS workbook")
        points = _parse_sge_lease_xls(resp.content, SGE_LEASE_TENOR)
        if not points:
            raise RuntimeError("SGE lease XLS contained no rows")
        records = [
            _record("SGE_GOLD_LEASE_3M_PCT", _utc(day), value, "sge", **{"tenor": SGE_LEASE_TENOR})
            for day, value in points
        ]
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider sge_lease failed: %s", exc)
        return ProviderResult(name, False, error=str(exc))


# ---------------------------------------------------------------- SHFE gold stock


SHFE_STOCK_LIST = "https://www.shfe.com.cn/data/tradedata/future/dailydata/stock_data_list.dat"
SHFE_STOCK_HTML = "https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_{day}/ZH/all.html"
SHFE_HISTORY_DAYS = 30


def _parse_shfe_gold_stock(html: str) -> float | None:
    """Gold warrant stock in kilograms from the SHFE daily warehouse-stock page."""
    for table in re.findall(r"<table\b.*?</table>", html, re.S | re.I):
        if "黄金" not in table:
            continue
        total = 0.0
        found = False
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S | re.I):
            cells = [
                re.sub(r"<[^>]+>", " ", cell).replace("\xa0", " ").strip()
                for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)
            ]
            if not any("金库" in cell for cell in cells):
                continue
            # 列：仓库 / 期货（千克）/ 增减 —— 取倒数第二列，避免把「增减」算进库存
            for cell in reversed(cells[:-1]):
                cleaned = cell.replace(",", "").strip()
                if re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
                    total += float(cleaned)
                    found = True
                    break
        if found:
            return total
    return None


def fetch_shfe_gold_stock() -> ProviderResult:
    """China gold vault proxy: SHFE designated-depository gold warrant stock (kg).

    The Shanghai Gold Exchange does not publish exchange inventory, so the
    SHFE gold warrant daily stock is used as the mainland physical-stock proxy.
    """
    name = "shfe_stock"
    try:
        records: list[dict] = []
        errors: list[str] = []
        with HttpClient(timeout=60, min_interval=0.4) as client:
            listing = client.get(SHFE_STOCK_LIST)
            if listing.status_code != 200:
                raise RuntimeError(f"SHFE stock list HTTP {listing.status_code}")
            payload = listing.json()
            days = payload.get("dataList")
            if isinstance(days, str):
                days = json.loads(days)
            days = [str(int(day)) for day in (days or [])][-SHFE_HISTORY_DAYS:]
            for day in days:
                page = client.get(SHFE_STOCK_HTML.format(day=day))
                if page.status_code != 200:
                    errors.append(f"{day}: HTTP {page.status_code}")
                    continue
                kilograms = _parse_shfe_gold_stock(page.text)
                if kilograms is None:
                    errors.append(f"{day}: gold stock row not found")
                    continue
                try:
                    as_of = _utc(date(int(day[:4]), int(day[4:6]), int(day[6:8])))
                except ValueError:
                    continue
                records.append(
                    _record("SHFE_GOLD_STOCK_TONNES", as_of, kilograms / 1000.0, "shfe", **{"kg": kilograms})
                )
        if not records:
            raise RuntimeError("; ".join(errors) or "no SHFE gold stock rows")
        return ProviderResult(name, True, records)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gold provider shfe_stock failed: %s", exc)
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
                    .limit(DERIVED_HISTORY_BARS)
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
            for day in sorted(set(au_map) & set(xau_map) & set(fx_map))[-DERIVED_HISTORY_BARS:]:
                implied = xau_map[day] * fx_map[day] / 31.1034768
                if implied > 0:
                    records.append(_record("CN_GOLD_PREMIUM_PCT", _utc(day), (au_map[day] / implied - 1) * 100, "derived"))
            for day in sorted(set(gc_map) & set(xau_map))[-DERIVED_HISTORY_BARS:]:
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
                    .limit(DERIVED_HISTORY_BARS)
                ).all()
                for bar in reversed(bars):
                    if bar.close:
                        records.append(_record(code, bar.ts_utc, float(bar.close), "derived", **{"history": True}))
            if real_series is not None:
                observations = session.scalars(
                    select(MacroObs)
                    .where(MacroObs.series_id == real_series.id)
                    .order_by(MacroObs.ts_utc.desc())
                    .limit(DERIVED_HISTORY_BARS)
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
    ("wgc_cbd", fetch_wgc_central_banks),
    ("cftc", fetch_cftc_cot),
    ("cftc_bpr", fetch_cftc_bank_participation),
    ("sge_lease", fetch_sge_gold_lease),
    ("metalcharts", fetch_comex_inventory),
    ("shfe_stock", fetch_shfe_gold_stock),
    ("eastmoney", fetch_china_gold_reserves),
    ("derived", fetch_derived),
]
