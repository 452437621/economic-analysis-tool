/** 后端 API 响应类型（与 backend/app/api 契约保持一致，2026-11 实测） */

export interface ApiMeta {
  asof?: string | null;
  count?: number;
  with_quote?: number;
  source?: string | null;
  delay_sec?: number;
}

export interface Envelope<T> {
  data: T;
  meta?: ApiMeta;
}

/* ---------- 系统 ---------- */

export interface SchedulerJob {
  id: string;
  next_run?: string | null;
}

export interface HealthCounts {
  instruments: number;
  quotes: number;
  market_bars: number;
  macro_observations: number;
  documents: number;
  document_bodies: number;
  claims: number;
  briefs: number;
  theses: number;
  trade_plans: number;
}

export interface Health {
  status: string;
  app: string;
  version: string;
  env: string;
  time_utc: string;
  time_local: string;
  timezone: string;
  database: { ok: boolean; engine: string; error: string | null };
  scheduler: { running: boolean; jobs: SchedulerJob[] };
  counts: HealthCounts;
  llm_enabled: boolean;
}

export interface JobRow {
  name: string;
  cron: string;
  description: string | null;
  enabled: boolean;
  last_status: string | null;
  last_run_at: string | null;
  last_error: string | null;
  run_count: number;
}

/** 任务执行历史（/api/system/job-runs）。 */
export interface JobRunRow {
  id: string;
  job_name: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  detail: string | null;
}

export interface SourceHealth {
  id: string;
  name: string;
  kind: string;
  tier: string | null;
  reliability: number | null;
  base_url: string | null;
  documents: number;
  last_ok: boolean | null;
  last_check: string | null;
  last_error: string | null;
}

export interface QualityRow {
  kind: string;
  dataset: string;
  symbol: string | null;
  check_date: string;
  expected: number | null;
  actual: number | null;
  deviation: number | null;
  passed: boolean;
  detail: string | null;
}

export interface QualityResponse {
  data: QualityRow[];
  summary: { total: number; passed: number; failed: number };
}

export interface AcceptanceCheck {
  name: string;
  passed: boolean;
  detail: unknown;
}

export interface Acceptance {
  passed: boolean;
  checks: AcceptanceCheck[];
  counts: Record<string, number>;
}

/* ---------- 市场 ---------- */

export interface SnapshotItem {
  symbol: string;
  name: string;
  asset_class: string;
  exchange: string | null;
  currency: string | null;
  unit?: string | null;
  contract_size?: number | null;
  price?: number | null;
  change_pct?: number | null;
  prev_close?: number | null;
  ts?: string | null;
  stale_sec?: number | null;
  delay_sec?: number | null;
  source?: string | null;
}

export interface SnapshotResponse {
  data: SnapshotItem[];
  meta: ApiMeta;
}

export interface Bar {
  ts: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  open_interest: number | null;
}

export interface BarsResponse {
  symbol: string;
  name: string;
  timeframe: string;
  data: Bar[];
}

export interface MacroLatestItem {
  code: string;
  name: string;
  unit: string;
  value: number;
  ts: string;
}

export interface MacroSeriesPoint {
  ts: string;
  value: number;
}

export interface MacroSeriesResponse {
  code: string;
  name: string;
  unit: string;
  data: MacroSeriesPoint[];
}

export interface PositionRow {
  product: string;
  name: string;
  long_pos: number;
  short_pos: number;
  net_pos: number;
  net_ratio: number | null;
  long_chg: number | null;
  short_chg: number | null;
}

export interface PositionsResponse {
  trade_date: string | null;
  data: PositionRow[];
}

export interface PositionMember {
  name: string;
  side: "long" | "short";
  rank: number;
  member: string;
  position: number;
  change: number;
}

export interface PositionMembersResponse {
  product: string;
  trade_date: string | null;
  data: PositionMember[];
}

export interface PositionProductsResponse {
  trade_date: string | null;
  data: Array<{ product: string; name: string }>;
}

