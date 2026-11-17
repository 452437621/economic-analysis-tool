<template>
  <section class="card table-card alr-table-card">
    <header class="card-head">
      <span class="card-title">预警表</span>
      <span class="card-sub">
        全量 {{ counts.all }} 条 · 显示 {{ visible.length }} 条 · 触发项置顶（沿用后端排序）
        <template v-if="counts.unknown">
          · <b class="alr-unknown-note">未知 {{ counts.unknown }} 条</b>：缺失指标记为未知，不默认未触发
        </template>
      </span>
      <div class="card-actions">
        <span v-if="loading" class="badge badge--sm badge--live">同步中</span>
        <div class="seg alr-seg" role="group" aria-label="严重度筛选">
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
        <thead>
          <tr>
            <th scope="col" style="width: 24px"><span class="sr-only">状态</span></th>
            <th scope="col" style="width: 56px">严重度</th>
            <th scope="col" style="width: 214px">规则</th>
            <th scope="col" style="width: 132px">指标</th>
            <th scope="col" class="num" style="width: 96px">当前值</th>
            <th scope="col" class="num" style="width: 104px">阈值</th>
            <th scope="col" class="num" style="width: 80px">距离</th>
            <th
              scope="col"
              class="num"
              style="width: 118px"
              title="该规则尚未积累样本：接口未返回胜率 / 置信度字段时显示「—」。"
            >
              胜率 / 置信度 <span class="alr-help" aria-hidden="true">?</span>
            </th>
            <th scope="col" style="width: 88px">观测日</th>
            <th scope="col" style="width: 80px">操作</th>
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
                <span class="alr-threshold">{{ opLabel(item.op) }} {{ fmtMacro(item.threshold, item.unit, 2) }}</span>
              </td>
              <td class="num">
                <span class="mono alr-dist" :class="distanceClass(item)">{{ fmtSigned(item.distance, 2) }}</span>
              </td>
              <td class="num">
                <div v-if="hasSample(item)" class="alr-win" title="胜率 = 触发后 20 日方向正确率；置信度 = 规则置信度">
                  <div class="alr-win-line">
                    <span class="alr-win-bar">
                      <i v-if="winPct(item.winrate)" :style="{ width: winPct(item.winrate) ?? '0%' }"></i>
                    </span>
                    <span class="mono alr-win-num">{{ winPct(item.winrate) ?? "—" }}</span>
                  </div>
                  <div class="alr-win-line">
                    <span class="alr-win-label">置信</span>
                    <span class="mono alr-win-num">{{ winPct(item.confidence) ?? "—" }}</span>
                  </div>
                </div>
                <span v-else class="alr-win-empty">—</span>
              </td>
              <td><span class="mono tm">{{ item.asof ? fmtDate(item.asof) : "—" }}</span></td>
              <td>
                <button class="btn btn--sm btn--ghost alr-why" type="button" @click.stop="toggle(item.id)">
                  {{ openId === item.id ? "收起" : "为什么" }}
                  <svg class="ic alr-why-ic" :class="{ 'is-open': openId === item.id }">
                    <use href="#i-chevron-down" />
                  </svg>
                </button>
              </td>
            </tr>
            <tr v-if="openId === item.id" :key="`${item.id}-detail`" class="alr-detail-row">
              <td colspan="10">
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
                    <p v-if="item.status === 'unknown'" class="alr-detail-note">缺失指标记为未知，不默认未触发。</p>
                  </div>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="!visible.length">
            <td colspan="10" class="alr-empty">
              {{ alerts.length ? "该严重度下暂无预警" : "本轮无预警数据" }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="table-foot">
      <span>状态点：红=已触发 · 橙=未知 · 灰=未触发；距离为负表示尚未触发，为正表示已越过阈值</span>
      <span class="spacer"></span>
      <span>{{ sampleNote }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { CycleAlert } from "@/api/types";
import { fmtDate, fmtMacro, fmtSigned } from "@/composables/useFormat";

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

const props = defineProps<{
  alerts: AlertRow[];
  loading?: boolean;
}>();

type SevFilter = "all" | "high" | "medium" | "low" | "unknown";

const filterOptions: Array<{ key: SevFilter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "high", label: "高" },
  { key: "medium", label: "中" },
  { key: "low", label: "低" },
  { key: "unknown", label: "未知" },
];

const filter = ref<SevFilter>("all");
const openId = ref<string | null>(null);

function toggle(id: string): void {
  openId.value = openId.value === id ? null : id;
}

const counts = computed<Record<SevFilter, number>>(() => {
  const tally: Record<SevFilter, number> = { all: props.alerts.length, high: 0, medium: 0, low: 0, unknown: 0 };
  for (const item of props.alerts) {
    if (item.severity === "high" || item.severity === "medium" || item.severity === "low") {
      tally[item.severity] += 1;
    }
    if (item.status === "unknown" || item.severity === "unknown") {
      tally.unknown += 1;
    }
  }
  return tally;
});

const visible = computed<AlertRow[]>(() => {
  if (filter.value === "all") return props.alerts;
  if (filter.value === "unknown") {
    return props.alerts.filter((item) => item.status === "unknown" || item.severity === "unknown");
  }
  return props.alerts.filter((item) => item.severity === filter.value);
});

const sampleNote = computed(() =>
  props.alerts.some((item) => hasSample(item))
    ? "胜率 = 触发后 20 日方向正确率 · 置信度 = 规则置信度"
    : "胜率 / 置信度：该规则尚未积累样本（接口未返回时显示「—」）",
);

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

.alr-unknown-note {
  color: var(--warn);
  font-weight: 600;
}

.alr-seg button.active .alr-seg-count {
  color: var(--muted);
}

.alr-table-wrap {
  max-height: 468px;
}

.alr-table {
  min-width: 1000px;
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
  white-space: normal;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.alr-rule-id {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}

.alr-metric {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
}

.alr-value {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text);
}

.alr-threshold {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
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

.alr-help {
  display: inline-grid;
  place-items: center;
  width: 11px;
  height: 11px;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  font-size: 8px;
  color: var(--dim);
  cursor: help;
}

.alr-win {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-end;
}

.alr-win-line {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 5px;
}

.alr-win-bar {
  display: block;
  flex: none;
  width: 30px;
  height: 4px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}

.alr-win-bar i {
  display: block;
  height: 100%;
  border-radius: 99px;
  background: var(--accent);
}

.alr-win-label {
  font-size: 8.5px;
  color: var(--dim);
}

.alr-win-num {
  font-size: 9.5px;
  color: var(--muted);
  min-width: 27px;
  text-align: right;
}

.alr-win-empty {
  color: var(--dim);
}

.alr-why {
  padding: 0 6px;
  font-size: 10px;
}

.alr-why-ic {
  width: 11px;
  height: 11px;
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
  padding: 10px 14px 12px;
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
  color: var(--warn) !important;
}

.alr-empty {
  padding: 18px 10px;
  text-align: center;
  font-size: 11px;
  color: var(--dim);
}

@media (max-width: 1100px) {
  .alr-detail {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
