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

# 外盘/现货日线（新浪 GlobalFuturesService）
SINA_GLOBAL_FUTURES: dict[str, str] = {
    "XAUUSD": "XAU",
    "GC": "GC",
    "SI": "SI",
    "CL": "CL",
    "BZ": "OIL",
    "HG": "CAD",
    "AL_LME": "AHD",
    "ZN_LME": "ZSD",
    "NI_LME": "NID",
}

# 腾讯行情代码（东财不可用时的兜底报价；DXY/USDCNH 无对应代码）
TENCENT_QUOTE: dict[str, str] = {
    "000300": "sh000300",
    "603993": "sh603993",
    "SPX": "usINX",
    "NDX": "usNDX",
    "DJIA": "usDJI",
    "HSI": "hkHSI",
}

# 必须优先走腾讯的美股指数：东财 100.NDX 返回的其实是纳斯达克综合指数
# （实测 2026-11-16 盘中东财 24817.5 / 涨跌 -1.27% ⇒ 昨收≈25137，与腾讯
# .IXIC 昨收 25136.27 吻合；而腾讯 .NDX=纳斯达克100 为 27464.28），
# 与本项目「NDX=纳斯达克100」的口径不符，会让日线与报价差出 11%。
TENCENT_QUOTE_PREFERRED: dict[str, str] = {
    "NDX": "usNDX",
}

# 腾讯日线兜底（走不同端点：A股/恒生用前复权 fqkline，美股指数用原始 kline）
TENCENT_KLINE: dict[str, str] = {
    "000300": "sh000300",
    "603993": "sh603993",
    "HSI": "hkHSI",
}
# 美股指数：fqkline 只返回当日一根，必须走 kline/kline 原始端点（实测 320 根）
TENCENT_KLINE_RAW: dict[str, str] = {
    "SPX": "usINX",
    "NDX": "us.NDX",
    "DJIA": "usDJI",
}

# 「单根接口」：fqkline 对不带点的美股指数代码只返回**当日一根**（实测 usNDX
# 2026-11-16 收 27197.15，而原始端点 us.NDX 同一天返回 close=10.0 的串码数据）。
# 用途：订正原始端点最新一根被上游写坏的情况——请求量也很小。
TENCENT_SINGLE_BAR: dict[str, str] = {
    "SPX": "usINX",
    "NDX": "usNDX",
    "DJIA": "usDJI",
}

# 新浪外汇日线（东财 K 线不可用时的兜底；同时覆盖美元指数与离岸人民币）
# 注意：与 SINA_FX 的实时报价代码不同，这里是日线服务的代码
SINA_FX_DAILY: dict[str, str] = {
    "DXY": "DINIW",
    "USDCNH": "fx_susdcnh",
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
