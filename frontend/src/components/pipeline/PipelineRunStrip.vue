<template>
  <section class="card pipe-run-strip">
    <header class="card-head">
      <span class="card-title">运行序列</span>
      <span class="card-sub">最近 {{ runs.length }} 次 · 点击切换选中运行</span>
      <div class="card-actions pipe-run-actions">
        <span v-if="error && runs.length" class="badge badge--warn badge--sm">运行列表刷新失败</span>
        <span class="pipe-run-current mono" :title="selectedRun?.id ?? ''">
          {{ selectedRun ? `${selectedRun.kind} · ${fmtDateTime(selectedRun.started_at)}` : "未选择运行" }}
        </span>
      </div>
    </header>
    <div v-if="selectedRun" class="pipe-run-summary">
      <div class="pipe-sum-cell">
        <span class="pipe-sum-label">运行编号</span>
        <b class="pipe-sum-value mono" :title="selectedRun.id">{{ shortId(selectedRun.id) }}</b>
      </div>
      <div class="pipe-sum-cell">
        <span class="pipe-sum-label">任务 · 环境</span>
        <b class="pipe-sum-value mono" :title="runEnvTitle">{{ runEnvText }}</b>
      </div>
      <div class="pipe-sum-cell">
        <span class="pipe-sum-label">耗时</span>
        <b class="pipe-sum-value mono">{{ fmtDuration(selectedRun.duration_ms) }}</b>
      </div>
      <div class="pipe-sum-cell">
        <span class="pipe-sum-label">步骤成功率</span>
        <b class="pipe-sum-value mono">{{ stepSuccessText }}</b>
      </div>
      <div class="pipe-sum-cell">
        <span class="pipe-sum-label">数据覆盖</span>
        <b class="pipe-sum-value mono" :title="coverageTitle">{{ coverageText }}</b>
      </div>
      <div class="pipe-sum-cell">
        <span class="pipe-sum-label">完成于</span>
        <b class="pipe-sum-value mono">{{ fmtDateTime(selectedRun.finished_at) }}</b>
      </div>
    </div>
    <div v-else class="pipe-run-summary pipe-run-summary--empty">
      未选择运行：选中下方任一运行后，这里展示运行编号、任务环境、耗时、步骤成功率、数据覆盖与完成时间。
    </div>
    <div class="pipe-run-chips">
      <SkeletonBlock v-if="loading && !runs.length" :rows="1" :height="28" />
      <ErrorState v-else-if="error && !runs.length" :error="error" @retry="emit('retry')" />
      <EmptyState
        v-else-if="!runs.length"
        text="暂无运行记录"
        hint="分析任务运行后会在这里按时间倒序出现，可点击切换查看。"
      />
      <button
        v-for="run in runs"
        :key="run.id"
        class="pipe-run-chip"
        :class="{ 'pipe-run-chip--active': run.id === selectedRunId }"
        type="button"
        :title="`${run.kind} · ${run.id}\n开始 ${fmtDateTime(run.started_at)} · 状态 ${runStatusText(run.status)}`"
        @click="emit('select', run.id)"
      >
        <span class="pipe-run-dot" :class="`pipe-run-dot--${statusTone(run.status)}`"></span>
        <span class="pipe-run-kind mono">{{ run.kind }}</span>
        <span class="pipe-run-time mono">{{ fmtTime(run.started_at, true) }}</span>
        <span class="pipe-run-status" :class="`pipe-run-status--${statusTone(run.status)}`">{{ runStatusText(run.status) }}</span>
        <span class="pipe-run-dur mono">{{ fmtDuration(run.duration_ms) }}</span>
        <span v-if="run.degraded" class="pipe-run-flag">降级</span>
      </button>
    </div>
    <footer class="card-foot pipe-run-foot">
      步骤成功率 = 本运行成功步骤 / 全部步骤；数据覆盖取 /api/system/coverage；接口未返回时显示 —，不做估算。
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { CoverageResponse, V2Run, V2RunDetail } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDate, fmtDateTime, fmtInt, fmtPct, fmtTime } from "@/composables/useFormat";
import {
  fmtDuration,
  runStatusText,
  shortId,
  statusTone,
} from "@/utils/pipelineStatus";

const props = defineProps<{
  runs: V2Run[];
  selectedRun: V2Run | null;
  selectedRunId: string | null;
  detail: V2RunDetail | null;
  coverage: CoverageResponse | null;
  coverageError: Error | null;
  loading: boolean;
  error: Error | null;
}>();

