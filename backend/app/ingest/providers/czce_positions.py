"""CZCE daily member position ranking (xlsx) for cotton and sugar."""

from __future__ import annotations

import io
import logging
import re
from datetime import date, timedelta

import openpyxl

from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE = "https://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/{ymd}/FutureDataHolding.xlsx"
TARGETS = {"CF": "棉花", "SR": "白糖"}


def _int(value) -> int:
    if value is None:
        return 0
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


def parse_rows(rows: list[tuple]) -> list[dict]:
    """Parse CZCE holding sheet rows into aggregate product positions."""
    result: list[dict] = []
    current: str | None = None
    index = 0
    while index < len(rows):
        row = rows[index]
        first = str(row[0]).strip() if row and row[0] is not None else ""
        if first.startswith("品种："):
            match = re.search(r"品种：(.+?)([A-Za-z]{1,3})", first)
            code = match.group(2).upper() if match else None
            current = code if code in TARGETS else None
            index += 1
            continue
        if first == "名次" and current:
            longs, shorts, long_chg, short_chg = [], [], [], []
            members: list[dict] = []
            cursor = index + 1
            while cursor < len(rows):
                data = rows[cursor]
                try:
                    rank = int(float(str(data[0]).strip()))
                except (TypeError, ValueError):
                    break
                if rank < 1 or rank > 20:
                    break
                if len(data) < 10:
                    cursor += 1
                    continue
                long_value, long_change = _int(data[5]), _int(data[6])
                short_value, short_change = _int(data[8]), _int(data[9])
                longs.append(long_value)
                long_chg.append(long_change)
                shorts.append(short_value)
                short_chg.append(short_change)
                members.append(
                    {
                        "side": "long",
                        "rank": rank,
                        "member": str(data[4]).strip(),
                        "position": long_value,
                        "change": long_change,
                    }
                )
                members.append(
                    {
                        "side": "short",
                        "rank": rank,
                        "member": str(data[7]).strip(),
                        "position": short_value,
                        "change": short_change,
                    }
                )
                cursor += 1
            if longs:
                total = sum(longs) + sum(shorts)
                result.append(
                    {
                        "product": current.lower(),
                        "name": TARGETS[current],
                        "long_pos": sum(longs),
                        "short_pos": sum(shorts),
                        "net_pos": sum(longs) - sum(shorts),
                        "net_ratio": round((sum(longs) - sum(shorts)) / total, 4) if total else None,
                        "long_chg": sum(long_chg),
                        "short_chg": sum(short_chg),
                        "members": members,
                    }
                )
            index = cursor
            continue
        index += 1
    return result


def fetch_latest(client: HttpClient, today: date | None = None) -> tuple[date | None, list[dict]]:
    today = today or date.today()
    for offset in range(0, 8):
        target = today - timedelta(days=offset)
        if target.weekday() >= 5:
            continue
        url = BASE.format(year=target.year, ymd=target.strftime("%Y%m%d"))
        try:
            resp = client.get(url)
        except Exception:  # noqa: BLE001
            continue
        if resp.status_code != 200 or not resp.content:
            continue
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
            sheet = workbook[workbook.sheetnames[0]]
            rows = list(sheet.iter_rows(values_only=True))
        except Exception:  # noqa: BLE001
            continue
        parsed = parse_rows(rows)
        if parsed:
            return target, parsed
    return None, []
