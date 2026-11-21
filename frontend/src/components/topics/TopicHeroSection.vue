<template>
  <div class="topic-hero-grid">
    <section class="card topic-score-card">
      <div class="card-head">
        <span class="card-title">综合评分</span>
        <span class="badge badge--sm" :class="labelClass">{{ payload.label }}</span>
        <div class="card-actions"><span class="card-sub">−100 强空 ~ +100 强多</span></div>
      </div>
      <div class="card-body topic-score-body">
        <div class="topic-score-main">
          <div class="topic-gauge">
            <svg class="topic-gauge-svg" viewBox="0 0 220 130" role="img" :aria-label="`综合评分 ${scoreText}，${payload.label}`">
              <path class="topic-gauge-track" d="M 25 115 A 85 85 0 0 1 195 115" pathLength="100" />
              <path
                class="topic-gauge-fill"
                :class="trend"
                d="M 25 115 A 85 85 0 0 1 195 115"
                pathLength="100"
                stroke-dasharray="100"
                :stroke-dashoffset="offset"
              />
              <line class="topic-gauge-tick" x1="25" y1="115" x2="20" y2="122" />
              <line class="topic-gauge-tick" x1="195" y1="115" x2="200" y2="122" />
              <line class="topic-gauge-tick topic-gauge-zero" x1="110" y1="26" x2="110" y2="38" />
            </svg>
            <div class="topic-gauge-center">
              <span class="topic-gauge-score" :class="trend">{{ scoreText }}</span>
              <span class="topic-gauge-unit">/ 100</span>
            </div>
          </div>
          <div class="topic-gauge-scale"><span>−100 强空</span><span>0</span><span>+100 强多</span></div>
        </div>
        <div class="topic-score-stats">
          <div class="topic-stat-row"><span>综合判断</span><b :class="trend">{{ payload.label }}</b></div>
          <div class="topic-stat-row"><span>覆盖率</span><b>{{ coverageText }}</b></div>
          <div class="topic-cov-bar"><i :style="{ width: `${payload.coverage}%` }"></i></div>
          <div class="topic-stat-row">
            <span>可用权重</span><b>{{ fmtNumber(payload.available_weight, 0) }} / {{ fmtNumber(payload.total_weight, 0) }}</b>
          </div>
          <div class="topic-stat-row"><span>评分生成</span><b class="muted">{{ generatedLabel }}</b></div>
        </div>
      </div>
      <div class="card-foot topic-badges">
        <span v-for="badge in payload.badges" :key="badge.label" class="badge badge--sm" :class="badgeClass(badge.tone)">
          {{ badge.label }}
        </span>
      </div>
    </section>

    <section class="card topic-drivers-card">
      <div class="card-head">
        <span class="card-title">结论与关键驱动</span>
        <span class="badge badge--sm">按 |贡献| 前 {{ payload.drivers.length }}</span>
        <div class="card-actions"><span class="card-sub">贡献 = 权重 × 标准化得分 × 方向</span></div>
      </div>
      <div class="card-body topic-drivers-body">
        <p class="topic-conclusion">{{ payload.conclusion || "暂无结论。" }}</p>
        <div class="topic-driver-list">
          <div v-for="driver in payload.drivers" :key="driver.code" class="topic-driver-row">
            <span class="topic-driver-name" :title="`${driver.name}（${driver.code}）`">{{ driver.name }}</span>
            <span class="topic-driver-value">{{ driverValue(driver) }}</span>
            <span class="topic-driver-contrib" :class="trendClass(driver.contribution)">
              {{ fmtSigned(driver.contribution, 2) }}
            </span>
            <span class="badge badge--sm" :class="signalClass(driver.signal)">{{ signalLabel(driver.signal) }}</span>
          </div>
          <EmptyState v-if="!payload.drivers.length" text="暂无可用驱动" hint="等待采集任务写入数据。" />
        </div>
        <div v-if="verdict?.action" class="topic-verdict">
          <div v-if="verdict.action.one_line" class="topic-verdict-line">{{ verdict.action.one_line }}</div>
          <div class="topic-verdict-actions">
            <span v-if="verdict.action.add_condition">加仓：{{ verdict.action.add_condition }}</span>
            <span v-if="verdict.action.reduce_condition">减仓：{{ verdict.action.reduce_condition }}</span>
          </div>
        </div>
        <ul v-if="verdict?.risk?.length" class="topic-risk">
          <li v-for="item in verdict.risk" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div class="card-foot">
        <span>贡献正值为利多、负值为利空；未采集项不计入评分，覆盖率 {{ coverageText }}。</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { LuoyangVerdict, TopicDriver, TopicHero } from "@/api/types";
import { fmtNumber, fmtSigned, trendClass } from "@/composables/useFormat";
import { signalClass, signalLabel } from "@/utils/topicFormat";

