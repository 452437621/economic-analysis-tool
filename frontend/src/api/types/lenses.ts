// ── 多透镜研判（美联储 / 宋鸿兵 / 宏观层 / 微观层 / 九位思想者）────────
export type LensTab = "synthesis" | "fed" | "song" | "layers" | "personas" | "evidence";
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

/** 单资产的决策说明：止损、风险预算与仓位权重（与账户余额无关）。 */
export interface LensAssetPlan {
  actionable: boolean;
  side: "long" | "short" | "flat";
  side_label: string;
  stop_pct: number;
  stop_level: number | null;
  stop_note: string;
  weight_pct: number;
  risk_pct: number;
  risk_at_pct: number;
  vol_pct: number | null;
  atr_pct: number | null;
  rationale: string;
}

/** 组合层：总敞口、多空、现金与组合风险。 */
export interface LensPortfolio {
  basis: string;
  gross_weight_pct: number;
  long_weight_pct: number;
  short_weight_pct: number;
  net_weight_pct: number;
  cash_weight_pct: number;
  portfolio_risk_pct: number;
  max_loss_pct: number;
  positions: Array<{
    asset: string;
    label: string;
    side: "long" | "short";
    side_label: string;
    weight_pct: number;
    risk_pct: number;
    stop_pct: number;
    stop_level: number | null;
  }>;
  scale_applied: number;
  rules: string[];
  note: string;
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
  scores?: Record<string, number>;
  lenses?: number;
  consensus: number | null;
  label_consensus: string;
  agreement: string;
  direction: "up" | "down" | "flat";
  probability: number | null;
  advice: string;
  plan?: LensAssetPlan;
}

/** 宏观层：增长 / 通胀 / 流动性 / 财政 / 融资 / 美元 / 曲线 */
export interface LensMacroState {
  regime: { id: string; label: string; note: string };
  liquidity: { value: number | null; label: string };
  fiscal: { value: number | null; label: string };
  funding: { value: number | null; label: string };
  flags: string[];
  narrative: string;
  coverage: { available: number; total: number };
}

/** 微观层：价格结构 / 实物紧张 / 拥挤度 */
export interface LensMicroState {
  risk_appetite: { id?: string; label: string; value?: number | null };
  gold_micro: number | null;
  crowding: string[];
  narrative: string;
  coverage: { available: number; total: number };
}

/** 人物透镜（9 位）：来自 config/personas/*.yaml */
export interface LensPersona {
  id: string;
  name: string;
  title?: string | null;
  school?: string | null;
  key_question?: string | null;
  thesis?: string | null;
  state: {
    lean: { score: number; label: string };
    coverage: { available: number; total: number };
    fired_rules: string[];
    critical_rules?: string[];
    key_readings?: Array<Record<string, unknown>>;
    narrative: string;
  };
  readings?: LensReading[];
  catalog?: Array<Record<string, unknown>>;
  scores?: Record<string, LensScore>;
  coverage?: { available: number; total: number };
  derivation?: LensDerivation;
  method_id?: string | null;
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
  portfolio?: LensPortfolio;
  divergences: LensDivergence[];
  warnings: LensWarning[];
  consensus_count: number;
  strong_count?: number;
  lens_count?: number;
  weights?: Record<string, number>;
  headline?: Record<string, unknown>;
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
    scores?: Record<string, LensScore>;
    derivation: LensDerivation;
    method_id: string | null;
  };
  song: {
    state: LensSongState;
    readings: LensReading[];
    catalog: string[];
    coverage: { available: number; total: number };
    scores?: Record<string, LensScore>;
    derivation: LensDerivation;
    method_id: string | null;
  };
  macro: {
    state: LensMacroState;
    readings: LensReading[];
    catalog: Array<Record<string, unknown>>;
    coverage: { available: number; total: number };
    scores?: Record<string, LensScore>;
    derivation?: LensDerivation;
    method_id?: string | null;
  } | null;
  micro: {
    state: LensMicroState;
    readings: LensReading[];
    catalog: Array<Record<string, unknown>>;
    coverage: { available: number; total: number };
    scores?: Record<string, LensScore>;
    derivation?: LensDerivation;
    method_id?: string | null;
  } | null;
  personas: LensPersona[];
  synthesis: LensSynthesis;
  portfolio?: LensPortfolio | null;
  rules: {
    fed: LensRule[];
    song: LensRule[];
    macro?: LensRule[];
    micro?: LensRule[];
    personas?: Record<string, LensRule[]>;
  };
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
