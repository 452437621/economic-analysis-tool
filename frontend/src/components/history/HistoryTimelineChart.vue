<script setup lang="ts">
/**
 * 世界长河 · 帝国兴衰 × 储备货币份额（内联 SVG 手绘时间轴）
 *
 * 这是 `docs/design/mockup-merged/index.html` 中 `#view-history` 时间轴卡片的 1:1 复刻：
 * 几何参数、字号、透明度、颜色、事件形状、图例全部照设计稿（SVG 部分见原型 buildTimeline()
 * 第 3999–4093 行，样式见第 1091–1104 行）。
 *
 * 数据来源优先级：
 *  1. 父级通过 props 传入后端 timeline 接口的真实数据（events / eras / reserve）；
 *  2. 后端不可用或事件无法归属四条泳道时，回落到设计稿的离线数据（LANES / EVENTS / CURVES），
 *     卡片右上角显示「示意数据」徽标，绝不白屏。
 */
import type { TimelineEra, TimelineEventItem, TimelinePowerPoint } from "@/api/types";
import TimelineCanvas from "@/components/history/TimelineCanvas.vue";
import TimelineFilters from "@/components/history/TimelineFilters.vue";
import { useTimelineViewport } from "@/composables/useTimelineViewport";

/* ── 组件接口 ───────────────────────────────────────────────────────── */

interface Props {
  /** 后端 timeline overview 的事件列表 */
  events?: TimelineEventItem[];
  /** 后端霸权分期，仅用于事件缺 power 时的泳道归属兜底 */
  eras?: TimelineEra[];
  /** 后端储备份额序列（powers.reserve） */
  reserve?: TimelinePowerPoint[];
}

const props = withDefaults(defineProps<Props>(), {
  events: () => [],
  eras: () => [],
  reserve: () => [],
});

const emit = defineEmits<{
  (event: "select", item: TimelineEventItem): void;
}>();

const {
  scrollEl,
  svgEl,
  windowStart,
  zoomIndex,
  layerState,
  W,
  PR,
  outYearX,
  ticks,
  xOfYear,
  showIllustrative,
  illustrativeHint,
  renderedCurves,
  laneRows,
  zoomPercent,
  setWindow,
  toggleLayer,
  zoomIn,
  zoomOut,
  onLaneClick,
  select,
} = useTimelineViewport(props, (item) => emit("select", item));

const setScrollEl = (el: unknown) => {
  scrollEl.value = el as HTMLDivElement | null;
};
const setSvgEl = (el: unknown) => {
  svgEl.value = el as SVGSVGElement | null;
};
</script>

<template>
  <div class="hst-tl">
    <TimelineFilters
      :window-start="windowStart"
      :layer-state="layerState"
      @set-window="setWindow"
      @toggle-layer="toggleLayer"
    />

    <div class="grid-history">
      <TimelineCanvas
        :scroll-el="setScrollEl"
        :svg-el="setSvgEl"
        :w="W"
        :pr="PR"
        :out-year-x="outYearX"
        :ticks="ticks"
        :x-of="xOfYear"
        :rendered-curves="renderedCurves"
        :lane-rows="laneRows"
        :layer-state="layerState"
        :show-illustrative="showIllustrative"
        :illustrative-hint="illustrativeHint"
        :zoom-index="zoomIndex"
        :zoom-percent="zoomPercent"
        @select="select"
        @lane-click="onLaneClick"
        @zoom-in="zoomIn"
        @zoom-out="zoomOut"
      />

      <!-- 右侧「事件详情」由父级传入，保持设计稿 292px 右栏位置 -->
      <slot />
    </div>
  </div>
</template>

<style scoped>
.hst-tl {
  min-width: 0;
}

/* 时间轴卡片 + 右侧详情（原型 index.html:483-491） */
.grid-history {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 292px;
  gap: 10px;
  margin-top: 10px;
  align-items: start;
}
@media (max-width: 1240px) {
  .grid-history {
    grid-template-columns: minmax(0, 1fr) 260px;
  }
}
@media (max-width: 1024px) {
  .grid-history {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
