import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { getBars, getMacroSeries } from "@/api/endpoints";

export type HistoryKind = "instrument" | "macro";
export type HistoryRange = "1m" | "3m" | "6m" | "1y" | "2y" | "5y" | "all";

export interface HistoryPoint {
  t: number;
  v: number;
}

export const HISTORY_RANGES: Array<{ value: HistoryRange; label: string }> = [
  { value: "1m", label: "1月" },
  { value: "3m", label: "3月" },
  { value: "6m", label: "6月" },
  { value: "1y", label: "1年" },
  { value: "2y", label: "2年" },
  { value: "5y", label: "5年" },
  { value: "all", label: "全部" },
];

const RANGE_DAYS: Record<Exclude<HistoryRange, "all">, number> = {
  "1m": 31,
  "3m": 92,
  "6m": 183,
  "1y": 366,
  "2y": 731,
  "5y": 1826,
};

/** 历史趋势弹窗：标的日线 / 宏观序列共用。 */
export const useHistoryStore = defineStore("history", () => {
  const open = ref(false);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const kind = ref<HistoryKind>("instrument");
  const key = ref("");
  const name = ref("");
  const unit = ref("");
  const range = ref<HistoryRange>("1y");
  const points = ref<HistoryPoint[]>([]);

  const rangeLabel = computed(
    () => HISTORY_RANGES.find((item) => item.value === range.value)?.label ?? "全部",
  );

  const visiblePoints = computed<HistoryPoint[]>(() => {
    if (!points.value.length) return [];
    if (range.value === "all") return points.value;
    const days = RANGE_DAYS[range.value as Exclude<HistoryRange, "all">];
    const last = points.value[points.value.length - 1].t;
    return points.value.filter((point) => point.t >= last - days * 86400000);
  });

  const stats = computed(() => {
    const list = visiblePoints.value;
    if (list.length < 2) return null;
    const first = list[0];
    const last = list[list.length - 1];
    const values = list.map((point) => point.v);
    const diff = last.v - first.v;
    const pct = first.v ? (diff / Math.abs(first.v)) * 100 : 0;
    return {
      last: last.v,
      diff,
      pct,
      min: Math.min(...values),
      max: Math.max(...values),
      count: list.length,
      from: new Date(first.t),
      to: new Date(last.t),
    };
  });

  async function openHistory(
    nextKind: HistoryKind,
    nextKey: string,
    nextName?: string,
    nextUnit = "",
  ): Promise<void> {
    open.value = true;
    loading.value = true;
    error.value = null;
    kind.value = nextKind;
    key.value = nextKey;
    name.value = nextName || nextKey;
    unit.value = nextUnit;
    points.value = [];
    try {
      if (nextKind === "instrument") {
        const payload = await getBars(nextKey, "1d", 3000);
        points.value = payload.data
          .map((row) => ({ t: Date.parse(row.ts), v: Number(row.close) }))
          .filter((point) => Number.isFinite(point.t) && Number.isFinite(point.v));
        unit.value = "";
      } else {
        const payload = await getMacroSeries(nextKey, 5000);
        points.value = payload.data
          .map((row) => ({ t: Date.parse(row.ts), v: Number(row.value) }))
          .filter((point) => Number.isFinite(point.t) && Number.isFinite(point.v));
        unit.value = payload.unit || nextUnit;
      }
      if (!points.value.length) error.value = "暂无历史数据（等待采集任务）";
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      loading.value = false;
    }
  }

  function close(): void {
    open.value = false;
  }

  function setRange(next: HistoryRange): void {
    range.value = next;
  }

  return {
    open,
    loading,
    error,
    kind,
    key,
    name,
    unit,
    range,
    points,
    visiblePoints,
    rangeLabel,
    stats,
    openHistory,
    close,
    setRange,
  };
});
