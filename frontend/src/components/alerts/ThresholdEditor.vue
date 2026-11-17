<template>
  <section class="card table-card alr-thr-card">
    <header class="card-head">
      <span class="card-title">规则与阈值 · 可编辑</span>
      <span class="card-sub">{{ rules.length }} 条可证伪规则 · 点击行展开规则依据</span>
      <div class="card-actions">
        <span v-if="loading && !rules.length" class="badge badge--sm badge--live">规则加载中</span>
        <span v-else-if="!rules.length" class="badge badge--sm">规则配置未加载</span>
        <span v-else class="badge badge--sm" :class="hasChanges ? 'badge--warn' : 'badge--live'">
          {{ hasChanges ? `${changeCount} 项待保存` : "配置已同步" }}
        </span>
        <button
          class="btn btn--sm btn--ghost"
          type="button"
          :disabled="!hasChanges || saving"
          title="恢复为 config/cycle.yaml 中的阈值"
          @click="reset"
        >
          重置
        </button>
      </div>
    </header>

    <div class="table-wrap alr-thr-wrap">
      <table class="data-table alr-thr-table">
        <thead>
          <tr>
            <th scope="col" style="width: 40px">ID</th>
            <th scope="col" style="width: 52px">等级</th>
            <th scope="col" style="width: 196px">名称</th>
            <th scope="col" style="width: 128px">指标</th>
            <th scope="col" style="width: 40px">op</th>
            <th scope="col" style="width: 104px">阈值</th>
            <th scope="col" class="num" style="width: 92px">当前值</th>
            <th scope="col" style="width: 76px">状态</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in rows" :key="row.rule.id">
            <tr class="alr-thr-line" @click="toggle(row.rule.id)">
              <td class="mono alr-thr-id">{{ row.rule.id }}</td>
              <td>
                <span class="badge badge--sm" :class="severityTone(row.rule.severity)">
                  {{ severityLabel(row.rule.severity) }}
                </span>
              </td>
              <td>
                <span class="alr-thr-name">
                  <svg class="ic alr-thr-chevron" :class="{ 'is-open': openId === row.rule.id }">
                    <use href="#i-chevron-right" />
                  </svg>
                  {{ row.rule.name }}
                </span>
              </td>
              <td class="mono alr-thr-metric">{{ row.rule.metric }}</td>
              <td class="mono alr-thr-op">{{ opLabel(row.rule.op) }}</td>
              <td>
                <input
                  class="alr-thr-input mono"
                  type="number"
                  step="0.01"
                  inputmode="decimal"
                  :aria-label="`${row.rule.name} 阈值`"
                  :value="draft[row.rule.id] ?? ''"
                  :class="{ 'is-dirty': isDirtyRule(row.rule) }"
                  @input="onInput(row.rule.id, $event)"
                  @click.stop
                />
              </td>
              <td class="num mono alr-thr-current">{{ currentText(row.alert) }}</td>
              <td>
                <span class="alr-status" :class="statusClass(row.alert?.status ?? '')">
                  {{ statusText(row.alert?.status ?? '') }}
                </span>
              </td>
            </tr>
            <tr v-if="openId === row.rule.id" :key="`${row.rule.id}-detail`" class="alr-thr-detail-row">
              <td colspan="8">
                <div class="alr-thr-detail">
                  <div class="alr-thr-detail-col">
                    <span class="alr-detail-label">为什么是这条规则</span>
                    <p>{{ row.rule.why || "—" }}</p>
                  </div>
                  <div class="alr-thr-detail-col">
                    <span class="alr-detail-label">失效条件（触发不等于必然）</span>
                    <p>{{ row.rule.falsifier || "—" }}</p>
                  </div>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="!rows.length">
            <td colspan="8" class="alr-thr-empty">规则配置未加载，暂时无法编辑阈值。</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="saveError" class="alr-thr-error" role="alert">
      <svg class="ic"><use href="#i-alert" /></svg>
      <span>{{ saveError }}</span>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--ghost" type="button" @click="saveError = null">知道了</button>
    </div>

    <div class="card-foot alr-thr-foot">
      <button
        class="btn btn--sm btn--primary"
        type="button"
        :disabled="!hasChanges || saving || !rules.length"
        @click="save"
      >
        <svg class="ic" :class="{ spin: saving }"><use href="#i-check" /></svg>
        {{ saving ? "保存中…" : "保存阈值" }}
      </button>
      <span v-if="hasChanges">已修改 {{ changeCount }} 项，保存后热加载</span>
      <span v-else class="dim">修改阈值后保存；写入落盘 config/cycle.overrides.yaml 并审计 data/audit/cycle-config.jsonl</span>
      <span class="spacer"></span>
      <span class="alr-thr-note">阈值改动不改变规则方向，仅调整触发线</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { patchJson, ApiError } from "@/api/client";
import type { CycleAlert, CycleAlertRule } from "@/api/types";
import { fmtMacro } from "@/composables/useFormat";
import { useToast } from "@/stores/toast";

interface Props {
  rules: CycleAlertRule[];
  current: CycleAlert[];
  loading?: boolean;
}

interface PatchResponse {
  ok?: boolean;
  version?: string;
  changed?: string[];
  overrides?: {
    path?: string;
    alerts?: Record<string, number>;
  };
}

const props = defineProps<Props>();
const emit = defineEmits<{ saved: [] }>();
const toast = useToast();

const openId = ref<string | null>(null);
const saving = ref(false);
const saveError = ref<string | null>(null);
const draft = ref<Record<string, string>>({});
/** PATCH 成功但配置轮询尚未返回时，作为「已保存」的本地基线，避免保存按钮又变脏。 */
const savedValues = ref<Record<string, number>>({});

