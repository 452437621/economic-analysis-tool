"""World Bank Open Data (keyless) annual indicators.

端点：``https://api.worldbank.org/v2/country/<ISO3>/indicator/<INDICATOR>?format=json&per_page=100``
返回 ``[meta, rows]``，rows 每项 ``{"date": "2024", "value": 123.4 | null, ...}``。
这里过滤 null 后返回 ``{year: value}``，供宏观序列兜底（IMF 不可用时）。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.ingest.providers.errors import ProviderError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.worldbank.org/v2"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _get_json(url: str, *, timeout: float = 45.0):
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProviderError(f"worldbank: {url} -> {exc}") from exc
    return payload


def fetch(
    indicator: str,
    country: str,
    per_page: int = 100,
    timeout: float = 45.0,
) -> dict[str, float]:
    """Return ``{year: value}`` for one indicator/country, dropping null values."""
    code = str(indicator or "").strip()
    area = str(country or "").strip().upper()
    if not code or not area:
        raise ProviderError("worldbank: indicator and country are required")
    size = max(1, min(int(per_page), 1000))
    url = f"{BASE_URL}/country/{area}/indicator/{code}?format=json&per_page={size}"
    payload = _get_json(url, timeout=timeout)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        # 指标不存在时 World Bank 返回 [{message: [...]}]，没有第二段 rows。
        raise ProviderError(f"worldbank: unexpected payload for {code}/{area}")

    result: dict[str, float] = {}
    for row in payload[1]:
        if not isinstance(row, dict):
            continue
        year = row.get("date")
        value = row.get("value")
        if year is None or value is None:
            continue
        try:
            result[str(year)] = float(value)
        except (TypeError, ValueError):
            continue
    logger.info("worldbank %s/%s: %s obs", code, area, len(result))
    return result
