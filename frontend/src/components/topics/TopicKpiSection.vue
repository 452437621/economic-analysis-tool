<template>
  <div class="kpi-grid topic-kpi-grid">
    <article v-for="item in items" :key="item.key" class="card topic-kpi">
      <div class="topic-kpi-label">{{ item.label }}</div>
      <div class="topic-kpi-value" :class="toneClass(item.tone)">
        {{ display(item) }}
        <small v-if="item.unit">{{ item.unit }}</small>
      </div>
      <div class="topic-kpi-note">{{ item.note || "—" }}</div>
    </article>
    <EmptyState v-if="!items.length" text="暂无关键读数" hint="等待采集任务写入数据。" />
  </div>
  <div v-if="payload.text" class="topic-kpi-foot">{{ payload.text }}</div>
  <div v-if="regimeText" class="topic-kpi-foot">
    波动状态 <b>{{ regimeText }}</b>
    <span v-if="payload.regime?.trend_state"> · 趋势 {{ payload.regime.trend_state }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicKpi, TopicKpisData } from "@/api/types";
import { formatValue } from "@/utils/topicFormat";

const props = defineProps<{ data: unknown; label?: string }>();

const payload = computed<TopicKpisData>(() => {
  const value = (props.data ?? {}) as TopicKpisData;
  return { items: value.items ?? [], regime: value.regime ?? null, text: value.text };
});
const items = computed<TopicKpi[]>(() => payload.value.items ?? []);
const regimeText = computed(() => {
  const regime = payload.value.regime as Record<string, unknown> | null | undefined;
  const state = regime?.vol_state;
  return state ? String(state) : "";
});

function display(item: TopicKpi): string {
  if (typeof item.value === "number") return formatValue(item.value, undefined, item.digits ?? 2);
  if (item.value === null || item.value === undefined || item.value === "") return "—";
  return String(item.value);
}

function toneClass(tone?: string): string {
  if (tone === "up" || tone === "down") return tone;
  return "";
}
</script>

<style scoped>
.topic-kpi-grid {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}
.topic-kpi {
  padding: 10px 12px;
  min-width: 0;
}
.topic-kpi-label {
  font-size: 10.5px;
  color: var(--muted);
}
.topic-kpi-value {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.topic-kpi-value small {
  margin-left: 3px;
  font-size: 10px;
  font-weight: 400;
  color: var(--muted);
}
.topic-kpi-value.up {
  color: var(--up-color);
}
.topic-kpi-value.down {
  color: var(--down-color);
}
.topic-kpi-note {
  margin-top: 4px;
  font-size: 10px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topic-kpi-foot {
  margin-top: 6px;
  font-size: 10.5px;
  color: var(--muted);
}
</style>
