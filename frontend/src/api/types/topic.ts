/** 专题研判（黄金 / 洛阳钼业）统一契约。 */

export type TopicSectionKind =
  | "hero"
  | "kpis"
  | "factors"
  | "charts"
  | "bullets"
  | "table"
  | "valuation"
  | "scenarios"
  | "position"
  | "events"
  | "sources"
  | "health"
  | "methodology";

export interface TopicSummary {
  id: string;
  label: string;
  subtitle: string;
  asset: string;
  adapter: string;
  order: number;
  refresh_job: string | null;
  sections: Array<{
    id: string;
    label: string;
    kind: TopicSectionKind;
    anchor: string;
    order: number;
    enabled: boolean;
  }>;
}

export interface TopicListResponse {
  data: TopicSummary[];
  config_version: string;
}

export interface TopicMeta {
  topic_id: string;
  name: string;
  subtitle: string;
  asset: string;
  as_of: string | null;
  generated_at: string;
  config_version: string;
  adapter: string;
  refresh_job: string | null;
  status?: "ok" | "degraded" | "blocked" | "unknown";
  notes?: string[];
}

export interface TopicBadge {
  label: string;
  tone?: "up" | "down" | "flat" | "warn";
}

export interface TopicFactor {
  code: string;
  name: string;
  category?: string;
  category_label?: string;
  unit?: string;
  freq?: string;
  source?: string;
  weight: number;
  direction?: number;
  value: number | null;
  change?: number | null;
  score: number;
  contribution: number;
  signal: string;
  available: boolean;
  manual?: boolean;
  note?: string;
  explain?: string;
  as_of?: string | null;
  kind?: string;
  raw_score?: number | null;
}

export type TopicDriver = TopicFactor;

export interface TopicHero {
  score: number | null;
  label: string;
  coverage: number;
  available_weight: number;
  total_weight: number;
  conclusion: string;
  badges: TopicBadge[];
  drivers: TopicDriver[];
  score_0_100?: number | null;
}

export interface TopicKpi {
  key: string;
  label: string;
  value: number | string | null;
  unit?: string;
  tone?: string;
  note?: string;
  as_of?: string | null;
  digits?: number;
}

export interface TopicKpisData {
  items: TopicKpi[];
  regime?: Record<string, unknown> | null;
  text?: string;
}

export interface TopicFactorGroup {
  key: string;
  label: string;
  contribution: number;
  available: number;
  items: TopicFactor[];
}

export interface TopicFactorsData {
  groups: TopicFactorGroup[];
  factors: TopicFactor[];
  signals?: TopicFactor[];
}

export interface TopicChartSeries {
  name: string;
  values: Array<number | null>;
  type?: "line" | "bar" | "scatter";
  axis?: number;
  code?: string;
}

export interface TopicChartSpec {
  key: string;
  title: string;
  subtitle?: string;
  kind: "line" | "bar" | "candlestick" | "combo" | "scatter";
  unit?: string;
  height?: number;
  wide?: boolean;
  dates: string[];
  ohlc?: Array<Array<number | null>>;
  series?: TopicChartSeries[];
  bands?: {
    ok?: boolean;
    p10?: number | null;
    p25?: number | null;
    p50?: number | null;
    p75?: number | null;
    p90?: number | null;
  };
  marks?: Array<{ type: string; value: number; label?: string; color?: string }>;
  note?: string;
  emptyText?: string;
  hasData?: boolean;
}

export interface TopicChartsData {
  charts: TopicChartSpec[];
  series?: Record<string, Array<{ t: string; v: number }>>;
}

export interface TopicTableColumn {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  format?: "number" | "percent" | "money" | "date" | "text" | "signed";
  digits?: number;
  wrap?: boolean;
}

export interface TopicTableSpec {
  id?: string;
  title?: string;
  columns: TopicTableColumn[];
  rows: Array<Record<string, unknown>>;
  note?: string;
}

export interface TopicTableData {
  columns: TopicTableColumn[];
  rows: Array<Record<string, unknown>>;
  note?: string;
}

export interface TopicTablesData {
  tables: TopicTableSpec[];
  note?: string;
}

export interface TopicProvider {
  dataset?: string;
  provider: string;
  ok: boolean;
  records: number;
  error: string | null;
  checked_at: string | null;
}

export interface TopicManualMetric {
  code: string;
  name: string;
  category: string;
  unit: string;
  freq: string;
  source: string;
  weight: number;
  available: boolean;
  value: number | null;
  as_of: string | null;
  note: string;
}

export interface TopicSourcesData {
  providers: TopicProvider[];
  manual: TopicManualMetric[];
  manualEditable?: boolean;
}

export interface TopicDatasetHealth {
  name: string;
  rows: number;
  first?: string | null;
  last?: string | null;
  fresh: boolean;
  note?: string;
}

export interface TopicHealthData {
  datasets: TopicDatasetHealth[];
  gaps: string[];
  providers?: TopicProvider[];
  status?: string;
}

export interface TopicMethodologyData {
  text: string;
  caveats: string[];
  disclaimer: string;
}

export interface TopicBulletsData {
  title: string;
  items: string[];
}

export interface TopicScorecard {
  metric: string;
  value: number | null;
  unit?: string;
  pct_5y?: number | null;
  assessment: string;
  caveat?: string;
}

export interface TopicPeer {
  code: string;
  name: string;
  price?: number | null;
  pe_ttm?: number | null;
  pb?: number | null;
  market_cap_yi?: number | null;
  pct_chg?: number | null;
}

export interface TopicValuationHistory {
  dates: string[];
  fair: Array<number | null>;
  actual: Array<number | null>;
}

