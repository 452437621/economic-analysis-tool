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
