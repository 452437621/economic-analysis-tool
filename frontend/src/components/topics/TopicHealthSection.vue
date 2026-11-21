<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">数据健康</span>
      <span v-if="payload.status" class="badge badge--sm" :class="statusClass">{{ payload.status }}</span>
      <span class="card-sub">{{ payload.datasets.length }} 个数据集</span>
    </div>
    <div v-if="payload.datasets.length" class="card-body table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>数据集</th>
            <th>行数</th>
            <th>最新</th>
            <th>状态</th>
            <th>来源</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in payload.datasets" :key="item.name">
            <td>{{ item.name }}</td>
            <td class="num">{{ item.rows }}</td>
            <td>{{ item.last || "—" }}</td>
            <td>
              <span class="badge badge--sm" :class="item.fresh ? 'badge--live' : 'badge--warn'">
                {{ item.fresh ? "新鲜" : "滞后/未采集" }}
              </span>
            </td>
            <td class="muted">{{ item.note || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else text="暂无数据集目录" hint="等待 collect_luoyang 首次运行。" />
    <div v-if="payload.gaps.length" class="card-foot topic-gaps">
      <b>缺口：</b>{{ payload.gaps.join("；") }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicHealthData } from "@/api/types";

const props = defineProps<{ data: unknown }>();
const payload = computed<TopicHealthData>(() => {
  const value = (props.data ?? {}) as Partial<TopicHealthData>;
  return {
    datasets: value.datasets ?? [],
    gaps: value.gaps ?? [],
    providers: value.providers ?? [],
    status: value.status,
  };
});
const statusClass = computed(() => {
  if (payload.value.status === "ok") return "badge--live";
  if (payload.value.status === "blocked") return "badge--down";
  return "badge--warn";
});
</script>

<style scoped>
.topic-gaps {
  line-height: 1.6;
}
</style>
