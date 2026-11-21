<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">历史类比明细</span>
      <span class="cyc-card-sub">20 维状态向量近邻 · 剔除最近 {{ analogs?.min_gap_months ?? 12 }} 个月</span>
      <div class="card-actions">
        <RouterLink class="cyc-card-sub cyc-inline-link" :to="{ path: '/pipeline', query: { code: 'cycle.analogs' } }">
          为什么 →
        </RouterLink>
      </div>
    </div>
    <div class="card-body">
      <ul v-if="analogList.length" class="cyc-analog-list">
        <li v-for="item in analogList.slice(0, 4)" :key="item.month" class="cyc-analog-line">
          <span class="cyc-analog-month mono">{{ item.month }}</span>
          <span class="cyc-analog-sim-bar">
            <i :style="{ width: `${barWidth(item.similarity * 100, 4)}%` }"></i>
          </span>
          <b class="mono">{{ ratioText(item.similarity) }}</b>
          <span class="cyc-analog-state mono">
            增长 {{ fmtNumber(item.state.growth, 0) }} · 通胀 {{ fmtNumber(item.state.inflation, 0) }}
          </span>
        </li>
      </ul>
      <EmptyState v-else text="暂无类比结果" hint="样本内近邻不足或未生成 analogs 段。" />
      <p v-if="Array.isArray(analogs?.caveats) && analogs.caveats.length" class="cyc-layer-meta">
        {{ analogs.caveats[0] ?? "" }}
      </p>
    </div>
    <div class="card-foot">
      <span>类比是「样本内比较」，相似不保证同路径。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtNumber } from "@/composables/useFormat";
import type { CycleAnalog, CycleAnalogs } from "@/api/types";
import type { RawOf } from "@/utils/cycleNormalize";
import { barWidth, ratioText } from "@/utils/cycleFormat";

defineProps<{
  analogList: CycleAnalog[];
  analogs: RawOf<CycleAnalogs>;
}>();
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-inline-link {
  text-decoration: none;
  color: var(--accent);
  font-weight: 500;
}
.cyc-analog-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.cyc-analog-line {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) 34px minmax(0, 1.15fr);
  gap: 7px;
  align-items: center;
  font-size: 9px;
  color: var(--muted);
}
.cyc-analog-month {
  font-size: 9px;
}
.cyc-analog-sim-bar {
  height: 5px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-analog-sim-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
}
.cyc-analog-line b {
  font-size: 9.5px;
  text-align: right;
  color: var(--text);
}
.cyc-analog-state {
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-layer-meta {
  margin: 3px 0 0;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
}
</style>
