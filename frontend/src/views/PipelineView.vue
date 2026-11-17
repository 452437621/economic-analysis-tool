<template>
  <div class="view active pipe-view">
    <div class="page-head pipe-page-head">
      <div class="pipe-page-title">
        <div class="page-eyebrow">研究分析 · 玻璃盒</div>
        <h1 class="page-h1">
          透明管线 · 数据如何生成结论
          <span class="page-sub">从采集到结论的每一步都可追溯：节点状态、输入特征、规则命中、反证与失效条件</span>
        </h1>
      </div>
      <div class="page-actions pipe-page-actions">
        <span class="badge badge--sm">最近运行 {{ lastRun ? fmtDateTime(lastRun.started_at) : "—" }}</span>
        <span class="badge badge--sm" :class="runBadgeClass(lastRun?.status)">{{ runStatusText(lastRun?.status) }}</span>
        <span class="badge badge--sm">耗时 {{ fmtDuration(lastRun?.duration_ms) }}</span>
        <span class="badge badge--sm pipe-updated-badge" :title="`状态接口更新于 ${updatedLabel}`">更新于 {{ updatedLabel }}</span>
        <button class="btn btn--sm" type="button" :disabled="pageLoading" :title="`更新于 ${updatedLabel}`" @click="refreshAll">
          <svg class="ic" :class="{ spin: pageLoading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <div v-if="statusError" class="pipe-status-strip">
      <span class="badge badge--warn badge--sm">状态接口异常</span>
      <span class="pipe-status-strip-text">{{ errorText(statusError) }}</span>
      <button class="link-btn" type="button" @click="refreshStatus">重试</button>
    </div>

    <section class="card pipe-run-strip">
      <header class="card-head">
        <span class="card-title">运行序列</span>
        <span class="card-sub">最近 {{ runs.length }} 次 · 点击切换选中运行</span>
        <div class="card-actions pipe-run-actions">
          <span v-if="runsError && runs.length" class="badge badge--warn badge--sm">运行列表刷新失败</span>
          <span class="pipe-run-current mono" :title="selectedRun?.id ?? ''">
            {{ selectedRun ? `${selectedRun.kind} · ${fmtDateTime(selectedRun.started_at)}` : "未选择运行" }}
          </span>
        </div>
      </header>
      <div class="pipe-run-chips">
        <SkeletonBlock v-if="runsLoading && !runs.length" :rows="1" :height="28" />
        <ErrorState v-else-if="runsError && !runs.length" :error="runsError" @retry="refreshRuns" />
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
          @click="selectRun(run.id)"
        >
          <span class="pipe-run-dot" :class="`pipe-run-dot--${statusTone(run.status)}`"></span>
          <span class="pipe-run-kind mono">{{ run.kind }}</span>
          <span class="pipe-run-time mono">{{ fmtTime(run.started_at, true) }}</span>
          <span class="pipe-run-status" :class="`pipe-run-status--${statusTone(run.status)}`">{{ runStatusText(run.status) }}</span>
          <span class="pipe-run-dur mono">{{ fmtDuration(run.duration_ms) }}</span>
          <span v-if="run.degraded" class="pipe-run-flag">降级</span>
        </button>
      </div>
    </section>

    <div class="kpi-grid pipe-kpi">
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
          <span class="kpi-label">运行</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.runs) : "—" }}</div>
        <div class="kpi-sub">降级 {{ counts ? fmtInt(counts.degraded) : "—" }} · 失败 {{ counts ? fmtInt(counts.failed) : "—" }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-file" /></svg></span>
          <span class="kpi-label">推导</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.derivations) : "—" }}</div>
        <div class="kpi-sub">证据等级 · 置信度 · 失效条件</div>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-db" /></svg></span>
          <span class="kpi-label">观测</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.observations) : "—" }}</div>
        <div class="kpi-sub">原始观测，可回溯 vintage</div>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-cpu" /></svg></span>
          <span class="kpi-label">方法</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.methods) : "—" }}</div>
        <div class="kpi-sub">方法版本登记 · Brier 校准</div>
      </div>
    </div>

    <PipelineDag :nodes="nodes" :selected="selectedNode" @select="onNodeSelect" />

    <NodeDetail
      v-if="selectedNodeData"
      :name="selectedNodeData.name"
      :status="selectedNodeData.status"
      :steps="selectedNodeData.steps"
      :duration-ms="selectedNodeData.durationMs"
      :error-count="selectedNodeData.errorCount"
      :degraded-count="selectedNodeData.degradedCount"
      @close="selectedNode = null"
    />

    <div class="pipe-main-grid">
      <PipelineTrace
        :derivation="selectedDerivation"
        :loading="derivationsLoading"
        :error="derivationsError"
        @open="openDerivation"
        @retry="refreshDerivations"
      />
      <ScenarioSandbox :initial="initialComposites" />
    </div>

    <ModelCard
      :methods="methods"
      :methods-loading="methodsLoading"
      :methods-error="methodsError"
      :calibration="calibration"
      :calibration-loading="calibrationLoading"
      :calibration-error="calibrationError"
      :meta="cycleMeta"
      @retry="refreshModel"
    />

    <section class="card pipe-steps-card">
      <header class="card-head">
        <span class="card-title">
          全部步骤链
          <span class="card-sub">
            {{ selectedRun ? `${selectedRun.kind} · ${detail ? detail.steps.length : 0} 步` : "未选择运行" }}
          </span>
        </span>
        <div class="card-actions pipe-steps-actions">
          <span v-if="detailError && detail" class="badge badge--warn badge--sm">步骤刷新失败</span>
          <button class="btn btn--ghost btn--sm" type="button" :disabled="!selectedRunId || detailLoading" @click="refreshSelected">
            <svg class="ic" :class="{ spin: detailLoading }"><use href="#i-refresh" /></svg>重新加载
          </button>
        </div>
      </header>
      <div class="card-body pipe-steps-body">
        <SkeletonBlock v-if="detailLoading && !detail" :rows="4" />
        <ErrorState v-else-if="detailError && !detail" :error="detailError" @retry="refreshSelected" />
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
              @click="openDerivation(derivation.id)"
            >
              <span class="mono">{{ derivation.code }}</span>
              <em>{{ derivation.evidence_grade }}</em>
            </button>
          </div>
        </template>
        <EmptyState v-else text="选择上方运行查看步骤" hint="运行序列中的每一步都会记录输入、输出与耗时。" />
      </div>
    </section>

    <section class="card pipe-deriv-card">
      <header class="card-head">
        <span class="card-title">
          推导清单
          <span class="card-sub">{{ derivations.length }} 条 · 点击行在溯源树查看</span>
        </span>
        <div class="card-actions pipe-deriv-actions">
          <label class="field pipe-filter-field">
            <svg class="ic"><use href="#i-filter" /></svg>
            <input v-model="codeFilter" class="mono" type="text" placeholder="按 code 过滤，如 cycle.state.world" />
          </label>
          <button class="btn btn--ghost btn--sm" type="button" @click="refreshDerivations">
            <svg class="ic"><use href="#i-refresh" /></svg>刷新
          </button>
        </div>
      </header>
      <div class="card-body pipe-deriv-body">
        <SkeletonBlock v-if="derivationsLoading && !derivations.length" :rows="4" />
        <ErrorState v-else-if="derivationsError && !derivations.length" :error="derivationsError" @retry="refreshDerivations" />
        <EmptyState
          v-else-if="!derivations.length"
          :text="codeFilter ? '没有匹配该 code 的推导' : '暂无推导数据'"
          :hint="codeFilter ? '试试清空过滤条件。' : '运行分析任务后会生成带证据链的推导。'"
        />
        <div v-else class="table-wrap pipe-table-wrap">
          <table class="data-table pipe-deriv-table">
            <thead>
              <tr>
                <th>结论</th>
                <th>code</th>
                <th>证据</th>
                <th class="num">置信度</th>
                <th>措辞</th>
                <th>观测日</th>
                <th class="num">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in derivations"
                :key="item.id"
                class="pipe-deriv-row"
                :class="{ 'pipe-deriv-row--active': item.id === selectedDerivation?.id }"
                @click="selectDerivation(item.id)"
              >
                <td class="pipe-claim-cell">{{ item.claim }}</td>
                <td class="mono pipe-code-cell">{{ item.code }}</td>
                <td><span class="badge badge--sm" :class="gradeClass(item.evidence_grade)">{{ item.evidence_grade }}</span></td>
                <td class="num mono">{{ confidencePct(item.confidence) }}</td>
                <td class="muted">{{ confidenceLabel(item.confidence) }}</td>
                <td class="mono dim">{{ fmtDate(item.asof) }}</td>
                <td class="num pipe-deriv-ops">
                  <button class="link-btn" type="button" @click.stop="selectDerivation(item.id)">溯源</button>
                  <button class="link-btn" type="button" @click.stop="openDerivation(item.id)">为什么 →</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <DerivationDrawer :derivation-id="openId" @close="openId = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getJson } from "@/api/client";
