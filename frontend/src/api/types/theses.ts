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
