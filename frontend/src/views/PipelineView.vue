<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 玻璃盒 · 数据生成过程</div>
        <h1 class="page-h1">
          透明管线
          <span class="page-sub">运行 · 步骤 · 推导 · 反证 —— 每个结论都能回答「它从哪来」</span>
        </h1>
      </div>
      <div class="page-actions">
        <span v-if="status?.last_run" class="badge badge--sm" :class="runBadgeClass(status.last_run.status)">
          {{ runStatusText(status.last_run.status) }}
        </span>
        <span class="badge badge--sm"><span class="dot"></span>更新于 {{ updatedLabel }}</span>
        <button class="btn btn--sm" type="button" :disabled="loading" @click="refreshAll">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <div class="kpi-grid">
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
          <span class="kpi-label">最近一次运行</span>
        </div>
        <div class="kpi-value">{{ status?.last_run?.kind ?? "—" }}<small>{{ status?.last_run?.subject ?? "" }}</small></div>
        <div class="kpi-sub">
          {{ runStatusText(status?.last_run?.status) }} · {{ fmtDuration(status?.last_run?.duration_ms) }}
          <template v-if="status?.last_run?.asof"> · 数据日 {{ fmtDate(status.last_run.asof) }}</template>
        </div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-branch" /></svg></span>
          <span class="kpi-label">推导（结论）</span>
        </div>
        <div class="kpi-value">{{ fmtInt(status?.counts.derivations ?? 0) }}<small>条</small></div>
        <div class="kpi-sub">每条带证据等级、置信度与失效条件</div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-db" /></svg></span>
          <span class="kpi-label">运行 / 观测</span>
        </div>
        <div class="kpi-value">{{ fmtInt(status?.counts.runs ?? 0) }}<small>次运行</small></div>
        <div class="kpi-sub">{{ fmtInt(status?.counts.observations ?? 0) }} 条观测 · {{ status?.counts.methods ?? 0 }} 个已登记方法</div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-alert" /></svg></span>
          <span class="kpi-label">降级 / 失败</span>
        </div>
        <div class="kpi-value">{{ fmtInt(status?.counts.degraded ?? 0) }}<small>/ {{ fmtInt(status?.counts.failed ?? 0) }}</small></div>
        <div class="kpi-sub">{{ status?.counts.failed ? "存在失败运行，请查错误" : "无失败运行" }}</div>
      </article>
    </div>

    <div class="pipe-grid">
      <section class="card">
        <div class="card-head">
          <span class="card-title">运行记录</span>
          <span class="card-sub">按时间倒序 · 点击查看步骤</span>
          <div class="card-actions"><span class="card-sub">{{ runs.length }} 条</span></div>
        </div>
        <div class="runs-list">
          <SkeletonBlock v-if="!runs.length && runsLoading" :rows="5" />
          <ErrorState v-else-if="runsError" :error="runsError" @retry="refreshRuns" />
          <button
            v-for="run in runs"
            :key="run.id"
            type="button"
            class="run-row"
            :class="{ 'run-row--active': run.id === selectedRunId }"
            @click="selectRun(run.id)"
          >
            <span class="run-dot" :class="`run-dot--${run.status}`"></span>
            <span class="run-kind">{{ run.kind }}</span>
            <span class="run-meta">
              <b :class="runBadgeText(run.status)">{{ runStatusText(run.status) }}</b>
              <span>{{ fmtDuration(run.duration_ms) }}</span>
              <span>{{ fmtDateTime(run.started_at) }}</span>
            </span>
            <span v-if="run.degraded" class="badge badge--warn badge--sm">降级</span>
          </button>
          <EmptyState v-if="!runs.length && !runsLoading" text="暂无运行记录" hint="等待分析任务第一次执行。" />
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <span class="card-title">步骤链</span>
          <span class="card-sub">{{ detail ? `${detail.steps.length} 个步骤 · ${detail.run.method_id ?? ""}` : "选择左侧运行" }}</span>
          <div class="card-actions">
            <span v-if="detail" class="card-sub">{{ runStatusText(detail.run.status) }}</span>
          </div>
        </div>
        <SkeletonBlock v-if="detailLoading" :rows="6" />
        <ErrorState v-else-if="detailError" :error="detailError" @retry="loadDetail" />
        <div v-else-if="detail" class="steps-wrap">
          <div v-if="detail.run.degraded_reasons.length" class="degraded-box">
            <svg class="ic"><use href="#i-alert" /></svg>
            <div>
              <b>本次运行有 {{ detail.run.degraded_reasons.length }} 项降级</b>
              <div v-for="reason in detail.run.degraded_reasons" :key="reason.code" class="degraded-reason">
                {{ reason.message }}（{{ reason.code }}）
              </div>
            </div>
          </div>
          <div v-if="detail.run.error" class="degraded-box">
            <svg class="ic"><use href="#i-alert" /></svg>
            <div><b>错误</b><div class="degraded-reason">{{ detail.run.error }}</div></div>
          </div>
          <ol class="steps">
            <li v-for="step in detail.steps" :key="step.id" class="step">
              <div class="step-head">
                <span class="step-seq mono">{{ String(step.seq).padStart(2, "0") }}</span>
                <span class="step-name">{{ step.name }}</span>
                <span class="badge badge--sm">{{ step.kind }}</span>
                <span class="spacer"></span>
                <span class="step-time mono">{{ fmtDuration(step.duration_ms) }}</span>
              </div>
              <div v-if="step.outputs" class="step-out mono">{{ JSON.stringify(step.outputs) }}</div>
              <div v-if="step.error" class="step-err">{{ step.error }}</div>
            </li>
            <li v-if="!detail.steps.length" class="step">
              <EmptyState text="该运行未记录步骤" />
            </li>
          </ol>
          <div v-if="detail.derivations.length" class="deriv-box">
            <div class="db-label">本次运行的结论（点击查看「为什么」）</div>
            <button
              v-for="item in detail.derivations"
              :key="item.id"
              type="button"
              class="deriv-chip"
              @click="openDerivation(item.id)"
            >
              <span class="badge badge--sm" :class="gradeClass(item.evidence_grade)">{{ item.evidence_grade }}</span>
              <span class="deriv-claim">{{ item.claim }}</span>
              <span class="mono deriv-code">{{ item.code }}</span>
            </button>
          </div>
        </div>
        <EmptyState v-else text="尚未选择运行" hint="左侧列表点一条运行，查看它的每一步。" />
      </section>
    </div>

    <section class="card deriv-list-card">
      <div class="card-head">
        <span class="card-title">推导清单</span>
        <span class="card-sub">结论 · 证据等级 · 置信度 · 置信措辞</span>
        <div class="card-actions">
          <input v-model="codeFilter" class="input input--sm mono" placeholder="按 code 过滤，如 regime.US" />
          <span class="card-sub">{{ derivations.length }} 条</span>
        </div>
      </div>
      <div class="table-wrap">
        <SkeletonBlock v-if="!derivations.length && derivationsLoading" :rows="6" />
        <ErrorState v-else-if="derivationsError" :error="derivationsError" @retry="refreshDerivations" />
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>结论</th>
              <th>code</th>
              <th>证据</th>
              <th class="num">置信度</th>
              <th>措辞</th>
              <th>观测日</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in derivations" :key="item.id">
              <td>{{ item.claim }}</td>
              <td class="mono">{{ item.code }}</td>
              <td><span class="badge badge--sm" :class="gradeClass(item.evidence_grade)">{{ item.evidence_grade }}</span></td>
              <td class="num mono">{{ item.confidence === null ? "—" : `${Math.round(item.confidence * 100)}%` }}</td>
              <td class="muted">{{ confidenceLabel(item.confidence) }}</td>
              <td class="muted">{{ fmtDate(item.asof) }}</td>
              <td class="num">
                <button class="link-btn" type="button" @click="openDerivation(item.id)">为什么 →</button>
              </td>
            </tr>
            <tr v-if="!derivations.length && !derivationsLoading">
              <td colspan="7"><EmptyState text="暂无推导" hint="分析任务运行后会生成带血缘的结论。" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <DerivationDrawer :derivation-id="openId" @close="openId = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DerivationDrawer from "@/components/domain/DerivationDrawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtInt } from "@/composables/useFormat";
