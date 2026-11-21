import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import type { TimelineEra, TimelineEventItem, TimelinePowerPoint } from "@/api/types";
import {
  LAYER_COLOR,
  LANES,
  buildApiEvents,
  buildCurveSeries,
  buildStaticDisplay,
  hasRealReserveSeries,
} from "@/components/history/timeline/data";
import {
  CURRENT_YEAR,
  END_YEAR,
  H,
  PL,
  WINDOWS,
  ZOOMS,
  buildLaneRows,
  buildRenderedCurves,
  canvasWidth,
  r1,
  ticksFor,
  xOf,
  yOfReserve,
} from "@/components/history/timeline/geometry";
import type { DisplayEvent, LaneId, LayerKey } from "@/components/history/timeline/types";

export interface TimelineSource {
  events?: TimelineEventItem[];
  eras?: TimelineEra[];
  reserve?: TimelinePowerPoint[];
}

export function useTimelineViewport(
  source: TimelineSource,
  onSelect: (item: TimelineEventItem) => void,
) {
  const scrollEl = ref<HTMLDivElement | null>(null);
  const svgEl = ref<SVGSVGElement | null>(null);
  const contentWidth = ref(0);
  const windowStart = ref<number>(WINDOWS[0]);
  const zoomIndex = ref(0);
  const lastSelectedId = ref<string | null>(null);

  const layerState = reactive<Record<LayerKey, boolean>>({
    empire: true,
    reserve: true,
    debt: true,
    war: true,
    tech: true,
  });

  /* ── 画布尺寸（原型：W = round(可视宽 × zoom)，H = 420） ─────────────── */

  const zoom = computed(() => ZOOMS[zoomIndex.value] ?? 1);

  const canvasW = computed(() => canvasWidth(contentWidth.value, zoom.value));

  const W = canvasW;
  const PR = computed(() => W.value - 12);

  const outYearX = computed(() => r1(xOf(CURRENT_YEAR, windowStart.value, PR.value)));

  const ticks = computed<number[]>(() => ticksFor(windowStart.value));

  const xOfYear = (year: number) => xOf(year, windowStart.value, PR.value);

  /* ── 事件 → 四条泳道（真实数据优先，无法归属则丢弃，不伪造） ──────────── */

  const apiEvents = computed(() => buildApiEvents(source.events ?? [], source.eras ?? []));

  const staticDisplay = computed(() => buildStaticDisplay());

  /** 后端事件映射到四条泳道后为空 → 用设计稿离线数据复刻这张图 */
  const usingStaticEvents = computed(() => apiEvents.value.length === 0);

  const allEvents = computed(() =>
    usingStaticEvents.value ? staticDisplay.value : apiEvents.value,
  );

  /* ── 储备份额曲线：真实序列覆盖四国才整组替换，否则用设计稿示意值 ────── */

  const hasRealReserve = computed(() => hasRealReserveSeries(source.reserve ?? []));

  const curveSeries = computed(() => buildCurveSeries(source.reserve ?? []));

  const showIllustrative = computed(() => usingStaticEvents.value || !hasRealReserve.value);

  const illustrativeHint = computed(() =>
    usingStaticEvents.value
      ? "timeline 接口暂无可用事件，当前用设计稿离线数据绘制"
      : "powers.reserve 观测点不足以覆盖荷兰盾 / 英镑 / 美元 / 人民币四条序列，储备份额曲线用设计稿示意值",
  );

  const renderedCurves = computed(() =>
    buildRenderedCurves(curveSeries.value, windowStart.value, PR.value),
  );

  /* ── 泳道 / 色带 / 事件标记 ─────────────────────────────────────────── */

  const laneRows = computed(() =>
    buildLaneRows(LANES, windowStart.value, layerState, allEvents.value, PR.value, LAYER_COLOR),
  );

  /* ── 交互 ───────────────────────────────────────────────────────────── */

  const measure = () => {
    const el = scrollEl.value;
    if (!el) return;
    const width = el.clientWidth - 8;
    if (width > 0) contentWidth.value = width;
  };

  let observer: ResizeObserver | null = null;

  const scrollRatio = () => {
    const el = scrollEl.value;
    if (!el) return 0;
    const max = el.scrollWidth - el.clientWidth;
    return max > 0 ? el.scrollLeft / max : 0;
  };

  const restoreScroll = async (ratio: number) => {
    await nextTick();
    const el = scrollEl.value;
    if (!el) return;
    el.scrollLeft = ratio * Math.max(0, el.scrollWidth - el.clientWidth);
  };

  const select = (item: TimelineEventItem) => {
    lastSelectedId.value = item.id;
    onSelect(item);
  };

  const visibleEvents = () =>
    allEvents.value.filter((event) => event.year >= windowStart.value && layerState[event.layer]);

  /** 时间窗切换后，若当前选中事件落在窗外，就改选首个可见事件（原型行为） */
  const ensureVisibleSelection = () => {
    const current = allEvents.value.find((event) => event.id === lastSelectedId.value);
    if (current && current.year >= windowStart.value) return;
    const first = visibleEvents()[0];
    if (first) select(first.item);
  };

  const setWindow = (year: number) => {
    if (windowStart.value === year) return;
    const ratio = scrollRatio();
    windowStart.value = year;
    void restoreScroll(ratio);
    ensureVisibleSelection();
  };

  const toggleLayer = (key: LayerKey) => {
    layerState[key] = !layerState[key];
  };

  const zoomIn = () => {
    if (zoomIndex.value >= ZOOMS.length - 1) return;
    const ratio = scrollRatio();
    zoomIndex.value += 1;
    void restoreScroll(ratio);
  };

  const zoomOut = () => {
    if (zoomIndex.value <= 0) return;
    const ratio = scrollRatio();
    zoomIndex.value -= 1;
    void restoreScroll(ratio);
  };

  const onLaneClick = (lane: LaneId, event: MouseEvent) => {
    const svg = svgEl.value;
    if (!svg) return;
    const box = svg.getBoundingClientRect();
    if (!box.width) return;
    const relX = ((event.clientX - box.left) / box.width) * W.value;
    const px = Math.min(PR.value, Math.max(PL, relX));
    const year = windowStart.value + ((px - PL) / (PR.value - PL)) * (END_YEAR - windowStart.value);
    let best: DisplayEvent | null = null;
    for (const item of visibleEvents()) {
      if (item.lane !== lane) continue;
      if (!best || Math.abs(item.year - year) < Math.abs(best.year - year)) best = item;
    }
    if (best) select(best.item);
  };

  onMounted(() => {
    measure();
    if (typeof ResizeObserver !== "undefined" && scrollEl.value) {
      observer = new ResizeObserver(() => measure());
      observer.observe(scrollEl.value);
    }
  });

  onBeforeUnmount(() => {
    observer?.disconnect();
    observer = null;
  });

  return {
    scrollEl,
    svgEl,
    windowStart,
    zoomIndex,
    layerState,
    zoom,
    W,
    H,
    PR,
    outYearX,
    ticks,
    xOfYear,
    yOfReserve,
    r1,
    allEvents,
    showIllustrative,
    illustrativeHint,
    renderedCurves,
    laneRows,
    zoomPercent: computed(() => Math.round((ZOOMS[zoomIndex.value] ?? 1) * 100)),
    visibleEvents,
    setWindow,
    toggleLayer,
    zoomIn,
    zoomOut,
    onLaneClick,
    select,
  };
}
