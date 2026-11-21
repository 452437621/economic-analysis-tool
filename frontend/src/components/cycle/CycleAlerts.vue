<template>
  <!-- D. 今日预警 -->
  <section class="card cyc-alerts">
    <div class="card-head">
      <span class="card-title">
        今日预警
        <span class="badge badge--up badge--sm">{{ alertCount }} 条</span>
      </span>
      <span class="cyc-card-sub">生成于 {{ generatedLabel }}</span>
      <div class="card-actions">
        <RouterLink class="btn btn--ghost btn--sm" to="/alerts">全部 ›</RouterLink>
      </div>
    </div>
    <div v-if="topAlerts.length" class="cyc-alert-list">
      <div v-for="alert in topAlerts" :key="alert.id" class="cyc-alert-row">
        <span class="cyc-sev" :class="`cyc-sev--${sevClass(alert.severity)}`">
          <i></i>{{ sevLabel(alert.severity) }}
        </span>
        <div class="cyc-alert-main">
          <div class="cyc-alert-title">{{ alert.name ?? alert.metric_name ?? "未命名预警" }}</div>
          <div class="cyc-alert-cond" :title="alert.why ?? ''">{{ alert.why ?? "—" }}</div>
        </div>
        <div class="cyc-alert-val">
          <b>{{ alertValue(alert) }}</b>
          <span>{{ alertThreshold(alert) }}</span>
        </div>
        <div class="cyc-alert-meta">{{ alertAsOf(alert) }}</div>
        <RouterLink class="btn btn--ghost btn--sm cyc-alert-src" to="/alerts">溯源</RouterLink>
      </div>
    </div>
    <EmptyState v-else text="今日无触发预警" hint="规则均未达到阈值；全部预警可在预警中心查看。" />
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import type { CycleAlert } from "@/api/types";
import { alertAsOf, alertThreshold, alertValue, sevClass, sevLabel } from "@/utils/cycleFormat";

defineProps<{
  alertCount: number;
  generatedLabel: string;
  topAlerts: CycleAlert[];
}>();
</script>

<style scoped>
/* ── D. 今日预警 ────────────────────────────────────── */
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-alerts {
  margin-top: 10px;
}
.cyc-alert-list {
  display: flex;
  flex-direction: column;
}
.cyc-alert-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 112px 72px 58px;
  gap: 10px;
  align-items: center;
  padding: 7px 12px;
  border-top: 1px dashed var(--border);
  min-height: 49px;
}
.cyc-alert-row:first-child {
  border-top: 0;
}
.cyc-sev {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9.5px;
  font-weight: 600;
  white-space: nowrap;
}
.cyc-sev i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.cyc-sev--high {
  color: var(--up);
}
.cyc-sev--mid {
  color: var(--warn);
}
.cyc-sev--low {
  color: color-mix(in srgb, var(--warn) 78%, var(--text) 22%);
}
.cyc-sev--unknown {
  color: var(--dim);
}
.cyc-alert-main {
  min-width: 0;
}
.cyc-alert-title {
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.35;
}
.cyc-alert-cond {
  font-size: 9.8px;
  color: var(--muted);
  line-height: 1.4;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cyc-alert-val {
  text-align: right;
  min-width: 0;
}
.cyc-alert-val b {
  display: block;
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.cyc-alert-val span {
  display: block;
  font-family: var(--mono);
  font-size: 8.8px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-alert-meta {
  text-align: right;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
  white-space: nowrap;
}
.cyc-alert-src {
  justify-self: end;
  text-decoration: none;
}
@media (max-width: 1023px) {
  .cyc-alert-row {
    grid-template-columns: 40px minmax(0, 1fr) 100px 66px;
  }
  .cyc-alert-src {
    display: none;
  }
}
@media (max-width: 759px) {
  .cyc-alert-row {
    grid-template-columns: 40px minmax(0, 1fr) 100px;
  }
  .cyc-alert-meta {
    display: none;
  }
}
</style>
