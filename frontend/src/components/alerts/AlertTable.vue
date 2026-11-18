<template>
  <section class="card table-card alr-table-card">
    <header class="card-head">
      <span class="card-title">预警表</span>
      <span class="card-sub">全量 {{ alerts.length }} 条 · 触发项置顶（沿用后端排序）</span>
      <div class="card-actions">
        <span v-if="loading" class="badge badge--sm badge--live">同步中</span>
        <span v-else-if="configLoading && !rules.length" class="badge badge--sm">阈值加载中</span>
        <span v-else-if="hasChanges" class="badge badge--sm badge--warn">{{ changeCount }} 项未保存</span>
        <div class="seg alr-seg" role="group" aria-label="状态筛选">
          <button
            v-for="option in filterOptions"
            :key="option.key"
            type="button"
            :class="{ active: filter === option.key }"
            @click="filter = option.key"
          >
            {{ option.label }}<span class="alr-seg-count">{{ counts[option.key] }}</span>
          </button>
        </div>
      </div>
    </header>

    <div class="table-wrap alr-table-wrap">
      <table class="data-table alr-table">
        <colgroup>
          <col style="width: 20px" />
          <col style="width: 54px" />
          <col />
          <col style="width: 100px" />
          <col style="width: 74px" />
          <col style="width: 96px" />
          <col style="width: 62px" />
          <col style="width: 72px" />
          <col style="width: 54px" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col"><span class="sr-only">状态</span></th>
            <th scope="col">严重度</th>
            <th scope="col">规则</th>
            <th scope="col">指标</th>
            <th scope="col" class="num">当前值</th>
            <th scope="col" class="num" title="直接修改触发线；保存后写入 config/cycle.overrides.yaml">阈值</th>
            <th scope="col" class="num">距离</th>
            <th scope="col">观测日</th>
            <th scope="col" class="num">展开</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="item in visible" :key="item.id">
            <tr class="alr-line" :class="{ 'is-open': openId === item.id }" @click="toggle(item.id)">
              <td>
                <span
                  class="alr-dot"
                  :class="dotClass(item.status)"
                  :title="statusText(item.status)"
                  :aria-label="statusText(item.status)"
                ></span>
              </td>
              <td>
                <span class="badge badge--sm" :class="severityTone(item.severity)">
                  {{ item.severity_label || severityLabel(item.severity) }}
                </span>
              </td>
              <td>
                <div class="alr-rule">
                  <span class="alr-rule-name">{{ item.name }}</span>
                  <span class="alr-rule-id">{{ item.id }}</span>
                </div>
              </td>
              <td><span class="alr-metric">{{ item.metric_name ?? item.metric ?? "—" }}</span></td>
              <td class="num"><span class="alr-value">{{ fmtMacro(item.value, item.unit, 2) }}</span></td>
              <td class="num">
                <div class="alr-thr" @click.stop>
                  <span class="alr-thr-op">{{ opLabel(item.op) }}</span>
                  <input
                    class="alr-thr-input mono"
                    :class="{ 'is-dirty': isDirty(item) }"
                    type="number"
                    step="0.01"
                    inputmode="decimal"
                    :aria-label="`${item.name} 阈值`"
                    :value="thresholdDraft(item)"
                    @input="onThresholdInput(item.id, $event)"
                  />
                </div>
              </td>
              <td class="num">
                <span class="mono alr-dist" :class="distanceClass(item)">{{ fmtSigned(item.distance, 2) }}</span>
              </td>
              <td><span class="mono alr-asof">{{ item.asof ? fmtDate(item.asof) : "—" }}</span></td>
              <td class="num">
                <button class="btn btn--sm btn--ghost alr-why" type="button" @click.stop="toggle(item.id)">
                  {{ openId === item.id ? "收起" : "详情" }}
                  <svg class="ic alr-why-ic" :class="{ 'is-open': openId === item.id }">
                    <use href="#i-chevron-down" />
                  </svg>
                </button>
              </td>
            </tr>
            <tr v-if="openId === item.id" :key="`${item.id}-detail`" class="alr-detail-row">
              <td colspan="9">
                <div class="alr-detail">
                  <div class="alr-detail-col">
                    <span class="alr-detail-label">为什么是这条规则</span>
                    <p>{{ item.why ?? "—" }}</p>
                  </div>
                  <div class="alr-detail-col">
                    <span class="alr-detail-label">失效条件（触发不等于必然）</span>
                    <p>{{ item.falsifier ?? "—" }}</p>
                  </div>
                  <div class="alr-detail-col">
                    <span class="alr-detail-label">数据来源与口径</span>
                    <p>{{ item.source ?? "—" }}</p>
                    <p v-if="item.status === 'unknown' && item.reason" class="alr-detail-note">{{ item.reason }}</p>
                  </div>
                  <div v-if="hasSample(item)" class="alr-detail-col">
                    <span class="alr-detail-label">样本表现</span>
                    <p>胜率 {{ winPct(item.winrate) ?? "—" }} · 置信度 {{ winPct(item.confidence) ?? "—" }}</p>
                  </div>
                </div>
                <p v-if="item.status === 'triggered'" class="alr-review">
                  复核说明：本表为周期规则快照，触发不会写入确认状态；告警确认入口在右上角「告警中心」，仅作用于价格 /
                  利差 / 事件等告警。
                </p>
              </td>
            </tr>
          </template>
          <tr v-if="!visible.length">
            <td colspan="9" class="alr-empty">
              {{ alerts.length ? "该状态下暂无预警" : "本轮无预警数据" }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="saveError" class="alr-error" role="alert">
      <svg class="ic"><use href="#i-alert" /></svg>
      <span>{{ saveError }}</span>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--ghost" type="button" @click="saveError = null">知道了</button>
    </div>

    <div class="card-foot alr-edit-foot">
      <button class="btn btn--sm btn--primary" type="button" :disabled="!hasChanges || saving" @click="save">
        <svg class="ic" :class="{ spin: saving }"><use href="#i-check" /></svg>
        {{ saving ? "保存中…" : "保存阈值" }}
      </button>
      <button class="btn btn--sm btn--ghost" type="button" :disabled="!hasChanges || saving" @click="reset">
        重置
      </button>
      <span v-if="hasChanges" class="alr-dirty-note">已修改 {{ changeCount }} 项未保存，保存后热加载</span>
      <span v-else class="dim">阈值改动不改变规则方向，仅调整触发线</span>
      <span class="spacer"></span>
      <span class="alr-foot-note">写入 config/cycle.overrides.yaml 并记入审计日志</span>
    </div>

    <div class="table-foot">
      <span>状态点：红=已触发 · 橙=未知 · 灰=未触发；距离为负表示尚未触发，为正表示已越过阈值</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ApiError, patchJson } from "@/api/client";
