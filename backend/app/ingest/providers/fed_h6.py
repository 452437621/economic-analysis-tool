"""Fed H.6 月频货币供应量（M1 / M2 / 货币基础），HTML 页面无免费 JSON。

表格结构：第 0 张表是「Seasonally adjusted」口径，行首是月份（``May 2025``、
``Aug. 2025``、``Sept. 2025``），接着三列即 M1、M2、Monetary base（十亿美元）。
历史通过归档索引页 ``/releases/h6/`` 的链接发现，按需回补。
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from datetime import date, datetime, time, timezone

from bs4 import BeautifulSoup

from app.ingest.contracts import MacroPoint
from app.ingest.providers.errors import ProviderError

logger = logging.getLogger(__name__)

CURRENT_URL = "https://www.federalreserve.gov/releases/h6/current/default.htm"
ARCHIVE_URL = "https://www.federalreserve.gov/releases/h6/{stamp}/default.htm"
INDEX_URL = "https://www.federalreserve.gov/releases/h6/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html",
}

# 季节调整口径三列（第 1~3 列）→ 序列 code。值单位十亿美元，乘 1e9 存美元。
COLUMNS: list[tuple[int, str]] = [(1, "US_M1"), (2, "US_M2"), (3, "US_MONETARY_BASE")]
UNIT_SCALE = 1_000_000_000.0

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
_MONTH_RE = re.compile(r"^([A-Za-z]{3})[a-z]*\.?\s+(\d{4})$")
_NUMBER_RE = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$")


def _get_html(url: str, *, timeout: float = 45.0) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"fed h6: {url} -> {exc}") from exc


def _to_float(text: str) -> float | None:
    token = (text or "").replace("\xa0", " ").strip()
    if not _NUMBER_RE.match(token):
        return None
    try:
        return float(token.replace(",", ""))
    except ValueError:  # pragma: no cover - 正则可保证可解析
        return None


def _parse_month(text: str) -> date | None:
    match = _MONTH_RE.match((text or "").replace("\xa0", " ").strip())
    if not match:
        return None
    month = _MONTHS.get(match.group(1)[:3].lower())
    if not month:
        return None
    return date(int(match.group(2)), month, 1)


def parse_page(html: str) -> dict[str, dict[date, float]]:
    """解析一页 H.6，返回 ``{code: {月份首日: usd_value}}``。"""
    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise ProviderError("fed h6: 页面没有表格")
    result: dict[str, dict[date, float]] = {code: {} for _, code in COLUMNS}
    for row in tables[0].find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) <= max(index for index, _ in COLUMNS):
            continue
        month = _parse_month(cells[0])
        if month is None:
            continue
        for index, code in COLUMNS:
            value = _to_float(cells[index])
            if value is not None:
                result[code][month] = round(value * UNIT_SCALE, 2)
    if not result["US_M2"]:
        raise ProviderError("fed h6: 未解析到 M2 行")
    return result


def _archive_dates(*, limit: int = 36, timeout: float = 45.0) -> list[str]:
    html = _get_html(INDEX_URL, timeout=timeout)
    stamps = sorted(set(re.findall(r"/releases/h6/(\d{8})/", html)))
    return stamps[-max(1, int(limit)) :]


def fetch_current(*, timeout: float = 45.0) -> dict[str, dict[date, float]]:
    payload = parse_page(_get_html(CURRENT_URL, timeout=timeout))
    logger.info("fed h6 current: M2=%s obs", len(payload.get("US_M2", {})))
    return payload


def fetch_history(*, months: int = 36, timeout: float = 45.0) -> dict[str, list[MacroPoint]]:
    """当前页 + 归档页合并出的月频序列（同月取归档页优先，因为已定稿）。"""
    merged: dict[str, dict[date, float]] = {code: {} for _, code in COLUMNS}
    pages: list[dict[str, dict[date, float]]] = []
    failures = 0
    for stamp in _archive_dates(limit=months, timeout=timeout):
        try:
            pages.append(parse_page(_get_html(ARCHIVE_URL.format(stamp=stamp), timeout=timeout)))
        except ProviderError as exc:
            failures += 1
            logger.warning("fed h6 archive %s failed: %s", stamp, exc)
    try:
        pages.append(fetch_current(timeout=timeout))
    except ProviderError as exc:  # pragma: no cover - 当前页不可达时仍用归档
        logger.warning("fed h6 current failed: %s", exc)
    for page in pages:
        for code, obs in page.items():
            merged.setdefault(code, {}).update(obs)

    series: dict[str, list[MacroPoint]] = {}
    for code, obs in merged.items():
        series[code] = [
            MacroPoint(
                code=code,
                ts=datetime.combine(month, time.min, tzinfo=timezone.utc),
                value=value,
            )
            for month, value in sorted(obs.items())
        ]
    logger.info("fed h6 history: %s pages, %s failures", len(pages), failures)
    if not series.get("US_M2"):
        raise ProviderError("fed h6: 历史 M2 为空")
    return series
