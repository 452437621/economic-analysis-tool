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
