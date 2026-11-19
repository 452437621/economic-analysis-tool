"""Fed H.4.1 周频资产负债表（HTML 页面，无免费 JSON 接口）。

页面把「资产、负债与资本合并报表」拆成资产表和负债表，另有一张「吸收准备金的
因素」汇总表，``Reserve balances with Federal Reserve Banks`` 只出现在汇总表里。
因此解析时先扫合并报表，再用整页扫描补齐缺失标签。

单位：页面是百万美元，这里统一乘 ``1e6`` 换成美元，与 ``US_FED_DEBT`` 同口径。
数据日从表头 ``Wednesday Nov 4, 2026`` 解析（页面 URL 日期是发布日，数据是前一日）。
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta, timezone

from bs4 import BeautifulSoup

from app.ingest.contracts import MacroPoint
from app.ingest.providers.errors import ProviderError

logger = logging.getLogger(__name__)

CURRENT_URL = "https://www.federalreserve.gov/releases/h41/current/h41.htm"
ARCHIVE_URL = "https://www.federalreserve.gov/releases/h41/{stamp}/h41.htm"
INDEX_URL = "https://www.federalreserve.gov/releases/h41/"

# 页面标签 → 序列 code。标签比较前会去掉尾部脚注编号与多余空白。
LABELS: dict[str, str] = {
    "Total assets": "US_FED_ASSETS",
    "U.S. Treasury securities": "US_FED_TREASURY",
    "Mortgage-backed securities": "US_FED_MBS",
    "Reserve balances with Federal Reserve Banks": "US_FED_RESERVES",
    "U.S. Treasury, General Account": "US_TGA",
    "Currency in circulation": "US_CURRENCY",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html",
}

UNIT_SCALE = 1_000_000.0
CONSOLIDATED_MARKER = "Assets, liabilities, and capital"

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_DATE_RE = re.compile(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})")
_NUMBER_RE = re.compile(r"^-?\d{1,3}(?:,\d{3})*$")
_FOOTNOTE_RE = re.compile(r"(?:\s+\d+)+$")


def _get_html(url: str, *, timeout: float = 45.0) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"fed h41: {url} -> {exc}") from exc


def _label_key(text: str) -> str:
    """去掉脚注编号（``Mortgage-backed securities 4``）并压缩空白。"""
    cleaned = _FOOTNOTE_RE.sub("", (text or "").replace("\xa0", " ")).strip()
    return re.sub(r"\s+", " ", cleaned)


def _to_number(text: str) -> float | None:
    token = (text or "").replace("\xa0", " ").strip()
    if not _NUMBER_RE.match(token):
        return None
    try:
        return float(token.replace(",", ""))
    except ValueError:  # pragma: no cover - 正则可保证可解析
        return None


def _row_values(row) -> tuple[str, float | None]:
    cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
    if not cells:
        return "", None
    label = _label_key(cells[0])
    for cell in cells[1:]:
        value = _to_number(cell)
        if value is not None:
            return label, value
    return label, None


def _parse_date(text: str) -> date | None:
    match = _DATE_RE.search(text or "")
    if not match:
        return None
    month = _MONTHS.get(match.group(1)[:3].lower())
    if not month:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(2)))
    except ValueError:
        return None


def parse_page(html: str) -> dict:
    """解析一页 H.4.1，返回 ``{"asof": date, "values": {code: usd_value}}``。"""
    soup = BeautifulSoup(html or "", "html.parser")
    consolidated: dict[str, float] = {}
    anywhere: dict[str, float] = {}
    asof: date | None = None

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        head = rows[0].get_text(" ", strip=True)
        is_consolidated = CONSOLIDATED_MARKER in head
        if is_consolidated and asof is None:
            asof = _parse_date(head)
        for row in rows:
            label, value = _row_values(row)
            if label is None or value is None:
                continue
            target = LABELS.get(label)
            if target is None:
                continue
            anywhere.setdefault(target, value)
            if is_consolidated:
                consolidated.setdefault(target, value)

    values: dict[str, float] = {}
    for code in LABELS.values():
        raw = consolidated.get(code, anywhere.get(code))
        if raw is not None:
            values[code] = round(raw * UNIT_SCALE, 2)
    if asof is None:
        raise ProviderError("fed h41: 表头未找到数据日期")
    return {"asof": asof, "values": values}


def _archive_dates(
    *, limit: int = 156, today: date | None = None, timeout: float = 45.0
) -> list[str]:
    """生成最近 ``limit`` 个归档发布日（H.4.1 每周四发布，yyyyMMdd，正序）。

    发布页索引是前端渲染的，静态 HTML 里没有归档链接，所以直接按周四推日期；
    个别周因假日提前/推迟发布时，取不到的那周由 ``fetch_history`` 跳过。
    """
    end = today or date.today()
    thursday = end - timedelta(days=(end.weekday() - 3) % 7)
    stamps: list[str] = []
    for index in range(max(1, int(limit))):
        stamps.append((thursday - timedelta(weeks=index)).strftime("%Y%m%d"))
    return sorted(stamps)


def fetch_current(*, timeout: float = 45.0) -> dict:
    """当前周快照：``{"asof": date, "values": {code: usd}}``。"""
    payload = parse_page(_get_html(CURRENT_URL, timeout=timeout))
    logger.info("fed h41 current %s: %s series", payload["asof"], len(payload["values"]))
    return payload


def fetch_history(*, weeks: int = 156, timeout: float = 45.0) -> dict[str, list[MacroPoint]]:
    """最近 ``weeks`` 周的历史序列，返回 ``{code: [MacroPoint]}``。

    每次运行只抓当前页 + 归档索引里缺失的周（调用方按需决定 ``weeks``），
    单个归档失败只跳过，不让整批失败。
    """
    series: dict[str, list[MacroPoint]] = {code: [] for code in LABELS.values()}
    stamps = _archive_dates(limit=weeks, timeout=timeout)
    failures = 0
    for stamp in stamps:
        try:
            payload = parse_page(_get_html(ARCHIVE_URL.format(stamp=stamp), timeout=timeout))
        except ProviderError as exc:
            failures += 1
            logger.warning("fed h41 archive %s failed: %s", stamp, exc)
            continue
        ts = datetime.combine(payload["asof"], time.min, tzinfo=timezone.utc)
        for code, value in payload["values"].items():
            series.setdefault(code, []).append(MacroPoint(code=code, ts=ts, value=value))
    for points in series.values():
        points.sort(key=lambda point: point.ts)
    logger.info("fed h41 history: %s weeks, %s failures", len(stamps), failures)
    if stamps and failures == len(stamps):
        raise ProviderError("fed h41: 全部归档周抓取失败")
    return series


def _next_monday(day: date) -> date:  # pragma: no cover - 保留给补采脚本
    return day + timedelta(days=(7 - day.weekday()) % 7)
