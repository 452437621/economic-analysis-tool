<template>
  <div class="sec-row">
    <span class="sec-title">图表</span>
    <span class="sec-count">{{ charts.length }} 张</span>
    <span class="sec-meta">数据来自本地数据库</span>
    <div class="sec-actions">
      <div class="topic-ranges" role="group" aria-label="图表时间范围">
        <button
          v-for="item in TOPIC_RANGES"
          :key="item.value"
          type="button"
          :class="{ active: range === item.value }"
          @click="$emit('update:range', item.value)"
        >
          {{ item.label }}
        </button>
      </div>
    </div>
  </div>
  <div class="topic-charts-grid">
    <section
      v-for="chart in charts"
      :key="chart.key"
      class="card topic-chart-card"
      :class="{ 'topic-chart-wide': chart.wide }"
    >
      <div class="card-head">
        <span class="card-title">{{ chart.title }}</span>
        <span v-if="chart.unit" class="badge badge--sm">{{ chart.unit }}</span>
        <span v-if="chart.subtitle" class="card-sub">{{ chart.subtitle }}</span>
        <div class="card-actions">
          <span class="card-sub">{{ chart.note || "" }}</span>
        </div>
      </div>
      <div class="card-body topic-chart-body">
        <EChart v-if="chartHasData(chart)" :option="buildTopicChartOption(chart, palette, range)" :height="chart.height || 260" />
        <EmptyState v-else :text="chart.emptyText || '暂无数据'" hint="等待专题采集任务完成。" />
      </div>
    </section>
    <EmptyState v-if="!charts.length" text="暂无图表" hint="等待专题数据返回。" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EChart from "@/components/charts/EChart.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicChartsData, TopicChartSpec } from "@/api/types";
import { TOPIC_RANGES, buildTopicChartOption, chartHasData, type TopicRange } from "@/utils/topicCharts";
import type { GoldPalette } from "@/utils/goldCharts";

const props = defineProps<{
  data: unknown;
  range: TopicRange;
  palette: GoldPalette;
}>();

defineEmits<{ (e: "update:range", range: TopicRange): void }>();

const charts = computed<TopicChartSpec[]>(() => {
  const value = (props.data ?? {}) as Partial<TopicChartsData>;
  return value.charts ?? [];
});
</script>

<style scoped>
.topic-ranges {
  display: inline-flex;
  gap: 2px;
  border: 1px solid var(--border);
  border-radius: 7px;
  padding: 1px;
}
.topic-ranges button {
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 5px;
  cursor: pointer;
}
.topic-ranges button.active {
  background: var(--accent-weak);
  color: var(--accent);
}
.topic-charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.topic-chart-card {
  min-width: 0;
  overflow: hidden;
}
.topic-chart-wide {
  grid-column: 1 / -1;
}
.topic-chart-body {
  padding: 6px 8px 4px;
}
@media (max-width: 1100px) {
  .topic-charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
