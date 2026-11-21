<template>
  <!-- 图表 -->
  <div class="sec-row">
    <span class="sec-title">走势图表</span>
    <span class="sec-count">{{ chartCards.length }} 张</span>
    <span class="sec-meta">数据来自本地数据库 · 默认不叠加金价，可按图表叠加伦敦金价对比</span>
    <div class="sec-actions">
      <div class="chart-ranges" role="group" aria-label="图表时间范围">
        <button
          v-for="item in HISTORY_RANGES"
          :key="item.value"
          type="button"
          :class="{ active: chartRange === item.value }"
          @click="$emit('range', item.value)"
        >
          {{ item.label }}
        </button>
      </div>
      <span class="badge badge--sm">{{ seriesCount }} 条序列</span>
    </div>
  </div>
  <div class="charts-grid">
    <section
      v-for="chart in chartCards"
      :key="chart.key"
      class="card chart-card"
      :class="{ 'chart-wide': chart.wide }"
    >
      <div class="card-head">
        <span class="card-title">{{ chart.title }}</span>
        <span class="badge badge--sm">{{ chart.unit }}</span>
        <span class="chart-legend">
          <span v-for="item in chart.legend" :key="item.label" class="lg-item" :class="{ 'lg-dim': !item.available }">
            <i class="lg-dot" :class="item.cls"></i>{{ item.label }}
          </span>
        </span>
        <span v-if="chart.note" class="chart-note">{{ chart.note }}</span>
        <div class="card-actions">
          <button
            type="button"
            class="chart-toggle"
            :class="{ active: priceOverlays[chart.key] }"
            :aria-pressed="!!priceOverlays[chart.key]"
            :title="priceOverlays[chart.key] ? '移除伦敦金价对比' : '叠加伦敦金价趋势对比'"
            @click="$emit('toggle-overlay', chart.key)"
          >
            叠加金价
          </button>
          <span class="card-sub">{{ chart.meta }}</span>
        </div>
      </div>
      <div class="card-body chart-body">
        <EChart v-if="chart.hasData" :option="chart.option" :height="chart.height" />
        <EmptyState v-else :text="chart.emptyText" :hint="chart.emptyHint" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import EChart from "@/components/charts/EChart.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import { HISTORY_RANGES, type HistoryRange } from "@/stores/history";
import type { ChartCard } from "@/utils/goldCharts";

defineProps<{
  chartCards: ChartCard[];
  chartRange: HistoryRange;
  seriesCount: number;
  priceOverlays: Record<string, boolean>;
}>();

defineEmits<{
  (e: "range", range: HistoryRange): void;
  (e: "toggle-overlay", key: string): void;
}>();
</script>

<style scoped>
/* ---------- 图表 ---------- */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.chart-card {
  min-width: 0;
  overflow: hidden;
}
.chart-wide {
  grid-column: 1 / -1;
}
.chart-body {
  padding: 6px 8px 4px;
}
.chart-legend {
  display: flex;
  gap: 9px;
  min-width: 0;
  overflow: hidden;
}
.lg-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9.5px;
  color: var(--muted);
  white-space: nowrap;
}
.lg-dim {
  color: var(--dim);
}
.lg-dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 2px;
}
.lg-a {
  background: var(--accent);
}
.lg-w {
  background: var(--warn);
}
.lg-m {
  background: var(--muted);
}
.lg-g {
  background: var(--gold);
}
.lg-dim .lg-dot {
  background: var(--dim);
}
.chart-note {
  flex: none;
  font-size: 9px;
  color: var(--warn);
  white-space: nowrap;
}
/* 时间范围切换：与资产历史走势弹窗（HistoryModal）保持同一组选项与样式 */
.chart-ranges {
  display: flex;
  gap: 3px;
}
.chart-ranges button {
  height: 24px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10.5px;
  cursor: pointer;
}
.chart-ranges button:hover {
  color: var(--text);
}
.chart-ranges button.active {
  color: var(--accent);
  border-color: var(--accent-line);
  background: var(--accent-weak);
}
/* 按图表叠加伦敦金价对比 */
.chart-toggle {
  height: 22px;
  padding: 0 7px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10px;
  cursor: pointer;
  white-space: nowrap;
}
.chart-toggle:hover {
  color: var(--gold);
  border-color: color-mix(in srgb, var(--gold) 45%, var(--border));
}
.chart-toggle.active {
  color: var(--gold);
  border-color: color-mix(in srgb, var(--gold) 55%, var(--border));
  background: color-mix(in srgb, var(--gold) 14%, transparent);
}
@media (max-width: 1360px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
  .chart-wide {
    grid-column: auto;
  }
}
</style>
