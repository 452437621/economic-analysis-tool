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
  group?: string | null;
  period_seconds?: number | null;
  due_at?: string | null;
  overdue?: boolean;
  action?: string | null;
  overdue_reason?: string | null;
  depends_on?: string[];
  critical?: boolean;
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
  enabled?: boolean;
  latency_ms?: number | null;
  last_success?: string | null;
  consecutive_failures?: number;
  success_rate_24h?: number | null;
  checks_24h?: number;
  cooldown_until?: string | null;
  status?: string;
  roles?: string[];
  domains?: string[];
  chains?: string[];
}

export interface SourceChainCandidate {
  source: string;
  role: string;
  tier: string | null;
  reliability: number | null;
  healthy: boolean;
  cooldown_until: string | null;
  consecutive_failures: number;
  success_rate_24h: number | null;
  last_success: string | null;
}

export interface SourceChain {
  id: string;
  domain: string;
  title: string;
  critical: boolean;
  single_source: boolean;
  action_job: string;
  status: string;
  last_used: string | null;
  last_success: string | null;
  last_provider: string | null;
  candidates: SourceChainCandidate[];
}

export interface SourcesResponse {
  data: SourceHealth[];
  chains: SourceChain[];
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
  severity?: string | null;
  cause?: string | null;
  impact?: string | null;
  remediation?: string | null;
  action_job?: string | null;
}

export interface QualityResponse {
  data: QualityRow[];
  summary: {
    total: number;
    passed: number;
    failed: number;
    unknown?: number;
    by_severity?: Record<string, number>;
  };
  batch_id?: string | null;
  checked_at?: string | null;
  age_seconds?: number | null;
  stale?: boolean;
  repair?: { jobs: string[]; last_run: unknown };
}

export interface AcceptanceCheck {
  name: string;
  passed: boolean;
  detail: unknown;
  id?: string;
  category?: string;
  status?: string;
  severity?: string;
  required?: number | string | boolean | null;
  actual?: number | string | null;
  reason?: string | null;
  impact?: string | null;
  remediation?: string | null;
  action_job?: string | null;
}

export interface Acceptance {
  passed: boolean;
  checks: AcceptanceCheck[];
  counts: Record<string, number>;
  status?: string;
  failed_summary?: {
    count: number;
    failed: AcceptanceCheck[];
    hints: string[];
  };
  warnings_summary?: { count: number; warnings: string[] };
  generated_at?: string;
}

export interface ScheduleJobRow {
  name: string;
  group: string;
  cron: string;
  period_seconds: number | null;
  last_run_at: string | null;
  due_at: string | null;
  overdue: boolean;
  late_seconds: number;
  action: string;
  reason: string | null;
  depends_on: string[];
  critical: boolean;
  data_requirements: string[];
  enabled: boolean;
  running: boolean;
}

export interface ScheduleResponse {
  as_of: string;
  timezone: string;
  summary: { total: number; overdue: number; disabled: number; running: number };
  jobs: ScheduleJobRow[];
}

export interface ScheduleCheckReport {
  status?: string;
  trigger?: string;
  readiness?: {
    status: string;
    reasons: Array<{ code: string; severity: string; message: string; action_job?: string }>;
    datasets?: Record<string, unknown>;
  };
  jobs?: Array<Record<string, unknown>>;
  blocked?: Array<Record<string, unknown>>;
  retries?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface ScheduleCheckRow {
  id: string;
  trigger: string;
  status: string;
  data_status: string | null;
  started_at: string | null;
  finished_at: string | null;
  report: ScheduleCheckReport | null;
  error: string | null;
}

export interface QualityGate {
  status: string;
  score: number;
  factor: number;
  allow_action: boolean;
  caveat: string | null;
  batch_id: string | null;
  batch_age_seconds: number | null;
  reasons: Array<{
    code: string;
    severity: string;
    message: string;
    impact?: string | null;
    remediation?: string | null;
    action_job?: string | null;
  }>;
  stale_datasets: string[];
  components: Record<string, unknown>;
}
