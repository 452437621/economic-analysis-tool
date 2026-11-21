/** 专题研判取数：专题列表、当前专题 overview、刷新、持仓与手动指标。 */
import { computed, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { ApiError } from "@/api/client";
import {
  getTopicOverview,
  getTopicPosition,
  getTopics,
  refreshTopic,
  saveGoldMetric,
  saveTopicPosition,
} from "@/api/endpoints";
import type {
  TopicOverview,
  TopicPositionInput,
  TopicPositionResponse,
  TopicSummary,
} from "@/api/types";
import { usePolling } from "@/composables/usePolling";
import { usePrefsStore } from "@/stores/prefs";
import { useToast } from "@/stores/toast";
import { buildGoldPalette } from "@/utils/goldCharts";
import type { TopicRange } from "@/utils/topicCharts";

export interface ManualMetricInput {
  code: string;
  value: number;
  as_of?: string;
  note?: string;
}

function errorText(err: unknown): string {
  if (err instanceof ApiError || err instanceof Error) return err.message;
  return String(err);
}

export function useTopicOverview(activeId: Ref<string>) {
  const toast = useToast();
  const prefs = usePrefsStore();

  const topics = ref<TopicSummary[]>([]);
  const configVersion = ref("");
  const topicsLoading = ref(false);
  const topicsError = ref<Error | null>(null);
  const refreshing = ref(false);

  const position = ref<TopicPositionResponse | null>(null);
  const positionLoading = ref(false);
  const positionError = ref<Error | null>(null);
  const positionSaving = ref(false);
  const manualSaving = ref(false);

  const chartRange = ref<TopicRange>("1y");
  const palette = computed(() => {
    void prefs.resolvedTheme;
    void prefs.updown;
    return buildGoldPalette(prefs.updown);
  });

  const interval = computed(() => (activeId.value === "luoyang" ? 300_000 : 60_000));
  const { data, error, loading, lastUpdated, refresh } = usePolling<TopicOverview>(
    () => getTopicOverview(activeId.value || "gold"),
    {
      interval,
      watchSource: activeId,
      resetOnSourceChange: true,
      immediate: false,
    },
  );

  const overview = computed<TopicOverview | null>(() => data.value);
  const sections = computed(() =>
    [...(overview.value?.sections ?? [])].sort((a, b) => a.order - b.order),
  );
  const activeTopic = computed(
    () => topics.value.find((item) => item.id === activeId.value) ?? null,
  );
  const hasPositionSection = computed(() => sections.value.some((item) => item.kind === "position"));

  async function loadTopics(): Promise<void> {
    topicsLoading.value = true;
    try {
      const payload = await getTopics();
      topics.value = payload.data;
      configVersion.value = payload.config_version;
      topicsError.value = null;
    } catch (err) {
      const wrapped = err instanceof Error ? err : new Error(String(err));
      topicsError.value = wrapped;
      toast.bad(`专题列表加载失败：${errorText(err)}`);
    } finally {
      topicsLoading.value = false;
    }
  }

  async function bootstrap(): Promise<void> {
    await loadTopics();
    if (!topics.value.length) {
      toast.bad("没有启用的专题，请检查 config/topics.yaml");
      return;
    }
    const first = topics.value[0].id;
    if (!topics.value.some((item) => item.id === activeId.value)) {
      // The polling source watcher performs the reset + fetch.
      activeId.value = first;
      return;
    }
    await refresh();
  }

  async function loadPosition(): Promise<void> {
    if (!activeId.value || !hasPositionSection.value) {
      position.value = null;
      return;
    }
    positionLoading.value = true;
    positionError.value = null;
    const requested = activeId.value;
    try {
      const payload = await getTopicPosition(requested);
      if (requested === activeId.value) position.value = payload;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        if (requested === activeId.value) position.value = null;
      } else if (requested === activeId.value) {
        positionError.value = err instanceof Error ? err : new Error(String(err));
        toast.warn(`持仓参数读取失败：${errorText(err)}`);
      }
    } finally {
      if (requested === activeId.value) positionLoading.value = false;
    }
  }

  /** Only send fields the user actually edited; never spread stale defaults. */
  function editablePatch(payload: TopicPositionInput): TopicPositionInput {
    const patch: TopicPositionInput = {};
    if (payload.buy_price !== undefined) patch.buy_price = payload.buy_price;
    if (payload.buy_date !== undefined) patch.buy_date = payload.buy_date;
    if (payload.shares_lots !== undefined) patch.shares_lots = payload.shares_lots;
    if (payload.dividends !== undefined) patch.dividends = payload.dividends;
    if (payload.add_prices !== undefined) patch.add_prices = payload.add_prices;
    if (payload.add_ratios !== undefined) patch.add_ratios = payload.add_ratios;
    return patch;
  }

  async function savePosition(payload: TopicPositionInput): Promise<boolean> {
    if (!activeId.value || positionSaving.value) return false;
    const snapshot = position.value;
    positionSaving.value = true;
    try {
      const saved = await saveTopicPosition(activeId.value, editablePatch(payload));
      position.value = saved;
      toast.ok("持仓参数已保存");
      await refresh(true);
      return true;
    } catch (err) {
      position.value = snapshot;
      toast.bad(`持仓保存失败：${errorText(err)}`);
      return false;
    } finally {
      positionSaving.value = false;
    }
  }

  async function saveManualMetric(payload: ManualMetricInput): Promise<boolean> {
    if (activeId.value !== "gold") {
      toast.warn("当前专题不支持手动指标录入");
      return false;
    }
    if (manualSaving.value) return false;
    manualSaving.value = true;
    try {
      await saveGoldMetric(payload);
      toast.ok("指标已保存");
      await refresh(true);
      return true;
    } catch (err) {
      toast.bad(`指标保存失败：${errorText(err)}`);
      return false;
    } finally {
      manualSaving.value = false;
    }
  }

  async function triggerRefresh(): Promise<void> {
    if (refreshing.value || !activeId.value) return;
    refreshing.value = true;
    let timer: number | null = null;
    try {
      await refreshTopic(activeId.value);
      const label = activeTopic.value?.label ?? "专题";
      toast.info(`${label}数据采集已开始，约 1 分钟后刷新`);
      timer = window.setTimeout(() => {
        void refresh();
      }, 65_000);
    } catch (err) {
      toast.bad(`触发采集失败：${errorText(err)}`);
    } finally {
      refreshing.value = false;
    }
    timers.add(timer);
  }

  function setChartRange(range: TopicRange): void {
    chartRange.value = range;
  }

  const timers = new Set<number | null>();

  watch(activeId, (next, previous) => {
    if (next === previous) return;
    position.value = null;
    positionError.value = null;
    chartRange.value = "1y";
  });

  watch(
    [activeId, hasPositionSection],
    () => {
      if (hasPositionSection.value) void loadPosition();
      else position.value = null;
    },
  );

  onBeforeUnmount(() => {
    for (const timer of timers) {
      if (timer !== null) window.clearTimeout(timer);
    }
    timers.clear();
  });

  return {
    topics,
    configVersion,
    topicsLoading,
    topicsError,
    activeTopic,
    overview,
    sections,
    error,
    loading,
    lastUpdated,
    refreshing,
    position,
    positionLoading,
    positionError,
    positionSaving,
    manualSaving,
    chartRange,
    palette,
    hasPositionSection,
    bootstrap,
    loadTopics,
    refresh,
    triggerRefresh,
    loadPosition,
    savePosition,
    saveManualMetric,
    setChartRange,
  };
}
