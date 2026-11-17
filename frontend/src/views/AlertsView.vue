<template>
  <div class="view active alr-view">
    <header class="page-head">
      <div class="alr-head">
        <div class="page-eyebrow">研究分析 · 预警台</div>
        <h1 class="page-h1">预警台 · 规则何时会被触发</h1>
        <div class="page-sub">{{ ruleTotal }} 条可证伪规则 · 缺失指标记为未知，不默认未触发</div>
      </div>
      <div class="page-actions alr-actions">
        <span
          v-if="stateError && payload"
          class="badge badge--sm badge--warn"
          title="最近一次轮询失败，当前展示上一次成功获取的数据"
        >
          数据可能过期
        </span>
        <span class="badge badge--sm alr-badge" :title="`数据日 ${dataDate}`">
          <svg class="ic"><use href="#i-calendar" /></svg>
          数据日 {{ dataDate }}
        </span>
        <span
          class="badge badge--sm"
          :class="triggeredCount > 0 ? 'badge--up' : 'badge--live'"
          :title="`已触发 ${triggeredCount} 条 / 共 ${ruleTotal} 条规则`"
        >
          已触发 {{ triggeredCount }}/{{ ruleTotal }}
        </span>
        <span class="badge badge--sm" :title="`最近运行时间 ${runLabel}`">
          <svg class="ic"><use href="#i-clock" /></svg>
          运行 {{ runLabel }}
        </span>
        <button class="btn btn--sm btn--primary" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中…" : "立即重算" }}
        </button>
      </div>
    </header>

    <SkeletonBlock v-if="!payload && stateLoading" :rows="8" :cells="4" :height="16" />
    <ErrorState v-else-if="!payload && stateError" :error="stateError" @retry="refresh" />
    <EmptyState
      v-else-if="!alerts"
      text="预警数据不可用"
      hint="本轮 cycle state 未返回 alerts 段，请稍后重试或检查后端运行状态。"
    />

    <template v-else>
      <div class="kpi-grid alr-summary">
        <div class="card kpi alr-sum alr-sum--high">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-alert" /></svg></span>
            <span class="kpi-label">高危触发</span>
            <span class="kpi-flag badge badge--sm badge--up">{{ share(counts.high) }}</span>
          </div>
          <div class="kpi-value">{{ counts.high }}<small>条触发</small></div>
          <div class="kpi-sub">本轮快照 · 触发即需当日复核</div>
        </div>

        <div class="card kpi alr-sum alr-sum--medium">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-bell" /></svg></span>
            <span class="kpi-label">中危</span>
            <span class="kpi-flag badge badge--sm badge--warn">{{ share(counts.medium) }}</span>
          </div>
          <div class="kpi-value">{{ counts.medium }}<small>条触发</small></div>
          <div class="kpi-sub">本轮快照 · 本周内复核</div>
        </div>

        <div class="card kpi alr-sum alr-sum--low">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-eye" /></svg></span>
            <span class="kpi-label">低危</span>
            <span class="kpi-flag badge badge--sm">{{ share(counts.low) }}</span>
          </div>
          <div class="kpi-value">{{ counts.low }}<small>条触发</small></div>
          <div class="kpi-sub">本轮快照 · 观察列表</div>
        </div>

        <div class="card kpi alr-sum alr-sum--unknown">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-info" /></svg></span>
            <span class="kpi-label">未知</span>
            <span class="kpi-flag badge badge--sm badge--warn">{{ share(counts.unknown) }}</span>
          </div>
          <div class="kpi-value">{{ counts.unknown }}<small>条未知</small></div>
          <div class="kpi-sub">本轮快照 · 缺失指标不默认未触发</div>
        </div>
      </div>

      <section class="alr-block" aria-label="预警表">
        <AlertTable :alerts="alertRows" :loading="stateLoading" />
      </section>

      <section class="alr-block" aria-label="阈值编辑器">
        <ThresholdEditor
          :rules="rules"
          :current="alertRows"
          :loading="configLoading"
          @saved="onSaved"
        />
      </section>

      <section class="alr-block" aria-label="财经日历">
        <MarketCalendar :political="politicalCalendar" />
      </section>

      <footer class="alr-foot">
        <span class="alr-foot-note">
          <svg class="ic"><use href="#i-shield-check" /></svg>
          缺失指标记为未知，不默认未触发；触发 ≠ 预测，需人工复核。
        </span>
        <span class="mono alr-run">run {{ runIdShort }}</span>
        <span class="dim">全部规则来自 config/cycle.yaml</span>
        <RouterLink class="alr-link" to="/pipeline">在透明管线查看运行记录</RouterLink>
      </footer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { getCycleConfig, getCycleState, runCycle } from "@/api/endpoints";
import type { CycleAlert, CycleAlertRule, CycleCalendarEntry, CycleConfigResponse, CycleStateResponse } from "@/api/types";
import AlertTable from "@/components/alerts/AlertTable.vue";
import MarketCalendar from "@/components/alerts/MarketCalendar.vue";
import ThresholdEditor from "@/components/alerts/ThresholdEditor.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDate, fmtTime } from "@/composables/useFormat";
import { usePolling } from "@/composables/usePolling";
import { useToast } from "@/stores/toast";

