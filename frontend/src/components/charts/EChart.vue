<template>
  <div class="echart-host" :style="{ height: typeof height === 'number' ? `${height}px` : height }">
    <VChart v-if="!empty" :option="option" autoresize :class="{ 'is-loading': loading }" />
    <div v-else class="echart-empty">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { BarChart, CandlestickChart, LineChart, ScatterChart, TreemapChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import type { EChartsOption } from "echarts";

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  CandlestickChart,
  ScatterChart,
  TreemapChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent,
  MarkLineComponent,
  VisualMapComponent,
  TitleComponent,
]);

const props = withDefaults(
  defineProps<{
    option: EChartsOption;
    height?: number | string;
    loading?: boolean;
  }>(),
  { height: 280, loading: false },
);

const empty = computed(() => !props.option || !props.option.series);
</script>

<style scoped>
.echart-host {
  position: relative;
  width: 100%;
}
.echart-host :deep(.echarts) {
  width: 100%;
  height: 100%;
  transition: opacity 0.2s ease;
}
.echart-host :deep(.is-loading) {
  opacity: 0.45;
}
.echart-empty {
  display: grid;
  place-items: center;
  height: 100%;
  min-height: 120px;
  color: var(--dim);
  font-size: 11px;
  border: 1px dashed var(--border);
  border-radius: 8px;
}
</style>
