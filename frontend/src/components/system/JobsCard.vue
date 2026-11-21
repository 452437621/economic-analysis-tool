<template>
  <section class="card" style="margin-top: 12px">
    <div class="card-head">
      <span class="card-title">任务调度</span>
      <span class="card-sub">任务目的 · cron 定义 · 最近运行 · 点击「调度次数」查看执行历史；超过 24h 未跑标黄，超过 72h 标红</span>
      <div class="card-actions">
        <span class="badge badge--sm" :class="neverRanJobs ? 'badge--warn' : 'badge--live'">
          {{ neverRanJobs }} 个未运行
        </span>
        <span class="badge badge--sm" :class="staleJobs ? 'badge--warn' : 'badge--live'">
          {{ staleJobs }} 个超 24h
        </span>
        <span class="card-sub">{{ jobs.length }} 项</span>
      </div>
    </div>
    <div class="table-wrap sys-wrap">
      <SkeletonBlock v-if="!jobs.length && jobsLoading" :rows="5" />
      <ErrorState v-else-if="jobsError" :error="jobsError" @retry="emit('retry')" />
      <table v-else class="data-table sys-jobs">
        <thead>
          <tr>
            <th class="col-job">任务</th>
            <th class="col-desc">任务描述</th>
            <th class="col-cron">计划</th>
            <th class="col-on">启用</th>
            <th class="col-status">最近状态</th>
            <th class="col-run">最近运行 / 时效</th>
            <th class="col-count">调度次数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.name">
            <td class="mono col-job">{{ job.name }}</td>
            <td class="job-desc col-desc">{{ job.description ?? "—" }}</td>
            <td class="mono col-cron">{{ job.cron }}</td>
            <td class="col-on">{{ job.enabled ? "是" : "否" }}</td>
            <td class="col-status">
              <span
                class="badge badge--sm"
                :class="job.last_status === 'error' ? 'badge--warn' : 'badge--live'"
                :title="job.last_error ?? statusLabel(job.last_status)"
              >
                {{ statusLabel(job.last_status) }}
              </span>
            </td>
            <td class="col-run">
              <span class="run-cell">
                <span class="muted">{{ fmtDateTime(job.last_run_at) }}</span>
                <span
                  v-if="job.overdue"
                  class="badge badge--sm badge--warn"
                  :title="job.overdue_reason ?? `应执行 ${fmtDateTime(job.due_at)}`"
                >
                  逾期
                </span>
                <span
                  v-if="jobStale(job).cls"
                  class="badge badge--sm"
                  :class="jobStale(job).cls"
                  :title="jobStale(job).title"
                >
                  {{ jobStale(job).text }}
                </span>
                <span v-else class="dim sys-age" :title="jobStale(job).title">{{ jobStale(job).text }}</span>
              </span>
            </td>
            <td class="col-count">
              <button class="link-count" type="button" :title="`查看 ${job.name} 的执行历史`" @click="emit('open', job)">
                <b class="mono">{{ job.run_count }}</b>
                <span class="link-count-more">次 · 历史</span>
              </button>
            </td>
          </tr>
          <tr v-if="!jobs.length">
            <td colspan="7">
              <EmptyState
                text="暂无调度任务"
                hint="后端 /api/system/jobs 没有返回任务：先确认「服务」卡里调度器正常，再看 backend 的 jobs 表是否为空（可用 scripts 里的种子脚本补齐）。"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { JobRow } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDateTime } from "@/composables/useFormat";
import { statusLabel } from "@/composables/useSystemData";

const props = defineProps<{
  jobs: JobRow[];
  jobsLoading: boolean;
  jobsError: Error | null;
}>();

const emit = defineEmits<{
  retry: [];
  open: [job: JobRow];
}>();

/** 超过 24h 未跑标黄，超过 72h 标红（用户要求的作业时效约束） */
const STALE_WARN_HOURS = 24;
const STALE_DOWN_HOURS = 72;

function runAgeHours(iso: string | null): number | null {
  if (!iso) return null;
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return null;
  return (Date.now() - ts) / 3_600_000;
}

interface StaleMark {
  text: string;
  cls: string;
  title: string;
}

function jobStale(job: JobRow): StaleMark {
  const hours = runAgeHours(job.last_run_at);
  if (hours === null) {
    return {
      text: "从未运行",
      cls: "badge--warn",
      title: "没有最近运行记录：确认任务已启用（启用列为「是」），或手动触发一次对应作业。",
    };
  }
  const since = `最近一次运行 ${fmtDateTime(job.last_run_at)}`;
  if (hours >= STALE_DOWN_HOURS) {
    return {
      text: `停滞 ${Math.floor(hours / 24)} 天`,
      cls: "badge--down",
      title: `${since}，已 ${Math.floor(hours / 24)} 天未运行（阈值 72 小时）：检查调度器是否在跑、任务是否被禁用。`,
    };
  }
  if (hours >= STALE_WARN_HOURS) {
    return {
      text: `${Math.round(hours)} 小时未跑`,
      cls: "badge--warn",
      title: `${since}，已 ${Math.round(hours)} 小时未运行（阈值 24 小时）：可能是调度间隔较长或上次运行失败。`,
    };
  }
  return {
    text: `${hours < 1 ? "刚刚" : `${hours.toFixed(1)}h 前`}`,
    cls: "",
    title: `${since}（${hours.toFixed(1)} 小时前）`,
  };
}

const staleJobs = computed(
  () => props.jobs.filter((job) => (runAgeHours(job.last_run_at) ?? Infinity) >= STALE_WARN_HOURS).length,
);
const neverRanJobs = computed(() => props.jobs.filter((job) => !job.last_run_at).length);
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.sys-wrap {
  max-height: none;
}
.sys-jobs {
  table-layout: fixed;
}
.sys-jobs .col-job {
  width: 150px;
}
.sys-jobs .col-cron {
  width: 118px;
}
.sys-jobs .col-on {
  width: 44px;
  text-align: center;
}
.sys-jobs .col-status {
  width: 84px;
}
.sys-jobs .col-run {
  width: 190px;
}
.sys-jobs .col-count {
  width: 96px;
  text-align: right;
}
.sys-jobs td.col-job {
  overflow: hidden;
  text-overflow: ellipsis;
}
.sys-jobs .job-desc {
  font-size: 10.5px;
  line-height: 1.45;
  color: var(--muted);
  white-space: normal;
  overflow-wrap: anywhere;
}
.run-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.link-count {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 10px;
  cursor: pointer;
}
.link-count:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.link-count b {
  font-size: 11px;
  color: var(--text);
}
.link-count-more {
  font-size: 9.5px;
  color: var(--dim);
}
.sys-age {
  font-family: var(--mono);
  font-size: 10px;
  white-space: nowrap;
}
</style>
