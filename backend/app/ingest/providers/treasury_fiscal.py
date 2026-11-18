"""US Treasury Fiscal Data API (keyless): Debt to the Penny and MTS tables.

- ``debt_to_penny``：每日联邦债务余额，字段 ``tot_pub_debt_out_amt`` 等金额为字符串。
- ``mts_table_*``：Monthly Treasury Statement；``mts_table_9`` 是收入/支出/利息的
  汇总表，用 ``line_code_nbr`` 区分同名行（120=Receipts Total、340=Outlays Total、
  320=Net Interest，金额在 ``current_month_rcpt_outly_amt``，空值是字符串 "null"）。

两个 ``fetch_*`` 都返回原始行 ``list[dict]``（保留 record_date 与金额字段），
解析/单位换算留给调用方，避免口径逻辑散落在 provider 里。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app.ingest.providers.errors import ProviderError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
DEBT_TO_PENNY_URL = f"{BASE_URL}/v2/accounting/od/debt_to_penny"
MTS_TABLE_URL = f"{BASE_URL}/v1/accounting/mts/mts_table_{{table}}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _get_rows(url: str, *, timeout: float = 30.0) -> list[dict]:
    """GET 一个 Fiscal Data 端点；网络/结构异常统一抛 ``ProviderError``。"""
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProviderError(f"treasury fiscal: {url} -> {exc}") from exc
    if not isinstance(payload, dict):
        raise ProviderError(f"treasury fiscal: unexpected payload from {url}")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise ProviderError(f"treasury fiscal: missing 'data' from {url}")
    return [row for row in rows if isinstance(row, dict) and row.get("record_date")]


def fetch_debt_to_penny(limit: int = 30, *, timeout: float = 30.0) -> list[dict]:
    """最近 ``limit`` 个交易日的联邦债务余额（按 record_date 倒序）。"""
    size = max(1, min(int(limit), 10000))
    url = f"{DEBT_TO_PENNY_URL}?sort=-record_date&page%5Bsize%5D={size}"
    rows = _get_rows(url, timeout=timeout)
    logger.info("treasury debt_to_penny: %s rows", len(rows))
    return rows


def fetch_mts(table: int = 9, page_size: int = 40, *, timeout: float = 30.0) -> list[dict]:
    """Monthly Treasury Statement 指定表的最近 ``page_size`` 行（按月份倒序）。"""
    number = int(table)
    if not 1 <= number <= 9:
        raise ProviderError(f"treasury fiscal: unsupported MTS table {number}")
    size = max(1, min(int(page_size), 5000))
    url = f"{MTS_TABLE_URL.format(table=number)}?sort=-record_date&page%5Bsize%5D={size}"
    rows = _get_rows(url, timeout=timeout)
    logger.info("treasury mts_table_%s: %s rows", number, len(rows))
    return rows
