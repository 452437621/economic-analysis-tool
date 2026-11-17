<template>
  <section class="card pipe-trace">
    <header class="card-head">
      <span class="card-title">
        本次研判溯源
        <span class="badge badge--accent badge--sm">静态展开</span>
      </span>
      <div class="card-actions pipe-trace-actions">
        <span v-if="derivation" class="pipe-trace-id mono" :title="derivation.id">#{{ shortId(derivation.id) }}</span>
        <button class="btn btn--ghost btn--sm" type="button" :disabled="!derivation" @click="derivation && emit('open', derivation.id)">
          为什么
        </button>
        <button class="btn btn--primary btn--sm" type="button" :disabled="!derivation" @click="derivation && emit('open', derivation.id)">
          <svg class="ic"><use href="#i-eye" /></svg>打开完整推导
        </button>
      </div>
    </header>

    <div class="card-body pipe-trace-body">
      <SkeletonBlock v-if="loading && !derivation" :rows="4" />
      <ErrorState v-else-if="error && !derivation" :error="error" @retry="emit('retry')" />
      <EmptyState
        v-else-if="!derivation"
        text="暂无可追溯的推导"
        hint="运行完成后会生成推导；可用下方推导清单或 URL ?code= 选择一条。"
      />
      <template v-else>
        <div class="pipe-conclusion">
          <div class="pipe-tc-label">L1 · 结论</div>
          <div class="pipe-tc-text">{{ derivation.claim }}</div>
          <div class="pipe-tc-meta">
            <span class="badge badge--sm" :class="gradeClass(derivation.evidence_grade)">{{ derivation.evidence_grade }}</span>
            <span class="pipe-tc-conf">
              置信度
              <b class="mono">{{ confidenceLabel(derivation.confidence) }}</b>
              <span class="pipe-tc-bar"><i :style="{ width: confidencePct(derivation.confidence) }"></i></span>
            </span>
            <span class="pipe-tc-code mono">{{ derivation.code }}</span>
            <span class="spacer"></span>
            <span class="pipe-tc-asof mono">{{ fmtDate(derivation.asof) }}</span>
          </div>
        </div>

        <div class="pipe-tree">
          <details class="pipe-layer" open>
            <summary class="pipe-layer-sum">
              <span class="pipe-tl-tag">L2</span>
              <span class="pipe-tl-title">输入</span>
              <span class="pipe-tl-note">{{ derivation.inputs.length }} 项原始输入</span>
            </summary>
            <div class="pipe-layer-body">
              <div v-if="derivation.inputs.length" class="pipe-chips">
                <span v-for="input in derivation.inputs" :key="input" class="chip mono pipe-chip" :title="input">{{ input }}</span>
              </div>
              <div v-else class="pipe-empty-line">本次推导未记录输入清单。</div>
            </div>
          </details>

          <details class="pipe-layer" open>
            <summary class="pipe-layer-sum">
              <span class="pipe-tl-tag">L3</span>
              <span class="pipe-tl-title">规则命中</span>
              <span class="pipe-tl-note">{{ derivation.rules_hit.length }} 条规则</span>
            </summary>
            <div class="pipe-layer-body">
              <div v-if="derivation.rules_hit.length" class="pipe-rules">
                <div v-for="(rule, index) in derivation.rules_hit" :key="index" class="pipe-rule">
                  <div class="pipe-rule-top">
                    <span class="pipe-rule-id mono">{{ ruleTitle(rule) }}</span>
                    <span class="badge badge--sm" :class="ruleBadge(rule)">{{ ruleFired(rule) ? "命中" : "未命中" }}</span>
                    <span v-if="ruleSeverity(rule)" class="pipe-rule-sev mono">{{ ruleSeverity(rule) }}</span>
                    <span class="spacer"></span>
                  </div>
                  <div v-if="ruleMessage(rule)" class="pipe-rule-msg">{{ ruleMessage(rule) }}</div>
                </div>
              </div>
              <div v-else class="pipe-empty-line">本次量化推导未命中阈值规则</div>
            </div>
          </details>

          <details class="pipe-layer" open>
            <summary class="pipe-layer-sum">
              <span class="pipe-tl-tag">L4</span>
              <span class="pipe-tl-title">特征 / 步骤</span>
              <span class="pipe-tl-note">{{ derivation.steps.length }} 个中间步骤</span>
            </summary>
            <div class="pipe-layer-body">
              <div v-if="derivation.steps.length" class="pipe-steps">
                <div v-for="(step, index) in derivation.steps" :key="index" class="pipe-step">
                  <div class="pipe-step-top">
                    <span class="pipe-step-idx mono">{{ index + 1 }}</span>
                    <span class="pipe-step-title">{{ stepTitle(step) }}</span>
                  </div>
                  <div v-if="stepEntries(step).length" class="pipe-step-entries">
                    <span v-for="entry in stepEntries(step)" :key="entry.key" class="pipe-entry mono">
                      <em>{{ entry.key }}</em> {{ entry.value }}
                    </span>
                  </div>
                </div>
              </div>
              <div v-else class="pipe-empty-line">本次推导未记录中间步骤。</div>
            </div>
          </details>

          <details class="pipe-layer" open>
            <summary class="pipe-layer-sum">
              <span class="pipe-tl-tag">L5</span>
              <span class="pipe-tl-title">原始观测</span>
              <span class="pipe-tl-note">输入 id · 点击按 code 回到管线</span>
            </summary>
            <div class="pipe-layer-body">
              <div v-if="derivation.inputs.length" class="pipe-src-list">
                <div v-for="input in derivation.inputs" :key="input" class="pipe-src">
                  <svg class="ic"><use href="#i-db" /></svg>
                  <span class="mono pipe-src-id" :title="input">{{ input }}</span>
                  <RouterLink class="pipe-src-link" :to="inputLink(input)">按 code 过滤</RouterLink>
                </div>
              </div>
              <div v-else class="pipe-empty-line">未记录可回溯的原始观测。</div>
            </div>
          </details>
        </div>

        <div v-if="derivation.caveats.length || derivation.falsifiers.length || derivation.opposing.length" class="pipe-trace-notes">
          <div v-if="derivation.falsifiers.length" class="pipe-note-block">
            <div class="pipe-note-title">失效条件</div>
            <ul class="pipe-note-list"><li v-for="(item, i) in derivation.falsifiers" :key="i">{{ item }}</li></ul>
          </div>
          <div v-if="derivation.opposing.length" class="pipe-note-block">
            <div class="pipe-note-title">反证</div>
            <ul class="pipe-note-list"><li v-for="(item, i) in derivation.opposing" :key="i">{{ item }}</li></ul>
          </div>
          <div v-if="derivation.caveats.length" class="pipe-note-block">
            <div class="pipe-note-title">注意事项</div>
            <ul class="pipe-note-list"><li v-for="(item, i) in derivation.caveats" :key="i">{{ item }}</li></ul>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";
