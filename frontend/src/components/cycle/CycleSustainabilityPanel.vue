<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">债务可持续性</span>
      <span class="cyc-card-sub">r−g / 利息负担 / 赤字三模式判别 · 证据 {{ sustainability?.evidence ?? "—" }}</span>
    </div>
    <div class="card-body">
      <EmptyState
        v-if="!sustainability"
        text="债务可持续性数据缺失"
        hint="本次运行未返回 sustainability 段；模式判别与阈值读数暂不可用。"
      />
      <template v-else>
      <div class="cyc-sustain-head">
        <span class="badge badge--sm badge--warn">{{ sustainability?.mode ?? "—" }}</span>
        <span class="mono cyc-sustain-risk">{{ sustainability?.risk ?? "" }}</span>
      </div>
      <p class="cyc-layer-meaning">{{ sustainability?.explanation ?? "" }}</p>
      <div class="cyc-metric-grid">
        <div class="cyc-metric">
          <span class="cyc-metric-label">r−g</span>
          <b class="mono">{{ fmtSigned(sustainability?.r_minus_g, 1) }}<small>pp</small></b>
        </div>
        <div class="cyc-metric">
          <span class="cyc-metric-label">利息 / 财政收入</span>
          <b class="mono">{{ fmtNumber(sustainability?.interest_to_revenue, 1) }}<small>%</small></b>
        </div>
        <div class="cyc-metric">
          <span class="cyc-metric-label">赤字 / GDP</span>
          <b class="mono">{{ fmtNumber(sustainability?.deficit_to_gdp, 1) }}<small>%</small></b>
        </div>
        <div class="cyc-metric">
          <span class="cyc-metric-label">债务 / GDP</span>
          <b class="mono">{{ fmtNumber(sustainability?.debt_to_gdp, 0) }}<small>%</small></b>
        </div>
      </div>
      <p class="cyc-layer-meta">
        关注阈值：利息/收入 ≥{{ thresholds.interest_watch ?? "—" }}%（警戒）、≥{{
          thresholds.interest_alarm ?? "—"
        }}%（警报）；赤字/GDP ≥{{ thresholds.deficit_watch ?? "—" }}%。
      </p>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtNumber, fmtSigned } from "@/composables/useFormat";
import type { CycleSustainability } from "@/api/types";

defineProps<{
  sustainability: CycleSustainability | null;
  thresholds: Partial<CycleSustainability["thresholds"]>;
}>();
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-sustain-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.cyc-sustain-risk {
  font-size: 9.5px;
  color: var(--muted);
}
.cyc-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}
.cyc-metric {
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
}
.cyc-metric-label {
  display: block;
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-metric b {
  display: block;
  margin-top: 3px;
  font-size: 14px;
  color: var(--text);
}
.cyc-metric b small {
  margin-left: 2px;
  font-size: 8.5px;
  color: var(--dim);
}
.cyc-layer-meaning {
  margin: 5px 0 0;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.55;
}
.cyc-layer-meta {
  margin: 3px 0 0;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
}
@media (max-width: 759px) {
  .cyc-metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