const props = defineProps<{
  data: unknown;
  generatedLabel: string;
  verdict?: LuoyangVerdict | null;
}>();

const payload = computed<TopicHero>(() => {
  const value = (props.data ?? {}) as Partial<TopicHero>;
  return {
    score: value.score ?? null,
    label: value.label ?? "数据不足",
    coverage: Number(value.coverage ?? 0),
    available_weight: Number(value.available_weight ?? 0),
    total_weight: Number(value.total_weight ?? 0),
    conclusion: value.conclusion ?? "",
    badges: value.badges ?? [],
    drivers: value.drivers ?? [],
  };
});

const score = computed(() => payload.value.score);
const scoreText = computed(() => (score.value == null ? "—" : fmtSigned(score.value, 1)));
const trend = computed(() => trendClass(score.value));
const offset = computed(() => {
  const value = score.value ?? 0;
  return String(100 - (Math.max(-100, Math.min(100, value)) + 100) / 2);
});
const coverageText = computed(() => `${fmtNumber(payload.value.coverage, 1)}%`);
const labelClass = computed(() => {
  if ((score.value ?? 0) >= 18) return "badge--up";
  if ((score.value ?? 0) <= -18) return "badge--down";
  return "";
});

function badgeClass(tone?: string): string {
  if (tone === "up") return "badge--up";
  if (tone === "down") return "badge--down";
  if (tone === "warn") return "badge--warn";
  return "";
}

function driverValue(driver: TopicDriver): string {
  if (driver.value == null || !Number.isFinite(driver.value)) return "—";
  return `${fmtNumber(driver.value, 2)}${driver.unit ? ` ${driver.unit}` : ""}`;
}
</script>

<style scoped>
.topic-hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.96fr) minmax(0, 1.04fr);
  gap: 10px;
  align-items: stretch;
}
.topic-score-card,
.topic-drivers-card {
  display: flex;
  flex-direction: column;
}
.topic-score-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1 1 auto;
}
.topic-score-main {
  display: grid;
  grid-template-columns: 216px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  flex: 1 1 auto;
}
.topic-gauge {
  position: relative;
}
.topic-gauge-svg {
  display: block;
  width: 100%;
  height: auto;
}
.topic-gauge-track,
.topic-gauge-fill {
  fill: none;
  stroke-width: 9;
  stroke-linecap: round;
}
.topic-gauge-track {
  stroke: var(--surface-3);
}
.topic-gauge-fill {
  transition: stroke-dashoffset 0.4s ease;
}
.topic-gauge-fill.up {
  stroke: var(--up-color);
}
.topic-gauge-fill.down {
  stroke: var(--down-color);
}
.topic-gauge-fill.flat {
  stroke: var(--muted);
}
.topic-gauge-tick {
  stroke: var(--border-strong, var(--border));
  stroke-width: 1.2;
}
.topic-gauge-zero {
  stroke: var(--muted);
}
.topic-gauge-center {
  position: absolute;
  inset: auto 0 12px;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 3px;
}
.topic-gauge-score {
  font-size: 27px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.topic-gauge-score.up {
  color: var(--up-color);
}
.topic-gauge-score.down {
  color: var(--down-color);
}
.topic-gauge-unit {
  font-size: 10px;
  color: var(--muted);
}
.topic-gauge-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
  font-size: 9px;
  color: var(--muted);
}
.topic-score-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.topic-stat-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 10.5px;
  color: var(--muted);
}
.topic-stat-row b {
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.topic-stat-row b.up {
  color: var(--up-color);
}
.topic-stat-row b.down {
  color: var(--down-color);
}
.topic-cov-bar {
  height: 5px;
  border-radius: 3px;
  background: var(--surface-3);
  overflow: hidden;
}
.topic-cov-bar i {
  display: block;
  height: 100%;
  background: var(--accent);
}
.topic-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.topic-drivers-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1 1 auto;
}
.topic-conclusion {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.65;
}
.topic-driver-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.topic-driver-row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 0.9fr) auto auto;
  gap: 7px;
  align-items: center;
  font-size: 10.5px;
  padding: 3px 0;
  border-bottom: 1px dashed var(--border);
}
.topic-driver-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topic-driver-value {
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topic-driver-contrib {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.topic-driver-contrib.up {
  color: var(--up-color);
}
.topic-driver-contrib.down {
  color: var(--down-color);
}
.topic-verdict {
  margin-top: 4px;
  padding: 7px 9px;
  border: 1px solid var(--accent-line);
  border-radius: 8px;
  background: var(--accent-weak);
  font-size: 10.5px;
  line-height: 1.6;
}
.topic-verdict-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 3px;
  color: var(--muted);
}
.topic-risk {
  margin: 0;
  padding-left: 16px;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.55;
}
@media (max-width: 1360px) {
  .topic-hero-grid {
    grid-template-columns: 1fr;
  }
}
</style>
