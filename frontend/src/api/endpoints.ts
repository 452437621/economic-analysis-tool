/** 所有后端端点封装（契约见 backend/app/api）。 */
import { deleteJson, getJson, patchJson, postJson } from "./client";
import type {
  Acceptance,
  AlertItem,
  AnalyticsOverview,
  BarsResponse,
  Brief,
  BriefSummary,
  CalendarEvent,
  DecisionsReview,
  DecisionsSummary,
  DocumentDetail,
  EventItem,
  Health,
  JobRow,
  JournalEntry,
  MacroLatestItem,
  MacroSeriesResponse,
  NewsItem,
  PositionMembersResponse,
  PositionsResponse,
  QualityResponse,
  SnapshotResponse,
  SourceHealth,
  Thesis,
  ThesisReview,
  TradePlan,
  WatchCandidate,
  WatchlistItem,
} from "./types";

/* 系统 */
export const getHealth = () => getJson<Health>("/api/system/health");
export const getJobs = () => getJson<{ data: JobRow[] }>("/api/system/jobs");
export const getSources = () => getJson<{ data: SourceHealth[] }>("/api/system/sources");
export const getQuality = () => getJson<QualityResponse>("/api/system/data-quality");
export const getAcceptance = () => getJson<Acceptance>("/api/system/acceptance");

/* 市场 */
export const getSnapshot = () => getJson<SnapshotResponse>("/api/market/snapshot");
export const getBars = (symbol: string, timeframe = "1d", limit = 3000) =>
  getJson<BarsResponse>("/api/market/bars", { params: { symbol, timeframe, limit } });
export const getMacroLatest = () => getJson<{ data: MacroLatestItem[] }>("/api/macro/latest");
export const getMacroSeries = (code: string, limit = 5000) =>
  getJson<MacroSeriesResponse>("/api/macro/series", { params: { code, limit } });
export const getPositions = () => getJson<PositionsResponse>("/api/positions");
export const getPositionMembers = (product: string, limit = 20) =>
  getJson<PositionMembersResponse>("/api/positions/members", { params: { product, limit } });
export const getCalendar = (days = 14, limit = 20) =>
  getJson<{ data: CalendarEvent[] }>("/api/calendar", { params: { days, limit } });
export const getNews = (limit = 12) => getJson<{ data: NewsItem[] }>("/api/news", { params: { limit } });
export const getEvents = (limit = 12) => getJson<{ data: EventItem[] }>("/api/events", { params: { limit } });

/* 自选 */
export const getWatchlist = () => getJson<{ data: WatchlistItem[] }>("/api/watchlist");
export const getWatchCandidates = () =>
  getJson<{ data: WatchCandidate[] }>("/api/watchlist/candidates");
export const addWatch = (payload: { symbol: string; group?: string | null; priority?: number }) =>
  postJson<{ ok: boolean }>("/api/watchlist", payload);
export const removeWatch = (symbol: string) =>
  deleteJson<{ ok: boolean }>(`/api/watchlist/${encodeURIComponent(symbol)}`);
export const moveWatch = (symbol: string, direction: "up" | "down") =>
  postJson<{ ok: boolean }>(`/api/watchlist/${encodeURIComponent(symbol)}/move`, { direction });
export const reorderWatch = (symbols: string[]) =>
  postJson<{ ok: boolean }>("/api/watchlist/reorder", { symbols });

/* 分析 */
export const getAnalytics = () => getJson<AnalyticsOverview>("/api/analytics/overview");

/* 决策 */
export const getDecisions = () => getJson<DecisionsSummary>("/api/decisions/summary");
export const getDecisionsReview = () =>
  getJson<{ data: DecisionsReview }>("/api/decisions/review");
export const getPlans = () => getJson<{ data: TradePlan[] }>("/api/decisions/plans");

/* 论点 */
export const getTheses = (limit = 20) =>
  getJson<{ data: Thesis[] }>("/api/theses", { params: { limit } });
export const getThesisReview = () => getJson<{ data: ThesisReview }>("/api/theses/review");
export const updateThesisStatus = (id: string, status: string) =>
  patchJson<{ id: string; status: string }>(`/api/theses/${id}`, { status });

/* 简报 / 文档 */
export const getLatestBrief = (kind?: "daily" | "weekly" | "monthly") =>
  getJson<{ data: Brief | null }>("/api/briefs/latest", {
    params: kind && kind !== "daily" ? { kind } : undefined,
  });
export const getBriefs = (limit = 10) =>
  getJson<{ data: BriefSummary[] }>("/api/briefs", { params: { limit } });
export const getDocument = (id: string) =>
  getJson<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}`);

/* 告警 */
export const getAlerts = (limit = 10) =>
  getJson<{ data: AlertItem[] }>("/api/alerts", { params: { limit } });
export const ackAlert = (id: string) =>
  postJson<{ ok: boolean }>(`/api/alerts/${encodeURIComponent(id)}/ack`, {});

/* 日志 */
export const getJournal = (limit = 5) =>
  getJson<{ data: JournalEntry[] }>("/api/journal", { params: { limit } });
export const saveJournal = (content: string) => postJson<JournalEntry>("/api/journal", { content });

/* 下载链接 */
export const briefPrintUrl = (id: string) => `/api/briefs/${id}/print`;
export const briefMarkdownUrl = (id: string) => `/api/briefs/${id}/markdown`;
