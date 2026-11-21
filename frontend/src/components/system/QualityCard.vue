<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">数据质检</span>
      <span class="card-sub">官方对账 · 新鲜度</span>
      <div class="card-actions">
        <span class="badge badge--sm" :class="quality?.summary.failed ? 'badge--warn' : 'badge--live'">
          {{ quality?.summary.passed ?? "—" }} / {{ quality?.summary.total ?? "—" }}
        </span>
        <button class="btn btn--sm btn--ghost" type="button" @click="emit('repair')">自动修复</button>
      </div>
    </div>
    <div class="table-wrap sys-wrap">
      <SkeletonBlock v-if="!quality && qualityLoading" :rows="5" />
      <ErrorState v-else-if="qualityError" :error="qualityError" @retry="emit('retry')" />
      <table v-else class="data-table sys-quality">
        <colgroup>
          <col class="q-dataset-col" />
          <col class="q-kind-col" />
          <col class="q-status-col" />
          <col class="q-status-col" />
          <col />
          <col />
          <col class="q-status-col" />
        </colgroup>
        <thead>
          <tr>
            <th>数据集</th>
            <th>类型</th>
            <th>严重度</th>
            <th>状态</th>
            <th>期望 / 实际 / 偏差</th>
            <th>明细 / 处置</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in quality?.data ?? []" :key="`${row.dataset}-${index}`">
            <td class="q-dataset" :title="row.dataset">{{ row.dataset }}<span v-if="row.symbol" class="dim"> / {{ row.symbol }}</span></td>
            <td class="muted q-kind">{{ row.kind }}</td>
            <td>
              <span class="badge badge--sm" :class="row.severity === 'error' || row.severity === 'critical' ? 'badge--down' : row.severity === 'warn' ? 'badge--warn' : 'badge--live'">
                {{ row.severity ?? (row.passed ? "info" : "warn") }}
              </span>
            </td>
            <td>
              <span class="badge badge--sm" :class="row.passed ? 'badge--live' : 'badge--warn'">
                {{ row.passed ? "通过" : "失败" }}
              </span>
            </td>
            <td class="muted mono">
              {{ row.expected ?? "—" }} / {{ row.actual ?? "—" }} / {{ row.deviation ?? "—" }}
            </td>
            <td class="muted q-detail">
              {{ row.detail ?? "—" }}
              <div v-if="!row.passed && row.remediation" class="dim">
                处置：{{ row.remediation }}
              </div>
            </td>
            <td>
              <button
                v-if="!row.passed && row.action_job"
                class="btn btn--sm btn--ghost"
                type="button"
                @click="emit('job', row.action_job)"
              >
                {{ row.action_job }}
              </button>
              <span v-else class="dim">—</span>
            </td>
          </tr>
          <tr v-if="!(quality?.data ?? []).length">
            <td colspan="7">
              <EmptyState
                text="暂无质检结果"
                hint="质检数据由定时作业把新鲜度 / 覆盖率 / 连续性 / 对账结果写入 data_quality；作业跑过之后这里才有行。"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { QualityResponse } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";

defineProps<{
  quality: QualityResponse | null;
  qualityLoading: boolean;
  qualityError: Error | null;
}>();

const emit = defineEmits<{
  retry: [];
  repair: [];
  job: [name: string];
}>();
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.sys-wrap {
  max-height: none;
}
.sys-quality {
  table-layout: fixed;
}
.sys-quality .q-dataset-col {
  width: 132px;
}
.sys-quality .q-kind-col {
  width: 84px;
}
.sys-quality .q-status-col {
  width: 72px;
}
.sys-quality .q-dataset {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sys-quality .q-kind,
.sys-quality .q-detail {
  font-size: 10.5px;
  line-height: 1.45;
}
.sys-quality .q-kind {
  white-space: nowrap;
}
.sys-quality .q-detail {
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
