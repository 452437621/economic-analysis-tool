"""Instrument display units (price unit shown by the frontend).

Stored into ``instruments.extra["unit"]`` by ``seed_instruments`` and used as a
fallback by API serializers. Kept in one place so snapshot / watchlist /
overview responses stay consistent.
"""

from __future__ import annotations

UNIT_BY_SYMBOL: dict[str, str] = {
    # 贵金属 / 外盘现货与期货
    "XAUUSD": "美元/盎司",
    "GC": "美元/盎司",
    "SI": "美元/盎司",
    "AU": "元/克",
    "AG": "元/千克",
    # 能源
    "CL": "美元/桶",
    "BZ": "美元/桶",
    "SC": "元/桶",
    # 工业金属
    "CU": "元/吨",
    "AL": "元/吨",
    "ZN": "元/吨",
    "NI": "元/吨",
    "HG": "美元/吨",
    "AL_LME": "美元/吨",
    "ZN_LME": "美元/吨",
    "NI_LME": "美元/吨",
    # 农产品 / 黑色
    "M": "元/吨",
    "P": "元/吨",
    "SR": "元/吨",
    "CF": "元/吨",
    "I": "元/吨",
    # 汇率 / 指数 / 个股
    "DXY": "点",
    "USDCNH": "汇率",
    "USDJPY": "汇率",
    "EURUSD": "汇率",
    "GBPUSD": "汇率",
    "USDCAD": "汇率",
    "USDSEK": "汇率",
    "USDCHF": "汇率",
    "000300": "点",
    "SPX": "点",
    "NDX": "点",
    "DJIA": "点",
    "HSI": "点",
    "603993": "元/股",
}


def resolve_unit(symbol: str, extra: dict | None) -> str | None:
    """Prefer the DB-stored unit (user override), fall back to the static map."""
    if extra:
        unit = extra.get("unit")
        if unit:
            return str(unit)
    return UNIT_BY_SYMBOL.get(symbol)
