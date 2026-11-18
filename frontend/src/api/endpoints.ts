/** 所有后端端点封装（契约见 backend/app/api）。 */
import { deleteJson, getJson, patchJson, postJson } from "./client";
import type {
  CoverageResponse,
  CycleReadingsResponse,
  Acceptance,
  AlertItem,
  AlertListResponse,
  AnalyticsOverview,
  BarsResponse,
  Brief,
  BriefKindsResponse,
  BriefListResponse,
  BriefSummary,
  CalendarEvent,
  CalendarPage,
  CalendarQuery,
  DecisionsReview,
  DecisionsSummary,
  DocumentDetail,
  EventItem,
  EventPage,
  EventQuery,
  GoldOverviewResponse,
  GoldSeriesResponse,
  Health,
  JobRow,
  JobRunRow,
  JournalEntry,
  JournalEntryItem,
  JournalInput,
  JournalList,
  LatestBriefResponse,
  MacroLatestItem,
  MacroSeriesResponse,
  NewsItem,
  NewsPage,
  NewsQuery,
  OverviewResponse,
  PositionMembersResponse,
  PositionProductsResponse,
  PositionsResponse,
  QualityResponse,
  SnapshotResponse,
  SourceHealth,
  Thesis,
  ThesisReview,
  TradePlan,
  TradeAssetClass,
  TradeDirection,
  TradeInput,
  TradeItem,
  TradeList,
  TradeStats,
  TradeStatus,
  TradeSummary,
  V2DerivationDetail,
  V2DerivationList,
  V2MethodList,
  V2RunDetail,
  V2RunList,
  V2Status,
  CycleConfigResponse,
  CycleIndicatorsResponse,
  LedgerCalibration,
  LedgerCounts,
  LedgerForecastInput,
  LedgerForecastList,
  LedgerOverview,
  LedgerPrincipleItem,
  LedgerRunResult,
  CycleRunResult,
  CycleStateResponse,
  TimelineEventItem,
  TimelineOverview,
  TimelineRunResult,
  TranslateResponse,
  WatchCandidate,
  WatchlistItem,
  WatchPatch,
} from "./types";


/* 系统 */
export const getHealth = () => getJson<Health>("/api/system/health");
export const getJobs = () => getJson<{ data: JobRow[] }>("/api/system/jobs");
export const getJobRuns = (jobName: string, limit = 50) =>
  getJson<{ data: JobRunRow[] }>(
    `/api/system/job-runs?job_name=${encodeURIComponent(jobName)}&limit=${limit}`,
  );
export const getSources = () => getJson<{ data: SourceHealth[] }>("/api/system/sources");
export const getQuality = () => getJson<QualityResponse>("/api/system/data-quality");
export const getAcceptance = () => getJson<Acceptance>("/api/system/acceptance");

/* 总览聚合（单请求） */
export const getOverview = () => getJson<OverviewResponse>("/api/overview");

/* 市场 */
export const getSnapshot = () => getJson<SnapshotResponse>("/api/market/snapshot");
export const getBars = (symbol: string, timeframe = "1d", limit = 3000) =>
  getJson<BarsResponse>("/api/market/bars", { params: { symbol, timeframe, limit } });
export const getMacroLatest = () => getJson<{ data: MacroLatestItem[] }>("/api/macro/latest");
export const getMacroSeries = (code: string, limit = 5000) =>
  getJson<MacroSeriesResponse>("/api/macro/series", { params: { code, limit } });
export const getPositions = () => getJson<PositionsResponse>("/api/positions");
export const getPositionProducts = () =>
  getJson<PositionProductsResponse>("/api/positions/products");
export const getPositionMembers = (product: string, limit = 20) =>
  getJson<PositionMembersResponse>("/api/positions/members", { params: { product, limit } });

/* 日历 / 新闻 / 事件：保留旧的按数量调用，新增带筛选的查询 */
function toParams(value: object): Record<string, string | number | boolean | undefined | null> {
  return value as unknown as Record<string, string | number | boolean | undefined | null>;
}

export function getCalendar(days?: number, limit?: number): Promise<{ data: CalendarEvent[] }>;
export function getCalendar(query: CalendarQuery): Promise<CalendarPage>;
export function getCalendar(
  daysOrQuery: number | CalendarQuery = 14,
  limitArg = 20,
): Promise<{ data: CalendarEvent[] } | CalendarPage> {
  const params =
    typeof daysOrQuery === "number"
      ? { days: daysOrQuery, limit: limitArg }
      : toParams(daysOrQuery);
  return getJson<CalendarPage>("/api/calendar", { params });
}