import {
  getCycleState,
  getLedgerCalibration,
  getV2Derivations,
  getV2Methods,
  getV2Run,
  getV2Runs,
  getV2Status,
} from "@/api/endpoints";
import type {
  CycleKey,
  CycleStateResponse,
  LedgerCalibration,
  V2Derivation,
  V2Method,
  V2Run,
  V2RunDetail,
  V2Step,
} from "@/api/types";
import DerivationDrawer from "@/components/domain/DerivationDrawer.vue";
import PipelineDag from "@/components/pipeline/PipelineDag.vue";
import NodeDetail from "@/components/pipeline/NodeDetail.vue";
import PipelineTrace from "@/components/pipeline/PipelineTrace.vue";
import ScenarioSandbox from "@/components/pipeline/ScenarioSandbox.vue";
import ModelCard from "@/components/pipeline/ModelCard.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtInt, fmtTime } from "@/composables/useFormat";

type NodeStatus = "ok" | "degraded" | "failed" | "pending";
type NodeId = "ingest" | "quality" | "feature" | "cycle" | "scenario" | "publish";

interface PipeNode {
  id: NodeId;
  name: string;
  en: string;
  status: NodeStatus;
  steps: V2Step[];
  durationMs: number | null;
  errorCount: number;
  degradedCount: number;
}

