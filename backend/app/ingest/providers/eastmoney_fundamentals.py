"""Eastmoney fundamentals / valuation / flow providers for topic research.

These endpoints power the Luoyang Molybdenum topic.  They intentionally return
plain normalized rows (``{as_of, row_key, payload}``) so the collector and the
offline tests share one contract and the storage layer can upsert them without
knowing any vendor field names.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Iterable

from app.ingest.http import HttpClient

DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
FFLOW_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
ULIST_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
NOTICE_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
REPORT_URL = "https://reportapi.eastmoney.com/report/list"

REFERERS = {
    "quote": {"Referer": "https://quote.eastmoney.com/"},
    "data": {"Referer": "https://data.eastmoney.com/"},
    "report": {"Referer": "https://data.eastmoney.com/report/"},
}

SECIDS = {
    "a": "1.603993",
    "h": "116.03993",
    "hs300": "1.000300",
    "sse": "1.000001",
    "sector": "90.BK0478",
    "shfe_cu": "113.cum",
    "dxy": "100.UDI",
    "usdcnh": "133.USDCNH",
    "hkd_cnh": "133.HKDCNH",
}

KLINE_FIELDS = ("date", "open", "close", "high", "low", "volume", "amount", "amplitude", "pct_chg", "chg", "turnover")
FLOW_FIELDS = (
    "date",
    "main_net",
    "small_net",
    "medium_net",
    "large_net",
    "super_large_net",
    "main_pct",
    "small_pct",
    "medium_pct",
    "large_pct",
    "super_large_pct",
    "close",
    "pct_chg",
    "extra1",
    "extra2",
)


def _json(client: HttpClient, url: str, params: dict[str, Any], *, referer: str = "data") -> dict:
    response = client.get(url, params=params, headers=REFERERS[referer])
    response.raise_for_status()
    try:
        payload = response.json()
    except json.JSONDecodeError:
        text = response.text.strip()
        match = re.search(r"\((\{.*\})\)", text, flags=re.S)
        if not match:
            raise ValueError(f"unexpected response from {url}: {text[:120]}")
        payload = json.loads(match.group(1))
    return payload if isinstance(payload, dict) else {}


def _num(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(str(value)).date()
        except ValueError:
            return None


def _lower_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).lower(): value for key, value in row.items()}


def fetch_kline(
    client: HttpClient,
    secid: str,
    *,
    fqt: int = 1,
    beg: str = "20100101",
    end: str = "20991231",
    klt: int = 101,
) -> list[dict[str, Any]]:
    payload = _json(
        client,
        KLINE_URL,
        {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": str(klt),
            "fqt": str(fqt),
            "beg": beg,
            "end": end,
        },
        referer="quote",
    )
    klines = ((payload.get("data") or {}).get("klines")) or []
    rows: list[dict[str, Any]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 7:
            continue
        values = dict(zip(KLINE_FIELDS, parts))
        as_of = _date(values.get("date"))
        if as_of is None:
            continue
        rows.append(
            {
                "as_of": as_of,
                "row_key": "default",
                "payload": {
                    "open": _num(values.get("open")),
                    "close": _num(values.get("close")),
                    "high": _num(values.get("high")),
                    "low": _num(values.get("low")),
                    "volume": _num(values.get("volume")),
                    "amount": _num(values.get("amount")),
                    "amplitude": _num(values.get("amplitude")),
                    "pct_chg": _num(values.get("pct_chg")),
                    "chg": _num(values.get("chg")),
                    "turnover": _num(values.get("turnover")),
                },
            }
        )
    return rows


def merge_raw_close(adjusted: Iterable[dict[str, Any]], raw: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge unadjusted OHLC into the adjusted rows (position/cost口径)."""
    raw_by_date = {item["as_of"]: item["payload"] for item in raw}
    merged: list[dict[str, Any]] = []
    for item in adjusted:
        payload = dict(item["payload"])
        raw_payload = raw_by_date.get(item["as_of"]) or {}
        payload.update(
            {
                "close_raw": raw_payload.get("close"),
                "open_raw": raw_payload.get("open"),
                "high_raw": raw_payload.get("high"),
                "low_raw": raw_payload.get("low"),
            }
        )
        merged.append({"as_of": item["as_of"], "row_key": item["row_key"], "payload": payload})
    return merged