export function getNews(limit?: number): Promise<{ data: NewsItem[] }>;
export function getNews(query: NewsQuery): Promise<NewsPage>;
export function getNews(limitOrQuery: number | NewsQuery = 12): Promise<{ data: NewsItem[] } | NewsPage> {
  const params = typeof limitOrQuery === "number" ? { limit: limitOrQuery } : toParams(limitOrQuery);
  return getJson<NewsPage>("/api/news", { params });
}

export function getEvents(limit?: number): Promise<{ data: EventItem[] }>;
export function getEvents(query: EventQuery): Promise<EventPage>;
export function getEvents(
  limitOrQuery: number | EventQuery = 12,
): Promise<{ data: EventItem[] } | EventPage> {
  const params = typeof limitOrQuery === "number" ? { limit: limitOrQuery } : toParams(limitOrQuery);
  return getJson<EventPage>("/api/events", { params });
}


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
export const updateWatch = (symbol: string, patch: WatchPatch) =>
  patchJson<{ symbol: string; saved: boolean }>(
    `/api/watchlist/${encodeURIComponent(symbol)}`,
    patch,
  );

/* 黄金监控（V1.3） */
export const getGoldOverview = (seriesLimit = 2500) =>
  getJson<GoldOverviewResponse>("/api/gold/overview", { params: { series_limit: seriesLimit } });
export const getGoldSeries = (code: string, limit = 240) =>
  getJson<GoldSeriesResponse>("/api/gold/series", { params: { code, limit } });
export const refreshGold = () => postJson<{ accepted: boolean }>("/api/gold/refresh", {});
export const saveGoldMetric = (payload: {
  code: string;
  value: number;
  as_of?: string;
  source?: string;
  note?: string;
}) => postJson<{ saved: boolean }>("/api/gold/metrics", payload);

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

/* 中文对照：英文事件 / 新闻标题与摘要 → 简体中文（本地语料优先，LLM 兜底） */
export const translateTexts = (texts: string[]) =>
  postJson<TranslateResponse>("/api/knowledge/translate", { texts });

/* 简报 / 文档 */
export const getLatestBrief = (kind?: "daily" | "weekly" | "monthly") =>
  getJson<LatestBriefResponse>("/api/briefs/latest", {
    params: kind ? { kind } : undefined,
  });
export const getBriefList = (kind?: "daily" | "weekly" | "monthly", limit = 20, offset = 0) =>
  getJson<BriefListResponse>("/api/briefs", { params: { kind, limit, offset } });
export const getBriefKinds = () => getJson<BriefKindsResponse>("/api/briefs/kinds");
export const getBrief = (id: string) => getJson<Brief>(`/api/briefs/${encodeURIComponent(id)}`);
export const getBriefs = (limit = 10) =>
  getJson<{ data: BriefSummary[] }>("/api/briefs", { params: { limit } });
