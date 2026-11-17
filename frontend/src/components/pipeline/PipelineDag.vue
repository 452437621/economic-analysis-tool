<template>
  <section class="card pipe-dag">
    <header class="card-head">
      <span class="card-title">
        流水线 DAG
        <span class="pipe-dag-sub">6 节点 · 左 → 右</span>
      </span>
      <div class="card-actions pipe-dag-stats">
        <span class="pipe-dag-stat"><span class="pipe-dot pipe-dot--ok"></span>成功 {{ counts.ok }}</span>
        <span class="pipe-dag-stat"><span class="pipe-dot pipe-dot--degraded"></span>降级 {{ counts.degraded }}</span>
        <span class="pipe-dag-stat"><span class="pipe-dot pipe-dot--failed"></span>失败 {{ counts.failed }}</span>
        <span class="pipe-dag-stat"><span class="pipe-dot pipe-dot--pending"></span>跳过 {{ counts.pending }}</span>
      </div>
    </header>

    <div class="pipe-dag-track">
      <template v-for="(node, index) in nodes" :key="node.id">
        <button
          class="pipe-node"
          :class="[`pipe-node--${node.status}`, { 'pipe-node--active': selected === node.id }]"
          type="button"
          :aria-pressed="selected === node.id"
          @click="emit('select', node.id)"
        >
          <span class="pipe-node-top">
            <span class="pipe-node-idx">{{ index + 1 }}</span>
            <span class="pipe-node-name">{{ node.name }}</span>
            <span class="pipe-node-status" :class="`pipe-node-status--${node.status}`">{{ statusText(node.status) }}</span>
          </span>
          <span class="pipe-node-en mono">{{ node.en }}</span>
          <span class="pipe-node-metrics">
            <span>耗时 <b class="mono">{{ fmtDuration(node.durationMs) }}</b></span>
            <span>步骤 <b class="mono">{{ node.steps.length }}</b></span>
            <span>错误 <b class="mono" :class="{ 'pipe-warn': node.errorCount > 0 }">{{ node.errorCount }}</b></span>
          </span>
          <span class="pipe-node-foot">
            <span class="mono">{{ firstTime(node.steps) }}</span>
            <span>{{ node.steps.length ? `#${node.steps[0].seq}-${node.steps[node.steps.length - 1].seq}` : "未记录" }}</span>
          </span>
        </button>
        <span v-if="index < nodes.length - 1" class="pipe-dag-arrow" aria-hidden="true">
          <i></i>
          <svg class="ic"><use href="#i-chevron-right" /></svg>
        </span>
      </template>
    </div>

    <div class="pipe-dag-hint">
      提示：点击任一节点，右侧抽屉展示该节点的步骤、输入 / 输出 / 参数（JSON 可折叠）、耗时与错误。
      <span v-if="props.unmappedCount" class="pipe-dag-unmapped">
        另有 {{ props.unmappedCount }} 个契约外步骤按步骤类型归并到相邻节点。
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { V2Step } from "@/api/types";
import { fmtTime } from "@/composables/useFormat";

type NodeStatus = "ok" | "degraded" | "failed" | "pending";

interface PipeNode {
  id: string;
  name: string;
  en: string;
  status: NodeStatus;
  steps: V2Step[];
  durationMs: number | null;
  errorCount: number;
  degradedCount: number;
}

const props = defineProps<{
  nodes: PipeNode[];
  selected: string | null;
  unmappedCount?: number;
}>();

const emit = defineEmits<{ select: [id: string] }>();

const counts = computed<Record<NodeStatus, number>>(() => {
  const result: Record<NodeStatus, number> = { ok: 0, degraded: 0, failed: 0, pending: 0 };
  for (const node of props.nodes) result[node.status] += 1;
  return result;
});

const STATUS_TEXT: Record<NodeStatus, string> = {
  ok: "成功",
  degraded: "降级",
  failed: "失败",
  pending: "跳过",
};