import type { CycleAlert, CycleAlertRule } from "@/api/types";
import { fmtDate, fmtMacro, fmtSigned } from "@/composables/useFormat";
import { useToast } from "@/stores/toast";

/**
 * 后端契约可能把 severity / status 扩为 unknown，且未来可能补充胜率 / 置信度字段，
 * 这里做本地放宽，不改 api/types.ts。
 */
type AlertRow = Omit<CycleAlert, "severity" | "status"> & {
  severity: string;
  status: string;
  winrate?: number | null;
  confidence?: number | null;
};

interface Props {
  alerts: AlertRow[];
  /** config/cycle.yaml 的规则配置；用于阈值编辑的基线值，缺失时退回当前快照的 threshold。 */
  rules?: CycleAlertRule[];
  loading?: boolean;
  configLoading?: boolean;
}

interface PatchResponse {
  ok?: boolean;
  version?: string;
  changed?: string[];
}

const props = defineProps<Props>();
const emit = defineEmits<{ saved: [] }>();
const toast = useToast();

type StatusFilter = "all" | "triggered" | "unknown" | "normal";

const filterOptions: Array<{ key: StatusFilter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "triggered", label: "已触发" },
  { key: "unknown", label: "未知" },
  { key: "normal", label: "正常" },
];

const filter = ref<StatusFilter>("all");
const openId = ref<string | null>(null);

const rules = computed(() => props.rules ?? []);

const counts = computed<Record<StatusFilter, number>>(() => {
  const tally: Record<StatusFilter, number> = { all: props.alerts.length, triggered: 0, unknown: 0, normal: 0 };
  for (const item of props.alerts) {
    if (item.status === "triggered") tally.triggered += 1;
    else if (item.status === "unknown") tally.unknown += 1;
    else tally.normal += 1;
  }
  return tally;
});

const visible = computed<AlertRow[]>(() => {
  if (filter.value === "all") return props.alerts;
  return props.alerts.filter((item) => item.status === filter.value);
});

const ruleById = computed<Map<string, CycleAlertRule>>(() => {
  const map = new Map<string, CycleAlertRule>();
  for (const rule of rules.value) map.set(rule.id, rule);
  return map;
});

/* ── 内联阈值编辑（由原 ThresholdEditor 并入，避免同一批规则渲染两遍） ── */

