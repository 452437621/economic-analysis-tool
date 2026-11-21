<template>
  <div v-if="readingsUnavailable" class="card cyc-readings-fallback">
    <span class="badge badge--sm badge--warn">读数接口不可用</span>
    <span class="cyc-readings-fallback-text">
      {{ readingsErrorText }}；其余区块照常展示。
    </span>
    <button class="btn btn--ghost btn--sm" type="button" @click="$emit('retry')">重试</button>
  </div>
  <SkeletonBlock v-else-if="!kpis.length && loading" :rows="2" :cells="4" :height="80" />
  <EmptyState
    v-else-if="!kpis.length"
    text="暂无关键读数"
    hint="/api/v2/cycle/readings 未返回任何读数。"
  />
  <div v-else class="cyc-kpi-grid">
    <div
      v-for="kpi in kpis"
      :key="kpi.id"
      class="cyc-kpi-card"
      :title="kpi.tooltip"
    >
      <div class="cyc-kpi-top">
        <span class="cyc-kpi-label">{{ kpi.label }}</span>
        <span class="cyc-kpi-z" :class="kpi.zClass">
          {{ kpi.z === null ? "z —" : `z ${fmtSigned(kpi.z, 1)}` }}
        </span>
      </div>
      <div class="cyc-kpi-val">
        <b>{{ kpi.value }}</b>
        <span v-if="kpi.unit && !kpi.missing" class="cyc-kpi-unit">{{ kpi.unit }}</span>
        <span v-if="kpi.missing" class="cyc-kpi-miss">数据缺失</span>
        <span v-if="kpi.deltaText" class="cyc-kpi-chg" :class="`cyc-kpi-chg--${kpi.deltaClass}`">
          {{ kpi.deltaText }}
        </span>
      </div>
      <div class="cyc-kpi-foot">
        <svg
          v-if="kpi.spark"
          class="cyc-spark"
          viewBox="0 0 120 24"
          preserveAspectRatio="none"
          role="img"
          :aria-label="`${kpi.label} 近 30 个观测走势`"
        >
          <polyline
            :points="kpi.spark"
            fill="none"
            :stroke="kpi.sparkColor"
            stroke-width="1.4"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        </svg>
        <span v-else class="cyc-kpi-note">{{ kpi.missing ? (kpi.reason ?? "数据缺失") : kpi.source ?? "—" }}</span>
        <RouterLink
          class="cyc-kpi-ev"
          :to="{ path: '/pipeline', query: { code: 'cycle.state.world' } }"
          :title="kpi.tooltip"
        >
          {{ kpi.evidence }} 证据
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtSigned } from "@/composables/useFormat";
import type { KpiView } from "@/utils/cycleFormat";

defineProps<{
  readingsUnavailable: boolean;
  readingsErrorText: string;
  loading: boolean;
  kpis: KpiView[];
}>();

defineEmits<{ (e: "retry"): void }>();
</script>

<style scoped>
/* ── C. 关键读数 ────────────────────────────────────── */
.cyc-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.cyc-kpi-card {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 80px;
  padding: 7px 10px 6px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow);
}
.cyc-kpi-card:hover {
  border-color: var(--border-strong);
}
.cyc-kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.cyc-kpi-label {
  font-size: 10.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-kpi-z {
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--dim);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 4px;
  line-height: 14px;
  white-space: nowrap;
}
.cyc-kpi-z--pos {
  color: var(--up);
  border-color: color-mix(in srgb, var(--up) 32%, transparent);
}
.cyc-kpi-z--neg {
  color: var(--down);
  border-color: color-mix(in srgb, var(--down) 32%, transparent);
}
.cyc-kpi-val {
  display: flex;
  align-items: baseline;
  gap: 3px;
  margin: 1px 0 2px;
  min-height: 26px;
}
.cyc-kpi-val b {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.4px;
  line-height: 1.1;
}
.cyc-kpi-unit {
  font-size: 10px;
  color: var(--muted);
}
.cyc-kpi-miss {
  margin-left: 4px;
  font-size: 8.5px;
  color: var(--warn);
  border: 1px solid color-mix(in srgb, var(--warn) 34%, transparent);
  border-radius: 4px;
  padding: 0 4px;
  line-height: 14px;
}
.cyc-kpi-chg {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 9.5px;
  white-space: nowrap;
}
.cyc-kpi-chg--up {
  color: var(--up);
}
.cyc-kpi-chg--down {
  color: var(--down);
}
.cyc-kpi-chg--flat {
  color: var(--dim);
}
.cyc-kpi-foot {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 6px;
  min-height: 22px;
}
.cyc-spark {
  flex: none;
  width: 116px;
  height: 22px;
  overflow: visible;
}
.cyc-kpi-note {
  font-size: 8.5px;
  color: var(--dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cyc-readings-fallback {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  font-size: 10.5px;
  color: var(--muted);
}
.cyc-readings-fallback-text {
  flex: 1 1 auto;
  min-width: 0;
}
.cyc-kpi-ev {
  flex: none;
  height: 15px;
  padding: 0 5px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--dim);
  font-size: 8px;
  line-height: 13px;
  letter-spacing: 0.2px;
  text-decoration: none;
  white-space: nowrap;
}
.cyc-kpi-ev:hover {
  color: var(--accent);
  border-color: var(--accent-line);
}

@media (max-width: 1023px) {
  .cyc-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 759px) {
  .cyc-kpi-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
