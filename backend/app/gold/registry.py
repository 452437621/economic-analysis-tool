"""Gold monitoring indicator registry.

Every indicator used by the gold dashboard/score is declared here: display
metadata, data source, update frequency, scoring weight and the transform used
to turn the latest observations into a -1..1 factor score.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Indicator:
    code: str
    name: str
    category: str  # central_bank / etf / lease / inventory / market_maker / price
    unit: str
    freq: str  # d / w / m / q
    source: str
    weight: float  # score weight (0 = context only)
    direction: int  # +1 higher value is gold-bullish, -1 gold-bearish
    transform: str  # pct_change_1m / pct_change_3m / level / percentile / mo_m
    scale: float  # normalisation denominator
    manual: bool = False
    note: str = ""


INDICATORS: dict[str, Indicator] = {
    # ---------- 行情 / 宏观驱动 ----------
    "GOLD_PRICE_USD": Indicator("GOLD_PRICE_USD", "伦敦金现", "price", "美元/盎司", "d", "sina", 0, 1, "level", 1, note="XAUUSD 快照，仅展示"),
    "GOLD_MOM_20D_PCT": Indicator("GOLD_MOM_20D_PCT", "黄金 20 日动量", "price", "%", "d", "market_bars", 10, 1, "level", 8, note="AU 日线 20 日涨跌幅"),
    "US10Y_REAL": Indicator("US10Y_REAL", "美债 10Y 实际利率", "price", "%", "d", "treasury", 16, -1, "level_and_change", 1.5, note="实际利率上行压制金价"),
    "DXY": Indicator("DXY", "美元指数", "price", "点", "d", "sina", 8, -1, "pct_change_1m", 3, note="美元走强压制金价"),
    # ---------- 央行购金 ----------
    "CN_GOLD_RESERVES_USD": Indicator("CN_GOLD_RESERVES_USD", "中国官方黄金储备", "central_bank", "亿美元", "m", "eastmoney", 12, 1, "pct_change_1m", 1.2, note="中国央行黄金储备（美元计价，月频）"),
    "CB_GOLD_GLOBAL_TONNES": Indicator("CB_GOLD_GLOBAL_TONNES", "全球央行黄金储备", "central_bank", "吨", "q", "WGC CBD（IMF IFS）", 12, 1, "pct_change_3m", 1.2, note="WGC 央行仪表盘按国别季度储备加总；最新季度若上报国家不足会自动丢弃"),
    # ---------- 全球黄金 ETF ----------
    "ETF_GLOBAL_TONNES": Indicator("ETF_GLOBAL_TONNES", "全球黄金 ETF 持仓", "etf", "吨", "w", "WGC", 15, 1, "pct_change_1m", 2.0, note="北美+欧洲+亚洲+其他合计持仓"),
    "ETF_FLOW_1M_TONNES": Indicator("ETF_FLOW_1M_TONNES", "ETF 近月净流入", "etf", "吨", "m", "WGC", 5, 1, "level", 20, note="持仓环比变化"),
    # ---------- 黄金租赁 / 掉期 / 存储 ----------
    "GOLD_LEASE_PROXY_PCT": Indicator("GOLD_LEASE_PROXY_PCT", "黄金租赁利率代理", "lease", "%", "d", "derived", 6, 1, "level", 4, note="由 COMEX 期现基差近似的租赁紧张度（正=贴水/紧张，负=升水/宽松）"),
    "COMEX_GOLD_BASIS_PCT": Indicator("COMEX_GOLD_BASIS_PCT", "COMEX 期现基差", "lease", "%", "d", "derived", 5, 1, "level", 1.2, note="GC 期货相对伦敦现货溢价，反映持有成本/紧张度"),
    "SGE_GOLD_LEASE_3M_PCT": Indicator("SGE_GOLD_LEASE_3M_PCT", "上金所黄金租借费率(3M)", "lease", "%", "d", "SGE 租借基准费率", 6, 1, "level", 1.5, note="上金所黄金租借基准费率 3M 期限；BIS 无公开序列，以此作为租赁紧张度代理"),
    "BIS_GOLD_SWAP_USD": Indicator("BIS_GOLD_SWAP_USD", "BIS 黄金掉期余额", "lease", "亿美元", "q", "BIS", 0, 1, "pct_change_1m", 5, manual=True, note="BIS 不公布可机读的黄金掉期序列，仅年报/季报披露；默认不参与评分，可用 COMEX 掉期商净持仓代理"),
    "BIS_GOLD_STORAGE_USD": Indicator("BIS_GOLD_STORAGE_USD", "BIS 黄金存储", "lease", "亿美元", "q", "BIS", 0, 1, "pct_change_1m", 5, manual=True, note="BIS 黄金存储/托管无公开数据；默认不参与评分，可用 LBMA 金库与 ETF 持仓代理"),
    # ---------- 库存 ----------
    "LBMA_GOLD_TONNES": Indicator("LBMA_GOLD_TONNES", "伦敦金库黄金", "inventory", "吨", "m", "LBMA", 8, -1, "pct_change_1m", 2.5, note="伦敦金库月度库存（吨）"),
    "LBMA_SILVER_TONNES": Indicator("LBMA_SILVER_TONNES", "伦敦金库白银", "inventory", "吨", "m", "LBMA", 0, 1, "level", 1, note="伦敦金库月度库存（吨），仅展示"),
    "COMEX_GOLD_INVENTORY_TONNES": Indicator("COMEX_GOLD_INVENTORY_TONNES", "COMEX 黄金库存", "inventory", "吨", "w", "CME / MetalCharts", 5, -1, "pct_change_1m", 3, note="CME 仓库库存（注册+合格，周频）；CME 官网不可达，读取 MetalCharts 免费 CSV 镜像（需署名 metalcharts.org）"),
    "SHFE_GOLD_STOCK_TONNES": Indicator("SHFE_GOLD_STOCK_TONNES", "上海黄金库存（上期所仓单）", "inventory", "吨", "d", "SHFE 仓单日报", 5, -1, "pct_change_1m", 3, note="上金所不公布库存；以上期所指定交割金库黄金仓单（千克→吨）作为中国黄金库存代理"),
    # ---------- 做市商 / 持仓 ----------
    "COT_SWAP_NET": Indicator("COT_SWAP_NET", "COMEX 掉期商净持仓", "market_maker", "张", "w", "CFTC", 6, -1, "percentile", 1, note="CFTC 分类持仓：Swap Dealers 净头寸（做市/套保代理）"),
    "COT_MONEY_NET": Indicator("COT_MONEY_NET", "COMEX 管理基金净持仓", "market_maker", "张", "w", "CFTC", 8, -1, "percentile", 1, note="CFTC 管理基金净头寸，极端值反向"),
    "COMEX_GOLD_OI": Indicator("COMEX_GOLD_OI", "COMEX 黄金未平仓", "market_maker", "张", "w", "CFTC", 0, 1, "level", 1, note="未平仓合约，仅展示"),
    "MM_BANK_GOLD_NET": Indicator("MM_BANK_GOLD_NET", "银行黄金净合约", "market_maker", "张", "m", "CFTC 银行参与报告", 4, -1, "percentile", 1, note="CFTC Bank Participation Report：CMX 黄金全部银行多空净头寸（月频，逆向分位）"),
    # ---------- 中国溢价 ----------
    "CN_GOLD_PREMIUM_PCT": Indicator("CN_GOLD_PREMIUM_PCT", "上海金溢价", "inventory", "%", "d", "derived", 8, 1, "level", 1.2, note="AU（元/克）相对伦敦金折算价的溢价，反映亚洲实物需求"),
}

#: 卡片分组
CATEGORY_LABELS = {
    "central_bank": "央行购金",
    "etf": "全球黄金 ETF",
    "lease": "租赁 / 掉期 / 存储",
    "inventory": "库存与实物",
    "market_maker": "做市商 / 持仓",
    "price": "价格与宏观驱动",
}

#: 总览页默认返回的序列
SERIES_CODES = [
    "GOLD_PRICE_USD",
    "US10Y_REAL",
    "ETF_GLOBAL_TONNES",
    "ETF_FLOW_1M_TONNES",
    "CN_GOLD_RESERVES_USD",
    "LBMA_GOLD_TONNES",
    "COMEX_GOLD_INVENTORY_TONNES",
    "SGE_GOLD_LEASE_3M_PCT",
    "COT_MONEY_NET",
    "COT_SWAP_NET",
    "CN_GOLD_PREMIUM_PCT",
]


def indicator(code: str) -> Indicator | None:
    return INDICATORS.get(code)


def manual_codes() -> list[str]:
    return [code for code, item in INDICATORS.items() if item.manual]
