<template>
  <section class="card" style="margin-top: 12px">
    <div class="card-head">
      <span class="card-title">验收自检（DoD）</span>
      <span class="card-sub">scripts/check_acceptance.ps1 · {{ acceptance?.checks.length ?? "—" }} 项</span>
      <div class="card-actions">
        <span class="badge badge--sm" :class="acceptance?.passed ? 'badge--live' : 'badge--warn'">
          {{ acceptance?.passed ? "全部通过" : `${acceptance?.failed_summary?.count ?? "存在"} 项失败` }}
        </span>
        <span v-if="acceptance?.warnings_summary?.count" class="badge badge--sm badge--warn">
          {{ acceptance.warnings_summary.count }} 项警告
        </span>
      </div>
    </div>
    <div v-if="acceptance?.failed_summary?.failed?.length" class="card-body">
      <div class="badge badge--down" style="display: block; white-space: normal; line-height: 1.6">
        <b>失败说明</b>
        <div v-for="item in acceptance.failed_summary.failed.slice(0, 5)" :key="item.id ?? item.name" style="margin-top: 4px">
          <b>{{ item.name }}</b>：{{ item.reason ?? item.detail }}
          <span v-if="item.remediation" class="dim"> · 处置：{{ item.remediation }}</span>
        </div>
        <div v-for="hint in acceptance.failed_summary.hints ?? []" :key="hint" class="dim" style="margin-top: 2px">
          {{ hint }}
        </div>
      </div>
    </div>
    <div class="table-wrap sys-wrap">
      <SkeletonBlock v-if="!acceptance && acceptanceLoading" :rows="5" />
      <ErrorState v-else-if="acceptanceError" :error="acceptanceError" @retry="emit('retry')" />
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>检查项</th>
            <th>分类</th>
            <th>严重度</th>
            <th>状态</th>
            <th>实际 / 要求</th>
            <th>说明与处置</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(check, index) in acceptance?.checks ?? []" :key="check.id ?? index">
            <td>{{ check.name }}</td>
            <td class="muted">{{ check.category ?? "—" }}</td>
            <td>
              <span class="badge badge--sm" :class="check.severity === 'error' || check.severity === 'critical' ? 'badge--down' : check.severity === 'warn' ? 'badge--warn' : 'badge--live'">
                {{ check.severity ?? "info" }}
              </span>
            </td>
            <td>
              <span class="badge badge--sm" :class="check.status === 'fail' ? 'badge--down' : check.status === 'warn' ? 'badge--warn' : 'badge--live'">
                {{ check.status === 'fail' ? "失败" : check.status === 'warn' ? "警告" : "通过" }}
              </span>
            </td>
            <td class="muted mono">{{ check.actual ?? "—" }} / {{ check.required ?? "—" }}</td>
            <td class="muted cell-wrap">
              <div v-if="check.reason">{{ check.reason }}</div>
              <div v-if="check.impact" class="dim">影响：{{ check.impact }}</div>
              <div v-if="check.remediation" class="dim">处置：{{ check.remediation }}</div>
              <div v-if="!check.reason && !check.remediation">{{ String(check.detail ?? "—") }}</div>
            </td>
            <td>
              <button
                v-if="check.status === 'fail' && check.action_job"
                class="btn btn--sm btn--ghost"
                type="button"
                @click="emit('job', check.action_job)"
              >
                {{ check.action_job }}
              </button>
              <span v-else class="dim">—</span>
            </td>
          </tr>
          <tr v-if="!(acceptance?.checks ?? []).length">
            <td colspan="7">
              <EmptyState
                text="尚未运行验收自检"
                hint="验收检查由 /api/system/acceptance 实时计算；确认后端就绪后点右上角刷新。"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="acceptance?.counts" class="card-foot">
      <span v-for="(value, key) in acceptance.counts" :key="key" class="count-chip">
        {{ countLabel(String(key)) }} <b>{{ fmtInt(Number(value)) }}</b>
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { Acceptance } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtInt } from "@/composables/useFormat";

defineProps<{
  acceptance: Acceptance | null;
  acceptanceLoading: boolean;
  acceptanceError: Error | null;
}>();

const emit = defineEmits<{
  retry: [];
  job: [name: string];
}>();

function countLabel(key: string): string {
  const labels: Record<string, string> = {
    instruments: "标的",
    market_bars: "日线",
    quotes: "快照",
    macro: "宏观",
    calendar: "日历",
    documents: "新闻",
    bodies: "原文",
    claims: "断言",
    briefs: "简报",
    analytics: "分析",
    signals: "信号",
    plans: "计划",
    theses: "论点",
    alerts: "告警",
  };
  return labels[key] ?? key;
}
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.sys-wrap {
  max-height: none;
}
.count-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 10px;
  color: var(--dim);
}
.count-chip b {
  font-family: var(--mono);
  color: var(--muted);
  font-weight: 600;
}
</style>
