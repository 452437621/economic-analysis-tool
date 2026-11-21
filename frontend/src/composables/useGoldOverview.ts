/** 黄金研判的取数、派生指标与手动录入。 */
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtNumber, fmtSigned, fmtTime } from "@/composables/useFormat";
import { getGoldOverview, refreshGold, saveGoldMetric } from "@/api/endpoints";
import type { GoldFactor, GoldScore } from "@/api/types";
import { HISTORY_RANGES, type HistoryRange } from "@/stores/history";
import { usePrefsStore } from "@/stores/prefs";
import { useToast } from "@/stores/toast";
import { buildGoldChartCards, buildGoldPalette } from "@/utils/goldCharts";
import { GROUP_ICONS, providerTime, todayIso } from "@/utils/goldFormat";

export interface ManualTarget {
  code: string;
  name: string;
  unit: string;
  freq: string;
  note: string;
  weight?: number;
  source?: string;
}
export interface EntryState {
  open: boolean;
  code: string;
  name: string;
  unit: string;
  freq: string;
  manualSource: string;
  value: string;
  asOf: string;
  note: string;
  noteTip: string;
  saving: boolean;
}

export function useGoldOverview() {
  const prefs = usePrefsStore();
  const toast = useToast();

  /* ---------- 取数 ---------- */
  const { data: overview, error, loading, lastUpdated, refresh } = usePolling(getGoldOverview, {
    interval: 60000,
  });

  const score = computed<GoldScore | null>(() => overview.value?.score ?? null);
  const factors = computed<GoldFactor[]>(() => overview.value?.score.factors ?? []);
  const providers = computed(() => overview.value?.providers ?? []);
  const manual = computed(() => overview.value?.manual ?? []);
  const categories = computed(() => overview.value?.score.categories ?? []);

  const scoreValue = computed(() => score.value?.score ?? 0);
  const scoreLabel = computed(() => score.value?.label ?? "—");
  const coverage = computed(() => score.value?.coverage ?? 0);
  const availableWeight = computed(() => score.value?.available_weight ?? 0);
  const totalWeight = computed(() => score.value?.total_weight ?? 0);
  const generatedAt = computed(() => score.value?.generated_at ?? overview.value?.generated_at ?? null);
  const methodology = computed(() => score.value?.methodology ?? "—");

  const generatedLabel = computed(() => (generatedAt.value ? fmtDateTime(generatedAt.value) : "—"));

  /** 展示口径：各可用因子里最早的观测日（而非评分生成时间），避免用「刚算过」掩盖「数据很旧」 */
  const earliestFactorAsOf = computed(() => {
    const dates = factors.value.filter((factor) => factor.available && factor.as_of).map((factor) => factor.as_of as string);
    if (!dates.length) return generatedLabel.value;
    const earliest = dates.reduce((min, current) => (current < min ? current : min), dates[0]);
    return fmtDate(earliest);
  });
  const updatedLabel = computed(() => (lastUpdated.value ? fmtTime(lastUpdated.value.toISOString(), true) : "—"));
  const scoreTrend = computed<"up" | "down" | "flat">(() => {
    const value = scoreValue.value;
    if (Math.abs(value) < 10) return "flat";
    return value > 0 ? "up" : "down";
  });
  const scoreBadgeClass = computed(() => {
    if (scoreLabel.value.includes("多")) return "badge--up";
    if (scoreLabel.value.includes("空")) return "badge--down";
    return "";
  });
  const gaugeOffset = computed(() => {
    const percent = Math.max(0, Math.min(100, (scoreValue.value + 100) / 2));
    return (100 - percent).toFixed(1);
  });
  const coveragePct = computed(() => Math.max(0, Math.min(100, coverage.value)));
  const availableFactorCount = computed(() => factors.value.filter((item) => item.available).length);
  const pendingCount = computed(() => factors.value.filter((item) => !item.available).length);
  const pendingManualCount = computed(
    () => manual.value.filter((item) => item.weight > 0 && !item.available).length,
  );
  const okCount = computed(() => providers.value.filter((item) => item.ok).length);
  const providerCheckedLabel = computed(() => {
    const times = providers.value
      .map((item) => item.checked_at)
      .filter((item): item is string => Boolean(item))
      .sort();
    if (!times.length) return "—";
    return fmtDateTime(providerTime(times[times.length - 1]));
  });
  const seriesCount = computed(() => {
    const series = overview.value?.series;
    if (!series) return 0;
    return Object.values(series).filter((points) => Array.isArray(points) && points.length > 0).length;
  });

  const methodologyBrief = computed(() => {
    const text = methodology.value.trim();
    if (!text) return "—";
    const first = text.indexOf("。");
    if (first < 0) return text;
    const second = text.indexOf("。", first + 1);
    const end = second < 0 ? first : second;
    return `${text.slice(0, end + 1)}${end < text.length - 1 ? "…" : ""}`;
  });
  const coverageNote = computed(
    () =>
      `当前 ${availableFactorCount.value} / ${factors.value.length} 项因子可用，覆盖率 ${fmtNumber(
        coverage.value,
        1,
      )}%；未采集因子不参与评分（可用权重 ${fmtNumber(availableWeight.value, 0)} / ${fmtNumber(
        totalWeight.value,
        0,
      )}）。`,
  );

  /* ---------- 因子分组 / 明细 ---------- */
  interface GroupView {
    key: string;
    label: string;
    icon: string;
    factors: GoldFactor[];
    contribution: number;
    available: number;
  }

  const sortedFactors = computed(() =>
    [...factors.value].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)),
  );
  const topDrivers = computed(() => sortedFactors.value.filter((item) => item.available).slice(0, 5));

  const groups = computed<GroupView[]>(() => {
    const order = categories.value.length
      ? categories.value.map((item) => ({ key: item.key, label: item.label }))
      : Array.from(
          new Map(factors.value.map((item) => [item.category, item.category_label])).entries(),
        ).map(([key, label]) => ({ key, label }));
    return order
      .map((item) => {
        const items = factors.value.filter((factor) => factor.category === item.key);
        return {
          key: item.key,
          label: item.label,
          icon: GROUP_ICONS[item.key] ?? "#i-dot-list",
          factors: items,
          contribution: items.reduce((sum, factor) => sum + factor.contribution, 0),
          available: items.filter((factor) => factor.available).length,
        };
      })
      .filter((item) => item.factors.length > 0);
  });

  const conclusionText = computed(() => {
    const drivers = topDrivers.value;
    if (!drivers.length) return "暂无可用的关键因子，等待采集任务写入数据。";
    const bullish = drivers.filter((item) => item.contribution > 0.05).map((item) => item.name);
    const bearish = drivers.filter((item) => item.contribution < -0.05).map((item) => item.name);
    const parts: string[] = [];
    if (bullish.length) parts.push(`${bullish.join("、")}偏多`);
    if (bearish.length) parts.push(`${bearish.join("、")}偏空`);
    const head = parts.length ? parts.join("；") : "多空因子势均力敌";
    return `${head}，综合判断「${scoreLabel.value}」（${fmtSigned(scoreValue.value, 1)} / 100）。`;
  });

  /* ---------- 手动录入 ---------- */
  const entry = reactive<EntryState>({
    open: false,
    code: "",
    name: "",
    unit: "",
    freq: "",
    manualSource: "",
    value: "",
    asOf: todayIso(),
    note: "",
    noteTip: "",
    saving: false,
  });

  function openEntry(target: ManualTarget): void {
    const current = factors.value.find((factor) => factor.code === target.code);
    entry.open = true;
    entry.code = target.code;
    entry.name = target.name;
    entry.unit = target.unit;
    entry.freq = target.freq;
    entry.manualSource = target.source ?? "手动录入";
    entry.value = current?.value === null || current?.value === undefined ? "" : String(current.value);
    entry.asOf = current?.as_of ? fmtDate(current.as_of) : todayIso();
    entry.note = "";
    entry.noteTip = current?.note ?? target.note ?? "";
  }

  function closeEntry(): void {
    entry.open = false;
    entry.saving = false;
  }

  async function submitEntry(): Promise<void> {
    if (entry.saving) return;
    const value = Number(entry.value);
    if (!entry.value || !Number.isFinite(value)) {
      toast.warn("请输入有效数值");
      return;
    }
    entry.saving = true;
    try {
      await saveGoldMetric({
        code: entry.code,
        value,
        as_of: entry.asOf || undefined,
        note: entry.note || undefined,
      });
      toast.ok(`已保存「${entry.name}」`);
      closeEntry();
      await refresh();
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "保存失败");
    } finally {
      entry.saving = false;
    }
  }

  /* ---------- 刷新（异步采集） ---------- */
  const collecting = ref(false);
  let collectTimer: number | null = null;

  async function triggerRefresh(): Promise<void> {
    if (collecting.value) return;
    collecting.value = true;
    try {
      await refreshGold();
      toast.info("已触发采集，约 1 分钟后刷新");
      if (collectTimer !== null) window.clearTimeout(collectTimer);
      collectTimer = window.setTimeout(() => {
        collectTimer = null;
        void refresh();
      }, 65000);
    } catch (err) {
      toast.bad(err instanceof Error ? err.message : "触发采集失败");
    } finally {
      collecting.value = false;
    }
  }

  onBeforeUnmount(() => {
    if (collectTimer !== null) {
      window.clearTimeout(collectTimer);
      collectTimer = null;
    }
  });

  /* ---------- 图表 ---------- */
  const chartRange = ref<HistoryRange>("1y");
  /** 每张图表是否叠加伦敦金价（默认关闭，按图表单独开关）。 */
  const priceOverlays = reactive<Record<string, boolean>>({});

  const palette = computed(() => {
    // 显式依赖主题与涨跌配色，切换后图表重算
    void prefs.resolvedTheme;
    void prefs.updown;
    return buildGoldPalette(prefs.updown);
  });

  const chartCards = computed(() =>
    buildGoldChartCards({
      series: overview.value?.series,
      range: chartRange.value,
      overlays: priceOverlays,
      palette: palette.value,
    }),
  );

  function togglePriceOverlay(key: string): void {
    priceOverlays[key] = !priceOverlays[key];
  }

  function setChartRange(next: HistoryRange): void {
    chartRange.value = next;
  }

  return {
    prefs,
    toast,
    overview,
    error,
    loading,
    refresh,
    score,
    factors,
    providers,
    manual,
    categories,
    scoreValue,
    scoreLabel,
    coverage,
    availableWeight,
    totalWeight,
    generatedLabel,
    methodology,
    earliestFactorAsOf,
    updatedLabel,
    scoreTrend,
    scoreBadgeClass,
    gaugeOffset,
    coveragePct,
    availableFactorCount,
    pendingCount,
    pendingManualCount,
    okCount,
    providerCheckedLabel,
    seriesCount,
    methodologyBrief,
    coverageNote,
    sortedFactors,
    topDrivers,
    groups,
    conclusionText,
    entry,
    openEntry,
    closeEntry,
    submitEntry,
    collecting,
    triggerRefresh,
    chartRange,
    priceOverlays,
    chartCards,
    togglePriceOverlay,
    setChartRange,
    HISTORY_RANGES,
  };
}
