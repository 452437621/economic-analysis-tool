/** 分析引擎的取数与派生：分析主数据、黄金摘要、引擎透明度各自独立轮询。 */
import { computed } from "vue";
import { usePolling } from "@/composables/usePolling";
import {
  fmtDate,
  fmtDateTime,
  fmtInt,
  fmtMacro,
  fmtNumber,
  fmtSigned,
  fmtTime,
} from "@/composables/useFormat";
import {
  getAnalytics,
  getGoldOverview,
  getQuality,
  getV2Derivations,
  getV2Methods,
  getV2Runs,
} from "@/api/endpoints";
import type {
  CalendarStudyGroup,
  GoldFactor,
  QualityResponse,
  Regime,
  V2Derivation,
  V2Method,
  V2Run,
} from "@/api/types";
import { useHistoryStore } from "@/stores/history";
import { gradeClass, methodKindText, shaText, toNumber } from "@/utils/analysisFormat";

export function useAnalysisOverview() {
  const historyStore = useHistoryStore();

  const { data: overview, error, loading, lastUpdated, refresh } = usePolling(getAnalytics, {
    interval: 120000,
  });

  /** 黄金研判：独立轮询，失败/加载都不影响下方分析区块 */
  const { data: gold, error: goldError, loading: goldLoading, refresh: refreshGold } = usePolling(
    getGoldOverview,
    { interval: 60000 },
  );

  /* ── 引擎透明度：方法注册表 / 运行 / 推导证据 / 数据质量（各自独立轮询） ── */
  const RUN_LIMIT = 6;
  const DERIV_LIMIT = 60;

  const {
    data: methods,
    error: methodsError,
    loading: methodsLoading,
    refresh: refreshMethods,
  } = usePolling(getV2Methods, { interval: 120000 });

  const {
    data: runsData,
    error: runsError,
    loading: runsLoading,
    refresh: refreshRuns,
  } = usePolling(() => getV2Runs({ limit: RUN_LIMIT }), { interval: 120000 });

  const {
    data: derivations,
    error: derivationsError,
    loading: derivationsLoading,
    refresh: refreshDerivations,
  } = usePolling(() => getV2Derivations({ limit: DERIV_LIMIT }), { interval: 120000 });

  const {
    data: quality,
    error: qualityError,
    loading: qualityLoading,
    refresh: refreshQuality,
  } = usePolling(getQuality, { interval: 120000 });

  const methodTotal = computed(() => methods.value?.total ?? 0);
  const methodRows = computed<V2Method[]>(() => methods.value?.items ?? []);
  const runs = computed<V2Run[]>(() => runsData.value?.items ?? []);

  /** 方法构成摘要：按类型计数，如「模型 3 · 流水线 2」 */
  const methodKindSummary = computed(() => {
    const counts = new Map<string, number>();
    for (const method of methodRows.value) {
      const kind = methodKindText(method.kind);
      counts.set(kind, (counts.get(kind) ?? 0) + 1);
    }
    if (!counts.size) return "—";
    return [...counts.entries()].map(([kind, count]) => `${kind} ${count}`).join(" · ");
  });

  /** 代码指纹摘要：单方法直接显示前 8 位；多方法显示首个 + 「等 N 个」 */
  const methodShaSummary = computed(() => {
    const shas = methodRows.value.map((method) => method.code_sha).filter((sha): sha is string => Boolean(sha));
    if (!shas.length) return "未记录";
    return shas.length > 1 ? `${shaText(shas[0])} 等 ${shas.length} 个` : shaText(shas[0]);
  });

  const methodShaTitle = computed(() => {
    const rows = methodRows.value
      .filter((method) => method.code_sha)
      .map((method) => `${method.method_id}: ${method.code_sha}`);
    return rows.length ? rows.join("\n") : "未记录代码指纹";
  });

  const derivTotal = computed(() => derivations.value?.total ?? 0);

  /** 证据等级计数（E1–E4 + 其它，只显示出现过的等级） */
  const gradeRows = computed(() => {
    const known = ["E1", "E2", "E3", "E4"];
    const counts = new Map<string, number>();
    for (const item of derivations.value?.items ?? []) {
      const grade = (item.evidence_grade || "—").toUpperCase();
      counts.set(grade, (counts.get(grade) ?? 0) + 1);
    }
    const grades = [
      ...known.filter((grade) => counts.has(grade)),
      ...[...counts.keys()].filter((grade) => !known.includes(grade)),
    ];
    const max = Math.max(1, ...grades.map((grade) => counts.get(grade) ?? 0));
    return grades.map((grade) => ({
      grade,
      n: counts.get(grade) ?? 0,
      width: `${Math.max(4, Math.round(((counts.get(grade) ?? 0) / max) * 100))}%`,
      cls: gradeClass(grade),
    }));
  });

  const qualitySummaryText = computed(() => {
    const summary = quality.value?.summary;
    if (!summary) return "— / — 通过";
    return `${summary.passed} / ${summary.total} 通过`;
  });

  const qualityFailedText = computed(() => {
    const summary = quality.value?.summary;
    if (!summary) return "— 项";
    return `${summary.failed} 项`;
  });

  const qualityPassedClass = computed(() => {
    const summary = quality.value?.summary;
    if (!summary) return "";
    return summary.failed > 0 ? "badge--warn" : "badge--live";
  });

  const qualityDateLabel = computed(() => {
    const first = quality.value?.data?.[0];
    return first?.check_date ? `检查于 ${fmtDateTime(first.check_date)}` : "尚未产出检查结果";
  });

  const goldScore = computed(() => gold.value?.score ?? null);
  const goldLabel = computed(() => goldScore.value?.label ?? "—");
  const goldScoreText = computed(() => (goldScore.value ? fmtSigned(goldScore.value.score, 1) : "—"));
  /** 正分涨色 / 负分跌色 / 中性或 0 用 muted（与后端 ±18 分档一致） */
  const goldTone = computed(() => {
    const score = goldScore.value;
    if (!score) return "flat";
    if (score.label === "中性") return "flat";
    if (score.score > 0) return "up";
    if (score.score < 0) return "down";
    return "flat";
  });
  const goldLabelClass = computed(() => {
    if (goldLabel.value === "强多" || goldLabel.value === "偏多") return "badge--up";
    if (goldLabel.value === "强空" || goldLabel.value === "偏空") return "badge--down";
    return "";
  });
  const goldCoverageText = computed(() =>
    goldScore.value ? fmtMacro(goldScore.value.coverage, "%", 0) : "—",
  );
  const goldAvailableCount = computed(
    () => (goldScore.value?.factors ?? []).filter((factor) => factor.available).length,
  );
  const goldTotalCount = computed(() => goldScore.value?.factors.length ?? 0);
  const goldAvailableWeight = computed(() => goldScore.value?.available_weight ?? 0);
  const goldTotalWeight = computed(() => goldScore.value?.total_weight ?? 0);
  const goldGeneratedLabel = computed(() => (goldScore.value ? fmtTime(goldScore.value.generated_at, true) : "—"));
  const goldMethodology = computed(() => goldScore.value?.methodology ?? "");

  /** 取 |贡献| 最大的前 4 个可用因子 */
  const goldTopFactors = computed<GoldFactor[]>(() => {
    const factors = goldScore.value?.factors ?? [];
    return factors
      .filter((factor) => factor.available && factor.value !== null && factor.value !== undefined)
      .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
      .slice(0, 4);
  });

  /** 刷新按钮同时刷新分析引擎、黄金研判与引擎透明度四块 */
  function refreshAll(): void {
    void Promise.all([
      refresh(),
      refreshGold(),
      refreshMethods(),
      refreshRuns(),
      refreshDerivations(),
      refreshQuality(),
    ]);
  }

  /** 归因资产展示名（后端只返回 symbol） */
  const SYMBOL_NAMES: Record<string, string> = {
    AU: "沪金",
    CU: "沪铜",
    SC: "原油",
    AG: "沪银",
    "603993": "洛阳钼业",
    "000300": "沪深300",
    GC: "COMEX黄金",
    SI: "COMEX白银",
    XAUUSD: "伦敦金现",
    BZ: "Brent原油",
    CL: "WTI原油",
    HG: "LME铜",
    I: "铁矿石",
    AL: "沪铝",
    ZN: "沪锌",
    NI: "沪镍",
    AL_LME: "伦铝",
    ZN_LME: "伦锌",
    NI_LME: "伦镍",
    M: "豆粕",
    P: "棕榈油",
    SR: "白糖",
    CF: "棉花",
    SPX: "标普500",
    NDX: "纳斯达克100",
    DJIA: "道琼斯",
    HSI: "恒生指数",
    DXY: "美元指数",
    USDCNH: "离岸人民币",
    EURUSD: "欧元美元",
    GBPUSD: "英镑美元",
    USDJPY: "美元日元",
    USDSEK: "美元瑞典克朗",
    USDCHF: "美元瑞郎",
    USDCAD: "美元加元",
  };

  const ATTR_ORDER: readonly string[] = ["AU", "CU", "SC", "AG", "603993", "000300"];

  const wind = computed(() => overview.value?.wind ?? null);
  const windRisk = computed(() => wind.value?.components.risk_assets ?? []);
  const regimeList = computed<Regime[]>(() => {
    const map = overview.value?.regimes;
    if (!map) return [];
    const order = ["US", "CN"];
    const keys = [
      ...order.filter((key) => Boolean(map[key])),
      ...Object.keys(map).filter((key) => !order.includes(key)),
    ];
    return keys.map((key) => map[key]);
  });
  const correlation = computed(() => overview.value?.correlation ?? null);
  const analogs = computed(() => overview.value?.analogs ?? null);
  const calendarStudy = computed(() => overview.value?.calendar_study ?? null);
  const movers = computed(() => overview.value?.movers ?? []);

  const updatedLabel = computed(() =>
    lastUpdated.value ? fmtTime(lastUpdated.value.toISOString()) : "—",
  );
  const asofLabel = computed(() => {
    if (wind.value?.asof) return wind.value.asof;
    return overview.value?.asof ? fmtDate(overview.value.asof) : "—";
  });
  const windNeedle = computed(() => {
    const score = Math.max(-100, Math.min(100, wind.value?.score ?? 0));
    return `${((score + 100) / 2).toFixed(1)}%`;
  });

  interface AttributionRow {
    symbol: string;
    name: string;
    actual: number | null;
    r2: number | null;
    realYield: number | null;
    breakeven: number | null;
    curve: number | null;
    dxy: number | null;
    residual: number | null;
    window: number | null;
    days: number | null;
  }

  const attributionRows = computed<AttributionRow[]>(() => {
    const map = overview.value?.attribution;
    if (!map) return [];
    const keys = [
      ...ATTR_ORDER.filter((key) => Boolean(map[key])),
      ...Object.keys(map).filter((key) => !ATTR_ORDER.includes(key)),
    ];
    return keys.map((symbol) => {
      const entry = map[symbol];
      const contributions = entry.contributions_pct ?? {};
      const factor = (key: string): number | null => toNumber(contributions[key]);
      return {
        symbol,
        name: SYMBOL_NAMES[symbol] ?? symbol,
        actual: toNumber(entry.actual_pct),
        r2: toNumber(entry.r2),
        realYield: factor("real_yield_chg"),
        breakeven: factor("breakeven_chg"),
        curve: factor("curve_chg"),
        dxy: factor("dxy_chg"),
        residual: toNumber(entry.residual_pct),
        window: toNumber(entry.window),
        days: toNumber(entry.contrib_days),
      };
    });
  });

  const attrWindow = computed(() => attributionRows.value[0]?.window ?? null);
  const attrDays = computed(() => attributionRows.value[0]?.days ?? null);

  function cell(group: CalendarStudyGroup, symbol: string, horizon: string): number | null {
    return toNumber(group.assets?.[symbol]?.[horizon]);
  }

  const calendarRows = computed(() => {
    const groups = calendarStudy.value?.groups ?? [];
    return [...groups]
      .sort((a, b) => (b.n ?? 0) - (a.n ?? 0))
      .slice(0, 12)
      .map((group) => ({
        country: group.country,
        category: group.category,
        n: group.n,
        au1d: cell(group, "AU", "1d"),
        au3d: cell(group, "AU", "3d"),
        cu1d: cell(group, "CU", "1d"),
        cu3d: cell(group, "CU", "3d"),
        hs3001d: cell(group, "000300", "1d"),
        hs3003d: cell(group, "000300", "3d"),
      }));
  });

  function openHistory(symbol: string, name: string): void {
    void historyStore.openHistory("instrument", symbol, name);
  }

  return {
    overview,
    error,
    loading,
    refresh,
    gold,
    goldError,
    goldLoading,
    refreshGold,
    methods,
    methodsError,
    methodsLoading,
    refreshMethods,
    runsData,
    runsError,
    runsLoading,
    refreshRuns,
    derivations,
    derivationsError,
    derivationsLoading,
    refreshDerivations,
    quality,
    qualityError,
    qualityLoading,
    refreshQuality,
    methodTotal,
    methodRows,
    runs,
    methodKindSummary,
    methodShaSummary,
    methodShaTitle,
    derivTotal,
    gradeRows,
    qualitySummaryText,
    qualityFailedText,
    qualityPassedClass,
    qualityDateLabel,
    goldScore,
    goldLabel,
    goldScoreText,
    goldTone,
    goldLabelClass,
    goldCoverageText,
    goldAvailableCount,
    goldTotalCount,
    goldAvailableWeight,
    goldTotalWeight,
    goldGeneratedLabel,
    goldMethodology,
    goldTopFactors,
    refreshAll,
    wind,
    windRisk,
    regimeList,
    correlation,
    analogs,
    calendarStudy,
    movers,
    updatedLabel,
    asofLabel,
    windNeedle,
    attributionRows,
    attrWindow,
    attrDays,
    calendarRows,
    openHistory,
  };
}