const NODE_DEFS: Array<{ id: NodeId; name: string; en: string; match: string[] }> = [
  { id: "ingest", name: "采集", en: "ingest", match: ["load_bars", "load_panel"] },
  { id: "quality", name: "质检", en: "quality", match: ["align_calendar", "quality", "degrade"] },
  { id: "feature", name: "特征", en: "feature", match: ["indicators", "read_indicators"] },
  { id: "cycle", name: "周期引擎", en: "cycle-engine", match: ["composite_scores", "phases", "sustainability", "world_order"] },
  { id: "scenario", name: "情景", en: "scenario", match: ["scenarios"] },
  { id: "publish", name: "输出", en: "publish", match: ["derive", "finish", "publish"] },
];

/** 契约外步骤的兜底归并：先按关键词，再按步骤顺序归到上一个已匹配节点。 */
const NODE_ALIASES: Array<{ id: NodeId; keywords: string[] }> = [
  { id: "ingest", keywords: ["load", "collect", "fetch"] },
  { id: "quality", keywords: ["seed", "clean", "validate"] },
  {
    id: "feature",
    keywords: ["indicator", "regime", "wind", "correlation", "attribution", "leadlag", "events", "study"],
  },
  { id: "cycle", keywords: ["composite", "phase", "sustainability", "world_order", "history", "read_cycle"] },
  { id: "scenario", keywords: ["scenario", "alert"] },
  { id: "publish", keywords: ["derive", "finish", "publish", "score"] },
];

const CYCLE_KEYS: CycleKey[] = ["DMI", "ICI", "ECI", "GROWTH", "INFLATION", "LIQUIDITY"];

const route = useRoute();
const router = useRouter();

const codeFilter = ref(typeof route.query.code === "string" ? route.query.code : "");

const statusPoll = usePolling(getV2Status, { interval: 30000, immediate: true });
const runsPoll = usePolling(() => getV2Runs({ limit: 10 }), { interval: 30000, immediate: true });
const derivationsPoll = usePolling(
  () => getV2Derivations({ code: codeFilter.value || undefined, limit: 50 }),
  { interval: 30000, immediate: true, watchSource: codeFilter },
);
const methodsPoll = usePolling(getV2Methods, { interval: 30000, immediate: true });
const calibrationPoll = usePolling(getLedgerCalibration, { interval: 30000, immediate: true });

