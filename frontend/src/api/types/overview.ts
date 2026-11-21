import type { Brief } from "./knowledge";
import type { CalendarEvent, MacroLatestItem, SnapshotResponse } from "./market";
import type { HealthCounts, SchedulerJob } from "./system";
import type { WatchlistItem } from "./watchlist";

/* ---------- 总览 ---------- */

export interface OverviewAlert {
  id: string;
  level: string;
  kind: string;
  title: string;
  message: string | null;
  created_at: string | null;
}

export interface OverviewMacro {
  latest: MacroLatestItem[];
  sparks: Record<string, number[]>;
}

export interface OverviewResponse {
  asof: string | null;
  health: {
    status: string;
    version: string;
    env: string;
    llm_enabled: boolean;
    time_local: string;
    database: { ok: boolean; engine: string; error: string | null };
    scheduler: { running: boolean; jobs: SchedulerJob[] };
    counts: HealthCounts;
  };
  brief: Brief | null;
  snapshot: SnapshotResponse;
  watchlist: { data: WatchlistItem[] };
  macro: OverviewMacro;
  alerts: { unread: number; items: OverviewAlert[] };
  calendar: CalendarEvent[];
  jobs: {
    total: number;
    failed: number;
    scheduler_running: boolean;
    next_run: string | null;
  };
}
