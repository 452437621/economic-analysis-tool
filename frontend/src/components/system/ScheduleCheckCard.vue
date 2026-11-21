<template>
  <section class="card" style="margin-top: 12px">
    <div class="card-head">
      <span class="card-title">调度自检</span>
      <span class="card-sub">
        启动/周期检查 · 数据就绪 · 逾期补跑 · {{ schedule ? `${schedule.summary.overdue} 个逾期` : "加载中" }}
      </span>
      <div class="card-actions">
        <span
          class="badge badge--sm"
          :class="schedule?.summary.overdue ? 'badge--warn' : 'badge--live'"
        >
          {{ schedule?.summary.overdue ?? "—" }} 逾期
        </span>
        <span
          class="badge badge--sm"
          :class="qualityGate?.status === 'blocked' ? 'badge--down' : qualityGate?.status === 'degraded' ? 'badge--warn' : 'badge--live'"
        >
          质量 {{ qualityGate?.status ?? "—" }}
        </span>
        <button class="btn btn--sm" type="button" :disabled="scheduleBusy" @click="emit('trigger')">
          {{ scheduleBusy ? "检查中…" : "立即检查并补跑" }}
        </button>
      </div>
    </div>
    <div class="card-body">
      <div v-if="schedule?.summary" class="cov-stats">
        <div class="cov-stat">
          <span class="cov-stat-label">上次自检</span>
          <b class="cov-stat-value">{{ scheduleCheck ? fmtDateTime(scheduleCheck.finished_at ?? scheduleCheck.started_at) : "—" }}</b>
          <span class="cov-stat-sub">{{ scheduleCheck?.status ?? "尚未运行" }}</span>
        </div>
        <div class="cov-stat">
          <span class="cov-stat-label">数据就绪</span>
          <b class="cov-stat-value">{{ scheduleCheck?.report?.readiness?.status ?? "—" }}</b>
          <span class="cov-stat-sub">日线 / 宏观 / 快照</span>
        </div>
        <div class="cov-stat">
          <span class="cov-stat-label">逾期作业</span>
          <b class="cov-stat-value mono">{{ schedule.summary.overdue }}<small>/ {{ schedule.summary.total }}</small></b>
          <span class="cov-stat-sub">按计划周期或最近定点时点判断</span>
        </div>
        <div class="cov-stat">
          <span class="cov-stat-label">质量门</span>
          <b class="cov-stat-value">{{ qualityGate?.status ?? "—" }}</b>
          <span class="cov-stat-sub">{{ qualityGate?.caveat ?? "等待质检批次" }}</span>
        </div>
      </div>
      <SkeletonBlock v-if="scheduleLoading && !schedule" :rows="3" />
      <div v-else-if="overdueJobs.length" class="table-wrap sys-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>作业</th>
              <th>分组</th>
              <th>计划</th>
              <th>上次运行</th>
              <th>应执行</th>
              <th>动作 / 原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in overdueJobs" :key="job.name">
              <td class="mono">{{ job.name }}</td>
              <td class="muted">{{ job.group }}</td>
              <td class="mono">{{ job.cron || (job.period_seconds ? `${job.period_seconds}s` : "—") }}</td>
              <td class="muted">{{ fmtDateTime(job.last_run_at) }}</td>
              <td class="muted">{{ fmtDateTime(job.due_at) }}</td>
              <td class="muted cell-wrap">{{ job.reason ?? job.action }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState
        v-else
        text="没有逾期作业"
        hint="调度器按计划运行；启动或周期自检会把错过的数据采集与研判作业补齐。"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import type { QualityGate, ScheduleCheckRow, ScheduleJobRow, ScheduleResponse } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDateTime } from "@/composables/useFormat";

defineProps<{
  schedule: ScheduleResponse | null;
  scheduleCheck: ScheduleCheckRow | null;
  qualityGate: QualityGate | null;
  overdueJobs: ScheduleJobRow[];
  scheduleLoading: boolean;
  scheduleBusy: boolean;
}>();

const emit = defineEmits<{ trigger: [] }>();
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.sys-wrap {
  max-height: none;
}
.cov-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.cov-stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.cov-stat-label {
  font-size: 10px;
  letter-spacing: 0.4px;
  color: var(--dim);
}
.cov-stat-value {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.25;
  color: var(--text);
}
.cov-stat-value small {
  margin-left: 3px;
  font-size: 10px;
  font-weight: 500;
  color: var(--muted);
}
.cov-stat-sub {
  font-size: 10px;
  line-height: 1.45;
  color: var(--muted);
}
@media (max-width: 1240px) {
  .cov-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
