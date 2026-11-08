"""Symbol mapping between EPIC instruments and upstream data-source codes."""

from __future__ import annotations

# 国内期货连续合约（新浪 InnerFuturesNewService 代码 = 品种 + "0"）
CN_FUTURES: dict[str, str] = {
    "AU": "AU0",
    "AG": "AG0",
    "CU": "CU0",
    "AL": "AL0",
    "ZN": "ZN0",
    "NI": "NI0",
    "SC": "SC0",
    "M": "M0",
    "I": "I0",
    "SR": "SR0",
    "CF": "CF0",
    "P": "P0",
}

# 外盘/现货（新浪 hf_ 系列，约 15 分钟延迟）
SINA_HF: dict[str, str] = {
    "XAUUSD": "hf_XAU",
    "GC": "hf_GC",
    "SI": "hf_SI",
    "CL": "hf_CL",
    "BZ": "hf_OIL",
    "HG": "hf_CAD",
    "AL_LME": "hf_AHD",
    "ZN_LME": "hf_ZSD",
    "NI_LME": "hf_NID",
}

# 汇率（新浪 fx_ 系列）
SINA_FX: dict[str, str] = {
    "USDCNH": "fx_susdcnh",
    "USDJPY": "fx_susdjpy",
    "EURUSD": "fx_seurusd",
    "GBPUSD": "fx_sgbpusd",
    "USDCAD": "fx_susdcad",
    "USDSEK": "fx_susdsek",
    "USDCHF": "fx_susdchf",
}

# A 股/指数（东财 secid：1=沪市, 0=深市）
EM_SECID: dict[str, str] = {
    "000300": "1.000300",
    "603993": "1.603993",
}

# 东财全球指数/外汇（可提供 DXY、USDCNH 及海外股指的实时报价与日线历史）
EM_QUOTE_SECID: dict[str, str] = {
    "DXY": "100.UDI",
    "USDCNH": "133.USDCNH",
    "SPX": "100.SPX",
    "NDX": "100.NDX",
    "DJIA": "100.DJIA",
    "HSI": "100.HSI",
}
EM_DAILY_SECID: dict[str, str] = {
    "DXY": "100.UDI",
    "USDCNH": "133.USDCNH",
    "SPX": "100.SPX",
    "NDX": "100.NDX",
    "DJIA": "100.DJIA",
    "HSI": "100.HSI",
}

# ICE 美元指数篮子权重（用于由 6 组汇率合成 DXY 代理）
DXY_BASKET: dict[str, float] = {
    "EURUSD": -0.576,
    "USDJPY": 0.136,
    "GBPUSD": -0.119,
    "USDCAD": 0.091,
    "USDSEK": 0.042,
    "USDCHF": 0.036,
}
DXY_CONSTANT = 50.14348112


def compute_dxy(prices: dict[str, float]) -> float | None:
    """Compute ICE-style DXY from six FX prices; returns None if any leg missing."""
    try:
        value = DXY_CONSTANT
        for symbol, exponent in DXY_BASKET.items():
            price = prices[symbol]
            if price <= 0:
                return None
            value *= price**exponent
        return round(value, 3)
    except KeyError:
        return None
