<template>
  <section class="card pipe-sandbox">
    <header class="card-head">
      <span class="card-title">反事实沙盘</span>
      <div class="card-actions pipe-sandbox-actions">
        <span v-if="loading" class="badge badge--accent badge--sm">计算中</span>
        <span v-else-if="errorMessage" class="badge badge--warn badge--sm">{{ errorBadge }}</span>
        <span v-else-if="response" class="badge badge--live badge--sm">已计算</span>
        <button class="btn btn--ghost btn--sm" type="button" @click="reset">重置</button>
      </div>
    </header>
    <div class="card-body pipe-sandbox-body">
      <div class="pipe-sandbox-sub">
        {{ hasInitial ? "初值取自当前周期状态分量" : "分量未就绪：滑杆以 50 起始" }}
        · 拖动滑块 400ms 后重算假设情景
      </div>

      <div class="pipe-sliders">
        <div v-for="item in SLIDERS" :key="item.key" class="pipe-slider-row">
          <div class="pipe-slider-head">
            <span class="pipe-slider-label">{{ item.label }}</span>
            <span class="pipe-slider-key mono">{{ item.key }}</span>
            <b class="pipe-slider-value mono">{{ values[item.key] }}</b>
          </div>
          <input
            class="pipe-range"
            type="range"
            min="0"
            max="100"
            step="1"
            :aria-label="item.label"
            :value="values[item.key]"
            @input="onInput(item.key, $event)"
          />
          <div class="pipe-slider-scale mono"><span>0</span><span>50</span><span>100</span></div>
        </div>
      </div>

      <div v-if="errorMessage" class="pipe-sandbox-error">
        <template v-if="errorStatus === 503">
          <div class="pipe-sandbox-error-title">周期引擎尚未运行</div>
          <div class="pipe-sandbox-error-text">
            先运行一次周期引擎（周期罗盘页点「立即重算」），再回到沙盘拖动滑杆。
          </div>
          <div class="pipe-sandbox-error-actions">
            <RouterLink class="btn btn--primary btn--sm" to="/cycle">去周期罗盘</RouterLink>
            <button class="btn btn--ghost btn--sm" type="button" @click="runScenario">重试</button>
          </div>
        </template>
        <template v-else>
          <div class="pipe-sandbox-error-title">接口未就绪</div>
          <div class="pipe-sandbox-error-text">
            反事实接口暂不可用，滑杆改动已保留。{{ errorMessage }}
          </div>
          <button class="btn btn--ghost btn--sm" type="button" @click="runScenario">重试</button>
        </template>
      </div>

      <div v-else-if="loading && !response" class="pipe-sandbox-loading">
        <SkeletonBlock :rows="2" :height="12" />
      </div>

      <template v-if="response">
        <div class="pipe-compare">
          <div class="pipe-compare-title">
            基线 vs 情景 · 分量对比
            <span class="pipe-compare-note mono">{{ baselineLabel }}</span>
          </div>
          <div v-for="row in compareRows" :key="row.id" class="pipe-compare-row">
            <span class="pipe-compare-label">{{ row.label }}</span>
            <div class="pipe-bars">
              <div class="pipe-bar-line">
                <span class="pipe-bar-tag">基线</span>
                <div class="pipe-bar"><i :style="{ width: barWidth(row.before) }"></i></div>
                <b class="mono">{{ fmtNumber(row.before, 1) }}</b>
              </div>
              <div class="pipe-bar-line">
                <span class="pipe-bar-tag pipe-bar-tag--after">情景</span>
                <div class="pipe-bar"><i class="pipe-bar-fill--after" :style="{ width: barWidth(row.after) }"></i></div>
                <b class="mono">{{ fmtNumber(row.after, 1) }}</b>
              </div>
            </div>
            <span class="pipe-compare-delta mono" :class="deltaClass(row.delta)">{{ signed(row.delta) }}</span>
          </div>
          <div v-if="!compareRows.length" class="pipe-empty-line">接口未返回分量对比。</div>
        </div>

        <div class="pipe-change-grid">
          <div class="pipe-change">
            <span class="pipe-change-label">阶段是否改变</span>
            <div class="pipe-change-value">
              <b>{{ beforePhase }}</b>
              <svg class="ic"><use href="#i-arrow-right" /></svg>
              <b class="pipe-change-after">{{ afterPhase }}</b>
              <span
                class="pipe-change-tag"
                :class="phaseChanged ? 'pipe-change-tag--changed' : 'pipe-change-tag--same'"
              >{{ phaseChanged ? "改变" : "未改变" }}</span>
            </div>
          </div>
          <div class="pipe-change">
            <span class="pipe-change-label">短周期状态是否改变</span>
            <div class="pipe-change-value">
              <b>{{ beforeShort }}</b>
              <svg class="ic"><use href="#i-arrow-right" /></svg>
              <b class="pipe-change-after">{{ afterShort }}</b>
              <span
                class="pipe-change-tag"
                :class="stateChanged ? 'pipe-change-tag--changed' : 'pipe-change-tag--same'"
              >{{ stateChanged ? "改变" : "未改变" }}</span>
            </div>
          </div>
          <div class="pipe-change pipe-change--wide">
            <span class="pipe-change-label">四情景概率变化</span>
            <div v-if="probDeltas.length" class="pipe-prob-deltas">
              <span v-for="row in probDeltas" :key="row.id" class="pipe-prob-delta">
                <span class="pipe-prob-delta-name">{{ row.name }}</span>
                <b class="mono" :class="row.tone">{{ row.display }}</b>
              </span>
            </div>
            <div v-else class="pipe-empty-line">接口未返回情景概率变化。</div>
          </div>
        </div>

      </template>

      <div class="pipe-sandbox-foot">
        假设性推演，仅用于观察结论对输入的敏感度，不构成预测或投资建议。
      </div>
      <div v-if="response?.note" class="pipe-sandbox-note">{{ response.note }}</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { ApiError, postJson } from "@/api/client";