const draft = ref<Record<string, string>>({});
/** PATCH 成功但配置轮询尚未返回时，作为「已保存」的本地基线，避免保存按钮又变脏。 */
const savedValues = ref<Record<string, number>>({});
const configSnapshot = ref<Record<string, number>>({});
const saving = ref(false);
const saveError = ref<string | null>(null);

function snapshotOf(list: CycleAlertRule[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const rule of list) out[rule.id] = rule.threshold;
  return out;
}

function sameSnapshot(a: Record<string, number>, b: Record<string, number>): boolean {
  const ids = Object.keys(a);
  if (ids.length !== Object.keys(b).length) return false;
  return ids.every((id) => b[id] !== undefined && Math.abs(a[id] - b[id]) <= 1e-9);
}

function seedDraft(): void {
  const next: Record<string, string> = {};
  for (const rule of rules.value) next[rule.id] = rule.threshold.toFixed(2);
  draft.value = next;
}

watch(
  () => rules.value,
  (next) => {
    const nextSnapshot = snapshotOf(next);
    // 600s 轮询会用同一份配置重建数组；若阈值本身没变，保留用户正在编辑的草稿。
    if (sameSnapshot(nextSnapshot, configSnapshot.value)) return;
    configSnapshot.value = nextSnapshot;
    savedValues.value = {};
    saveError.value = null;
    seedDraft();
  },
  { immediate: true, deep: true },
);

function thresholdDraft(item: AlertRow): string {
  const value = draft.value[item.id];
  if (value !== undefined) return value;
  return Number.isFinite(item.threshold) ? item.threshold.toFixed(2) : "";
}

function onThresholdInput(id: string, event: Event): void {
  const target = event.target as HTMLInputElement | null;
  if (!target) return;
  draft.value = { ...draft.value, [id]: target.value };
}

function parsedValue(id: string): number | null {
  const raw = draft.value[id];
  if (raw === undefined || raw.trim() === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function baseline(item: AlertRow): number {
  const rule = ruleById.value.get(item.id);
  const saved = savedValues.value[item.id];
  if (saved !== undefined) return saved;
  return rule ? rule.threshold : item.threshold;
}

function isDirty(item: AlertRow): boolean {
  const value = parsedValue(item.id);
  if (value === null) return false;
  return Math.abs(value - baseline(item)) > 1e-9;
}

const changed = computed<Record<string, number>>(() => {
  const out: Record<string, number> = {};
  for (const item of props.alerts) {
    const value = parsedValue(item.id);
    if (value !== null && isDirty(item)) out[item.id] = value;
  }
  return out;
});

const changeCount = computed(() => Object.keys(changed.value).length);
const hasChanges = computed(() => changeCount.value > 0);

function reset(): void {
  savedValues.value = {};
  saveError.value = null;
  configSnapshot.value = snapshotOf(rules.value);
  seedDraft();
}

async function save(): Promise<void> {
  if (!hasChanges.value || saving.value) return;
  const payload = changed.value;
  saving.value = true;
  saveError.value = null;
  try {
    const response = await patchJson<PatchResponse>("/api/v2/cycle/config", { alerts: payload });
    if (response.ok === false) {
      throw new Error("配置写入被拒绝");
    }
    savedValues.value = { ...savedValues.value, ...payload };
    toast.ok("阈值已保存并生效（本进程立即生效，多进程部署需重启其他 worker）");
    emit("saved");
  } catch (err) {
    const message = saveFailureMessage(err);
    saveError.value = message;
    toast.bad(message);
  } finally {
    saving.value = false;
  }
}

/** FastAPI 的 400 会把校验原因放在 detail 里；404/405/501 视为接口尚未启用。 */
function saveFailureMessage(err: unknown): string {
  if (err instanceof ApiError && (err.status === 400 || err.status === 422)) {
    return `阈值被拒绝：${serverDetail(err.message)}`;
  }
  return "阈值写入未启用，请编辑 config/cycle.yaml";
}

function serverDetail(message: string): string {
  try {
    const parsed = JSON.parse(message) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* 非 JSON 错误体，原样返回 */
  }
  return message;
}

/* ── 展示辅助 ── */

function toggle(id: string): void {
  openId.value = openId.value === id ? null : id;
}

function severityLabel(severity: string): string {
  if (severity === "high") return "高";
  if (severity === "medium") return "中";
  if (severity === "low") return "低";
  return "未知";
}

function severityTone(severity: string): string {
  if (severity === "high") return "badge--up";
  if (severity === "medium") return "badge--warn";
  if (severity === "unknown") return "badge--accent";
  return "";
}

function statusText(status: string): string {
  if (status === "triggered") return "已触发";
  if (status === "unknown") return "未知";
  return "未触发";
}

function dotClass(status: string): string {
  if (status === "triggered") return "alr-dot--triggered";
  if (status === "unknown") return "alr-dot--unknown";
  return "alr-dot--normal";
}

function opLabel(op: string | null | undefined): string {
  const value = (op ?? "").trim();
  if (value === ">=") return "≥";
  if (value === "<=") return "≤";
  if (value === "==") return "=";
  return value || "—";
}

function hasSample(item: AlertRow): boolean {
  return (
    (item.winrate !== null && item.winrate !== undefined) ||
    (item.confidence !== null && item.confidence !== undefined)
  );
}

/** 兼容 0–1 比例与 0–100 百分数两种口径 */
function winPct(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  const pct = Math.abs(value) <= 1 ? value * 100 : value;
  return `${Math.round(pct)}%`;
}

function distanceClass(item: AlertRow): string {
  if (item.distance === null) return "alr-dist--none";
  if (item.status === "triggered") return "alr-dist--hot";
  if (item.status === "unknown") return "alr-dist--unknown";
  return "alr-dist--normal";
}
</script>

<style scoped>
.alr-table-card {
  overflow: hidden;
}

.alr-seg button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.alr-seg-count {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}

.alr-seg button.active .alr-seg-count {
  color: var(--muted);
}

.alr-table-wrap {
  max-height: 452px;
}

/* 固定列宽 + 规则列自适应：1440 视口下整表落在内容区内，不再出现横向滚动。 */
.alr-table {
  width: 100%;
  table-layout: fixed;
}

.alr-table th,
.alr-table td {
  padding-left: 7px;
  padding-right: 7px;
}

.alr-table td {
  padding-top: 4px;
  padding-bottom: 4px;
}

.alr-line {
  cursor: pointer;
}

.alr-line.is-open td {
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}

.alr-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--dim);
  vertical-align: middle;
}

