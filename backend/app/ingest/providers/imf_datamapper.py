"""IMF DataMapper (World Economic Outlook) annual indicators, keyless.

端点形如 ``https://www.imf.org/external/datamapper/api/v1/<INDICATOR>/<ISO3>``，
返回 ``{"values": {"<INDICATOR>": {"USA": {"2024": 121.5, ...}, ...}}}``，含
WEO 预测年份（调用方按当前年份截断即可）。

注意：IMF 的 CDN 会按来源站点做校验，缺少 ``Referer``/``Origin`` 时直接 403，
因此这里固定带上浏览器头；本机网络不可达时由采集作业记录 degraded。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.ingest.providers.errors import ProviderError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.imf.org/external/datamapper/api/v1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.imf.org/",
    "Origin": "https://www.imf.org",
}


def _get_json(url: str, *, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProviderError(f"imf datamapper: {url} -> {exc}") from exc
    if not isinstance(payload, dict):
        raise ProviderError(f"imf datamapper: unexpected payload from {url}")
    return payload


def fetch(
    indicator: str,
    countries: list[str],
    *,
    timeout: float = 20.0,
) -> dict[str, dict[str, float]]:
    """Return ``{iso3: {year: value}}`` for one indicator across countries.

    ``countries`` 用 ISO3（USA/CHN）；返回键保留上游大小写（统一大写）。值为空
    或非数值的年份直接跳过，避免把 ``null`` 写成 0。
    """
    code = str(indicator or "").strip().upper()
    codes = [str(item).strip().upper() for item in countries or [] if str(item).strip()]
    if not code or not codes:
        raise ProviderError("imf datamapper: indicator and countries are required")
    url = f"{BASE_URL}/{code}/{','.join(codes)}"
    payload = _get_json(url, timeout=timeout)
    values = payload.get("values")
    if not isinstance(values, dict):
        raise ProviderError(f"imf datamapper: missing 'values' for {code}")
    per_country = values.get(code)
    if not isinstance(per_country, dict):
        raise ProviderError(f"imf datamapper: no series for {code}")

    result: dict[str, dict[str, float]] = {}
    for country_key, series in per_country.items():
        if not isinstance(series, dict):
            continue
        years: dict[str, float] = {}
        for year, value in series.items():
            try:
                years[str(year)] = float(value)
            except (TypeError, ValueError):
                continue
        if years:
            result[str(country_key).strip().upper()] = years
    if not result:
        raise ProviderError(f"imf datamapper: empty series for {code}/{','.join(codes)}")
    logger.info("imf datamapper %s: %s", code, {key: len(value) for key, value in result.items()})
    return result
