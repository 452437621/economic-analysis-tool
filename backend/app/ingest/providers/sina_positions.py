"""Sina futures member position ranking (DCE products: meal, palm, iron ore)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE = "https://vip.stock.finance.sina.com.cn/q/view/vFutures_Positions_cjcc.php"
PRODUCTS = {"M": "豆粕", "P": "棕榈油", "I": "铁矿石"}
OPTION = re.compile(r"<option value='([A-Z]+)(\d{4})'", re.I)


def choose_contract(options: list[str], today: date, min_days: int = 45) -> str | None:
    best = None
    best_expiry = None
    fallback = None
    for code in options:
        match = re.match(r"^([A-Z]+)(\d{4})$", code.upper())
        if not match:
            continue
        year = 2000 + int(match.group(2)[:2])
        month = int(match.group(2)[2:])
        if not 1 <= month <= 12:
            continue
        expiry = date(year, month, 15)
        fallback = expiry
        if (expiry - today).days >= min_days and (best_expiry is None or expiry < best_expiry):
            best, best_expiry = code.upper(), expiry
    if best:
        return best
    return None


def parse_tables(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    long_sum = short_sum = 0
    long_chg = short_chg = 0
    members: list[dict] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [cell.get_text(strip=True) for cell in rows[0].find_all(["th", "td"])]
        if len(header) != 4 or header[0] != "名次":
            continue  # 跳过导航/汇总大表，只取标准 4 列排名表
        if header[2] not in ("多单持仓", "空单持仓"):
            continue
        is_long = header[2] == "多单持仓"
        for row in rows[1:]:
            cells = [cell.get_text(strip=True) for cell in row.find_all("td")]
            if len(cells) < 4 or cells[0] == "合计":
                continue
            try:
                rank = int(cells[0])
                value = int(cells[2].replace(",", ""))
                change = int(cells[3].replace(",", ""))
            except ValueError:
                continue
            if is_long:
                long_sum += value
                long_chg += change
            else:
                short_sum += value
                short_chg += change
            members.append(
                {
                    "side": "long" if is_long else "short",
                    "rank": rank,
                    "member": cells[1],
                    "position": value,
                    "change": change,
                }
            )
    return {
        "long_pos": long_sum,
        "short_pos": short_sum,
        "long_chg": long_chg,
        "short_chg": short_chg,
        "members": members,
    }


def _parse_date(html: str) -> date | None:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", html)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def _last_weekday(today: date) -> date:
    candidate = today
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def fetch_latest(client: HttpClient, today: date | None = None) -> tuple[date | None, list[dict]]:
    today = today or date.today()
    base = client.get(BASE, params={"t_breed": "m0"})
    base.raise_for_status()
    base_html = base.content.decode("gb18030", errors="replace")
    options: dict[str, list[str]] = {}
    for product, contract in OPTION.findall(base_html):
        options.setdefault(product.upper(), []).append(f"{product.upper()}{contract}")

    report_date = _last_weekday(today)
    rows: list[dict] = []
    for product, name in PRODUCTS.items():
        contract = choose_contract(options.get(product, []), today)
        if not contract:
            continue
        try:
            resp = client.get(BASE, params={"t_breed": contract.lower()})
            resp.raise_for_status()
        except Exception:  # noqa: BLE001
            continue
        html = resp.content.decode("gb18030", errors="replace")
        parsed = parse_tables(html)
        total = parsed["long_pos"] + parsed["short_pos"]
        if total == 0:
            continue
        parsed.update(
            {
                "product": product.lower(),
                "name": name,
                "contract": contract,
                "net_pos": parsed["long_pos"] - parsed["short_pos"],
                "net_ratio": round((parsed["long_pos"] - parsed["short_pos"]) / total, 4),
            }
        )
        rows.append(parsed)
        page_date = _parse_date(html)
        if page_date and page_date > report_date - timedelta(days=30):
            report_date = page_date
    return report_date if rows else None, rows