const toast = useToast();

const {
  data: payload,
  error: stateError,
  loading: stateLoading,
  lastUpdated,
  refresh,
} = usePolling<CycleStateResponse>(getCycleState, { interval: 60_000 });

const {
  data: configData,
  loading: configLoading,
  refresh: refreshConfig,
} = usePolling<CycleConfigResponse>(getCycleConfig, { interval: 600_000 });

const running = ref(false);

const alerts = computed(() => payload.value?.alerts?.value ?? null);
const alertRows = computed<CycleAlert[]>(() => alerts.value?.alerts ?? []);
const rules = computed<CycleAlertRule[]>(() => configData.value?.alerts ?? []);
const politicalCalendar = computed<CycleCalendarEntry[]>(() => configData.value?.political_calendar ?? []);

const counts = computed<Record<"high" | "medium" | "low" | "unknown", number>>(() => {
  const raw = alerts.value?.counts;
  return {
    high: raw?.high ?? 0,
    medium: raw?.medium ?? 0,
    low: raw?.low ?? 0,
    unknown: raw?.unknown ?? 0,
  };
});

const totalRules = computed(() => alerts.value?.total ?? 0);
const ruleTotal = computed(() => {
  const total = totalRules.value;
  if (total > 0) return total;
  return rules.value.length || 12;
});
const triggeredCount = computed(() => alerts.value?.triggered ?? 0);

const dataDate = computed(() => {
  const iso = payload.value?.asof;
  return iso ? fmtDate(iso) : "—";
});

const runLabel = computed(() => {
  const iso = payload.value?.generated_at ?? payload.value?.asof;
  if (iso) return fmtTime(iso, true);
  const updated = lastUpdated.value;
  return updated ? fmtTime(updated.toISOString(), true) : "—";
});

const runIdShort = computed(() => payload.value?.run_id?.slice(0, 8) ?? "—");

function share(value: number): string {
  const total = totalRules.value;
  return total > 0 ? `${Math.round((value / total) * 100)}%` : "—";
}

async function recalc(): Promise<void> {
  if (running.value) return;
  running.value = true;
  try {
    await runCycle();
    await Promise.all([refresh(), refreshConfig()]);
    toast.ok("已重新计算本轮预警");
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : "重算失败，请稍后重试");
  } finally {
    running.value = false;
  }
}

/** 阈值保存成功后：刷新预警状态与规则配置，使表格「当前值 / 阈值」同步更新。 */
async function onSaved(): Promise<void> {
  await Promise.all([refresh(), refreshConfig()]);
}
</script>

<style scoped>
.alr-head {
  min-width: 0;
}

.alr-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
  row-gap: 6px;
}

.alr-badge .ic {
  width: 11px;
  height: 11px;
  margin-right: 4px;
  vertical-align: -2px;
}

.alr-actions .ic {
  width: 12px;
  height: 12px;
}

.alr-summary {
  margin-top: 10px;
}

.alr-sum .kpi-label {
  white-space: nowrap;
}

.alr-sum .kpi-icon {
  flex: none;
}

.alr-sum .kpi-flag {
  flex: none;
  font-family: var(--mono);
}

.alr-sum--high .kpi-icon {
  color: var(--up);
  background: color-mix(in srgb, var(--up) 12%, var(--surface-2));
  border-color: color-mix(in srgb, var(--up) 32%, var(--border));
}

.alr-sum--medium .kpi-icon {
  color: var(--warn);
  background: color-mix(in srgb, var(--warn) 14%, var(--surface-2));
  border-color: color-mix(in srgb, var(--warn) 34%, var(--border));
}

.alr-sum--low .kpi-icon {
  color: var(--ok);
  background: color-mix(in srgb, var(--ok) 12%, var(--surface-2));
  border-color: color-mix(in srgb, var(--ok) 30%, var(--border));
}

.alr-sum--unknown .kpi-icon {
  color: var(--warn);
  background: color-mix(in srgb, var(--warn) 8%, var(--surface-2));
  border-style: dashed;
  border-color: color-mix(in srgb, var(--warn) 48%, var(--border));
}

.alr-block {
  margin-top: 10px;
}

.alr-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 12px;
  margin-top: 10px;
  padding: 8px 2px 6px;
  font-size: 10px;
  color: var(--dim);
}

.alr-foot-note {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.alr-foot-note .ic {
  width: 12px;
  height: 12px;
  flex: none;
  color: var(--warn);
}

.alr-run {
  color: var(--muted);
}

.alr-link {
  color: var(--accent);
  text-decoration: none;
}

.alr-link:hover {
  text-decoration: underline;
}

@media (max-width: 1240px) {
  .alr-actions {
    gap: 5px;
  }
}

@media (max-width: 1024px) {
  .alr-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .alr-summary {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
