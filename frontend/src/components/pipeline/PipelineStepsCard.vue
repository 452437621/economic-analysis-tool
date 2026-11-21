<template>
  <section class="card pipe-steps-card">
    <header class="card-head">
      <span class="card-title">
        全部步骤链
        <span class="card-sub">
          {{ selectedRun ? `${selectedRun.kind} · ${detail ? detail.steps.length : 0} 步` : "未选择运行" }}
        </span>
      </span>
      <div class="card-actions pipe-steps-actions">
        <span v-if="error && detail" class="badge badge--warn badge--sm">步骤刷新失败</span>
        <button class="btn btn--ghost btn--sm" type="button" :disabled="!selectedRunId || loading" @click="emit('refresh')">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>重新加载
        </button>
      </div>
    </header>
    <div class="card-body pipe-steps-body">
      <SkeletonBlock v-if="loading && !detail" :rows="4" />
      <ErrorState v-else-if="error && !detail" :error="error" @retry="emit('refresh')" />
      <template v-else-if="detail">
        <div v-if="detail.run.degraded_reasons.length" class="pipe-degraded-box">
          <div class="pipe-degraded-title">降级完成 · {{ detail.run.degraded_reasons.length }} 条原因</div>
          <ul class="pipe-degraded-list">
            <li v-for="reason in detail.run.degraded_reasons" :key="reason.code + reason.message">
              <span class="mono pipe-degraded-code">{{ reason.code }}</span>
              <span>{{ reason.message }}</span>
            </li>
          </ul>
        </div>
        <div v-if="detail.run.error" class="pipe-error-box">{{ detail.run.error }}</div>
        <div v-if="!detail.steps.length" class="pipe-empty-line">该运行未记录步骤。</div>
        <ol v-else class="pipe-step-list">
          <li v-for="step in detail.steps" :key="step.id" class="pipe-step-item">
            <span class="pipe-step-seq mono">#{{ step.seq }}</span>
            <div class="pipe-step-main">
              <div class="pipe-step-line">
                <span class="pipe-step-name">{{ step.name }}</span>
                <span class="badge badge--sm">{{ step.kind }}</span>
                <span class="pipe-step-state" :class="stepTone(step)">{{ step.status }}</span>
                <span class="spacer"></span>
                <span class="pipe-step-dur mono">{{ fmtDuration(step.duration_ms) }}</span>
              </div>
              <div v-if="step.inputs" class="pipe-step-io">
                <span class="pipe-step-io-label">inputs</span>
                <pre class="pipe-step-out mono">{{ prettyJson(step.inputs) }}</pre>
              </div>
              <div v-if="step.outputs" class="pipe-step-io">
                <span class="pipe-step-io-label">outputs</span>
                <pre class="pipe-step-out mono">{{ prettyJson(step.outputs) }}</pre>
              </div>
              <div v-if="step.error" class="pipe-step-error">{{ step.error }}</div>
            </div>
          </li>
        </ol>
        <div v-if="detail.derivations.length" class="pipe-run-derivs">
          <span class="pipe-run-derivs-label">本次运行推导</span>
          <button
            v-for="derivation in detail.derivations"
            :key="derivation.id"
            class="chip pipe-deriv-chip"
            type="button"
            :title="derivation.claim"
            @click="emit('open', derivation.id)"
          >
            <span class="mono">{{ derivation.code }}</span>
            <em>{{ derivation.evidence_grade }}</em>
          </button>
        </div>
      </template>
      <EmptyState v-else text="选择上方运行查看步骤" hint="运行序列中的每一步都会记录输入、输出与耗时。" />
    </div>
  </section>
</template>

<script setup lang="ts">
import type { V2Run, V2RunDetail } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDuration, prettyJson, stepTone } from "@/utils/pipelineStatus";

defineProps<{
  selectedRun: V2Run | null;
  selectedRunId: string | null;
  detail: V2RunDetail | null;
  loading: boolean;
  error: Error | null;
}>();

const emit = defineEmits<{
  refresh: [];
  open: [id: string];
}>();
</script>

<style scoped>
.pipe-steps-card {
  margin-top: 12px;
}
.pipe-steps-actions {
  flex-wrap: wrap;
  row-gap: 4px;
}
.pipe-steps-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pipe-degraded-box {
  padding: 7px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 9%, transparent);
}
.pipe-degraded-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--warn);
}
.pipe-degraded-list {
  margin: 4px 0 0;
  padding-left: 14px;
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.55;
}
.pipe-degraded-list li {
  margin-bottom: 2px;
  overflow-wrap: anywhere;
}
.pipe-degraded-code {
  margin-right: 5px;
  color: var(--warn);
  font-size: 9px;
}
.pipe-error-box {
  padding: 7px 10px;
  border: 1px solid color-mix(in srgb, var(--up) 40%, transparent);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--up) 9%, transparent);
  color: var(--up);
  font-size: 10px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.pipe-empty-line {
  font-size: 10px;
  color: var(--dim);
}
.pipe-step-list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 460px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pipe-step-item {
  display: flex;
  gap: 8px;
  padding: 6px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
  min-width: 0;
}
.pipe-step-seq {
  flex: none;
  font-size: 9px;
  color: var(--dim);
  padding-top: 1px;
}
.pipe-step-main {
  flex: 1;
  min-width: 0;
}
.pipe-step-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-wrap: wrap;
}
.pipe-step-name {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
  overflow-wrap: anywhere;
}
.pipe-step-state {
  font-size: 9px;
  font-family: var(--mono);
}
.pipe-step-tone--ok { color: var(--muted); }
.pipe-step-tone--warn { color: var(--warn); }
.pipe-step-tone--bad { color: var(--up); }
.pipe-step-dur {
  margin-left: auto;
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-step-io {
  margin-top: 5px;
}
.pipe-step-io-label {
  display: block;
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 0.4px;
  color: var(--dim);
  text-transform: uppercase;
}
.pipe-step-out {
  margin: 2px 0 0;
  padding: 5px 7px;
  max-height: 120px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
  color: var(--muted);
  font-size: 9px;
  line-height: 1.5;
  white-space: pre;
}
.pipe-step-error {
  margin-top: 4px;
  color: var(--up);
  font-size: 9.5px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.pipe-run-derivs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  padding-top: 7px;
  border-top: 1px dashed var(--border);
}
.pipe-run-derivs-label {
  font-size: 9px;
  color: var(--dim);
}
.pipe-deriv-chip {
  font-size: 9px;
  max-width: 100%;
}
</style>
