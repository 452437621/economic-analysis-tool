import type { ApiMeta } from "./common";

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
