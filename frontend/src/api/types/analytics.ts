/* ---------- 分析 ---------- */

export interface Wind {
  score: number;
  label: string;
  components: {
    breadth_above_ma60: number;
    momentum_20d_avg_pct: number;
    us10y_change_20d_pp: number | null;
    risk_assets: string[];
  };
  asof: string;
}

export interface Regime {
  country: string;
  growth_score: number;
  inflation_score: number;
  liquidity_score: number;
  growth_z: number;
  inflation_z: number;
  quadrant: string;
  confidence: number;
  method: string;
}

export interface CorrelationPair {
  a: string;
  b: string;
  corr: number;
}

export interface Correlation {
  window: number;
  avg_abs_corr: number;
  top_pairs: CorrelationPair[];
}

export interface AttributionEntry {
  window: number;
  contrib_days: number;
  betas: Record<string, number>;
  contributions_pct: Record<string, number>;
  actual_pct: number;
  residual_pct: number;
  r2: number;
}

export interface AnalogMatch {
  date: string;
  distance: number;
  forward: Record<string, number>;
}

export interface Analogs {
  current_date: string;
  features: string[];
  matches: AnalogMatch[];
  note: string;
}

export interface CalendarStudyGroup {
  country: string;
  category: string;
  n: number;
  assets: Record<string, Record<string, number>>;
}

export interface CalendarStudy {
  asof: string;
  window: string;
  events: number;
  groups: CalendarStudyGroup[];
  note: string;
}

export interface Mover {
  symbol: string;
  name: string;
  change_20d: number;
  trend: string;
  percentile_252: number;
  vol20: number;
}

export interface AnalyticsOverview {
  wind?: Wind | null;
  regimes?: Record<string, Regime> | null;
  correlation?: Correlation | null;
  attribution?: Record<string, AttributionEntry> | null;
  analogs?: Analogs | null;
  calendar_study?: CalendarStudy | null;
  movers?: Mover[] | null;
  asof?: string;
}
