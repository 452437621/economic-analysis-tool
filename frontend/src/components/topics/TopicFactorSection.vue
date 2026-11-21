<template>
  <div class="topic-factor-groups">
    <section v-for="group in groups" :key="group.key" class="card topic-factor-card">
      <div class="card-head">
        <span class="card-title">{{ group.label }}</span>
        <span class="badge badge--sm" :class="group.contribution >= 0 ? 'badge--up' : 'badge--down'">
          贡献 {{ fmtSigned(group.contribution, 2) }}
        </span>
        <span class="card-sub">{{ group.available }}/{{ group.items.length }} 可用</span>
      </div>
      <div class="card-body topic-factor-body">
        <div v-for="item in group.items" :key="item.code" class="topic-factor-row">
          <span class="topic-factor-name" :title="`${item.name}（${item.code}）`">{{ item.name }}</span>
          <span class="topic-factor-value">{{ valueText(item) }}</span>
          <span class="topic-factor-score" :class="trendClass(item.weightedScore)">
            {{ item.available ? fmtSigned(item.score, 1) : "—" }}
          </span>
          <span class="badge badge--sm" :class="signalClass(item.signal)">{{ signalLabel(item.signal) }}</span>
        </div>
        <EmptyState v-if="!group.items.length" text="暂无因子" />
      </div>
    </section>
    <EmptyState v-if="!groups.length" text="暂无因子分组" hint="等待采集任务写入数据。" />
  </div>

  <section v-if="rows.length" class="card table-card">
    <div class="card-head">
      <span class="card-title">因子明细</span>
      <span class="card-sub">{{ rows.length }} 项 · 仅计权因子与量化信号</span>
    </div>
    <div class="card-body table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>因子</th><th>分组</th><th>数值</th><th>权重</th><th>得分</th><th>贡献</th><th>信号</th><th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in rows" :key="`${item.kind || 'f'}-${item.code}`">
            <td>{{ item.name }}<span class="topic-code">{{ item.code }}</span></td>
            <td class="muted">{{ item.category_label || item.category || "—" }}</td>
            <td class="num">{{ valueText(item) }}</td>
            <td class="num">{{ item.weight }}</td>
            <td class="num">{{ item.available ? fmtSigned(item.score, 1) : "—" }}</td>
            <td class="num" :class="trendClass(item.contribution)">{{ fmtSigned(item.contribution, 2) }}</td>
            <td><span class="badge badge--sm" :class="signalClass(item.signal)">{{ signalLabel(item.signal) }}</span></td>
            <td class="cell-wrap muted">{{ item.explain || item.note || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicFactor, TopicFactorGroup, TopicFactorsData } from "@/api/types";
import { fmtSigned, trendClass } from "@/composables/useFormat";
import { formatValue, signalClass, signalLabel } from "@/utils/topicFormat";

const props = defineProps<{ data: unknown }>();

interface RowFactor extends TopicFactor {
  weightedScore: number;
}

const payload = computed(() => {
  const value = (props.data ?? {}) as Partial<TopicFactorsData>;
  return {
    groups: (value.groups ?? []) as TopicFactorGroup[],
    factors: value.factors ?? [],
    signals: value.signals ?? [],
  };
});
const groups = computed(() =>
  payload.value.groups.map((group) => ({
    ...group,
    items: (group.items ?? []).map((item) => ({ ...item, weightedScore: item.available ? item.score : 0 })),
  })),
);
const rows = computed<RowFactor[]>(() =>
  [...payload.value.factors, ...payload.value.signals].map((item) => ({
    ...item,
    weightedScore: item.available ? item.score : 0,
  })),
);

function valueText(item: TopicFactor): string {
  if (item.value == null) return "—";
  return formatValue(item.value, item.unit, 2);
}
</script>

<style scoped>
.topic-factor-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 10px;
}
.topic-factor-card {
  min-width: 0;
}
.topic-factor-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.topic-factor-row {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 7px;
  padding: 3px 0;
  border-bottom: 1px dashed var(--border);
  font-size: 10.5px;
}
.topic-factor-name,
.topic-factor-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topic-factor-value {
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.topic-factor-score {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.topic-factor-score.up {
  color: var(--up-color);
}
.topic-factor-score.down {
  color: var(--down-color);
}
.topic-code {
  margin-left: 5px;
  font-size: 9px;
  color: var(--muted);
  font-family: var(--mono, monospace);
}
</style>
