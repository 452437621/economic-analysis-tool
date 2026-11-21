"""Metadata for macro series and the annual/structural source mappings."""

from __future__ import annotations


MACRO_SERIES_META: dict[str, dict] = {
    "US2Y": {"name": "美债2年", "unit": "%", "country": "US"},
    "US5Y": {"name": "美债5年", "unit": "%", "country": "US"},
    "US10Y": {"name": "美债10年", "unit": "%", "country": "US"},
    "US30Y": {"name": "美债30年", "unit": "%", "country": "US"},
    "US5Y_REAL": {"name": "美债5年实际利率", "unit": "%", "country": "US"},
    "US10Y_REAL": {"name": "美债10年实际利率", "unit": "%", "country": "US"},
    "US5Y_BE": {"name": "5年盈亏平衡通胀", "unit": "%", "country": "US"},
    "US10Y_BE": {"name": "10年盈亏平衡通胀", "unit": "%", "country": "US"},
    "JP2Y": {"name": "日本国债2年", "unit": "%", "country": "JP"},
    "JP10Y": {"name": "日本国债10年", "unit": "%", "country": "JP"},
    "JP30Y": {"name": "日本国债30年", "unit": "%", "country": "JP"},
    "DE2Y": {"name": "德国国债2年", "unit": "%", "country": "DE"},
    "DE10Y": {"name": "德国国债10年", "unit": "%", "country": "DE"},
    "FR10Y": {"name": "法国国债10年（月度）", "unit": "%", "country": "FR", "freq": "m"},
    "CN2Y": {"name": "中国国债2年", "unit": "%", "country": "CN"},
    "CN5Y": {"name": "中国国债5年", "unit": "%", "country": "CN"},
    "CN10Y": {"name": "中国国债10年", "unit": "%", "country": "CN"},
    "CN30Y": {"name": "中国国债30年", "unit": "%", "country": "CN"},
    "CN10Y2Y": {"name": "中国国债10年-2年利差", "unit": "pp", "country": "CN"},
    "SOFR": {"name": "担保隔夜融资利率(SOFR)", "unit": "%", "country": "US"},
    "EFFR": {"name": "联邦基金有效利率(EFFR)", "unit": "%", "country": "US"},
    "SOFR_EFFR": {"name": "SOFR-EFFR 利差", "unit": "pp", "country": "US"},
    # ── 结构性宏观序列（IMF WEO 年频）───────────────────────────────
    "US_DEBT_GDP": {"name": "美国联邦债务/GDP（IMF）", "unit": "%", "country": "US", "freq": "y"},
    "US_NET_LENDING_GDP": {
        "name": "美国净贷出/借入占GDP（IMF，负=赤字）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "US_GDP_GROWTH": {"name": "美国实际GDP增速（IMF）", "unit": "%", "country": "US", "freq": "y"},
    "US_INFLATION": {"name": "美国CPI通胀（IMF）", "unit": "%", "country": "US", "freq": "y"},
    "US_UNEMPLOYMENT": {"name": "美国失业率（IMF）", "unit": "%", "country": "US", "freq": "y"},
    "US_GOV_REVENUE_GDP": {
        "name": "美国政府收入/GDP（IMF）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "US_GOV_EXPENSE_GDP": {
        "name": "美国政府支出/GDP（IMF）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "CN_DEBT_GDP": {"name": "中国政府债务/GDP（IMF）", "unit": "%", "country": "CN", "freq": "y"},
    "CN_NET_LENDING_GDP": {
        "name": "中国净贷出/借入占GDP（IMF，负=赤字）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
    "CN_GDP_GROWTH": {"name": "中国实际GDP增速（IMF）", "unit": "%", "country": "CN", "freq": "y"},
    "CN_INFLATION": {"name": "中国CPI通胀（IMF）", "unit": "%", "country": "CN", "freq": "y"},
    "CN_UNEMPLOYMENT": {"name": "中国失业率（IMF）", "unit": "%", "country": "CN", "freq": "y"},
    "CN_GOV_REVENUE_GDP": {
        "name": "中国政府收入/GDP（IMF）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
    "CN_GOV_EXPENSE_GDP": {
        "name": "中国政府支出/GDP（IMF）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
    # ── 美国财政部 Fiscal Data（日频债务 + 月频收支）─────────────────
    "US_FED_DEBT": {"name": "美国联邦债务总额（日频）", "unit": "USD", "country": "US", "freq": "d"},
    "US_MTS_INTEREST": {"name": "美国联邦净利息支出（月度）", "unit": "USD", "country": "US", "freq": "m"},
    "US_MTS_RECEIPTS": {"name": "美国联邦财政收入（月度）", "unit": "USD", "country": "US", "freq": "m"},
    "US_MTS_OUTLAYS": {"name": "美国联邦财政支出（月度）", "unit": "USD", "country": "US", "freq": "m"},
    "US_MTS_DEFICIT": {
        "name": "美国联邦财政赤字（月度，支出−收入）",
        "unit": "USD",
        "country": "US",
        "freq": "m",
    },
    # ── 世界银行兜底（IMF 不可达时的年频替代）───────────────────────
    "WB_US_GDP": {"name": "美国名义GDP（世界银行）", "unit": "USD", "country": "US", "freq": "y"},
    "WB_US_CPI": {"name": "美国CPI通胀（世界银行）", "unit": "%", "country": "US", "freq": "y"},
    "WB_US_UNEMPLOYMENT": {"name": "美国失业率（世界银行）", "unit": "%", "country": "US", "freq": "y"},
    "WB_US_DEBT_GDP": {
        "name": "美国中央政府债务/GDP（世界银行）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "WB_CN_GDP": {"name": "中国名义GDP（世界银行）", "unit": "USD", "country": "CN", "freq": "y"},
    "WB_CN_CPI": {"name": "中国CPI通胀（世界银行）", "unit": "%", "country": "CN", "freq": "y"},
    "WB_CN_UNEMPLOYMENT": {"name": "中国失业率（世界银行）", "unit": "%", "country": "CN", "freq": "y"},
    "WB_CN_DEBT_GDP": {
        "name": "中国政府债务/GDP（世界银行）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
    # ── 纽约联储货币市场管道（TGCR/BGCR/OBFR 与隔夜逆回购规模）──────────
    "US_TGCR": {"name": "三方一般担保回购利率(TGCR)", "unit": "%", "country": "US", "freq": "d"},
    "US_BGCR": {"name": "广义一般担保回购利率(BGCR)", "unit": "%", "country": "US", "freq": "d"},
    "US_OBFR": {"name": "隔夜银行融资利率(OBFR)", "unit": "%", "country": "US", "freq": "d"},
    "US_RRP_AMT": {
        "name": "隔夜逆回购(RRP)规模",
        "unit": "USD",
        "country": "US",
        "freq": "d",
    },
    # ── 美联储资产负债表（H.4.1，周频）与货币供应（H.6，月频）──────────
    "US_FED_ASSETS": {"name": "美联储总资产（H.4.1）", "unit": "USD", "country": "US", "freq": "w"},
    "US_FED_TREASURY": {
        "name": "美联储持有美国国债（H.4.1）",
        "unit": "USD",
        "country": "US",
        "freq": "w",
    },
    "US_FED_MBS": {
        "name": "美联储持有MBS（H.4.1）",
        "unit": "USD",
        "country": "US",
        "freq": "w",
    },
    "US_FED_RESERVES": {
        "name": "准备金余额（H.4.1，周频）",
        "unit": "USD",
        "country": "US",
        "freq": "w",
    },
    "US_TGA": {
        "name": "财政部一般账户余额(TGA)",
        "unit": "USD",
        "country": "US",
        "freq": "w",
    },
    "US_CURRENCY": {"name": "流通中货币（H.4.1）", "unit": "USD", "country": "US", "freq": "w"},
    "US_M1": {"name": "美国M1（季节调整，H.6）", "unit": "USD", "country": "US", "freq": "m"},
    "US_M2": {"name": "美国M2（季节调整，H.6）", "unit": "USD", "country": "US", "freq": "m"},
    "US_MONETARY_BASE": {
        "name": "美国货币基础（季节调整，H.6）",
        "unit": "USD",
        "country": "US",
        "freq": "m",
    },
    # ── 世界银行扩展指标（储蓄/投资/货币化/经常账户，佩蒂斯—辜朝明框架需要）──
    "WB_US_CA_GDP": {"name": "美国经常账户/GDP（世界银行）", "unit": "%", "country": "US", "freq": "y"},
    "WB_CN_CA_GDP": {"name": "中国经常账户/GDP（世界银行）", "unit": "%", "country": "CN", "freq": "y"},
    "WB_US_SAVINGS_GDP": {
        "name": "美国总储蓄/GDP（世界银行）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "WB_CN_SAVINGS_GDP": {
        "name": "中国总储蓄/GDP（世界银行）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
    "WB_US_M2_GDP": {
        "name": "美国广义货币/GDP（世界银行）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "WB_CN_M2_GDP": {
        "name": "中国广义货币/GDP（世界银行）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
    "WB_US_CAPFORM_GDP": {
        "name": "美国资本形成/GDP（世界银行）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "WB_CN_CAPFORM_GDP": {
        "name": "中国资本形成/GDP（世界银行）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
    "WB_US_REAL_GDP_GROWTH": {
        "name": "美国实际GDP增速（世界银行）",
        "unit": "%",
        "country": "US",
        "freq": "y",
    },
    "WB_CN_REAL_GDP_GROWTH": {
        "name": "中国实际GDP增速（世界银行）",
        "unit": "%",
        "country": "CN",
        "freq": "y",
    },
}

# IMF WEO 指标 → 序列 code（键为 DataMapper 的指标名，ISO3 为国家代码）。
IMF_ANNUAL_SERIES: dict[str, dict[str, str]] = {
    "GGXWDG_NGDP": {"USA": "US_DEBT_GDP", "CHN": "CN_DEBT_GDP"},
    "GGXCNL_NGDP": {"USA": "US_NET_LENDING_GDP", "CHN": "CN_NET_LENDING_GDP"},
    "NGDP_RPCH": {"USA": "US_GDP_GROWTH", "CHN": "CN_GDP_GROWTH"},
    "PCPIPCH": {"USA": "US_INFLATION", "CHN": "CN_INFLATION"},
    "LUR": {"USA": "US_UNEMPLOYMENT", "CHN": "CN_UNEMPLOYMENT"},
    "GGR_NGDP": {"USA": "US_GOV_REVENUE_GDP", "CHN": "CN_GOV_REVENUE_GDP"},
    "GGX_NGDP": {"USA": "US_GOV_EXPENSE_GDP", "CHN": "CN_GOV_EXPENSE_GDP"},
}

# 世界银行指标 → 序列 code（年频兜底）。
WORLDBANK_ANNUAL_SERIES: dict[str, dict[str, str]] = {
    "NY.GDP.MKTP.CD": {"USA": "WB_US_GDP", "CHN": "WB_CN_GDP"},
    "FP.CPI.TOTL.ZG": {"USA": "WB_US_CPI", "CHN": "WB_CN_CPI"},
    "SL.UEM.TOTL.ZS": {"USA": "WB_US_UNEMPLOYMENT", "CHN": "WB_CN_UNEMPLOYMENT"},
    "GC.DOD.TOTL.GD.ZS": {"USA": "WB_US_DEBT_GDP", "CHN": "WB_CN_DEBT_GDP"},
    # 储蓄—投资—货币化：佩蒂斯（贸易差额是 S−I 残差）与辜朝明（资产负债表衰退）的核心口径。
    "BN.CAB.XOKA.GD.ZS": {"USA": "WB_US_CA_GDP", "CHN": "WB_CN_CA_GDP"},
    "NY.GNS.ICTR.ZS": {"USA": "WB_US_SAVINGS_GDP", "CHN": "WB_CN_SAVINGS_GDP"},
    "FM.LBL.BMNY.GD.ZS": {"USA": "WB_US_M2_GDP", "CHN": "WB_CN_M2_GDP"},
    "NE.GDI.TOTL.ZS": {"USA": "WB_US_CAPFORM_GDP", "CHN": "WB_CN_CAPFORM_GDP"},
    "NY.GDP.MKTP.KD.ZG": {"USA": "WB_US_REAL_GDP_GROWTH", "CHN": "WB_CN_REAL_GDP_GROWTH"},
}

# MTS table 9 的 line_code_nbr → 序列 code（表里两行都叫 "Total"，必须按行号区分）。
MTS_LINE_SERIES: dict[str, str] = {
    "120": "US_MTS_RECEIPTS",
    "320": "US_MTS_INTEREST",
    "340": "US_MTS_OUTLAYS",
}

__all__ = [
    "MACRO_SERIES_META",
    "IMF_ANNUAL_SERIES",
    "WORLDBANK_ANNUAL_SERIES",
    "MTS_LINE_SERIES",
]
