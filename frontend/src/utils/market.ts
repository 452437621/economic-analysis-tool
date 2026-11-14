/** 市场快照的分类、内外盘判定（与旧版 SNAPSHOT_CATEGORIES 保持一致）。 */

export interface SnapshotCategory {
  key: string;
  label: string;
  symbols: string[];
}

export const SNAPSHOT_CATEGORIES: SnapshotCategory[] = [
  { key: "energy", label: "能源", symbols: ["CL", "BZ", "SC"] },
  { key: "metals", label: "金属", symbols: ["XAUUSD", "GC", "AU", "SI", "AG", "HG", "CU", "I"] },
  { key: "agri", label: "农业", symbols: ["M", "P", "CF", "SR"] },
  { key: "industrial", label: "工业", symbols: ["AL_LME", "ZN_LME", "NI_LME", "AL", "ZN", "NI"] },
  {
    key: "index",
    label: "指数 / 个股",
    symbols: ["SPX", "NDX", "DJIA", "HSI", "000300", "603993"],
  },
  {
    key: "fx",
    label: "汇率",
    symbols: ["DXY", "USDCNH", "USDJPY", "EURUSD", "GBPUSD", "USDCAD", "USDSEK", "USDCHF"],
  },
];

/** 市场页筛选 chip（含数量），与原型一致 */
export const MARKET_FILTERS: Array<{ key: string; label: string; symbols: string[] }> = [
  { key: "all", label: "全部", symbols: [] },
  { key: "precious", label: "贵金属", symbols: ["XAUUSD", "GC", "AU", "SI", "AG", "XAG"] },
  {
    key: "metal",
    label: "有色金属",
    symbols: ["HG", "CU", "ZN", "AL", "NI", "AL_LME", "ZN_LME", "NI_LME"],
  },
  { key: "energy", label: "能源化工", symbols: ["CL", "BZ", "SC"] },
  { key: "black", label: "黑色建材", symbols: ["I"] },
  { key: "agri", label: "农产品", symbols: ["M", "P", "SR", "CF"] },
  { key: "index", label: "指数个股", symbols: ["SPX", "NDX", "DJIA", "HSI", "000300", "603993"] },
  { key: "fx", label: "汇率", symbols: ["DXY", "USDCNH", "USDJPY", "EURUSD", "GBPUSD", "USDCAD", "USDSEK", "USDCHF"] },
];

export const DOMESTIC_EXCHANGES = new Set(["SHFE", "INE", "DCE", "CZCE"]);
export const DOMESTIC_SYMBOLS = new Set(["000300", "603993"]);

export function isDomestic(item: { exchange?: string | null; symbol: string }): boolean {
  return DOMESTIC_EXCHANGES.has(item.exchange ?? "") || DOMESTIC_SYMBOLS.has(item.symbol);
}

export const ASSET_CLASS_LABEL: Record<string, string> = {
  metal: "金属",
  energy: "能源",
  black: "黑色",
  agri: "农产品",
  fx: "汇率",
  equity: "权益",
  rate: "利率",
};

/** 宏观利率卡顺序（与旧版一致） */
export const MACRO_ORDER = [
  "SOFR",
  "EFFR",
  "SOFR_EFFR",
  "US2Y",
  "US5Y",
  "US10Y",
  "US30Y",
  "US5Y_REAL",
  "US10Y_REAL",
  "US5Y_BE",
  "US10Y_BE",
  "CN2Y",
  "CN5Y",
  "CN10Y",
  "CN30Y",
  "CN10Y2Y",
  "JP2Y",
  "JP10Y",
  "JP30Y",
  "DE2Y",
  "DE10Y",
  "FR10Y",
];

/** 利率区域分组（利率页） */
export const MACRO_GROUPS: Array<{ label: string; codes: string[] }> = [
  { label: "美国 · 政策与短端", codes: ["SOFR", "EFFR", "SOFR_EFFR"] },
  { label: "美国 · 国债曲线", codes: ["US2Y", "US5Y", "US10Y", "US30Y"] },
  { label: "美国 · 实际利率 / 通胀预期", codes: ["US5Y_REAL", "US10Y_REAL", "US5Y_BE", "US10Y_BE"] },
  { label: "中国", codes: ["CN2Y", "CN5Y", "CN10Y", "CN30Y", "CN10Y2Y"] },
  { label: "日本 / 德国 / 法国", codes: ["JP2Y", "JP10Y", "JP30Y", "DE2Y", "DE10Y", "FR10Y"] },
];

export const SIGNAL_TYPE_LABEL: Record<string, string> = {
  momentum: "动量",
  mean_reversion: "均值回归",
  breakout: "突破",
};

export const THESIS_STATUS_LABEL: Record<string, string> = {
  watch: "观察",
  active: "进行中",
  confirmed: "已确认",
  invalidated: "已失效",
  closed: "已关闭",
};