const emit = defineEmits<{
  select: [id: string];
  retry: [];
}>();

/** 运行摘要条：任务类型 + 代码版本/方法作为「环境」，缺失一律 —，不做推断。 */
const runEnvText = computed(() => {
  const run = props.selectedRun;
  if (!run) return "—";
  const parts = [run.kind, run.code_version || run.method_id].filter((part): part is string => !!part);
  return parts.length ? parts.join(" · ") : "—";
});

const runEnvTitle = computed(() => {
  const run = props.selectedRun;
  if (!run) return "";
  return [
    `运行 ID：${run.id}`,
    `类型：${run.kind}`,
    `方法：${run.method_id || "—"}`,
    `代码版本：${run.code_version || "—"}`,
    `标的：${run.subject || "—"}`,
  ].join("\n");
});

/** 步骤成功率 = 本运行 ok 步骤 / 全部步骤；未加载到步骤明细时显示 —。 */
const stepSuccessText = computed(() => {
  const steps = props.detail?.steps ?? [];
  if (!steps.length) return "—";
  const ok = steps.filter((step) => step.status === "ok" && !step.error).length;
  return `${ok}/${steps.length}`;
});

const coverageText = computed(() => {
  const coverage = props.coverage;
  if (!coverage) return "—";
  const covered = fmtInt(coverage.series_covered);
  const total = fmtInt(coverage.series_total);
  const pct = typeof coverage.data_quality_pct === "number" ? ` (${fmtPct(coverage.data_quality_pct, 0)})` : "";
  return `${covered}/${total}${pct}`;
});

const coverageTitle = computed(() => {
  const coverage = props.coverage;
  if (!coverage) return props.coverageError ? "覆盖率接口不可用" : "覆盖率数据尚未返回";
  return [
    `来源：${coverage.method || "/api/system/coverage"}`,
    `序列：${coverage.series_covered}/${coverage.series_total}`,
    `任务：${coverage.jobs_ok ?? "—"}/${coverage.jobs_total ?? "—"}`,
    `最近同步：${coverage.last_sync ? fmtDateTime(coverage.last_sync) : "—"}`,
    `数据日：${coverage.as_of ? fmtDate(coverage.as_of) : "—"}`,
  ].join("\n");
});
</script>

<style scoped>
.pipe-run-strip {
  margin-top: 10px;
}
.pipe-run-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1px;
  margin: 0 12px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--border);
  overflow: hidden;
}
.pipe-run-summary--empty {
  display: block;
  padding: 10px 12px;
  border-style: dashed;
  background: transparent;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.5;
}
.pipe-sum-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding: 8px 10px;
  background: var(--panel, var(--bg));
}
.pipe-sum-label {
  font-size: 9px;
  letter-spacing: 0.03em;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-sum-value {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pipe-run-foot {
  color: var(--dim);
  line-height: 1.5;
}
.pipe-run-actions {
  flex-wrap: wrap;
  row-gap: 4px;
}
.pipe-run-current {
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}
.pipe-run-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 5px;
  padding: 8px 12px 10px;
}
.pipe-run-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface-2);
  color: var(--muted);
  font: inherit;
  font-size: 9.5px;
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s, box-shadow 0.12s;
}
.pipe-run-chip:hover {
  border-color: var(--accent-line);
  background: var(--surface-3);
}
.pipe-run-chip--active {
  border-color: var(--accent);
  background: var(--accent-weak);
  box-shadow: 0 0 0 1px var(--accent-line);
}
.pipe-run-dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: var(--dim);
}
.pipe-run-dot--ok { background: var(--ok); }
.pipe-run-dot--warn { background: var(--warn); }
.pipe-run-dot--bad { background: var(--up); }
.pipe-run-dot--live { background: var(--accent); }
.pipe-run-kind {
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-run-time {
  font-size: 9px;
  color: var(--muted);
  white-space: nowrap;
}
.pipe-run-status {
  font-size: 9px;
  white-space: nowrap;
}
.pipe-run-status--ok { color: var(--ok); }
.pipe-run-status--warn { color: var(--warn); }
.pipe-run-status--bad { color: var(--up); }
.pipe-run-status--live { color: var(--accent); }
.pipe-run-status--muted { color: var(--dim); }
.pipe-run-dur {
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-run-flag {
  padding: 0 4px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--warn) 16%, transparent);
  color: var(--warn);
  font-size: 8px;
  line-height: 1.5;
}
@media (max-width: 1240px) {
  .pipe-run-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 900px) {
  .pipe-run-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