const { data: statusData, error: statusError, loading: statusLoading, lastUpdated: statusUpdated, refresh: refreshStatus } = statusPoll;
const { data: runsData, error: runsError, loading: runsLoading, refresh: refreshRuns } = runsPoll;
const {
  data: derivationsData,
  error: derivationsError,
  loading: derivationsLoading,
  refresh: refreshDerivations,
} = derivationsPoll;
const { data: methodsData, error: methodsError, loading: methodsLoading, refresh: refreshMethods } = methodsPoll;
const { data: calibrationData, error: calibrationError, loading: calibrationLoading, refresh: refreshCalibration } =
  calibrationPoll;

const counts = computed(() => statusData.value?.counts ?? null);
const runs = computed<V2Run[]>(() => runsData.value?.items ?? []);
const derivations = computed<V2Derivation[]>(() => derivationsData.value?.items ?? []);
const methods = computed<V2Method[]>(() => methodsData.value?.items ?? []);
const calibration = computed<LedgerCalibration | null>(() => calibrationData.value?.calibration ?? null);

const pageLoading = computed(() => statusLoading.value || runsLoading.value || derivationsLoading.value);
const updatedLabel = computed(() => (statusUpdated.value ? fmtDateTime(statusUpdated.value.toISOString()) : "—"));

const selectedRunId = ref<string | null>(null);
const detail = ref<V2RunDetail | null>(null);
const detailLoading = ref(false);
const detailError = ref<Error | null>(null);
const selectedNode = ref<NodeId | null>(null);
const selectedDerivationId = ref<string | null>(null);
const openId = ref<string | null>(null);

const cycleState = ref<CycleStateResponse | null>(null);

interface CycleMeta {
  rule_version?: string | null;
  next_calibration?: string | null;
  brier?: number | null;
  calibration_n?: number | null;
  coverage?: { series_covered?: number | null; series_total?: number | null } | null;
}

const cycleMeta = ref<CycleMeta | null>(null);

const selectedRun = computed<V2Run | null>(
  () => runs.value.find((run) => run.id === selectedRunId.value) ?? detail.value?.run ?? null,
);

const lastRun = computed<V2Run | null>(() => statusData.value?.last_run ?? runs.value[0] ?? null);

const initialComposites = computed<Record<CycleKey, number | null>>(() => {
  const composites = cycleState.value?.state?.value?.composites;
  const result = {} as Record<CycleKey, number | null>;
  for (const key of CYCLE_KEYS) {
    const value = composites?.[key]?.value;
    result[key] = typeof value === "number" && Number.isFinite(value) ? value : null;
  }
  return result;
});

function stepNode(step: V2Step): NodeId | null {
  const name = (step.name || "").toLowerCase().trim();
  const last = name.split(".").pop() ?? name;
  for (const def of NODE_DEFS) {
    if (def.match.includes(last)) return def.id;
  }
  for (const alias of NODE_ALIASES) {
    if (alias.keywords.some((keyword) => name.includes(keyword))) return alias.id;
  }
  return null;
}

function nodeStatus(nodeSteps: V2Step[], run: V2Run | null, def: { id: NodeId; match: string[] }): NodeStatus {
  if (!nodeSteps.length) return run?.status === "failed" ? "failed" : "pending";
  if (nodeSteps.some((step) => step.status === "failed" || !!step.error)) return "failed";
  const softBad = nodeSteps.some((step) => step.status !== "ok");
  const reasonHit =
    run?.degraded_reasons.some((reason) => {
      const text = `${reason.code} ${reason.message}`.toLowerCase();
      return text.includes(def.id) || def.match.some((name) => text.includes(name));
    }) ?? false;
  return softBad || reasonHit ? "degraded" : "ok";
}

