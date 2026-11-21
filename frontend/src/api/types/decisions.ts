/* ---------- 决策 ---------- */

export interface Signal {
  id: string;
  symbol: string;
  type: string;
  direction: "long" | "short";
  strength: number;
  note: string | null;
  params?: Record<string, unknown>;
  ts?: string;
}

export interface RiskCheck {
  rule: string;
  passed: boolean;
  detail: string;
}

export interface PlanDetail {
  lots: number;
  lots_int?: number;
  raw_lots: number;
  contract_size: number;
  margin_pct: number;
  notional: number;
  margin: number;
  fee: number;
  equity: number;
  base_equity?: number;
  risk_amount?: number;
  stop_distance_pct?: number;
  weight_pct?: number;
  leverage?: number;
  risk_reward?: number;
  sizing_note?: string;
  checks?: RiskCheck[];
}

export interface TradePlan {
  id: string;
  symbol: string;
  side: "long" | "short";
  entry_low: number;
  entry_high: number;
  stop: number;
  targets: Record<string, number>;
  size: number;
  risk_pct: number;
  time_stop_days: number;
  invalidation: string | null;
  status: string;
  detail: PlanDetail;
  checks: RiskCheck[];
}

export interface BacktestSegment {
  count: number;
  hit_rate: number;
  avg_return_pct: number;
  median_return_pct: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  profit_factor: number;
}

export interface BacktestRule extends BacktestSegment {
  rule: string;
  horizon: number;
  cost_pct: number;
  by_symbol: Record<string, number>;
  walk_forward: { train: BacktestSegment; test: BacktestSegment; split: string };
}

export interface SignalTypeStat {
  count: number;
  long: number;
  short: number;
  avg_strength: number;
}

export interface DecisionsSummary {
  signals: Signal[];
  plans: TradePlan[];
  backtest: Record<string, BacktestRule>;
  signal_types: Record<string, SignalTypeStat>;
  open_predictions: number;
  counts: { signals: number; plans: number };
}

export interface PredictionRecord {
  prediction_id: string;
  symbol: string;
  side: string;
  probability: number;
  actual: number;
  brier: number;
  resolved_at: string | null;
  notes: string | null;
}

export interface CalibrationBucket {
  bucket: string;
  n: number;
  avg_probability: number;
  hit_rate: number;
}

export interface DecisionsReview {
  count: number;
  brier: number | null;
  hit_rate: number | null;
  calibration: CalibrationBucket[];
  records: PredictionRecord[];
}