import type { V2Derivation } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDate } from "@/composables/useFormat";

defineProps<{
  derivation: V2Derivation | null;
  loading: boolean;
  error: Error | null;
}>();

const emit = defineEmits<{ open: [id: string]; retry: [] }>();

const route = useRoute();

function inputLink(input: string) {
  return { path: "/pipeline", query: { ...route.query, code: input } };
}

function shortId(id: string): string {
  return id.length > 12 ? id.slice(0, 12) : id;
}

function gradeClass(grade: string): string {
  if (grade === "E4") return "badge--warn";
  if (grade === "E3") return "badge--accent";
  return "badge--live";
}

function confidencePct(confidence: number | null): string {
  if (confidence === null || !Number.isFinite(confidence)) return "0%";
  const pct = Math.max(0, Math.min(100, Math.round(confidence * 100)));
  return `${pct}%`;
}

function confidenceLabel(confidence: number | null): string {
  if (confidence === null || !Number.isFinite(confidence)) return "—";
  return confidencePct(confidence);
}

function ruleTitle(rule: Record<string, unknown>): string {
  const value = rule.rule_id ?? rule.id ?? rule.code ?? rule.name;
  return typeof value === "string" ? value : "rule";
}

function ruleFired(rule: Record<string, unknown>): boolean {
  return rule.fired !== false;
}

function ruleBadge(rule: Record<string, unknown>): string {
  return ruleFired(rule) ? "badge--warn" : "badge--sm";
}

function ruleSeverity(rule: Record<string, unknown>): string {
  const value = rule.severity;
  return typeof value === "string" ? value : "";
}

function ruleMessage(rule: Record<string, unknown>): string {
  const value = rule.message ?? rule.desc ?? rule.description;
  return typeof value === "string" ? value : "";
}

function stepTitle(step: Record<string, unknown>): string {
  for (const key of ["name", "label", "step", "step_id", "feature", "title", "metric"]) {
    const value = step[key];
    if (typeof value === "string" && value) return value;
  }
  return "步骤";
}

