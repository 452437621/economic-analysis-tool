<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 预警台 · W1–W12</div>
        <h1 class="page-h1">
          预警台
          <span class="page-sub">规则命中不是预测：每条阈值都附带原因与失效条件，触发后应人工复核</span>
        </h1>
      </div>
      <div class="page-actions">
        <span v-if="payload?.asof" class="badge badge--sm">数据日 {{ fmtDate(payload.asof) }}</span>
        <span v-if="alerts" class="badge badge--sm" :class="alerts.triggered ? 'badge--up' : 'badge--live'">
          已触发 {{ alerts.triggered }} / {{ alerts.total }}
        </span>
        <button class="btn btn--sm" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中…" : "立即重算" }}
        </button>
      </div>
    </div>

    <SkeletonBlock v-if="!payload && loading" :rows="6" :cells="3" :height="16" />
    <ErrorState v-else-if="!payload && error" :error="error" @retry="refresh" />

    <template v-else-if="alerts">
      <div class="kpi-grid">
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-alert" /></svg></span>
            <span class="kpi-label">高风险（≥ 警报线）</span>
          </div>
          <div class="kpi-value">{{ alerts.counts.high }}<small>条触发</small></div>
          <div class="kpi-sub">阈值见下方规则表；高严重度规则优先复核</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-bell" /></svg></span>
            <span class="kpi-label">中风险（≥ 警戒线）</span>
          </div>
          <div class="kpi-value">{{ alerts.counts.medium }}<small>条触发</small></div>
          <div class="kpi-sub">距离阈值越近，越应关注后续确认</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-eye" /></svg></span>
            <span class="kpi-label">低风险（观察项）</span>
          </div>
          <div class="kpi-value">{{ alerts.counts.low }}<small>条触发</small></div>
          <div class="kpi-sub">观察级规则仅提示，不构成行动</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-calendar" /></svg></span>
            <span class="kpi-label">临近政治事件</span>
          </div>
          <div class="kpi-value">{{ upcoming.length }}<small>个 · 未来半年</small></div>
          <div class="kpi-sub">{{ upcoming[0] ? `${upcoming[0].name}（${upcoming[0].days} 天）` : "无临近事件" }}</div>
        </article>
      </div>

      <section class="card table-card alert-card">
        <div class="card-head">
          <span class="card-title">预警清单</span>
          <span class="card-sub">按「已触发 → 高 → 中」排序 · 点击行展开原因与失效条件</span>
          <div class="card-actions">
            <span class="card-sub">{{ alerts.note }}</span>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 22px"></th>
                <th style="width: 58px">严重度</th>
                <th>规则</th>
                <th>指标</th>
                <th class="num">当前值</th>
                <th class="num">阈值</th>
                <th class="num">距离</th>
                <th class="num">状态</th>
                <th>观测日</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="item in alerts.alerts" :key="item.id">
                <tr class="alert-line" :class="{ 'is-open': openId === item.id }" @click="toggle(item.id)">
                  <td><span class="sev-dot" :class="`sev-dot--${item.status}`"></span></td>
                  <td>
                    <span class="badge badge--sm" :class="severityTone(item.severity)">
                      {{ item.severity_label }}
                    </span>
                  </td>
                  <td>
                    <div class="rule-name">{{ item.name }}</div>
                    <div class="rule-id mono">{{ item.id }}</div>
                  </td>
                  <td class="mono rule-metric">{{ item.metric_name ?? item.metric ?? "—" }}</td>
                  <td class="num">{{ fmtNumber(item.value, 2) }}</td>
                  <td class="num mono">{{ item.op }} {{ fmtNumber(item.threshold, 2) }}</td>
                  <td class="num" :class="distanceTone(item.distance)">
                    {{ item.distance === null ? "—" : fmtSigned(item.distance, 2) }}
                  </td>
                  <td class="num">
                    <span class="state-text" :class="`state-text--${item.status}`">{{ statusText(item.status) }}</span>
                  </td>
                  <td class="mono tm">{{ item.asof ? fmtDate(item.asof) : "—" }}</td>
                </tr>
                <tr v-if="openId === item.id" :key="`${item.id}-detail`" class="detail-row">
                  <td colspan="9">
                    <div class="detail-box">
                      <div class="detail-col">
                        <span class="detail-label">为什么是这条规则</span>
                        <p>{{ item.why ?? "—" }}</p>
                      </div>
                      <div class="detail-col">
                        <span class="detail-label">失效条件（触发不等于必然）</span>
                        <p>{{ item.falsifier ?? "—" }}</p>
                      </div>
                      <div class="detail-col">
                        <span class="detail-label">数据来源与口径</span>
                        <p>{{ item.source ?? "—" }}</p>
                        <p v-if="item.reason" class="detail-note">{{ item.reason }}</p>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div class="card-foot">
          <span>缺失指标记为「未知」，不会默认为「未触发」。</span>
          <span class="mono">{{ payload?.run_id ? `run ${payload.run_id.slice(0, 8)}` : "" }}</span>
        </div>
      </section>

      <div class="alert-bottom">
        <section class="card table-card">
          <div class="card-head">
            <span class="card-title">规则与阈值</span>
            <span class="card-sub">只读展示 · 修改请编辑 config/cycle.yaml 后重算</span>
          </div>
          <div class="table-wrap small">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 40px">ID</th>
                  <th style="width: 52px">等级</th>
                  <th>规则</th>
                  <th>指标</th>
                  <th class="num">阈值</th>
                  <th>失效条件</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rule in rules" :key="rule.id">
                  <td class="mono">{{ rule.id }}</td>
                  <td>
                    <span class="badge badge--sm" :class="severityTone(rule.severity)">{{ severityLabel(rule.severity) }}</span>
                  </td>
                  <td class="rule-name">{{ rule.name }}</td>
                  <td class="mono rule-metric">{{ rule.metric }}</td>
                  <td class="num mono">{{ rule.op }} {{ fmtNumber(rule.threshold, 2) }}</td>
                  <td class="falsifier-cell">{{ rule.falsifier }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <span class="card-title">政治日历</span>
            <span class="card-sub">半年内临近事件 · 30 天内进入高不确定性窗口</span>
          </div>
          <div class="card-body cal-list">
            <div v-for="event in calendar" :key="event.date" class="cal-row" :class="{ 'cal-row--hot': event.days <= 30 }">
              <span class="cal-date mono">{{ event.date.slice(5) }}</span>
              <span class="cal-imp" :class="{ high: event.importance >= 3 }">{{ stars(event.importance) }}</span>
              <div class="cal-main">
                <span class="cal-name">{{ event.name }}</span>
                <span class="cal-note">{{ event.note }}</span>
              </div>
              <span class="cal-days mono" :class="{ hot: event.days <= 30 }">
                {{ event.days < 0 ? `已过 ${Math.abs(event.days)} 天` : `${event.days} 天` }}
              </span>
            </div>
            <EmptyState v-if="!calendar.length" text="政治日历为空" hint="在 config/cycle.yaml 的 political_calendar 中添加事件。" />
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtNumber, fmtSigned, stars } from "@/composables/useFormat";
import { getCycleConfig, getCycleState, runCycle } from "@/api/endpoints";
import type { CycleAlertRule, CycleConfigResponse, CycleStateResponse } from "@/api/types";

