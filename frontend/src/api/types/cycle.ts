/** 追加到 V2.0 类型定义文件末尾：周期引擎（M2）。 */
export type CycleKey = "DMI" | "ICI" | "ECI" | "GROWTH" | "INFLATION" | "LIQUIDITY";

export interface CycleReading {
  id: string;
  name: string;
  score: number | null;
  weight: number;
  direction: number;
  value: number | null;
  unit: string | null;
  asof: string | null;
  z: number | null;
  score_value: number | null;
  evidence: string;
  source: string | null;
  layer: string;
  why: string | null;
  caveat: string | null;
  stale_days: number | null;
  degraded: boolean;
  degrade_reason: string | null;
}

/**
 * /api/v2/cycle/indicators 的单条指标：在 CycleReading 基础上带证据等级、来源、
 * 时效（stale_days）与降级原因，用于「结构性 / 人工观测」透明度区块。
 * 注意 score 在这里是分量键（DMI/ICI/ECI/GROWTH/INFLATION/LIQUIDITY），不是数值。
 */
export interface CycleIndicator {
  id: string;
  name: string;
  score: string | null;
  weight: number;
  direction: number;
  value: number | null;
  unit: string | null;
  asof: string | null;
  z: number | null;
  score_value: number | null;
  evidence: string;
  source: string | null;
  layer: string;
  why: string | null;
  caveat: string | null;
  stale_days: number | null;
  degraded: boolean;
  degrade_reason: string | null;
}

export interface CycleIndicatorsResponse {
  items: CycleIndicator[];
  total: number;
  asof: string | null;
}

export interface CycleComposite {
  name: string | null;
  value: number | null;
  coverage: number;
  confidence: number;
  evidence: string | null;
  degraded: boolean;
  degrade_reason: string | null;
}

export interface CycleLongCycle {
  phase: string;
  phase_id: string;
  score: number;
  band: [number, number];
  position: number;
  meaning: string;
  asset: string;
  confidence: number;
  evidence: string | null;
  next_phase: string | null;
  exit_condition: string;
  hysteresis_held: boolean;
}

export interface CycleShortCycle {
  state: string;
  raw_state: string;
  hysteresis_held: boolean;
  variables: { growth: number | null; inflation: number | null; liq: number | null; d12: number | null };
  meaning: string;
  confidence: number;
  growth_12m_change: number | null;
}

export interface CycleLiquidity {
  available: boolean;
  state: string;
  score: number | null;
  meaning: string;
  confidence: number;
  evidence: string;
}

export interface CycleInventory {
  state: string;
  degraded: boolean;
  degrade_reason: string | null;
  meaning: string | null;
  asset: string | null;
  price_momentum_60d: number | null;
  inventory_proxy_20d: number | null;
  confidence: number | null;
  evidence: string | null;
}

export interface CycleCalendarEvent {
  date: string;
  name: string;
  importance: number;
  note: string;
  days: number;
  past: boolean;
}

export interface CyclePolitical {
  window: string;
  nearest: CycleCalendarEvent | null;
  days_to_nearest: number | null;
  events: CycleCalendarEvent[];
}

export interface CycleStateValue {
  readings: CycleReading[];
  composites: Record<CycleKey, CycleComposite>;
  long_cycle: CycleLongCycle;
  short_cycle: CycleShortCycle;
  liquidity: CycleLiquidity;
  inventory: CycleInventory;
  political: CyclePolitical;
}

export interface CycleSustainability {
  available: boolean;
  mode: string;
  mode_id: string;
  explanation: string;
  risk: string;
  r_minus_g: number | null;
  interest_to_revenue: number | null;
  deficit_to_gdp: number | null;
  debt_to_gdp: number | null;
  thresholds: { interest_watch: number; interest_alarm: number; deficit_watch: number };
  readings: Array<{ id: string; name: string; value: number; unit: string; asof: string }>;
  evidence: string;
}

export interface CycleStage {
  id: string;
  name: string;
  stage: number;
  stage_name: string;
  confidence: number;
  evidence: string;
  asof: string;
  reason: string;
  falsifier: string;
  source: string;
  url: string;
  degraded: boolean;
}

export interface CycleWorld {
  us_internal: CycleStage;
  global_order: CycleStage;
  power_index: {
    name: string;
    value: number;
    asof: string;
    evidence: string;
    components: Array<{ id: string; name: string; value: number; weight: number }>;
    degraded: boolean;
    degrade_reason: string;
  };
  reserve_currency: { code: string; share: number; asof: string; evidence: string; source: string; url: string };
}