.alr-dot--normal {
  background: var(--border-strong);
}

.alr-dot--triggered {
  background: var(--up);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--up) 18%, transparent);
}

.alr-dot--unknown {
  border: 1px solid var(--warn);
  background: transparent;
}

.alr-rule {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.alr-rule-name {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.alr-rule-id {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alr-metric {
  display: block;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alr-value {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text);
}

.alr-thr {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 3px;
}

.alr-thr-op {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}

.alr-thr-input {
  width: 58px;
  height: 23px;
  padding: 0 4px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text);
  font-size: 10.5px;
  text-align: right;
}

.alr-thr-input.is-dirty {
  border-color: color-mix(in srgb, var(--warn) 65%, var(--border));
  background: color-mix(in srgb, var(--warn) 8%, var(--surface-2));
}

.alr-thr-input:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.alr-dist {
  font-size: 10px;
}

.alr-dist--hot {
  color: var(--up);
  font-weight: 650;
}

.alr-dist--normal {
  color: var(--muted);
}

.alr-dist--unknown {
  color: var(--warn);
}

.alr-dist--none {
  color: var(--dim);
}

.alr-asof {
  font-size: 10px;
  color: var(--muted);
}

.alr-why {
  padding: 0 5px;
  font-size: 10px;
  white-space: nowrap;
}

.alr-why-ic {
  width: 10px;
  height: 10px;
  transition: transform 0.15s ease;
}

.alr-why-ic.is-open {
  transform: rotate(180deg);
}

.alr-table .alr-detail-row td {
  padding: 0;
  height: auto;
  background: color-mix(in srgb, var(--surface-2) 62%, transparent);
  border-bottom: 1px solid var(--border);
}

.alr-detail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  padding: 10px 14px 8px;
}

.alr-detail-label {
  font-size: 9.5px;
  letter-spacing: 0.3px;
  color: var(--dim);
}

.alr-detail p {
  margin: 3px 0 0;
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.55;
  white-space: normal;
}

.alr-detail-note {
  color: var(--warn);
}

.alr-review {
  margin: 0;
  padding: 0 14px 10px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--warn);
}

.alr-empty {
  padding: 18px 10px;
  text-align: center;
  font-size: 11px;
  color: var(--dim);
}

.alr-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 13px;
  border-top: 1px solid var(--border);
  background: color-mix(in srgb, var(--up) 8%, transparent);
  font-size: 10.5px;
  color: var(--muted);
}

.alr-error .ic {
  width: 13px;
  height: 13px;
  color: var(--warn);
  flex: none;
}

.alr-edit-foot {
  flex-wrap: wrap;
  row-gap: 4px;
}

.alr-dirty-note {
  color: var(--warn);
  font-size: 10px;
}

.alr-foot-note {
  color: var(--dim);
  font-size: 10px;
}

@media (max-width: 1100px) {
  .alr-detail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .alr-detail {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