import type { CycleKey } from "@/api/types";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtNumber } from "@/composables/useFormat";

interface ScenarioCompositeValue {
  value?: number | null;
  name?: string | null;
}

interface ScenarioPhase {
  phase?: string | null;
  phase_id?: string | null;
}

interface ScenarioShort {
  state?: string | null;
}

interface ScenarioProbItem {
  id?: string;
  name?: string;
  probability?: number | null;
}

interface ScenarioBranch {
  composites?: Record<string, number | ScenarioCompositeValue> | null;
  long_cycle?: ScenarioPhase | null;
  short_cycle?: ScenarioShort | null;
  scenarios?: ScenarioProbItem[] | { scenarios?: ScenarioProbItem[] } | null;
}

interface ScenarioDeltas {
  phase_changed?: boolean;
  state_changed?: boolean;
  scenario_probability_delta?: Record<string, number> | null;
}

interface ScenarioResponse {
  baseline?: ScenarioBranch | null;
  scenario?: ScenarioBranch | null;
  deltas?: ScenarioDeltas | null;
  applied?: Record<string, number> | null;
  note?: string | null;
}

type InitialComposites = Record<CycleKey, number | null>;

const props = defineProps<{ initial: InitialComposites }>();

const SLIDERS: Array<{ key: CycleKey; label: string }> = [
  { key: "DMI", label: "债务货币" },
  { key: "ICI", label: "内部秩序" },
  { key: "ECI", label: "外部秩序" },
  { key: "GROWTH", label: "增长" },
  { key: "INFLATION", label: "通胀" },
  { key: "LIQUIDITY", label: "流动性" },
];