const nodes = computed<PipeNode[]>(() => {
  const run = selectedRun.value;
  const steps = detail.value?.steps ?? [];
  const grouped = new Map<NodeId, V2Step[]>();
  for (const def of NODE_DEFS) grouped.set(def.id, []);
  let cursor: NodeId = "ingest";
  for (const step of steps) {
    const id = stepNode(step);
    if (id) cursor = id;
    grouped.get(cursor)?.push(step);
  }
  return NODE_DEFS.map((def) => {
    const nodeSteps = (grouped.get(def.id) ?? []).slice().sort((a, b) => a.seq - b.seq);
    const durationMs = nodeSteps.reduce<number | null>((total, step) => {
      if (typeof step.duration_ms !== "number" || !Number.isFinite(step.duration_ms)) return total;
      return (total ?? 0) + step.duration_ms;
    }, null);
    return {
      id: def.id,
      name: def.name,
      en: def.en,
      status: nodeStatus(nodeSteps, run, def),
      steps: nodeSteps,
      durationMs,
      errorCount: nodeSteps.filter((step) => step.status === "failed" || !!step.error).length,
      degradedCount: nodeSteps.filter((step) => step.status !== "ok" && step.status !== "failed").length,
    };
  });
});

const selectedNodeData = computed<PipeNode | null>(
  () => nodes.value.find((node) => node.id === selectedNode.value) ?? null,
);

const selectedDerivation = computed<V2Derivation | null>(() => {
  const list = derivations.value;
  if (selectedDerivationId.value) {
    const hit = list.find((item) => item.id === selectedDerivationId.value);
    if (hit) return hit;
  }
  if (codeFilter.value) {
    return list.find((item) => item.code === codeFilter.value || item.id === codeFilter.value) ?? null;
  }
  const runDerivation = detail.value?.derivations[0];
  if (runDerivation) return runDerivation;
  return list[0] ?? null;
});

function runStatusText(status: string | null | undefined): string {
  if (status === "ok") return "成功";
  if (status === "running") return "运行中";
  if (status === "degraded") return "降级完成";
  if (status === "failed") return "失败";
  return status ?? "—";
}

function runBadgeClass(status: string | null | undefined): string {
  if (status === "failed") return "badge--warn";
  if (status === "degraded") return "badge--accent";
  return "badge--live";
}

function statusTone(status: string | null | undefined): string {
  if (status === "failed") return "bad";
  if (status === "degraded") return "warn";
  if (status === "running") return "live";
  if (status === "ok") return "ok";
  return "muted";
}

function stepTone(step: V2Step): string {
  if (step.status === "failed" || step.error) return "pipe-step-tone--bad";
  if (step.status !== "ok") return "pipe-step-tone--warn";
  return "pipe-step-tone--ok";
}

function gradeClass(grade: string): string {
  if (grade === "E4") return "badge--warn";
  if (grade === "E3") return "badge--accent";
  return "badge--live";
}

function confidencePct(confidence: number | null): string {
  if (confidence === null || !Number.isFinite(confidence)) return "—";
  return `${Math.round(confidence * 100)}%`;
}

function confidenceLabel(confidence: number | null): string {
  if (confidence === null || !Number.isFinite(confidence)) return "—";
  if (confidence >= 0.8) return "很可能";
  if (confidence >= 0.65) return "较可能";
  if (confidence >= 0.5) return "可能存在";
  if (confidence >= 0.35) return "证据不足";
  return "无法判断";
}