import {
  getV2Derivations,
  getV2Run,
  getV2Runs,
  getV2Status,
} from "@/api/endpoints";
import type { V2RunDetail } from "@/api/types";

const route = useRoute();
const router = useRouter();

const codeFilter = ref(typeof route.query.code === "string" ? route.query.code : "");

const {
  data: statusData,
  loading: statusLoading,
  lastUpdated,
  refresh: refreshStatus,
} = usePolling(getV2Status, { interval: 30000 });

const {
  data: runsData,
  error: runsError,
  loading: runsLoading,
  refresh: refreshRuns,
} = usePolling(() => getV2Runs({ limit: 30 }), { interval: 30000 });

const {
  data: derivationsData,
  error: derivationsError,
  loading: derivationsLoading,
  refresh: refreshDerivations,
} = usePolling(
  () => getV2Derivations({ code: codeFilter.value || undefined, limit: 80 }),
  { interval: 30000, watchSource: codeFilter },
);

const status = computed(() => statusData.value ?? null);
const runs = computed(() => runsData.value?.items ?? []);
const derivations = computed(() => derivationsData.value?.items ?? []);
const loading = computed(() => statusLoading.value || runsLoading.value || derivationsLoading.value);
const updatedLabel = computed(() =>
  lastUpdated.value ? fmtDateTime(lastUpdated.value.toISOString()) : "—",
);

