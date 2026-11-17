<template>
  <section class="card pipe-node-detail">
    <header class="card-head">
      <span class="card-title">
        节点详情 · {{ name }}
        <span class="badge badge--sm" :class="statusBadge">{{ statusText }}</span>
      </span>
      <div class="card-actions pipe-node-actions">
        <span class="pipe-node-meta mono">{{ steps.length }} 步 · {{ fmtDuration(durationMs) }}</span>
        <button class="btn btn--ghost btn--sm btn--icon" type="button" title="关闭" @click="emit('close')">
          <svg class="ic"><use href="#i-close" /></svg>
        </button>
      </div>
    </header>
    <div class="card-body pipe-node-body">
      <div class="pipe-node-facts">
        <div class="pipe-fact"><span>步骤数</span><b class="mono num">{{ steps.length }}</b></div>
        <div class="pipe-fact"><span>总耗时</span><b class="mono num">{{ fmtDuration(durationMs) }}</b></div>
        <div class="pipe-fact"><span>错误</span><b class="mono num" :class="{ 'pipe-bad': errorCount > 0 }">{{ errorCount }}</b></div>
        <div class="pipe-fact"><span>降级</span><b class="mono num" :class="{ 'pipe-warn': degradedCount > 0 }">{{ degradedCount }}</b></div>
      </div>

      <EmptyState
        v-if="!steps.length"
        text="该节点在本次运行中未记录步骤"
        hint="不同分析任务使用的步骤不同；切换上方运行可查看其他任务。"
      />

      <div v-else class="pipe-node-steps">
        <details v-for="step in steps" :key="step.id" class="pipe-step">
          <summary class="pipe-step-sum">
            <span class="pipe-step-seq mono">#{{ step.seq }}</span>
            <span class="pipe-step-name">{{ step.name }}</span>
            <span class="badge badge--sm">{{ step.kind }}</span>
            <span class="pipe-step-status" :class="stepStatusClass(step)">{{ step.status }}</span>
            <span class="spacer"></span>
            <span class="pipe-step-dur mono">{{ fmtDuration(step.duration_ms) }}</span>
          </summary>
          <div class="pipe-step-body">
            <div v-if="step.error" class="pipe-step-error">{{ step.error }}</div>
            <div class="pipe-step-io">
              <div class="pipe-io-block">
                <div class="pipe-io-label">输入 inputs</div>
                <pre class="pipe-json mono">{{ pretty(step.inputs) }}</pre>
              </div>
              <div class="pipe-io-block">
                <div class="pipe-io-label">输出 outputs</div>
                <pre class="pipe-json mono">{{ pretty(step.outputs) }}</pre>
              </div>
              <div class="pipe-io-block">
                <div class="pipe-io-label">参数 params</div>
                <pre class="pipe-json mono">{{ pretty(step.params) }}</pre>
              </div>
            </div>
          </div>
        </details>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { V2Step } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";

type NodeStatus = "ok" | "degraded" | "failed" | "pending";

const props = defineProps<{
  name: string;
  status: NodeStatus;
  steps: V2Step[];
  durationMs: number | null;
  errorCount: number;
  degradedCount: number;
}>();

const emit = defineEmits<{ close: [] }>();

const STATUS_TEXT: Record<NodeStatus, string> = {
  ok: "成功",
  degraded: "降级",
  failed: "失败",
  pending: "待运行",
};

const statusText = computed(() => STATUS_TEXT[props.status]);
const statusBadge = computed(() => {
  if (props.status === "failed") return "badge--warn";
  if (props.status === "degraded") return "badge--accent";
  if (props.status === "pending") return "";
  return "badge--live";
});

function fmtDuration(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)} s`;
}

function stepStatusClass(step: V2Step): string {
  if (step.status === "failed" || step.error) return "pipe-step-status--bad";
  if (step.status && step.status !== "ok") return "pipe-step-status--warn";
  return "pipe-step-status--ok";
}

function pretty(value: Record<string, unknown> | null): string {
  if (value === null || value === undefined) return "未记录";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
</script>

<style scoped>
.pipe-node-detail {
  margin-top: 12px;
}
.pipe-node-actions {
  align-items: center;
}
.pipe-node-meta {
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-node-body {
  display: flex;
  flex-direction: column;
  gap: 9px;
  max-height: 460px;
  overflow: auto;
}
.pipe-node-facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 7px;
}
.pipe-fact {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-fact b {
  font-size: 11px;
  color: var(--text);
  font-weight: 600;
}
.pipe-warn { color: var(--warn) !important; }
.pipe-bad { color: var(--up) !important; }

.pipe-node-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pipe-step {
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
  overflow: hidden;
}
.pipe-step[open] {
  border-color: var(--border-strong);
}
.pipe-step-sum {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 9px;
  font-size: 10.5px;
  color: var(--muted);
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.pipe-step-sum::-webkit-details-marker {
  display: none;
}
.pipe-step-sum:hover {
  background: var(--surface-3);
}
.pipe-step-seq {
  font-size: 9px;
  color: var(--dim);
}
.pipe-step-name {
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pipe-step-status {
  font-size: 9.5px;
  font-family: var(--mono);
  white-space: nowrap;
}
.pipe-step-status--ok { color: var(--muted); }
.pipe-step-status--warn { color: var(--warn); }
.pipe-step-status--bad { color: var(--up); }
.pipe-step-dur {
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-step-body {
  padding: 2px 9px 9px;
  border-top: 1px dashed var(--border);
}
.pipe-step-error {
  margin: 7px 0;
  padding: 6px 8px;
  border: 1px solid color-mix(in srgb, var(--up) 40%, transparent);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--up) 10%, transparent);
  color: var(--up);
  font-size: 10px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.pipe-step-io {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 7px;
}
.pipe-io-label {
  margin-bottom: 3px;
  font-size: 9px;
  letter-spacing: 0.3px;
  color: var(--dim);
  text-transform: uppercase;
}
.pipe-json {
  margin: 0;
  max-height: 168px;
  overflow: auto;
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
  color: var(--muted);
  font-size: 9.5px;
  line-height: 1.55;
  white-space: pre;
}
@media (max-width: 1024px) {
  .pipe-node-facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