function fmtDuration(ms: number | null | undefined): string {
  if (typeof ms !== "number" || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)} s`;
}

function errorText(error: Error | null): string {
  return error ? error.message : "";
}

function prettyJson(value: Record<string, unknown> | null): string {
  if (!value) return "未记录";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function onNodeSelect(id: string) {
  selectedNode.value = selectedNode.value === id ? null : (id as NodeId);
}

function selectDerivation(id: string) {
  selectedDerivationId.value = id;
}

function openDerivation(id: string) {
  openId.value = id;
}

async function loadDetail(runId: string) {
  detailLoading.value = true;
  detailError.value = null;
  try {
    const data = await getV2Run(runId);
    if (selectedRunId.value === runId) detail.value = data;
  } catch (error) {
    if (selectedRunId.value === runId) {
      detailError.value = error instanceof Error ? error : new Error(String(error));
    }
  } finally {
    if (selectedRunId.value === runId) detailLoading.value = false;
  }
}

function selectRun(runId: string) {
  if (selectedRunId.value === runId && detail.value) return;
  selectedRunId.value = runId;
  selectedDerivationId.value = null;
  detail.value = null;
  void loadDetail(runId);
}

function refreshSelected() {
  if (selectedRunId.value) void loadDetail(selectedRunId.value);
}

async function loadCycleState() {
  try {
    cycleState.value = await getCycleState();
  } catch {
    cycleState.value = null;
  }
}

async function loadCycleMeta() {
  try {
    cycleMeta.value = await getJson<CycleMeta>("/api/v2/cycle/meta");
  } catch {
    cycleMeta.value = null;
  }
}

async function refreshModel() {
  await Promise.all([refreshMethods(), refreshCalibration(), loadCycleMeta()]);
}

async function refreshAll() {
  await Promise.all([
    refreshStatus(),
    refreshRuns(),
    refreshDerivations(),
    refreshMethods(),
    refreshCalibration(),
    loadCycleState(),
    loadCycleMeta(),
  ]);
  refreshSelected();
}

watch(
  runs,
  (list) => {
    if (!list.length) {
      selectedRunId.value = null;
      detail.value = null;
      return;
    }
    if (!selectedRunId.value || !list.some((run) => run.id === selectedRunId.value)) {
      selectRun(list[0].id);
      return;
    }
    const persisted = list.find((run) => run.id === selectedRunId.value);
    if (
      persisted &&
      !detailLoading.value &&
      (!detail.value ||
        persisted.status === "running" ||
        detail.value.run.status !== persisted.status ||
        detail.value.run.duration_ms !== persisted.duration_ms)
    ) {
      void loadDetail(persisted.id);
    }
  },
  { immediate: true },
);

watch(codeFilter, (value) => {
  selectedDerivationId.value = null;
  const current = typeof route.query.code === "string" ? route.query.code : "";
  if (value === current) return;
  const query = { ...route.query };
  if (value) query.code = value;
  else delete query.code;
  void router.replace({ query });
});

watch(
  () => route.query.code,
  (value) => {
    const next = typeof value === "string" ? value : "";
    if (next !== codeFilter.value) codeFilter.value = next;
  },
);

void loadCycleState();
void loadCycleMeta();
</script>

<style scoped>
.pipe-view {
  min-width: 0;
}
.pipe-page-head {
  flex-wrap: wrap;
  row-gap: 6px;
}
.pipe-page-title {
  min-width: 0;
}
.pipe-page-actions {
  flex-wrap: wrap;
  row-gap: 5px;
}
.pipe-updated-badge {
  color: var(--dim);
  font-weight: 400;
}
.pipe-status-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
  padding: 6px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 32%, var(--border));
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 7%, transparent);
}
.pipe-status-strip-text {
  font-size: 9.5px;
  color: var(--muted);
  overflow-wrap: anywhere;
}

.pipe-run-strip {
  margin-top: 10px;
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

.pipe-kpi {
  margin-top: 10px;
}

.pipe-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.06fr) minmax(0, 0.94fr);
  gap: 10px;
  margin-top: 12px;
  align-items: start;
}

.pipe-steps-card,
.pipe-deriv-card {
  margin-top: 12px;
}
.pipe-steps-actions,
.pipe-deriv-actions {
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

.pipe-filter-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: 240px;
  max-width: 100%;
  height: 26px;
  padding: 0 7px;
}
.pipe-filter-field svg {
  width: 11px;
  height: 11px;
  flex: none;
  color: var(--dim);
}
.pipe-filter-field input {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--text);
  font-size: 9.5px;
  outline: none;
}
.pipe-deriv-body {
  min-width: 0;
}
.pipe-table-wrap {
  max-height: none;
}
.pipe-deriv-table {
  width: 100%;
}
.pipe-deriv-table th,
.pipe-deriv-table td {
  white-space: nowrap;
}
.pipe-claim-cell {
  white-space: normal !important;
  min-width: 220px;
  max-width: 420px;
  padding: 5px 10px !important;
  line-height: 1.45;
}
.pipe-code-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pipe-deriv-row {
  cursor: pointer;
}
.pipe-deriv-row:hover td {
  background: var(--surface-2);
}
.pipe-deriv-row--active td {
  background: var(--accent-weak);
}
.pipe-deriv-ops {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  align-items: center;
}

@media (max-width: 1240px) {
  .pipe-main-grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 0.95fr);
  }
}
@media (max-width: 1024px) {
  .pipe-main-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .pipe-filter-field {
    width: 210px;
  }
}
</style>
