<template>
  <div class="cyc-ov-grid">
    <article class="card cyc-ov-card">
      <div class="cyc-ov-top">
        <span class="cyc-ov-icon"><svg class="ic"><use href="#i-target" /></svg></span>
        <span class="cyc-ov-label">长债务周期</span>
        <span class="badge badge--sm" :class="longToneClass">{{ long.phase }}</span>
      </div>
      <div class="cyc-ov-value">{{ fmtNumber(long.score, 1) }}<small>DMI</small></div>
      <div class="cyc-ov-sub">
        区间 {{ long.bandText }} · 位置上沿 {{ long.positionPct === null ? "—" : `${long.positionPct}%` }} · 置信
        {{ fmtNumber(long.confidence, 2) }}
      </div>
    </article>
    <article class="card cyc-ov-card">
      <div class="cyc-ov-top">
        <span class="cyc-ov-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
        <span class="cyc-ov-label">短债务周期</span>
        <span class="badge badge--sm" :class="shortToneClass">{{ short.state }}</span>
      </div>
      <div class="cyc-ov-value">
        增长 {{ fmtNumber(short.variables.growth, 0) }}<small>通胀 {{ fmtNumber(short.variables.inflation, 0) }}</small>
      </div>
      <div class="cyc-ov-sub">
        流动性 {{ fmtNumber(short.variables.liq, 0) }} · 12 月增长变化
        {{ fmtSigned(short.variables.d12, 1) }}<template v-if="short.hysteresis_held"> · 滞回保持</template>
      </div>
    </article>
    <article class="card cyc-ov-card">
      <div class="cyc-ov-top">
        <span class="cyc-ov-icon"><svg class="ic"><use href="#i-rates" /></svg></span>
        <span class="cyc-ov-label">债务可持续性</span>
        <span class="badge badge--sm badge--warn">{{ sustainability?.mode ?? "—" }}</span>
      </div>
      <div class="cyc-ov-value">{{ fmtNumber(sustainability?.interest_to_revenue, 1) }}<small>利息 / 收入 %</small></div>
      <div class="cyc-ov-sub">
        r−g {{ fmtSigned(sustainability?.r_minus_g, 1) }}pp · 赤字
        {{ fmtNumber(sustainability?.deficit_to_gdp, 1) }}% GDP
      </div>
    </article>
    <article class="card cyc-ov-card">
      <div class="cyc-ov-top">
        <span class="cyc-ov-icon"><svg class="ic"><use href="#i-layers" /></svg></span>
        <span class="cyc-ov-label">历史类比（样本内）</span>
        <span class="badge badge--sm">{{ analogs?.n ?? 0 }} 个</span>
      </div>
      <div class="cyc-ov-value">
        {{ topAnalogs[0] ? ratioText(topAnalogs[0].similarity) : "—" }}<small>最相似</small>
      </div>
      <div class="cyc-ov-sub">
        {{ topAnalogs[0]?.month ?? "—" }} · 相似≠相同，需人工核对时代背景
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import { fmtNumber, fmtSigned } from "@/composables/useFormat";
import type { CycleAnalog, CycleAnalogs, CycleSustainability } from "@/api/types";
import type { RawOf, SafeLongCycle, SafeShortCycle } from "@/utils/cycleNormalize";
import { ratioText } from "@/utils/cycleFormat";

defineProps<{
  long: SafeLongCycle;
  short: SafeShortCycle;
  sustainability: CycleSustainability | null;
  analogs: RawOf<CycleAnalogs>;
  topAnalogs: CycleAnalog[];
  longToneClass: string;
  shortToneClass: string;
}>();
</script>

<style scoped>
/* ── F. 保留区块 ────────────────────────────────────── */
.cyc-ov-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.cyc-ov-card {
  padding: 9px 11px 8px;
  min-height: 84px;
}
.cyc-ov-top {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cyc-ov-icon {
  display: inline-flex;
  color: var(--dim);
  flex: none;
}
.cyc-ov-icon svg {
  width: 14px;
  height: 14px;
}
.cyc-ov-label {
  font-size: 10.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
}
.cyc-ov-value {
  margin-top: 5px;
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  line-height: 1.1;
}
.cyc-ov-value small {
  margin-left: 4px;
  font-family: var(--sans);
  font-size: 9.5px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-ov-sub {
  margin-top: 4px;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.45;
}
@media (max-width: 1279px) {
  .cyc-ov-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 759px) {
  .cyc-ov-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
