import type { CalendarEvent, EventItem, NewsItem } from "./market";

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

export interface JournalEntryItem {
  id: string;
  entry_date: string;
  title: string;
  tags: string[];
  content: string;
  length: number;
  created_at: string;
  updated_at: string;
}

export interface JournalList {
  items: JournalEntryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface JournalInput {
  entry_date?: string;
  title?: string;
  tags?: string[];
  content: string;
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