def fetch_datacenter(
    client: HttpClient,
    report_name: str,
    *,
    filter_: str | None = None,
    sort_columns: str = "REPORT_DATE",
    sort_types: str = "-1",
    page_size: int = 500,
    max_pages: int = 40,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params: dict[str, Any] = {
            "reportName": report_name,
            "columns": "ALL",
            "pageNumber": page,
            "pageSize": page_size,
            "source": "WEB",
            "client": "WEB",
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
        }
        if filter_:
            params["filter"] = filter_
        payload = _json(client, DATACENTER_URL, params, referer="data")
        result = payload.get("result") or {}
        data = result.get("data") or []
        rows.extend(data)
        if not data or page >= int(result.get("pages") or 1):
            break
    return rows


def normalize_valuation(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = _lower_keys(raw)
        as_of = _date(row.get("trade_date") or row.get("date"))
        if as_of is None:
            continue
        out.append(
            {
                "as_of": as_of,
                "row_key": "default",
                "payload": {
                    "close_price": _num(row.get("close_price")),
                    "total_market_cap": _num(row.get("total_market_cap")),
                    "total_shares": _num(row.get("total_shares")),
                    "pe_ttm": _num(row.get("pe_ttm")),
                    "pe_lar": _num(row.get("pe_lar")),
                    "pb_mrq": _num(row.get("pb_mrq")),
                    "ps_ttm": _num(row.get("ps_ttm")),
                    "pcf_ocf_ttm": _num(row.get("pcf_ocf_ttm")),
                    "peg_car": _num(row.get("peg_car")),
                },
            }
        )
    return out


FINANCIAL_FIELDS = (
    "report_type",
    "report_date_name",
    "notice_date",
    "epsjb",
    "bps",
    "totaloperatereve",
    "parentnetprofit",
    "kcfjcxsyjlr",
    "totaloperaterevetz",
    "parentnetprofittz",
    "kcfjcxsyjlrtz",
    "xsmll",
    "xsjll",
    "roejq",
    "roic",
    "zcfzl",
    "mgjyxjje",
    "total_assets_pk",
    "operate_income_pk",
    "operate_profit_pk",
    "netcash_operate_pk",
    "total_equity_pk",
    "total_share",
)


def normalize_financials(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = _lower_keys(raw)
        as_of = _date(row.get("report_date"))
        if as_of is None:
            continue
        payload = {key: (_num(row.get(key)) if key not in {"report_type", "report_date_name", "notice_date"} else row.get(key)) for key in FINANCIAL_FIELDS}
        out.append({"as_of": as_of, "row_key": "default", "payload": payload})
    return out


INCOME_MAP = {
    "operate_income": "operate_income",
    "total_operate_income": "total_operate_income",
    "operate_cost": "operate_cost",
    "operate_profit": "operate_profit",
    "total_profit": "total_profit",
    "netprofit": "netprofit",
    "parent_netprofit": "parent_netprofit",
    "finance_expense": "finance_expense",
}
CASHFLOW_MAP = {
    "fa_ir_depr": "fa_ir_depr",
    "ia_amortize": "ia_amortize",
    "lpe_amortize": "lpe_amortize",
    "construct_long_asset": "construct_long_asset",
    "netcash_operate": "netcash_operate",
    "assign_dividend_profit": "assign_dividend_profit",
}
BALANCE_MAP = {
    "monetaryfunds": "monetaryfunds",
    "short_loan": "short_loan",
    "long_loan": "long_loan",
    "bond_payable": "bond_payable",
    "lease_liab": "lease_liab",
    "noncurrent_liab_1year": "noncurrent_liab_1year",
    "minority_equity": "minority_equity",
    "total_assets": "total_assets",
    "liab_balance": "liab_balance",
    "equity_balance": "equity_balance",
}


def merge_statements(
    income: Iterable[dict[str, Any]],
    cashflow: Iterable[dict[str, Any]],
    balance: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[date, dict[str, Any]] = {}

    def _absorb(rows: Iterable[dict[str, Any]], mapping: dict[str, str]) -> None:
        for raw in rows:
            row = _lower_keys(raw)
            as_of = _date(row.get("report_date"))
            if as_of is None:
                continue
            target = merged.setdefault(as_of, {})
            target.setdefault("notice_date", row.get("notice_date"))
            for source, dest in mapping.items():
                target[dest] = _num(row.get(source))

    _absorb(income, INCOME_MAP)
    _absorb(cashflow, CASHFLOW_MAP)
    _absorb(balance, BALANCE_MAP)
    return [{"as_of": as_of, "row_key": "default", "payload": payload} for as_of, payload in sorted(merged.items())]


def normalize_segments(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = _lower_keys(raw)
        as_of = _date(row.get("report_date"))
        if as_of is None:
            continue
        item = str(row.get("item_name") or "")
        kind = str(row.get("mainop_type") or "")
        out.append(
            {
                "as_of": as_of,
                "row_key": f"{kind}:{item}"[:120],
                "payload": {
                    "mainop_type": _num(row.get("mainop_type")),
                    "item_name": item,
                    "income": _num(row.get("main_business_income")),
                    "cost": _num(row.get("main_business_cost")),
                    "gross_profit": _num(row.get("main_business_rpofit")),
                    "gross_margin_pct": (_num(row.get("gross_rpofit_ratio")) or 0) * 100 if row.get("gross_rpofit_ratio") not in (None, "") else None,
                    "mbi_ratio": _num(row.get("mbi_ratio")),
                },
            }
        )
    return out


def normalize_margin(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = _lower_keys(raw)
        as_of = _date(row.get("date"))
        if as_of is None:
            continue
        out.append(
            {
                "as_of": as_of,
                "row_key": "default",
                "payload": {
                    "rz_balance": _num(row.get("rzye")),
                    "rq_balance": _num(row.get("rqye")),
                    "rzrq_balance": _num(row.get("rzrqye")),
                    "rz_balance_pct_float": _num(row.get("rzyezb")),
                    "rz_buy": _num(row.get("rzmre")),
                    "rz_repay": _num(row.get("rzche")),
                },
            }
        )
    return out


def normalize_dividends(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = _lower_keys(raw)
        as_of = _date(row.get("report_date"))
        if as_of is None:
            continue
        ex_date = _date(row.get("ex_dividend_date"))
        out.append(
            {
                "as_of": as_of,
                "row_key": (ex_date.isoformat() if ex_date else as_of.isoformat()),
                "payload": {
                    "ex_dividend_date": ex_date.isoformat() if ex_date else None,
                    "equity_record_date": row.get("equity_record_date"),
                    "pretax_bonus_rmb": _num(row.get("pretax_bonus_rmb")),
                    "bonus_it_ratio": _num(row.get("bonus_it_ratio")),
                    "bonus_ratio": _num(row.get("bonus_ratio")),
                    "it_ratio": _num(row.get("it_ratio")),
                    "divident_ratio": _num(row.get("divident_ratio")),
                    "assign_progress": row.get("assign_progress"),
                },
            }
        )
    return out


def fetch_flows(client: HttpClient, secid: str = SECIDS["a"]) -> list[dict[str, Any]]:
    payload = _json(
        client,
        FFLOW_URL,
        {
            "secid": secid,
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "klt": "101",
            "lmt": "0",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
        },
        referer="quote",
    )
    klines = ((payload.get("data") or {}).get("klines")) or []
    out: list[dict[str, Any]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 7:
            continue
        values = dict(zip(FLOW_FIELDS, parts))
        as_of = _date(values.get("date"))
        if as_of is None:
            continue
        out.append(
            {
                "as_of": as_of,
                "row_key": "default",
                "payload": {key: _num(value) for key, value in values.items() if key != "date"},
            }
        )
    return out


def fetch_announcements(client: HttpClient, *, pages: int = 5, page_size: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        payload = _json(
            client,
            NOTICE_URL,
            {
                "sr": -1,
                "page_size": page_size,
                "page_index": page,
                "ann_type": "A",
                "client_source": "web",
                "stock_list": "603993",
                "f_node": 0,
                "s_node": 0,
            },
            referer="data",
        )
        items = ((payload.get("data") or {}).get("list")) or []
        if not items:
            break
        for item in items:
            article = item.get("art_code")
            as_of = _date((item.get("notice_date") or "")[:10])
            if not article or as_of is None:
                continue
            columns = [column.get("column_name") for column in (item.get("columns") or []) if column.get("column_name")]
            rows.append(
                {
                    "as_of": as_of,
                    "row_key": str(article)[:120],
                    "payload": {
                        "title": item.get("title"),
                        "columns": "/".join(columns),
                        "art_code": article,
                        "url": f"https://data.eastmoney.com/notices/detail/603993/{article}.html",
                    },
                }
            )
        if len(items) < page_size:
            break
    return rows


def fetch_reports(client: HttpClient, *, pages: int = 8, page_size: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        payload = _json(
            client,
            REPORT_URL,
            {
                "cb": "cb",
                "industryCode": "*",
                "pageSize": page_size,
                "industry": "*",
                "rating": "",
                "ratingChange": "",
                "beginTime": "2019-01-01",
                "endTime": "2099-12-31",
                "pageNo": page,
                "fields": "",
                "qType": 0,
                "orgCode": "",
                "code": "603993",
                "rcode": "",
                "p": page,
                "pageNum": page,
                "pageNumber": page,
            },
            referer="report",
        )
        items = payload.get("data") or []
        if not items:
            break
        for item in items:
            code = item.get("infoCode")
            as_of = _date((item.get("publishDate") or "")[:10])
            if not code or as_of is None:
                continue
            rows.append(
                {
                    "as_of": as_of,
                    "row_key": str(code)[:120],
                    "payload": {
                        "title": item.get("title"),
                        "org": item.get("orgSName") or item.get("orgName"),
                        "rating": item.get("emRatingName") or item.get("sRatingName"),
                        "eps_this_year": _num(item.get("predictThisYearEps")),
                        "eps_next_year": _num(item.get("predictNextYearEps")),
                        "pe_this_year": _num(item.get("predictThisYearPe")),
                        "info_code": code,
                    },
                }
            )
        if len(items) < page_size:
            break
    return rows


def fetch_quotes(client: HttpClient, secids: dict[str, str]) -> list[dict[str, Any]]:
    """Snapshot quotes for peers / A+H / sector (single batch request)."""
    payload = _json(
        client,
        ULIST_URL,
        {
            "fltt": 2,
            "secids": ",".join(secids.values()),
            "fields": "f12,f14,f2,f3,f9,f23,f20,f8",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        },
        referer="quote",
    )
    items = ((payload.get("data") or {}).get("diff")) or []
    today = date.today()
    by_code = {value: key for key, value in secids.items()}
    rows: list[dict[str, Any]] = []
    for item in items:
        code = str(item.get("f12") or "")
        key = by_code.get(f"1.{code}") or by_code.get(f"0.{code}") or code
        rows.append(
            {
                "as_of": today,
                "row_key": str(key)[:120],
                "payload": {
                    "code": code,
                    "name": item.get("f14"),
                    "price": _num(item.get("f2")),
                    "pct_chg": _num(item.get("f3")),
                    "pe_ttm": _num(item.get("f9")),
                    "pb": _num(item.get("f23")),
                    "market_cap": _num(item.get("f20")),
                    "turnover": _num(item.get("f8")),
                },
            }
        )
    return rows


def normalize_kline_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identity helper kept for symmetry / future vendor changes."""
    return list(rows)