export interface CalendarEvent {
  id: string;
  ts: string;
  name: string;
  category: string | null;
  country: string | null;
  importance: number;
}

export interface NewsItem {
  id: string;
  title: string;
  url: string;
  published_at: string;
  source: string | null;
  source_id?: string | null;
  tier: string | null;
  summary: string | null;
}

export interface EventItem {
  id: string;
  type: string;
  subtype: string | null;
  event_date: string;
  title: string;
  summary: string | null;
  impact?: number | null;
  instruments: string[];
  document_id?: string | null;
  document_ids?: string[];
}

export interface AlertItem {
  id: string;
  level: "critical" | "warn" | "info" | string;
  kind: string;
  title: string;
  message: string | null;
  acknowledged: boolean;
  created_at: string;
}

export interface AlertListResponse {
  data: AlertItem[];
  meta: { count: number; unread: number };
}

/* ---------- 自选 ---------- */

export interface WatchlistItem {
  symbol: string;
  name: string;
  asset_class: string;
  unit?: string | null;
  group: string | null;
  priority: number;
  sort_order: number;
  note: string | null;
  price: number | null;
  change_pct: number | null;
  quote_ts: string | null;
  change_20d: number | null;
  trend: string | null;
  /** 最近 30 根日线收盘价（仅总览聚合接口返回） */
  spark?: number[];
}

export interface WatchCandidate {
  symbol: string;
  name: string;
  asset_class: string;
  watched: boolean;
}

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
  raw_lots: number;
  contract_size: number;
  margin_pct: number;
  notional: number;
  margin: number;
  fee: number;
  equity: number;
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

/* ---------- 论点 ---------- */

export interface Scenario {
  name: string;
  probability: number;
  triggers: string | null;
  impacts: Record<string, unknown> | null;
}

export interface Thesis {
  id: string;
  title: string;
  direction: "long" | "short";
  prior: number;
  posterior: number;
  horizon_days: number;
  status: string;
  invalidation: string | null;
  main_driver: string | null;
  evidence_count: number;
  scenarios: Scenario[];
  created_at: string;
}

export interface ThesisReviewRecord {
  id: string;
  symbol: string | null;
  title: string;
  direction: string;
  status: string;
  return_pct: number | null;
  hit: boolean | null;
  since: string;
}

export interface ThesisReview {
  count: number;
  scored: number;
  hit_rate: number | null;
  avg_return_pct: number | null;
  records: ThesisReviewRecord[];
}

/* ---------- 简报 / 文档 / 日志 ---------- */

export interface BriefSummary {
  id: string;
  kind: string;
  trade_date: string;
  created_at: string;
  chars: number;
}

export interface Brief {
  id: string;
  kind: string;
  trade_date: string;
  created_at: string;
  markdown: string | null;
  meta: Record<string, unknown> | null;
}

export interface DocumentClaim {
  id: string;
  type: string;
  subject: string;
  predicate: string;
  value: string | number | null;
  unit: string | null;
  confidence: number;
  span: { start: number | null; end: number | null; quote: string | null };
}

export interface DocumentDetail {
  id: string;
  title: string;
  url: string | null;
  published_at: string | null;
  source: { name: string; tier: string } | null;
  status: string | null;
  body: {
    text: string | null;
    sha256: string | null;
    word_count: number | null;
    extracted_at: string | null;
  } | null;
  claims: DocumentClaim[];
}

export interface JournalEntry {
  id?: string;
  entry_date: string;
  content: string;
  created_at?: string;
}

export interface JournalEntryItem {
  id: string;
  entry_date: string;
  title: string;
  tags: string[];
  content: string;
  length: number;
  created_at: string;
  updated_at: string;
}

