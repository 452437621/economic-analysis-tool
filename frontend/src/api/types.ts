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
  enabled: boolean;
  last_status: string | null;
  last_run_at: string | null;
  last_error: string | null;
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

