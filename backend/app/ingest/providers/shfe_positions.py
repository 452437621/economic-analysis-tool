"""SHFE daily member position report (aggregate long/short by product)."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE = "https://www.shfe.com.cn/data/tradedata/future/dailydata/pm{date}.dat"
PRODUCTS = {
    "cu": "铜",
    "al": "铝",
    "zn": "锌",
    "ni": "镍",
    "au": "黄金",
    "ag": "白银",
    "pb": "铅",
    "sn": "锡",
}
CONTRACT = re.compile(r"^([a-z]+)(\d{3,4})$")


def _aggregate(rows: list[dict]) -> list[dict]:
    """Top-20 member long/short concentration for the dominant contract of each product."""
    contracts: dict[str, dict[str, list[dict]]] = {}
    for row in rows:
        instrument = str(row.get("INSTRUMENTID") or "").lower()
        if instrument.endswith("all"):
            continue
        match = CONTRACT.match(instrument)
        if not match:
            continue
        product = match.group(1)
        if product not in PRODUCTS:
            continue
        contracts.setdefault(product, {}).setdefault(instrument, []).append(row)

    result: list[dict] = []
    for product, by_contract in contracts.items():
        # 主力合约：以多空持仓量之和最大的合约近似
        dominant = max(
            by_contract,
            key=lambda name: max(
                int(row.get("CJ2") or 0) + int(row.get("CJ3") or 0)
                for row in by_contract[name]
            ),
        )
        ranked = [
            row
            for row in by_contract[dominant]
            if isinstance(row.get("RANK"), int) and 1 <= row["RANK"] <= 20
        ]
        if not ranked:
            continue
        long_pos = sum(int(row.get("CJ2") or 0) for row in ranked)
        short_pos = sum(int(row.get("CJ3") or 0) for row in ranked)
        total = long_pos + short_pos
        result.append(
            {
                "product": product,
                "name": PRODUCTS[product],
                "contract": dominant.upper(),
                "long_pos": long_pos,
                "short_pos": short_pos,
                "net_pos": long_pos - short_pos,
                "net_ratio": round((long_pos - short_pos) / total, 4) if total else None,
                "long_chg": sum(int(row.get("CJ2_CHG") or 0) for row in ranked),
                "short_chg": sum(int(row.get("CJ3_CHG") or 0) for row in ranked),
            }
        )
    result.sort(key=lambda item: item["net_ratio"] if item["net_ratio"] is not None else 0, reverse=True)
    return result


def fetch_latest(client: HttpClient, today: date | None = None) -> tuple[date | None, list[dict]]:
    today = today or date.today()
    for offset in range(0, 8):
        target = today - timedelta(days=offset)
        if target.weekday() >= 5:
            continue
        url = BASE.format(date=target.strftime("%Y%m%d"))
        try:
            resp = client.get(url)
        except Exception:  # noqa: BLE001
            continue
        if resp.status_code != 200:
            continue
        try:
            payload = resp.json()
        except ValueError:
            continue
        rows = payload.get("o_cursor") or []
        if not rows:
            continue
        report_date = str(payload.get("report_date") or target.strftime("%Y%m%d"))
        parsed = date(int(report_date[:4]), int(report_date[4:6]), int(report_date[6:8]))
        return parsed, _aggregate(rows)
    return None, []