export interface JournalList {
  items: JournalEntryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface JournalInput {
  entry_date?: string;
  title?: string;
  tags?: string[];
  content: string;
}

/* ---------- 分页 / 查询（V1.2 新增后端接口） ---------- */

export interface PageMeta {
  count: number;
  total: number;
  offset: number;
  has_more?: boolean;
}

export interface NewsQuery {
  limit?: number;
  offset?: number;
  q?: string;
  source?: string;
  tier?: string;
  since_days?: number;
}

export interface NewsPage {
  data: NewsItem[];
  meta: PageMeta;
}

export interface EventQuery {
  limit?: number;
  offset?: number;
  type?: string;
  q?: string;
  instrument?: string;
}

export interface EventPage {
  data: EventItem[];
  meta: PageMeta;
}

export interface CalendarQuery {
  days?: number;
  limit?: number;
  offset?: number;
  country?: string;
  category?: string;
  importance_min?: number;
}

export interface CalendarPage {
  data: CalendarEvent[];
  meta: PageMeta & { days: number };
}

export interface BriefListMeta extends PageMeta {
  kinds: Record<string, number>;
}

export interface BriefListResponse {
  data: BriefSummary[];
  meta: BriefListMeta;
}

export interface BriefKindsResponse {
  data: {
    kinds: Record<string, number>;
    groups: { daily: number; weekly: number; monthly: number };
  };
}

export interface LatestBriefResponse {
  data: Brief | null;
  neighbors: { previous_id: string | null; next_id: string | null };
}

export interface WatchPatch {
  group?: string | null;
  priority?: number;
  note?: string | null;
}

/* ---------- 黄金监控（V1.3） ---------- */

export interface GoldFactor {
  code: string;
  name: string;
  category: string;
  category_label: string;
  unit: string;
  freq: string;
  source: string;
  weight: number;
  direction: number;
  value: number | null;
  change: number | null;
  score: number;
  contribution: number;
  signal: "bullish" | "bearish" | "neutral" | "unavailable" | string;
  available: boolean;
  manual: boolean;
  note: string;
  explain: string;
  as_of: string | null;
}

export interface GoldScore {
  score: number;
  label: string;
  coverage: number;
  available_weight: number;
  total_weight: number;
  factors: GoldFactor[];
  categories: Array<{ key: string; label: string; count: number }>;
  generated_at: string;
  methodology: string;
}

export interface GoldSeriesPoint {
  t: string;
  v: number;
}

export interface GoldProvider {
  provider: string;
  ok: boolean;
  records: number;
  error: string | null;
  checked_at: string | null;
}

export interface GoldManualIndicator {
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

export interface GoldIndicatorMeta {
  code: string;
  name: string;
  category: string;
  unit: string;
  freq: string;
  source: string;
  weight: number;
  direction: number;
  manual: boolean;
  note: string;
}

export interface GoldOverviewResponse {
  score: GoldScore;
  series: Record<string, GoldSeriesPoint[]>;
  providers: GoldProvider[];
  manual: GoldManualIndicator[];
  indicators: GoldIndicatorMeta[];
  categories: Array<{ key: string; label: string }>;
  generated_at: string;
}

export interface GoldSeriesResponse {
  code: string;
  name: string;
  unit: string;
  freq: string;
  source: string;
  data: GoldSeriesPoint[];
}


export interface OverviewAlert {
  id: string;
  level: string;
  kind: string;
  title: string;
  message: string | null;
  created_at: string | null;
}

export interface OverviewMacro {
  latest: MacroLatestItem[];
  sparks: Record<string, number[]>;
}

export interface OverviewResponse {
  asof: string | null;
  health: {
    status: string;
    version: string;
    env: string;
    llm_enabled: boolean;
    time_local: string;
    database: { ok: boolean; engine: string; error: string | null };
    scheduler: { running: boolean; jobs: SchedulerJob[] };
    counts: HealthCounts;
  };
  brief: Brief | null;
  snapshot: SnapshotResponse;
  watchlist: { data: WatchlistItem[] };
  macro: OverviewMacro;
  alerts: { unread: number; items: OverviewAlert[] };
  calendar: CalendarEvent[];
  jobs: {
    total: number;
    failed: number;
    scheduler_running: boolean;
    next_run: string | null;
  };
}

/* ---------- V2.0 玻璃盒（/api/v2） ---------- */

export interface V2Run {
  id: string;
  kind: string;
  subject: string;
  asof: string | null;
  status: "running" | "ok" | "degraded" | "failed" | string;
  method_id: string | null;
  code_version: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  degraded: boolean;
  degraded_reasons: Array<{ code: string; message: string; severity: string }>;
  summary: Record<string, unknown> | null;
  error: string | null;
}

export interface V2Step {
  id: string;
  seq: number;
  name: string;
  kind: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  inputs: Record<string, unknown> | null;
  outputs: Record<string, unknown> | null;
  params: Record<string, unknown> | null;
  error: string | null;
}

export interface V2RuleHit {
  rule_id: string;
  severity: string;
  fired: boolean;
  message: string | null;
  inputs: Record<string, unknown> | null;
  created_at: string | null;
}

export interface V2Derivation {
  id: string;
  run_id: string | null;
  code: string;
  subject: string;
  claim: string;
  value: Record<string, unknown> | null;
  confidence: number | null;
  evidence_grade: string;
  method_id: string | null;
  inputs: string[];
  steps: Array<Record<string, unknown>>;
  rules_hit: Array<Record<string, unknown>>;
  caveats: string[];
  falsifiers: string[];
  opposing: string[];
  asof: string | null;
  created_at: string | null;
}

export interface V2Method {
  method_id: string;
  name: string;
  version: string;
  kind: string;
  description: string | null;
  code_sha: string | null;
  params_schema: Record<string, unknown> | null;
}

export interface V2RunList {
  items: V2Run[];
  total: number;
  generated_at: string;
}

export interface V2RunDetail {
  run: V2Run;
  steps: V2Step[];
  rules: V2RuleHit[];
  derivations: V2Derivation[];
}

export interface V2DerivationList {
  items: V2Derivation[];
  total: number;
}

export interface V2DerivationDetail {
  derivation: V2Derivation;
  method: V2Method | null;
  parents: V2Derivation[];
  children: V2Derivation[];
}

export interface V2MethodList {
  items: V2Method[];
  total: number;
}

export interface V2Status {
  last_run: V2Run | null;
  counts: {
    runs: number;
    degraded: number;
    failed: number;
    derivations: number;
    observations: number;
    methods: number;
  };
  generated_at: string;
}

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

// ── V2.0 世界长河（1500–2026） ───────────────────────────────────────────────

export interface TimelineEventItem {
  id: string;
  year: number;
  month: number | null;
  title: string;
  category: string;
  category_label: string;
  layer: "L" | "B" | "S" | "E";
  layer_label: string;
  evidence_grade: "A" | "B" | "C";
  power: string | null;
  power_label: string | null;
  summary: string | null;
  source_url: string | null;
}

export interface TimelineEra {
  id: string;
  name: string;
  rise: number;
  peak: number;
  decline: number;
  reserve: string;
  innovation: string;
  lesson: string;
  grade: "A" | "B" | "C";
}

export interface TimelineLesson {
  id: string;
  name: string;
  mechanism: string;
  computable: string;
}

export interface TimelinePowerPoint {
  power: string;
  power_label: string;
  year: number;
  value: number;
  unit: string | null;
  evidence_grade: "A" | "B" | "C";
  source_url: string | null;
}

export interface TimelineDimension {
  dimension: string;
  anchor: string;
  current: string;
  judgment: string;
  cycle_key: string;
  grade: "A" | "B" | "C";
  value: number | null;
}

export interface TimelineAnalog {
  id: string;
  name: string;
  similarity: number;
  similar: string[];
  different: string[];
  grade: "D";
}

export interface TimelinePosition {
  code: string;
  claim: string;
  value: {
    dimensions: TimelineDimension[];
    analogs: TimelineAnalog[];
    cycle: {
      asof?: string | null;
      composites?: Record<string, { value: number; confidence: number }>;
      phase?: string;
      phase_id?: string;
      short_state?: string;
      liquidity?: string;
    } | null;
  };
  confidence: number | null;
  evidence_grade: string;
  asof: string | null;
  run_id: string | null;
  caveats: string[];
  falsifiers: string[];
  opposing: string[];
}

export interface TimelineCounts {
  events: number;
  eras: number;
  lessons: number;
  grades: Record<string, number>;
  layers: Record<string, number>;
}

export interface TimelineOverview {
  generated_at: string;
  asof: string | null;
  run_id: string | null;
  status: string | null;
  degraded: boolean;
  degraded_reasons: Array<{ code: string; message: string }>;
  counts: TimelineCounts;
  eras: TimelineEra[];
  events: TimelineEventItem[];
  powers: { gdp: TimelinePowerPoint[]; reserve: TimelinePowerPoint[] };
  position: TimelinePosition | null;
  lessons: TimelineLesson[];
  labels: {
    categories: Record<string, string>;
    layers: Record<string, string>;
    powers: Record<string, string>;
  };
}

export interface TimelineRunResult {
  ok: boolean;
  run_id: string;
  status: string;
  events: number;
  eras: number;
  lessons: number;
  cycle_found: boolean;
}

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
  degraded_reasons: string[];
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

export interface CoverageResponse {
  data_quality_pct: number;
  series_covered: number;
  series_total: number;
  last_sync: string | null;
  jobs_ok: number;
  jobs_total: number;
  as_of: string | null;
  method: string;
}

/* ---------- 中文对照（英文事件 / 新闻 / 文档摘要） ---------- */

/** 译文来源：seed=仓库内人工语料，cache=运行期缓存，llm=本次自动翻译，none=未命中 */
export type TranslateSource = "seed" | "cache" | "llm" | "none";

export interface TranslateItem {
  hash: string;
  text: string;
  zh: string | null;
  source: TranslateSource;
}

export interface TranslateResponse {
  items: TranslateItem[];
  total: number;
  translated: number;
  missing: number;
}

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
  profit_factor: number;
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

// ── 双透镜（美联储主席 / 宋鸿兵）─────────────────────────────────────
export type LensTab = "synthesis" | "fed" | "song" | "evidence";
export type LensEvidence = "E0" | "E1" | "E2" | "E3" | "E4";

export interface LensReading {
  id: string;
  label: string;
  value: number | null;
  unit: string;
  digits: number;
  asof: string | null;
  change: number | null;
  change_label: string;
  z: number | null;
  percentile: number | null;
  source: string;
  evidence: string;
  note: string;
  missing_reason: string | null;
}

export interface LensScore {
  score: number | null;
  label: string;
  why: string;
}

export interface LensFedState {
  stance: number | null;
  stance_label: string;
  stance_components: Array<{ label: string; percentile: number | null; weight: number }>;
  regime: { id: string; label: string; note: string };
  fed_put: {
    id: string;
    label: string;
    drawdown: number | null;
    note: string;
    strike: number | null;
    spot: number | null;
    distance_pct: number | null;
  };
  policy: { bias: string; cut_probability_3m: number | null };
  asset_scores: Record<string, LensScore>;
  narrative: string;
  coverage: { available: number; total: number };
}

export interface LensSongState {
  phase: { id: string; label: string; note: string };
  dollar_heart: { id: string; label: string; level_bp: number | null; spike_bp: number | null; note: string };
  harvest_risk: number | null;
  debt_risk: number | null;
  gold_regime: { id: string; label: string; note: string };
  asset_scores: Record<string, LensScore>;
  narrative: string;
  coverage: { available: number; total: number };
}

export interface LensAsset {
  id: string;
  label: string;
  symbol: string;
  unit: string;
  note: string;
  last: number | null;
  fed: number | null;
  song: number | null;
  consensus: number | null;
  label_consensus: string;
  agreement: string;
  direction: "up" | "down" | "flat";
  probability: number | null;
  advice: string;
}

export interface LensWarning {
  id: string;
  severity: "info" | "watch" | "warn" | "critical";
  title: string;
  detail: string;
}

export interface LensDivergence {
  asset: string;
  label: string;
  fed: number | null;
  song: number | null;
  spread: number | null;
  reading: string;
  catalyst: string;
}

export interface LensOutlook {
  horizon_days: number;
  base_case: string;
  bull_case: string;
  bear_case: string;
  triggers: LensWarning[];
  invalidators: string[];
}

export interface LensCycleContext {
  asof: string | null;
  long_cycle?: { phase: string; phase_id: string; score: number | null; meaning: string };
  short_cycle?: { state: string; state_name?: string };
  liquidity?: { state: string; value: number | null };
  political?: { window: string } | null;
}

export interface LensDerivation {
  id: string;
  code: string;
  claim: string;
  value: Record<string, unknown>;
  confidence: number | null;
  evidence_grade: string;
  asof: string | null;
  run_id: string | null;
  method_id: string | null;
  inputs: string[];
  steps: Array<Record<string, unknown>>;
  rules_hit: Array<{ id: string; message: string; severity: string }>;
  caveats: string[];
  falsifiers: string[];
  opposing: string[];
}

export interface LensRule {
  id: string;
  name: string;
  severity: "info" | "watch" | "warn" | "critical";
  fired: boolean;
  status: "fired" | "miss" | "unknown";
  message: string;
  falsifier: string | null;
  assets: string[];
  sources: string[];
  trace: Array<{ condition: string; met: boolean }>;
}

export interface LensSynthesis {
  assets: LensAsset[];
  divergences: LensDivergence[];
  warnings: LensWarning[];
  consensus_count: number;
  narrative: string;
  outlook: LensOutlook;
  cycle_context: LensCycleContext;
  confidence: number | null;
  derivation: LensDerivation;
}

export interface LensStateResponse {
  asof: string | null;
  run: {
    id: string;
    status: string;
    asof: string | null;
    finished_at: string | null;
    degraded: boolean;
    degraded_reasons: Array<{ code: string; message: string; severity?: string }>;
    summary: Record<string, unknown>;
    duration_ms: number | null;
  } | null;
  fed: {
    state: LensFedState;
    readings: LensReading[];
    catalog: string[];
    coverage: { available: number; total: number };
    derivation: LensDerivation;
    method_id: string | null;
  };
  song: {
    state: LensSongState;
    readings: LensReading[];
    catalog: string[];
    coverage: { available: number; total: number };
    derivation: LensDerivation;
    method_id: string | null;
  };
  synthesis: LensSynthesis;
  rules: { fed: LensRule[]; song: LensRule[] };
  data_gaps: Array<{ id: string; label: string; reason: string; impact: string }>;
  disclaimer: string;
  config_version: string | null;
  confidence: number | null;
  evidence_grade: string;
}

export interface LensForecast {
  id: string;
  code: string;
  asset: string;
  subject: string;
  direction: "up" | "down" | "flat";
  horizon_days: number;
  made_at: string | null;
  target_date: string | null;
  probability: number | null;
  point: number | null;
  status: string;
  baseline_value: number | null;
  notes: string | null;
  derivation_id: string | null;
}

export interface LensForecastList {
  items: LensForecast[];
  open: LensForecast[];
  resolved: LensForecast[];
}

export interface LensForecastCode {
  code: string;
  asset: string;
  label: string;
  symbol: string;
}

export interface LensPing {
  available: boolean;
  model: string;
  budget_usd: number;
  hint: string | null;
}

export interface LensCommentary {
  text: string;
  model: string;
  cached: boolean;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}