function initialValue(key: CycleKey): number {
  const value = props.initial[key];
  if (value === null || !Number.isFinite(value)) return 50;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function snapshot(): Record<CycleKey, number> {
  const next = {} as Record<CycleKey, number>;
  for (const slider of SLIDERS) next[slider.key] = initialValue(slider.key);
  return next;
}

const values = ref<Record<CycleKey, number>>(snapshot());
const baseline = ref<Record<CycleKey, number>>(snapshot());
const dirty = ref(false);
const response = ref<ScenarioResponse | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const errorStatus = ref<number | null>(null);
const errorBadge = computed(() => (errorStatus.value === 503 ? "需先运行周期" : "接口未就绪"));
let timer: ReturnType<typeof setTimeout> | null = null;
let requestToken = 0;

const hasInitial = computed(() => SLIDERS.some((slider) => {
  const value = props.initial[slider.key];
  return value !== null && Number.isFinite(value);
}));

const baselineLabel = computed(() => {
  const label = SLIDERS.map((slider) => `${slider.key} ${baseline.value[slider.key]}`).join(" · ");
  return label;
});

function compositeOf(branch: ScenarioBranch | null | undefined, key: string): number | null {
  const composites = branch?.composites;
  if (!composites) return null;
  const raw = composites[key];
  if (typeof raw === "number") return raw;
  if (raw && typeof raw === "object" && typeof raw.value === "number") return raw.value;
  return null;
}

function readProbItems(branch: ScenarioBranch | null | undefined): ScenarioProbItem[] {
  const scenarios = branch?.scenarios;
  if (!scenarios) return [];
  if (Array.isArray(scenarios)) return scenarios;
  return Array.isArray(scenarios.scenarios) ? scenarios.scenarios : [];
}

const scenarioNames = computed(() => {
  const names = new Map<string, string>();
  for (const item of readProbItems(response.value?.scenario)) {
    if (item.id) names.set(item.id, item.name ?? item.id);
  }
  if (!names.size) {
    for (const item of readProbItems(response.value?.baseline)) {
      if (item.id) names.set(item.id, item.name ?? item.id);
    }
  }
  return names;
});

/** 响应契约（后端 A2）：baseline/scenario.composites 为 {key:{value}}，deltas 为对象而非数组。 */
const compareRows = computed(() => {
  const data = response.value;
  if (!data) return [];
  return SLIDERS.map((slider) => {
    const before = compositeOf(data.baseline, slider.key);
    const after = compositeOf(data.scenario, slider.key);
    return {
      id: slider.key,
      label: slider.label,
      before,
      after,
      delta: before !== null && after !== null ? after - before : null,
    };
  });
});

const beforePhase = computed(() => phaseOf(response.value?.baseline) || "—");
const afterPhase = computed(() => phaseOf(response.value?.scenario) || "—");
const beforeShort = computed(() => response.value?.baseline?.short_cycle?.state ?? "—");
const afterShort = computed(() => response.value?.scenario?.short_cycle?.state ?? "—");
const phaseChanged = computed(() => {
  const flag = response.value?.deltas?.phase_changed;
  if (typeof flag === "boolean") return flag;
  return beforePhase.value !== afterPhase.value;
});
const stateChanged = computed(() => {
  const flag = response.value?.deltas?.state_changed;
  if (typeof flag === "boolean") return flag;
  return beforeShort.value !== afterShort.value;
});

const probDeltas = computed(() => {
  const map = response.value?.deltas?.scenario_probability_delta;
  if (!map) return [];
  return Object.entries(map)
    .filter((entry): entry is [string, number] => numberOrNull(entry[1]) !== null)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([id, delta]) => ({
      id,
      name: scenarioNames.value.get(id) ?? id,
      display: probDeltaText(delta),
      tone: deltaClass(delta * 100),
    }));
});

function phaseOf(branch: ScenarioBranch | null | undefined): string {
  const phase = branch?.long_cycle?.phase ?? branch?.long_cycle?.phase_id;
  return typeof phase === "string" && phase ? phase : "";
}

