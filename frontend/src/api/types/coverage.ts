/* ---------- 数据覆盖 ---------- */

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
