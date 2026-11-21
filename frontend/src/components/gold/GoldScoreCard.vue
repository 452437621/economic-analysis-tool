<template>
  <!-- 评分 + 结论 -->
  <section class="card score-card">
    <div class="card-head">
      <span class="card-title">综合评分</span>
      <span class="badge badge--sm" :class="scoreBadgeClass">{{ scoreLabel }}</span>
      <div class="card-actions"><span class="card-sub">−100 强空 ~ +100 强多</span></div>
    </div>
    <div class="card-body score-body">
      <div class="score-main">
        <div class="gauge-col">
          <div class="gauge">
            <svg class="gauge-svg" viewBox="0 0 220 130" role="img" :aria-label="`综合评分 ${fmtSigned(scoreValue, 1)}，${scoreLabel}`">
              <path class="gauge-track" d="M 25 115 A 85 85 0 0 1 195 115" pathLength="100" />
              <path
                class="gauge-fill"
                :class="scoreTrend"
                d="M 25 115 A 85 85 0 0 1 195 115"
                pathLength="100"
                stroke-dasharray="100"
                :stroke-dashoffset="gaugeOffset"
              />
              <line class="gauge-tick" x1="25" y1="115" x2="20" y2="122" />
              <line class="gauge-tick" x1="195" y1="115" x2="200" y2="122" />
              <line class="gauge-tick gauge-zero" x1="110" y1="26" x2="110" y2="38" />
            </svg>
            <div class="gauge-center">
              <span class="gauge-score" :class="scoreTrend">{{ fmtSigned(scoreValue, 1) }}</span>
              <span class="gauge-unit">/ 100</span>
            </div>
          </div>
          <div class="gauge-scale"><span>−100 强空</span><span>0</span><span>+100 强多</span></div>
        </div>
        <div class="score-stats">
          <div class="stat-row"><span>综合判断</span><b :class="scoreTrend">{{ scoreLabel }}</b></div>
          <div class="stat-row"><span>覆盖率</span><b>{{ fmtNumber(coverage, 1) }}%</b></div>
          <div class="cov-bar"><i :style="{ width: `${coveragePct}%` }"></i></div>
          <div class="stat-row"><span>可用权重</span><b>{{ fmtNumber(availableWeight, 0) }} / {{ fmtNumber(totalWeight, 0) }}</b></div>
          <div class="stat-row"><span>可用因子</span><b>{{ availableFactorCount }} / {{ factorsCount }}</b></div>
          <div class="stat-row"><span>评分生成</span><b class="stat-time">{{ generatedLabel }}</b></div>
        </div>
      </div>
      <div class="method-brief">
        <span class="mb-label">方法论摘要</span>
        <p>{{ methodologyBrief }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fmtNumber, fmtSigned } from "@/composables/useFormat";

defineProps<{
  scoreValue: number;
  scoreLabel: string;
  scoreBadgeClass: string;
  scoreTrend: "up" | "down" | "flat";
  gaugeOffset: string;
  coverage: number;
  coveragePct: number;
  availableWeight: number;
  totalWeight: number;
  availableFactorCount: number;
  factorsCount: number;
  generatedLabel: string;
  methodologyBrief: string;
}>();
</script>

<style scoped>
/* ---------- 顶部评分区 ---------- */
.score-card {
  display: flex;
  flex-direction: column;
}
.score-body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 10px;
}
.score-main {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: 216px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}
.gauge-col {
  min-width: 0;
}
.gauge {
  position: relative;
  width: 100%;
}
.gauge-svg {
  display: block;
  width: 100%;
  height: auto;
}
.gauge-track,
.gauge-fill {
  fill: none;
  stroke-width: 9;
  stroke-linecap: round;
}
.gauge-track {
  stroke: var(--surface-3);
}
.gauge-fill {
  transition: stroke-dashoffset 0.4s ease;
}
.gauge-fill.up {
  stroke: var(--up-color);
}
.gauge-fill.down {
  stroke: var(--down-color);
}
.gauge-fill.flat {
  stroke: var(--muted);
}
.gauge-tick {
  stroke: var(--border-strong);
  stroke-width: 1.4;
  stroke-linecap: round;
}
.gauge-zero {
  stroke: var(--dim);
}
.gauge-center {
  position: absolute;
  right: 0;
  bottom: 16px;
  left: 0;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
}
.gauge-score {
  font-family: var(--mono);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -1px;
  line-height: 1;
}
.gauge-score.up {
  color: var(--up-color);
}
.gauge-score.down {
  color: var(--down-color);
}
.gauge-score.flat {
  color: var(--text);
}
.gauge-unit {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
.gauge-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
  font-size: 9px;
  color: var(--dim);
}
.score-stats {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.stat-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 10.5px;
  color: var(--muted);
}
.stat-row > b {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  text-align: right;
}
.stat-row > b.up {
  color: var(--up-color);
}
.stat-row > b.down {
  color: var(--down-color);
}
.stat-row > b.flat {
  color: var(--muted);
}
.stat-time {
  font-size: 9.5px !important;
  color: var(--muted) !important;
}
.cov-bar {
  height: 4px;
  margin: 1px 0 3px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.cov-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}
.method-brief {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
.mb-label {
  font-size: 9.5px;
  letter-spacing: 0.4px;
  color: var(--dim);
}
.method-brief p {
  margin-top: 3px;
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--muted);
}
</style>