const currentById = computed<Map<string, CycleAlert>>(() => {
  const map = new Map<string, CycleAlert>();
  for (const item of props.current) map.set(item.id, item);
  return map;
});

const rows = computed<Array<{ rule: CycleAlertRule; alert: CycleAlert | undefined }>>(() =>
  props.rules.map((rule) => ({ rule, alert: currentById.value.get(rule.id) })),
);

function seedDraft(): void {
  const next: Record<string, string> = {};
  for (const rule of props.rules) next[rule.id] = rule.threshold.toFixed(2);
  draft.value = next;
}

/** 最近一次从 config 读到的阈值，用于判断轮询结果是否真的变化。 */
const configSnapshot = ref<Record<string, number>>({});

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

watch(
  () => props.rules,
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

function toggle(id: string): void {
  openId.value = openId.value === id ? null : id;
}

function onInput(id: string, event: Event): void {
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

function baseline(rule: CycleAlertRule): number {
  const saved = savedValues.value[rule.id];
  return saved === undefined ? rule.threshold : saved;
}

function isDirtyRule(rule: CycleAlertRule): boolean {
  const value = parsedValue(rule.id);
  if (value === null) return false;
  return Math.abs(value - baseline(rule)) > 1e-9;
}

const changed = computed<Record<string, number>>(() => {
  const out: Record<string, number> = {};
  for (const rule of props.rules) {
    const value = parsedValue(rule.id);
    if (value !== null && isDirtyRule(rule)) out[rule.id] = value;
  }
  return out;
});

const changeCount = computed(() => Object.keys(changed.value).length);
const hasChanges = computed(() => changeCount.value > 0);

function reset(): void {
  savedValues.value = {};
  saveError.value = null;
  configSnapshot.value = snapshotOf(props.rules);
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
    toast.ok("已保存并生效（本进程立即生效，多进程部署需重启其他 worker）");
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

function opLabel(op: string | null | undefined): string {
  const value = (op ?? "").trim();
  if (value === ">=") return "≥";
  if (value === "<=") return "≤";
  if (value === "==") return "=";
  return value || "—";
}

function currentText(alert: CycleAlert | undefined): string {
  if (!alert) return "—";
  return fmtMacro(alert.value, alert.unit, 2);
}

function statusText(status: string): string {
  if (status === "triggered") return "已触发";
  if (status === "unknown") return "未知";
  if (status === "normal") return "未触发";
  return "—";
}

function statusClass(status: string): string {
  if (status === "triggered") return "alr-status--hot";
  if (status === "unknown") return "alr-status--unknown";
  if (status === "normal") return "alr-status--normal";
  return "alr-status--none";
}
</script>

<style scoped>
.alr-thr-card {
  overflow: hidden;
}

.alr-thr-wrap {
  max-height: 352px;
}

.alr-thr-table {
  min-width: 780px;
}

.alr-thr-table td {
  padding-top: 3px;
  padding-bottom: 3px;
}

.alr-thr-line {
  cursor: pointer;
}

.alr-thr-line:hover td {
  background: color-mix(in srgb, var(--accent) 3%, transparent);
}

.alr-thr-id {
  font-size: 10px;
  color: var(--dim);
}

.alr-thr-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--text);
  white-space: normal;
  line-height: 1.3;
}

.alr-thr-chevron {
  width: 10px;
  height: 10px;
  flex: none;
  color: var(--dim);
  transition: transform 0.15s ease;
}

.alr-thr-chevron.is-open {
  transform: rotate(90deg);
}

.alr-thr-metric {
  font-size: 9.5px;
  color: var(--muted);
}

.alr-thr-op {
  font-size: 10px;
  color: var(--muted);
}

.alr-thr-input {
  width: 78px;
  height: 24px;
  padding: 0 6px;
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

.alr-thr-current {
  font-size: 10.5px;
  color: var(--muted);
}

.alr-status {
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}

.alr-status--hot {
  color: var(--up);
  font-weight: 650;
}

.alr-status--unknown {
  color: var(--warn);
}

.alr-status--normal {
  color: var(--muted);
}

.alr-thr-table .alr-thr-detail-row td {
  padding: 0;
  height: auto;
  background: color-mix(in srgb, var(--surface-2) 62%, transparent);
  white-space: normal;
}

.alr-thr-detail {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  padding: 8px 14px 10px;
}

.alr-detail-label {
  font-size: 9.5px;
  letter-spacing: 0.3px;
  color: var(--dim);
}

.alr-thr-detail-col p {
  margin: 3px 0 0;
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.55;
  white-space: normal;
}

.alr-thr-empty {
  padding: 18px 10px;
  text-align: center;
  font-size: 11px;
  color: var(--dim);
}

.alr-thr-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 13px;
  border-top: 1px solid var(--border);
  background: color-mix(in srgb, var(--up) 8%, transparent);
  font-size: 10.5px;
  color: var(--muted);
}

.alr-thr-error .ic {
  width: 13px;
  height: 13px;
  color: var(--warn);
  flex: none;
}

.alr-thr-error .spacer {
  flex: 1;
}

.alr-thr-foot {
  flex-wrap: wrap;
  row-gap: 4px;
}

.alr-thr-foot .spacer {
  flex: 1;
}

.alr-thr-note {
  color: var(--dim);
}

@media (max-width: 900px) {
  .alr-thr-detail {
    grid-template-columns: minmax(0, 1fr);
  }

  .alr-thr-note {
    display: none;
  }
}
</style>