function stepEntries(step: Record<string, unknown>): Array<{ key: string; value: string }> {
  const skip = new Set(["name", "label", "step", "step_id", "feature", "title", "metric"]);
  return Object.entries(step)
    .filter(([key, value]) => !skip.has(key) && value !== null && value !== undefined)
    .slice(0, 5)
    .map(([key, value]) => ({ key, value: formatValue(value) }));
}

function formatValue(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (typeof value === "string") return value.length > 60 ? `${value.slice(0, 60)}…` : value;
  if (typeof value === "boolean") return value ? "true" : "false";
  try {
    const text = JSON.stringify(value);
    return text && text.length > 60 ? `${text.slice(0, 60)}…` : (text ?? "—");
  } catch {
    return String(value);
  }
}
</script>

<style scoped>
.pipe-trace {
  min-width: 0;
}
.pipe-trace-actions {
  flex-wrap: wrap;
  row-gap: 4px;
}
.pipe-trace-id {
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-trace-body {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.pipe-conclusion {
  padding: 9px 11px;
  border: 1px solid color-mix(in srgb, var(--accent) 26%, var(--border));
  border-radius: var(--radius-control);
  background: linear-gradient(180deg, var(--accent-weak), transparent);
}
.pipe-tc-label {
  margin-bottom: 4px;
  font-size: 9px;
  letter-spacing: 0.4px;
  color: var(--accent);
  text-transform: uppercase;
}
.pipe-tc-text {
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text);
  font-weight: 550;
}
.pipe-tc-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 9px;
  margin-top: 7px;
  font-size: 9.5px;
  color: var(--muted);
}
.pipe-tc-conf {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.pipe-tc-conf b {
  color: var(--text);
  font-weight: 600;
}
.pipe-tc-bar {
  width: 48px;
  height: 4px;
  border-radius: 2px;
  background: var(--surface-3);
  overflow: hidden;
}
.pipe-tc-bar i {
  display: block;
  height: 100%;
  background: var(--accent);
}
.pipe-tc-code {
  color: var(--muted);
  font-size: 9.5px;
  overflow-wrap: anywhere;
}
.pipe-tc-asof {
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}

.pipe-tree {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pipe-layer {
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
  overflow: hidden;
}
.pipe-layer[open] {
  border-color: var(--border-strong);
}
.pipe-layer-sum {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 9px;
  font-size: 10.5px;
  color: var(--muted);
  cursor: pointer;
  list-style: none;
  user-select: none;
}
.pipe-layer-sum::-webkit-details-marker {
  display: none;
}
.pipe-layer-sum:hover {
  background: var(--surface-3);
}
.pipe-tl-tag {
  min-width: 22px;
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--accent);
}
.pipe-tl-title {
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
}
.pipe-tl-note {
  margin-left: auto;
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-layer-body {
  padding: 2px 9px 9px;
  border-top: 1px dashed var(--border);
}
.pipe-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-top: 7px;
}
.pipe-chip {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 9px;
}
.pipe-empty-line {
  padding-top: 7px;
  font-size: 10px;
  color: var(--dim);
  line-height: 1.5;
}
.pipe-rules {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-top: 7px;
}
.pipe-rule {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
}
.pipe-rule-top {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.pipe-rule-id {
  font-size: 9.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipe-rule-sev {
  font-size: 8.5px;
  color: var(--dim);
}
.pipe-rule-msg {
  margin-top: 3px;
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.5;
}
.pipe-steps {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 7px;
}
.pipe-step {
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
}
.pipe-step-top {
  display: flex;
  align-items: center;
  gap: 6px;
}
.pipe-step-idx {
  font-size: 8.5px;
  color: var(--accent);
}
.pipe-step-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
}
.pipe-step-entries {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 9px;
  margin-top: 2px;
}
.pipe-entry {
  font-size: 9px;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.pipe-entry em {
  font-style: normal;
  color: var(--dim);
}
.pipe-src-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-top: 7px;
}
.pipe-src {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 9.5px;
  color: var(--muted);
  min-width: 0;
}
.pipe-src svg {
  width: 11px;
  height: 11px;
  flex: none;
}
.pipe-src-id {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipe-src-link {
  flex: none;
  font-size: 9px;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
}
.pipe-src-link:hover {
  text-decoration: underline;
}
.pipe-trace-notes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 7px;
  padding-top: 7px;
  border-top: 1px dashed var(--border);
}
.pipe-note-title {
  margin-bottom: 3px;
  font-size: 9px;
  letter-spacing: 0.3px;
  color: var(--warn);
  text-transform: uppercase;
}
.pipe-note-list {
  margin: 0;
  padding-left: 13px;
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.55;
}
.pipe-note-list li {
  margin-bottom: 2px;
  overflow-wrap: anywhere;
}
</style>
