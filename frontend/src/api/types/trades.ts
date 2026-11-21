/* ---------- 交易记录（V2.0）：交易品种不限股票 / 期货 ---------- */

export type TradeAssetClass = "futures" | "stock" | "option" | "forex" | "crypto" | "other";
export type TradeDirection = "long" | "short";
export type TradeStatus = "planned" | "open" | "closed" | "cancelled";

export interface TradeItem {
  id: string;
  /** 交易日 YYYY-MM-DD */
  trade_date: string;
  symbol: string;
  name: string | null;
  asset_class: TradeAssetClass;
  direction: TradeDirection;
  status: TradeStatus;
  strategy: string | null;
  planned_qty: number | null;
  filled_qty: number | null;
  entry_price: number | null;
  exit_price: number | null;
  stop_price: number | null;
  target_price: number | null;
  margin: number | null;
  leverage: number | null;
  fee: number | null;
  pnl: number | null;
  /** 收益率（分数，0.12 = 12%），由后端按 pnl / margin 计算 */
  pnl_pct: number | null;
  risk_amount: number | null;
  rr: number | null;
  /** 预计胜率（百分比数值，55 = 55%） */
  planned_win_rate: number | null;
  attribution: string | null;
  plan_note: string | null;
  review_note: string | null;
  tags: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface TradeSummary {
  count: number;
  closed: number;
  open: number;
  planned: number;
  wins: number;
  losses: number;
  /** 胜率（分数，0.5 = 50%；分母为已平仓数） */
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number | null;
  avg_rr: number;
  total_fee: number;
}

export interface TradeList {
  items: TradeItem[];
  total: number;
  limit: number;
  offset: number;
  summary: TradeSummary;
}

export interface TradeInput {
  trade_date: string;
  symbol: string;
  name?: string | null;
  asset_class: TradeAssetClass;
  direction: TradeDirection;
  status?: TradeStatus;
  strategy?: string | null;
  planned_qty?: number | null;
  filled_qty?: number | null;
  entry_price?: number | null;
  exit_price?: number | null;
  stop_price?: number | null;
  target_price?: number | null;
  margin?: number | null;
  leverage?: number | null;
  fee?: number | null;
  pnl?: number | null;
  pnl_pct?: number | null;
  risk_amount?: number | null;
  rr?: number | null;
  planned_win_rate?: number | null;
  attribution?: string | null;
  plan_note?: string | null;
  review_note?: string | null;
  tags?: string[];
}

export interface TradeAssetClassStat {
  asset_class: TradeAssetClass;
  count: number;
  pnl: number;
  win_rate: number;
}

export interface TradeMonthStat {
  /** YYYY-MM */
  month: string;
  count: number;
  pnl: number;
}

export interface TradeStats extends TradeSummary {
  by_asset_class: TradeAssetClassStat[];
  by_month: TradeMonthStat[];
}
