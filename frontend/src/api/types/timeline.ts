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