const { data, error, loading, refresh } = usePolling<CycleStateResponse>(getCycleState, { interval: 60_000 });
const { data: configData } = usePolling<CycleConfigResponse>(getCycleConfig, { interval: 600_000 });

const running = ref(false);
const openId = ref<string | null>(null);
const payload = computed(() => data.value);
const alerts = computed(() => payload.value?.alerts?.value ?? null);
const rules = computed<CycleAlertRule[]>(() => configData.value?.alerts ?? []);

function today(): Date {
  return new Date();
}

const calendar = computed(() => {
  const items = configData.value?.political_calendar ?? [];
  const now = today();
  return items
    .map((item) => ({ ...item, days: Math.round((new Date(item.date).getTime() - now.getTime()) / 86_400_000) }))
    .sort((a, b) => a.days - b.days);
});

const upcoming = computed(() => calendar.value.filter((item) => item.days >= 0 && item.days <= 180));

function toggle(id: string | null): void {
  if (!id) return;
  openId.value = openId.value === id ? null : id;
}

type Severity = "high" | "medium" | "low";
function severityTone(severity: Severity | string): string {
  if (severity === "high") return "badge--up";
  if (severity === "medium") return "badge--warn";
  return "";
}
function severityLabel(severity: Severity | string): string {
  return severity === "high" ? "高" : severity === "medium" ? "中" : "低";
}
function statusText(status: string | null): string {
  if (status === "triggered") return "已触发";
  if (status === "unknown") return "未知";
  return "未触发";
}
function distanceTone(distance: number | null): string {
  if (distance === null) return "";
  return Math.abs(distance) <= 0 ? "is-hot" : "";
}