/** Gold fair-value model and Luoyang valuation share one loose container. */
export interface TopicValuationData {
  ok?: boolean;
  reason?: string;
  fair_value?: number | null;
  current_price?: number | null;
  gap_pct?: number | null;
  z_score?: number | null;
  percentile?: number | null;
  window?: number | null;
  real_yield?: number | null;
  beta?: number | null;
  history?: TopicValuationHistory;
  pe_ttm?: number | null;
  pb_mrq?: number | null;
  ps_ttm?: number | null;
  pe_percentile?: Record<string, { ok?: boolean; pct?: number | null; n?: number }>;
  pb_percentile?: Record<string, { ok?: boolean; pct?: number | null; n?: number }>;
  ps_percentile?: Record<string, { ok?: boolean; pct?: number | null; n?: number }>;
  pe_band_5y?: Record<string, number | null>;
  pb_band_5y?: Record<string, number | null>;
  scorecards?: TopicScorecard[];
  scorecard?: TopicScorecard[];
  peers?: TopicPeer[];
  relative?: Record<string, unknown>;
  fundamentals?: Record<string, unknown>;
  yearly_bands?: Array<Record<string, number | null>>;
  series?: {
    dates: string[];
    pe_ttm?: Array<number | null>;
    pb_mrq?: Array<number | null>;
    close?: Array<number | null>;
  };
  valuation_note?: string;
  as_of?: string;
}

export interface LuoyangScenario {
  label: string;
  prob: number;
  copper_price_yuan_t: number;
  np_2027e_yi: number;
  eps_2027e: number;
  bps_2027e: number;
  target_pe_band: number | null;
  target_pb_band: number | null;
  target_ev_ebitda: number | null;
  target_dcf: number | null;
  target_mid: number | null;
  target_range: Array<number | null>;
  upside_pct: number | null;
}

export interface TopicScenariosData {
  ok?: boolean;
  reason?: string;
  assumptions?: Record<string, unknown>;
  spot_cu?: number | null;
  cu_pct_5y?: number | null;
  shares_yi?: number | null;
  copper_sensitivity?: Record<string, unknown>;
  scenarios?: Partial<Record<"bear" | "base" | "bull", LuoyangScenario>>;
  weighted?: Record<string, number | null>;
  methods?: Array<{ name: string; weight: number | null }>;
  verdict?: Record<string, unknown>;
  copper_grid?: Array<Record<string, number | null>>;
  eps_source?: string;
}

export interface TopicTriggerSet {
  add_condition?: string;
  reduce_condition?: string;
  [key: string]: unknown;
}

export interface TopicPositionData {
  ok?: boolean;
  reason?: string;
  buy_price?: number | null;
  buy_date?: string | null;
  current_price?: number | null;
  price_date?: string | null;
  pnl_pct?: number | null;
  pnl_per_share?: number | null;
  total_return_pct_with_div?: number | null;
  dividend_2026_ps?: number | null;
  dividend_yield_on_cost_pct?: number | null;
  breakeven_price_price_only?: number | null;
  breakeven_price_with_div?: number | null;
  rally_needed_pct?: number | null;
  rally_needed_with_div_pct?: number | null;
  averaging_table?: Array<Record<string, number | null>>;
  score?: number | null;
  score_reasons?: string[];
  stance?: string;
  triggers?: TopicTriggerSet;
  scenario_expectation?: Record<string, unknown>;
  effective?: Partial<TopicPositionValues>;
  defaults?: Partial<TopicPositionValues>;
  overrides?: Partial<TopicPositionValues>;
  editable?: boolean;
}

export interface TopicEventRow {
  [key: string]: unknown;
  date: string;
  type: string;
  title: string;
  next_day?: number | null;
  five_day?: number | null;
  reaction?: {
    next_day_ret_pct?: number | null;
    ret_5d_pct?: number | null;
    next_date?: string | null;
  };
}

export interface TopicEventsData {
  columns: TopicTableColumn[];
  rows: TopicEventRow[];
  note?: string;
}

export type TopicSectionDataMap = {
  hero: TopicHero;
  kpis: TopicKpisData;
  factors: TopicFactorsData;
  charts: TopicChartsData;
  bullets: TopicBulletsData;
  table: TopicTableData | TopicTablesData;
  valuation: TopicValuationData;
  scenarios: TopicScenariosData;
  position: TopicPositionData;
  events: TopicEventsData;
  sources: TopicSourcesData;
  health: TopicHealthData;
  methodology: TopicMethodologyData;
};

export interface TopicSection<K extends TopicSectionKind = TopicSectionKind> {
  id: string;
  label: string;
  kind: K;
  anchor: string;
  order: number;
  data: TopicSectionDataMap[K];
}

export interface LuoyangVerdict {
  headline: string;
  driver: { headline: string; evidence: string[] };
  valuation: { headline: string; caveat: string };
  target: Record<string, unknown>;
  position: Record<string, unknown>;
  action: Record<string, unknown>;
  risk: string[];
}

export interface TopicOverview {
  meta: TopicMeta;
  hero: TopicHero;
  sections: TopicSection[];
  verdict?: LuoyangVerdict;
}

export interface TopicPositionValues {
  buy_price: number | null;
  buy_date: string | null;
  shares_lots: number | null;
  dividends: Array<{ date: string; per_share: number }>;
  add_prices: number[];
  add_ratios: number[];
}

export interface TopicPositionInput {
  buy_price?: number | null;
  buy_date?: string | null;
  shares_lots?: number | null;
  dividends?: Array<{ date: string; per_share: number }>;
  add_prices?: number[];
  add_ratios?: number[];
}

export interface TopicPositionResponse {
  topic_id: string;
  defaults: TopicPositionValues;
  overrides: Partial<TopicPositionValues>;
  effective: TopicPositionValues;
  editable: string[];
  updated_at: string | null;
}
