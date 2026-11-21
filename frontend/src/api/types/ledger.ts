/* V2.0 台账（M4）：原则库核对与预测台账 */
export type LedgerStatus = "hit" | "near" | "miss" | "unknown";

export interface LedgerPrincipleItem {
  id: string;
  category: string;
  category_label: string;
  name: string;
  statement: string;
  evidence: string;
  evidence_label: string;
  observable: string;
  signal: string;
  falsifier: string;
  grade: string;
  metric: string | null;
  op: string | null;
  threshold: number | null;
  near: number | null;
  status: LedgerStatus;
  value: number | null;
  note: string;
  checked_at: string | null;
}

export interface LedgerCounts {
  hit: number;
  near: number;
  miss: number;
  unknown: number;
  total: number;
}

export interface LedgerCalibrationHorizon {
  bucket: string;
  n: number;
  brier: number;
}

export interface LedgerCalibration {
  n: number;
  brier: number | null;
  hit_rate: number | null;
  by_horizon: LedgerCalibrationHorizon[];
  note?: string;
}

export interface LedgerForecast {
  id: string;
  code: string;
  code_label: string;
  subject: string;
  direction: "up" | "down" | "flat";
  horizon_days: number;
  probability: number | null;
  point: number | null;
  baseline_value: number | null;
  status: "open" | "resolved";
  made_at: string | null;
  target_date: string;
  notes: string | null;
  actual: number | null;
  hit: boolean | null;
  brier: number | null;
  resolved_at: string | null;
}

export interface LedgerForecastCode {
  code: string;
  label: string;
}

export interface LedgerForecastsBlock {
  open: number;
  resolved: number;
  next_due: string | null;
  items: LedgerForecast[];
}

export interface LedgerOverview {
  generated_at: string;
  asof: string | null;
  run_id: string;
  status: string;
  degraded: boolean;
  degraded_reasons: Array<{ code: string; message: string; severity?: string }>;
  counts: LedgerCounts;
  principles: LedgerPrincipleItem[];
  principles_claim: string | null;
  calibration: LedgerCalibration;
  forecasts: LedgerForecastsBlock;
  forecast_codes: LedgerForecastCode[];
  method_id: string;
}

export interface LedgerForecastList {
  total: number;
  items: LedgerForecast[];
  codes: LedgerForecastCode[];
}

export interface LedgerRunResult {
  ok: boolean;
  run_id: string;
  status: string;
  asof: string;
  counts: LedgerCounts;
  calibration: { n: number; brier: number | null };
  forecasts: number;
}

export interface LedgerForecastInput {
  code: string;
  direction: "up" | "down" | "flat";
  horizon_days: number;
  probability?: number | null;
  point?: number | null;
  baseline_value?: number | null;
  notes?: string | null;
}