async function recalc(): Promise<void> {
  if (running.value) return;
  running.value = true;
  try {
    await runCycle();
    await refresh();
  } finally {
    running.value = false;
  }
}
</script>

<style scoped>
.alert-card {
  margin-top: 10px;
}
.alert-line {
  cursor: pointer;
}
.alert-line.is-open td {
  background: color-mix(in srgb, var(--surface-2) 78%, transparent);
}
.sev-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--dim);
}
.sev-dot--triggered {
  background: var(--up);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--up) 18%, transparent);
}
.sev-dot--unknown {
  border: 1px solid var(--warn);
  background: transparent;
}
.rule-name {
  font-size: 11.5px;
  color: var(--text);
}
.rule-id {
  font-size: 9px;
  color: var(--dim);
}
.rule-metric {
  font-size: 10px;
  color: var(--muted);
}
.state-text {
  font-size: 10px;
  color: var(--dim);
}
.state-text--triggered {
  color: var(--up-color, var(--up));
  font-weight: 650;
}
.state-text--unknown {
  color: var(--warn);
}
.detail-row td {
  background: color-mix(in srgb, var(--surface-2) 62%, transparent);
  padding: 0;
}
.detail-box {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  padding: 10px 14px 12px;
}
.detail-col p {
  margin: 3px 0 0;
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.55;
  white-space: normal;
}
.detail-label {
  font-size: 9.5px;
  letter-spacing: 0.3px;
  color: var(--dim);
}
.detail-note {
  color: var(--warn) !important;
}
.is-hot {
  color: var(--warn);
}
.alert-bottom {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
  align-items: start;
}
.table-wrap.small {
  max-height: 316px;
}
.falsifier-cell {
  font-size: 10px;
  color: var(--dim);
  white-space: normal;
  min-width: 160px;
}
.cal-list {
  display: grid;
  gap: 2px;
}
.cal-row {
  display: grid;
  grid-template-columns: 44px 30px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}
.cal-row:last-child {
  border-bottom: 0;
}
.cal-row--hot {
  background: linear-gradient(90deg, color-mix(in srgb, var(--warn) 8%, transparent), transparent 70%);
}
.cal-date {
  font-size: 10.5px;
  color: var(--accent);
}
.cal-imp {
  font-size: 7px;
  color: var(--dim);
  letter-spacing: 1px;
}
.cal-imp.high {
  color: var(--warn);
}
.cal-main {
  display: grid;
  gap: 2px;
}
.cal-name {
  font-size: 11px;
  color: var(--text);
}
.cal-note {
  font-size: 9.5px;
  color: var(--dim);
}
.cal-days {
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
}
.cal-days.hot {
  color: var(--warn);
}
.spin {
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1180px) {
  .alert-bottom {
    grid-template-columns: minmax(0, 1fr);
  }
  .detail-box {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
