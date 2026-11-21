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