function statusText(status: NodeStatus): string {
  return STATUS_TEXT[status];
}

function fmtDuration(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)} s`;
}

function firstTime(steps: V2Step[]): string {
  const first = steps[0];
  return first ? fmtTime(first.started_at) : "—";
}
</script>

<style scoped>
.pipe-dag {
  margin-top: 12px;
}
.pipe-dag-sub {
  margin-left: 5px;
  font-size: 10px;
  font-weight: 400;
  color: var(--dim);
}
.pipe-dag-stats {
  flex-wrap: wrap;
  row-gap: 3px;
}
.pipe-dag-stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
}
.pipe-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex: none;
}
.pipe-dot--ok { background: var(--ok); }
.pipe-dot--degraded { background: var(--warn); }
.pipe-dot--failed { background: var(--up); }
.pipe-dot--pending { background: var(--dim); }

.pipe-dag-track {
  display: flex;
  align-items: stretch;
  padding: 11px 13px 8px;
}
.pipe-node {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 9px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface-2);
  color: var(--muted);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s, box-shadow 0.12s;
}
.pipe-node:hover {
  border-color: var(--accent-line);
  background: var(--surface-3);
}
.pipe-node--active {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-weak);
}
.pipe-node--pending {
  border-style: dashed;
  background: transparent;
}
.pipe-node--degraded {
  border-color: color-mix(in srgb, var(--warn) 32%, var(--border));
}
.pipe-node--failed {
  border-color: color-mix(in srgb, var(--up) 42%, var(--border));
}
.pipe-node-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.pipe-node-idx {
  width: 15px;
  height: 15px;
  flex: none;
  display: grid;
  place-items: center;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--dim);
}
.pipe-node-name {
  font-size: 11.5px;
  font-weight: 650;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pipe-node-status {
  margin-left: auto;
  flex: none;
  padding: 1px 5px;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-size: 8.5px;
  line-height: 1.4;
  white-space: nowrap;
}
.pipe-node-status--ok {
  color: var(--ok);
  border-color: color-mix(in srgb, var(--ok) 36%, transparent);
  background: color-mix(in srgb, var(--ok) 12%, transparent);
}
.pipe-node-status--degraded {
  color: var(--warn);
  border-color: color-mix(in srgb, var(--warn) 40%, transparent);
  background: color-mix(in srgb, var(--warn) 13%, transparent);
}
.pipe-node-status--failed {
  color: var(--up);
  border-color: color-mix(in srgb, var(--up) 40%, transparent);
  background: color-mix(in srgb, var(--up) 12%, transparent);
}
.pipe-node-status--pending {
  color: var(--dim);
}
.pipe-node-en {
  font-size: 8.5px;
  color: var(--dim);
  letter-spacing: 0.3px;
}
.pipe-node-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 7px;
  font-size: 8.5px;
  color: var(--dim);
  line-height: 1.4;
}
.pipe-node-metrics b {
  color: var(--muted);
  font-weight: 500;
}
.pipe-node-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  margin-top: 1px;
  padding-top: 4px;
  border-top: 1px dashed var(--border);
  font-family: var(--mono);
  font-size: 8px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-warn {
  color: var(--warn) !important;
}

.pipe-dag-arrow {
  flex: 0 0 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
}
.pipe-dag-arrow i {
  width: 8px;
  border-top: 1px solid var(--border-strong);
}
.pipe-dag-arrow svg {
  width: 11px;
  height: 11px;
  margin-left: -1px;
}
.pipe-dag-hint {
  padding: 0 13px 10px;
  font-size: 9.5px;
  color: var(--dim);
  line-height: 1.5;
}
.pipe-dag-unmapped {
  color: var(--warn);
}

@media (max-width: 1240px) {
  .pipe-dag-track {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }
  .pipe-dag-arrow {
    display: none;
  }
}
@media (max-width: 1024px) {
  .pipe-dag-track {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