function probDeltaText(delta: number): string {
  const sign = delta > 0 ? "+" : "";
  return `${sign}${(delta * 100).toFixed(1)}pp`;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function barWidth(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "0%";
  const pct = Math.max(0, Math.min(100, value));
  return `${pct}%`;
}

function signed(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}`;
}

function deltaClass(value: number | null): string {
  if (value === null || value === 0) return "";
  return value > 0 ? "pipe-delta--up" : "pipe-delta--down";
}

watch(
  () => props.initial,
  () => {
    if (dirty.value || !hasInitial.value) return;
    baseline.value = snapshot();
    values.value = snapshot();
    void runScenario();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer);
});

function onInput(key: CycleKey, event: Event) {
  const target = event.target as HTMLInputElement;
  const next = Number(target.value);
  if (!Number.isFinite(next)) return;
  values.value = { ...values.value, [key]: Math.max(0, Math.min(100, Math.round(next))) };
  dirty.value = true;
  schedule();
}

function schedule() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    void runScenario();
  }, 400);
}

function reset() {
  if (timer) clearTimeout(timer);
  timer = null;
  values.value = { ...baseline.value };
  dirty.value = false;
  void runScenario();
}

async function runScenario() {
  const token = ++requestToken;
  loading.value = true;
  try {
    const data = await postJson<ScenarioResponse>("/api/v2/cycle/scenario", {
      overrides: { ...values.value },
    });
    if (token !== requestToken) return;
    response.value = data;
    errorMessage.value = "";
    errorStatus.value = null;
  } catch (error) {
    if (token !== requestToken) return;
    response.value = null;
    errorStatus.value = error instanceof ApiError ? error.status : null;
    errorMessage.value = error instanceof Error ? error.message : "请求失败";
  } finally {
    if (token === requestToken) loading.value = false;
  }
}

void runScenario();
</script>

<style scoped>
.pipe-sandbox {
  min-width: 0;
}
.pipe-sandbox-actions {
  flex-wrap: wrap;
  row-gap: 4px;
}
.pipe-sandbox-body {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.pipe-sandbox-sub {
  font-size: 9.5px;
  color: var(--dim);
  line-height: 1.5;
}
.pipe-sliders {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px 12px;
}
.pipe-slider-row {
  min-width: 0;
}
.pipe-slider-head {
  display: flex;
  align-items: baseline;
  gap: 5px;
  margin-bottom: 1px;
}
.pipe-slider-label {
  font-size: 10px;
  color: var(--text);
  font-weight: 550;
  white-space: nowrap;
}
.pipe-slider-key {
  font-size: 8.5px;
  color: var(--dim);
}
.pipe-slider-value {
  margin-left: auto;
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
}
.pipe-range {
  width: 100%;
  margin: 0;
  height: 14px;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}
.pipe-range::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
  background: var(--surface-3);
}
.pipe-range::-moz-range-track {
  height: 4px;
  border-radius: 2px;
  background: var(--surface-3);
}
.pipe-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px;
  height: 12px;
  margin-top: -4px;
  border: 2px solid var(--bg);
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-line);
}
.pipe-range::-moz-range-thumb {
  width: 10px;
  height: 10px;
  border: 2px solid var(--bg);
  border-radius: 50%;
  background: var(--accent);
}
.pipe-range:focus-visible {
  outline: 1px solid var(--accent);
  outline-offset: 3px;
}
.pipe-slider-scale {
  display: flex;
  justify-content: space-between;
  font-size: 8px;
  color: var(--dim);
  line-height: 1;
}

.pipe-sandbox-error {
  padding: 8px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 40%, var(--border));
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 9%, transparent);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.pipe-sandbox-error-title {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--warn);
}
.pipe-sandbox-error-text {
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.pipe-sandbox-error-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.pipe-sandbox-loading {
  padding: 2px 0;
}
.pipe-sandbox-foot {
  padding-top: 6px;
  border-top: 1px dashed var(--border);
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
}

.pipe-compare {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pipe-compare-title {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
}
.pipe-compare-note {
  margin-left: auto;
  font-size: 8px;
  font-weight: 400;
  color: var(--dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 58%;
}
.pipe-compare-row {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) 42px;
  align-items: center;
  gap: 6px;
}
.pipe-compare-label {
  font-size: 9.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pipe-bars {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.pipe-bar-line {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.pipe-bar-tag {
  flex: none;
  width: 20px;
  font-size: 8px;
  color: var(--dim);
}
.pipe-bar-tag--after {
  color: var(--accent);
}
.pipe-bar {
  flex: 1;
  height: 5px;
  border-radius: 2px;
  background: var(--surface-3);
  overflow: hidden;
}
.pipe-bar i {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: var(--dim);
  transition: width 0.25s ease;
}
.pipe-bar i.pipe-bar-fill--after {
  background: var(--accent);
}
.pipe-bar-line b {
  width: 34px;
  flex: none;
  text-align: right;
  font-size: 8.5px;
  color: var(--muted);
  font-weight: 500;
}
.pipe-compare-delta {
  font-size: 9px;
  text-align: right;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-delta--up { color: var(--up); }
.pipe-delta--down { color: var(--down); }

.pipe-change-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}
.pipe-change {
  padding: 6px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
  min-width: 0;
}
.pipe-change-label {
  display: block;
  margin-bottom: 2px;
  font-size: 8.5px;
  color: var(--dim);
}
.pipe-change-value {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  font-size: 10px;
  color: var(--muted);
}
.pipe-change-value b {
  font-weight: 550;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipe-change-value svg {
  width: 10px;
  height: 10px;
  flex: none;
  color: var(--dim);
}
.pipe-change-after {
  color: var(--accent);
}
.pipe-change-tag {
  margin-left: auto;
  flex: none;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 8px;
  line-height: 1.6;
}
.pipe-change-tag--changed {
  background: color-mix(in srgb, var(--warn) 16%, transparent);
  color: var(--warn);
}
.pipe-change-tag--same {
  background: var(--surface-3);
  color: var(--dim);
}
.pipe-change--wide {
  grid-column: 1 / -1;
}
.pipe-prob-deltas {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
}
.pipe-prob-delta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 6px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-3);
  font-size: 9px;
  min-width: 0;
  max-width: 100%;
}
.pipe-prob-delta-name {
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipe-prob-delta b {
  flex: none;
  font-size: 9px;
  color: var(--dim);
}
.pipe-sandbox-note {
  font-size: 8px;
  color: var(--dim);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.pipe-empty-line {
  font-size: 9.5px;
  color: var(--dim);
}

@media (max-width: 1024px) {
  .pipe-sliders {
    grid-template-columns: minmax(0, 1fr);
  }
  .pipe-change-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