const selectedRunId = ref<string | null>(null);
const detail = ref<V2RunDetail | null>(null);
const detailLoading = ref(false);
const detailError = ref<Error | null>(null);
const openId = ref<string | null>(null);

async function loadDetail(): Promise<void> {
  if (!selectedRunId.value) return;
  detailLoading.value = true;
  detailError.value = null;
  try {
    detail.value = await getV2Run(selectedRunId.value);
  } catch (err) {
    detailError.value = err instanceof Error ? err : new Error(String(err));
  } finally {
    detailLoading.value = false;
  }
}

function selectRun(runId: string): void {
  if (selectedRunId.value === runId) return;
  selectedRunId.value = runId;
  detail.value = null;
  void loadDetail();
}

function openDerivation(derivationId: string): void {
  openId.value = derivationId;
}

function refreshAll(): void {
  void refreshStatus();
  void refreshRuns();
  void refreshDerivations();
  void loadDetail();
}

function runStatusText(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    ok: "成功",
    running: "运行中",
    degraded: "降级完成",
    failed: "失败",
  };
  return value ? labels[value] ?? value : "—";
}

function runBadgeClass(value: string | null | undefined): string {
  if (value === "failed") return "badge--warn";
  if (value === "degraded") return "badge--accent";
  return "badge--live";
}

function runBadgeText(value: string): string {
  return value === "failed" ? "text-warn" : "text-ok";
}

function gradeClass(grade: string): string {
  if (grade === "E4") return "badge--warn";
  if (grade === "E3") return "badge--accent";
  return "";
}

function confidenceLabel(value: number | null): string {
  if (value === null || value === undefined) return "—";
  if (value >= 0.8) return "很可能";
  if (value >= 0.65) return "较可能";
  if (value >= 0.5) return "可能存在";
  if (value >= 0.35) return "证据不足";
  return "无法判断";
}

function fmtDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)} s`;
}

// 首次进入或 runs 更新后自动选中最近一次运行
watch(
  runs,
  (list) => {
    if (selectedRunId.value) return;
    const first = list[0]?.id;
    if (first) {
      selectedRunId.value = first;
      void loadDetail();
    }
  },
  { immediate: true },
);

// 支持 /pipeline?code=regime.US 深链：过滤推导清单
if (codeFilter.value) {
  router.replace({ query: { ...route.query, code: codeFilter.value } });
}
</script>

<style scoped>
.pipe-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.35fr);
  gap: 10px;
  margin-top: 12px;
}
.runs-list {
  max-height: 460px;
  overflow-y: auto;
  padding: 4px 6px 8px;
}
.run-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.run-row:hover {
  background: var(--surface-2);
}
.run-row--active {
  border-color: var(--border-strong);
  background: var(--surface-2);
}
.run-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--dim);
  flex: none;
}
.run-dot--ok {
  background: var(--down);
}
.run-dot--degraded {
  background: var(--warn);
}
.run-dot--failed {
  background: var(--up);
}
.run-kind {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text);
  width: 74px;
  flex: none;
}
.run-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--dim);
  flex: 1;
  min-width: 0;
}
.run-meta span {
  white-space: nowrap;
}
.text-ok {
  color: var(--muted);
}
.text-warn {
  color: var(--warn);
}
.steps-wrap {
  padding: 10px 12px 12px;
  max-height: 520px;
  overflow-y: auto;
}
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
}
.step {
  padding: 8px 0;
  border-bottom: 1px dashed var(--border);
}
.step:last-child {
  border-bottom: 0;
}
.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.step-seq {
  color: var(--dim);
  font-size: 10px;
}
.step-name {
  color: var(--text);
  font-weight: 600;
}
.step-time {
  color: var(--dim);
  font-size: 10px;
}
.step-out {
  margin-top: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10px;
  line-height: 1.5;
  word-break: break-all;
}
.step-err {
  margin-top: 4px;
  font-size: 11px;
  color: var(--warn);
}
.degraded-box {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  margin-bottom: 8px;
  border: 1px solid rgba(245, 165, 36, 0.35);
  border-radius: 8px;
  background: rgba(245, 165, 36, 0.08);
  font-size: 11px;
  color: var(--muted);
}
.degraded-box b {
  color: var(--warn);
}
.degraded-reason {
  margin-top: 2px;
  line-height: 1.5;
}
.deriv-box {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.db-label {
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dim);
  margin-bottom: 6px;
}
.deriv-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  margin-bottom: 4px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
.deriv-chip:hover {
  border-color: var(--border-strong);
}
.deriv-claim {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.deriv-code {
  font-size: 10px;
  color: var(--dim);
}
.deriv-list-card {
  margin-top: 12px;
}
.table-wrap {
  overflow-x: auto;
}
.input--sm {
  height: 26px;
  padding: 0 8px;
  font-size: 11px;
  width: 200px;
}
@media (max-width: 1240px) {
  .pipe-grid {
    grid-template-columns: 1fr;
  }
}
</style>