export interface CycleAlert {
  id: string;
  name: string;
  severity: "high" | "medium" | "low";
  severity_label: string;
  metric: string | null;
  metric_name: string | null;
  value: number | null;
  unit: string | null;
  asof: string | null;
  threshold: number;
  op: string;
  triggered: boolean | null;
  status: "triggered" | "normal" | "unknown";
  distance: number | null;
  why: string | null;
  falsifier: string | null;
  source?: string | null;
  reason?: string;
}

export interface CycleAlerts {
  counts: { high: number; medium: number; low: number; unknown: number };
  total: number;
  triggered: number;
  unknown: number;
  alerts: CycleAlert[];
  note: string;
}

export interface CycleScenarioItem {
  id: string;
  name: string;
  probability: number;
  base: number;
  adjustment: number;
  desc: string;
  assets: string;
  triggers: string[];
}

export interface CycleScenarios {
  horizon: string;
  sum: number;
  scenarios: CycleScenarioItem[];
  formula?: string;
  caveats?: string[];
  confidence?: number;
}

export interface CycleAnalog {
  month: string;
  similarity: number;
  distance: number;
  state: { growth: number | null; inflation: number | null };
}

export interface CycleAnalogs {
  available: boolean;
  n: number;
  dimensions: string[];
  min_gap_months: number;
  analogs: CycleAnalog[];
  caveats: string[];
}

export interface CycleHistory {
  months: string[];
  series: Record<string, Array<number | null>>;
  coverage: Record<string, number[]>;
}

export interface CyclePayload<T> {
  code: string;
  claim: string;
  value: T;
  confidence: number | null;
  evidence_grade: string;
  asof: string | null;
  run_id: string | null;
  method_id: string | null;
  caveats: string[];
  falsifiers: string[];
  opposing: string[];
  inputs: string[];
  steps: Array<Record<string, unknown>>;
  rules_hit: Array<Record<string, unknown>>;
}

export interface CycleStateResponse {
  asof: string | null;
  run_id: string | null;
  status: string | null;
  degraded: boolean;
  degraded_reasons: Array<{ code: string; message: string; severity?: string }>;
  generated_at: string;
  state: CyclePayload<CycleStateValue>;
  indicators: CycleReading[];
  sustainability: CyclePayload<CycleSustainability> | null;
  world: CyclePayload<CycleWorld> | null;
  alerts: CyclePayload<CycleAlerts> | null;
  scenarios: CyclePayload<CycleScenarios> | null;
  analogs: CyclePayload<CycleAnalogs> | null;
  history: CyclePayload<CycleHistory> | null;
}

export interface CycleRunResult {
  ok: boolean;
  run_id: string;
  status: string;
  asof: string | null;
  degraded_reasons: Array<{ code: string; message: string }>;
  summary: {
    long: string;
    short: string;
    scenarios: Array<{ id: string; probability: number }>;
    alerts: { high: number; medium: number; low: number; unknown: number };
    analogs: number;
  };
}

export interface CycleAlertRule {
  id: string;
  name: string;
  severity: "high" | "medium" | "low";
  metric: string;
  op: string;
  threshold: number;
  why: string;
  falsifier: string;
}

export interface CycleCalendarEntry {
  date: string;
  name: string;
  importance: number;
  note: string;
}

export interface CycleReadingSparkPoint {
  date: string;
  value: number;
}

export interface CycleReadingCard {
  id: string;
  label: string;
  missing: boolean;
  value?: number | null;
  unit?: string;
  digits?: number;
  z?: number | null;
  delta_1d?: number | null;
  asof?: string;
  spark?: CycleReadingSparkPoint[];
  source?: string;
  evidence?: string;
  reason?: string | null;
}

export interface CycleReadingsResponse {
  items: CycleReadingCard[];
  total: number;
  missing: number;
  generated_at: string;
  method: string;
}

export interface CycleConfigResponse {
  version: string;
  normalization: Record<string, unknown>;
  scores: Array<Record<string, unknown>>;
  indicators: Array<Record<string, unknown>>;
  manual: Array<Record<string, unknown>>;
  long_cycle: Record<string, unknown>;
  short_cycle: Record<string, unknown>;
  alerts: CycleAlertRule[];
  scenarios: Array<Record<string, unknown>>;
  political_calendar: CycleCalendarEntry[];
}