export const getDocument = (id: string) =>
  getJson<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}`);

/* 告警 */
export const getAlerts = (limit = 10) =>
  getJson<AlertListResponse>("/api/alerts", { params: { limit } });
export const ackAlert = (id: string) =>
  postJson<{ ok: boolean }>(`/api/alerts/${encodeURIComponent(id)}/ack`, {});

/* 日志 */
export interface JournalQuery {
  limit?: number;
  offset?: number;
  q?: string;
  date_from?: string;
  date_to?: string;
}

export const listJournal = (query: JournalQuery = {}) =>
  getJson<JournalList>("/api/journal", { params: query as Record<string, string | number | undefined> });
export const getJournalEntry = (id: string) => getJson<JournalEntryItem>(`/api/journal/${id}`);
export const createJournal = (payload: JournalInput) =>
  postJson<{ item: JournalEntryItem; created: boolean }>("/api/journal", payload);
export const updateJournal = (id: string, payload: Partial<JournalInput>) =>
  patchJson<JournalEntryItem>(`/api/journal/${id}`, payload);
export const deleteJournal = (id: string) => deleteJson<{ ok: boolean }>(`/api/journal/${id}`);

/* 下载链接 */
export const briefPrintUrl = (id: string) => `/api/briefs/${id}/print`;
export const briefMarkdownUrl = (id: string) => `/api/briefs/${id}/markdown`;

/* 玻璃盒（V2.0 M0） */
export const getV2Status = () => getJson<V2Status>("/api/v2/status");
export const getV2Runs = (params: { kind?: string; subject?: string; limit?: number } = {}) =>
  getJson<V2RunList>("/api/v2/runs", { params });
export const getV2Run = (runId: string) =>
  getJson<V2RunDetail>(`/api/v2/runs/${encodeURIComponent(runId)}`);
export const getV2Derivations = (params: { code?: string; subject?: string; limit?: number } = {}) =>
  getJson<V2DerivationList>("/api/v2/derivations", { params });
export const getV2Derivation = (derivationId: string) =>
  getJson<V2DerivationDetail>(`/api/v2/derivations/${encodeURIComponent(derivationId)}`);
export const getV2Methods = () => getJson<V2MethodList>("/api/v2/methods");

/* 周期引擎（V2.0 M2） */
export const getCycleState = () => getJson<CycleStateResponse>("/api/v2/cycle/state");
export const getCycleConfig = () => getJson<CycleConfigResponse>("/api/v2/cycle/config");
export const runCycle = () => postJson<CycleRunResult>("/api/v2/cycle/run", {});
export const getCycleReadings = () => getJson<CycleReadingsResponse>("/api/v2/cycle/readings");
/** 32 条指标的明细（evidence / source / stale_days / degraded / degrade_reason） */
export const getCycleIndicators = () =>
  getJson<CycleIndicatorsResponse>("/api/v2/cycle/indicators");

/* 世界长河（V2.0 M3） */
export const getTimelineOverview = () => getJson<TimelineOverview>("/api/v2/timeline/overview");
export const getTimelineEvents = (params: { layer?: string; q?: string; era?: string } = {}) =>
  getJson<{ items: TimelineEventItem[]; total: number }>("/api/v2/timeline/events", { params });
export const runTimeline = () => postJson<TimelineRunResult>("/api/v2/timeline/run", {});

/* 台账（V2.0 M4）：原则库核对与预测台账 */
export const getLedgerOverview = () => getJson<LedgerOverview>("/api/v2/ledger/overview");
export const getLedgerPrinciples = () =>
  getJson<{ asof: string | null; run_id: string; counts: LedgerCounts; items: LedgerPrincipleItem[]; categories: Record<string, string> }>(
    "/api/v2/ledger/principles",
  );
export const getLedgerForecasts = (status?: "open" | "resolved") =>
  getJson<LedgerForecastList>("/api/v2/ledger/forecasts", { params: status ? { status } : {} });
export const getLedgerCalibration = () =>
  getJson<{ run_id: string; calibration: LedgerCalibration; claim: string | null }>("/api/v2/ledger/calibration");
export const createLedgerForecast = (payload: LedgerForecastInput) =>
  postJson<{ ok: boolean; id: string; code: string; direction: string; target_date: string }>(
    "/api/v2/ledger/forecasts",
    payload,
  );
export const runLedger = () => postJson<LedgerRunResult>("/api/v2/ledger/run", {});

export const getSystemCoverage = () => getJson<CoverageResponse>("/api/system/coverage");

/* 交易记录（V2.0）：股票 / 期货 / 期权等多品种 CRUD、筛选分页与统计 */
export interface TradeQuery {
  limit?: number;
  offset?: number;
  q?: string;
  asset_class?: TradeAssetClass;
  direction?: TradeDirection;
  status?: TradeStatus;
  date_from?: string;
  date_to?: string;
  sort?: "trade_date" | "pnl" | "created_at";
  order?: "desc" | "asc";
}

export const listTrades = (query: TradeQuery = {}) =>
  getJson<TradeList>("/api/trades", {
    params: query as Record<string, string | number | boolean | undefined>,
  });
export const getTrade = (id: string) => getJson<TradeItem>(`/api/trades/${encodeURIComponent(id)}`);
export const createTrade = (body: TradeInput) => postJson<TradeItem>("/api/trades", body);
export const updateTrade = (id: string, body: Partial<TradeInput>) =>
  patchJson<TradeItem>(`/api/trades/${encodeURIComponent(id)}`, body);
export const deleteTrade = (id: string) =>
  deleteJson<{ deleted: boolean; id: string }>(`/api/trades/${encodeURIComponent(id)}`);
export const getTradeStats = () => getJson<TradeStats>("/api/trades/stats");
