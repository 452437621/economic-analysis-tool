<template>
  <section class="card cyc-compass-card">
    <div class="card-head">
      <span class="card-title">周期罗盘 <span class="cyc-card-sub">四象限 · 相位角</span></span>
      <span class="cyc-card-right">状态 <b class="mono">{{ statusLabel || "—" }}</b></span>
    </div>
    <div class="cyc-compass-body">
      <svg
        class="cyc-compass-svg"
        viewBox="0 0 520 280"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        :aria-label="`周期相位罗盘，当前${quadrant}`"
      >
        <!-- 四象限底色 -->
        <rect x="260" y="20" width="240" height="120" class="cyc-quad cyc-quad--hot" />
        <rect x="20" y="20" width="240" height="120" class="cyc-quad cyc-quad--stag" />
        <rect x="20" y="140" width="240" height="120" class="cyc-quad cyc-quad--recession" />
        <rect x="260" y="140" width="240" height="120" class="cyc-quad cyc-quad--recovery" />

        <!-- 象限名 -->
        <text x="380" y="74" class="cyc-quad-label" fill="#F5A524" text-anchor="middle">过热</text>
        <text x="140" y="74" class="cyc-quad-label" fill="#F0544F" text-anchor="middle">滞胀</text>
        <text x="140" y="214" class="cyc-quad-label" fill="#4CC2FF" text-anchor="middle">衰退</text>
        <text x="380" y="214" class="cyc-quad-label" fill="#2FBF71" text-anchor="middle">复苏</text>

        <!-- 坐标轴 -->
        <line x1="20" y1="140" x2="500" y2="140" class="cyc-axis" />
        <line x1="260" y1="20" x2="260" y2="260" class="cyc-axis" />
        <line x1="20" y1="140" x2="500" y2="140" class="cyc-axis-tick" stroke-dasharray="2 4" />

        <!-- 刻度 -->
        <text x="20" y="155" class="cyc-axis-label" text-anchor="start">0</text>
        <text x="500" y="155" class="cyc-axis-label" text-anchor="end">100</text>
        <text x="252" y="32" class="cyc-axis-label" text-anchor="end">通胀 100</text>
        <text x="252" y="256" class="cyc-axis-label" text-anchor="end">0</text>
        <text x="496" y="132" class="cyc-axis-label" text-anchor="end">增长 →</text>
        <text x="268" y="24" class="cyc-axis-label" text-anchor="start">↑ 通胀</text>

        <!-- 当前相位指针 -->
        <template v-if="available">
          <line x1="260" y1="140" :x2="point.x" :y2="point.y" class="cyc-pointer" />
          <line x1="260" y1="140" :x2="point.x" y2="140" class="cyc-guide" />
          <line :x1="point.x" y1="140" :x2="point.x" :y2="point.y" class="cyc-guide" />
          <circle :cx="point.x" :cy="point.y" r="7" class="cyc-point-halo" />
          <circle :cx="point.x" :cy="point.y" r="4.2" class="cyc-point" />
          <text :x="point.x" :y="point.y - 12" class="cyc-point-label" text-anchor="middle">当前</text>
        </template>

        <!-- 中心 -->
        <circle cx="260" cy="140" r="2.6" class="cyc-center" />
      </svg>
      <div class="cyc-compass-foot">
        <span v-for="item in LEGEND" :key="item.label" class="cyc-legend-item">
          <span class="cyc-legend-dot" :style="{ background: item.color }"></span>{{ item.label }}
        </span>
        <span class="cyc-spacer"></span>
        <span class="cyc-phase-note">{{ phaseNote }}</span>
        <RouterLink class="cyc-how-link" to="/analysis">如何判定 ›</RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    growth: number | null;
    inflation: number | null;
    statusLabel?: string | null;
  }>(),
  { statusLabel: null },
);

const LEGEND = [
  { label: "复苏", color: "#2FBF71" },
  { label: "过热", color: "#F5A524" },
  { label: "滞胀", color: "#F0544F" },
  { label: "衰退", color: "#4CC2FF" },
] as const;

const available = computed<boolean>(
  () => props.growth !== null && props.inflation !== null && Number.isFinite(props.growth) && Number.isFinite(props.inflation),
);

const growthCentered = computed<number>(() => clamp(props.growth) - 50);
const inflationCentered = computed<number>(() => clamp(props.inflation) - 50);

/** 相位角：以增长为横轴、通胀为纵轴；角度 0° 指向过热方向，正角度偏过热 */
const angle = computed<number>(() => Math.round((Math.atan2(inflationCentered.value, growthCentered.value) * 180) / Math.PI));

const quadrant = computed<string>(() => {
  const growth = growthCentered.value;
  const inflation = inflationCentered.value;
  if (growth >= 0 && inflation >= 0) return "过热";
  if (growth < 0 && inflation >= 0) return "滞胀";
  if (growth < 0 && inflation < 0) return "衰退";
  return "复苏";
});

const phaseNote = computed<string>(() => {
  if (!available.value) return "相位数据缺失";
  return `${angle.value > 0 ? "+" : ""}${angle.value}° 偏${quadrant.value}`;
});

const point = computed<{ x: number; y: number }>(() => ({
  x: 260 + (growthCentered.value / 50) * 220,
  y: 140 - (inflationCentered.value / 50) * 110,
}));

function clamp(value: number | null): number {
  if (value === null || !Number.isFinite(value)) return 50;
  return Math.max(0, Math.min(100, value));
}
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
  margin-left: 4px;
}
.cyc-card-right {
  margin-left: auto;
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}
.cyc-card-right b {
  color: var(--accent);
}
.cyc-compass-card {
  display: flex;
  flex-direction: column;
  min-height: 334px;
  overflow: hidden;
}
.cyc-compass-body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 0 12px;
  display: flex;
  flex-direction: column;
}
.cyc-compass-svg {
  width: 100%;
  flex: 1 1 auto;
  min-height: 0;
  max-height: 300px;
}
.cyc-quad {
  stroke-width: 1;
  fill-opacity: 0.1;
  stroke-opacity: 0.32;
}
.cyc-quad--hot {
  fill: #f5a524;
  stroke: #f5a524;
}
.cyc-quad--stag {
  fill: #f0544f;
  stroke: #f0544f;
}
.cyc-quad--recession {
  fill: #4cc2ff;
  stroke: #4cc2ff;
}
.cyc-quad--recovery {
  fill: #2fbf71;
  stroke: #2fbf71;
}
.cyc-quad-label {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.72;
  font-family: var(--sans);
}
.cyc-axis {
  stroke: var(--border-strong);
  stroke-width: 1;
}
.cyc-axis-tick {
  stroke: var(--border);
  stroke-width: 1;
}
.cyc-axis-label {
  font-size: 8px;
  fill: var(--dim);
  font-family: var(--mono);
}
.cyc-pointer {
  stroke: var(--accent);
  stroke-width: 2;
  stroke-dasharray: 4 3;
}
.cyc-guide {
  stroke: var(--accent-line);
  stroke-width: 1;
  stroke-dasharray: 2 3;
}
.cyc-point-halo {
  fill: var(--accent);
  opacity: 0.22;
}
.cyc-point {
  fill: var(--accent);
  stroke: var(--surface);
  stroke-width: 1.4;
}
.cyc-point-label {
  font-size: 8.5px;
  fill: var(--muted);
  font-family: var(--mono);
}
.cyc-center {
  fill: var(--dim);
}
.cyc-compass-foot {
  flex: none;
  display: flex;
  align-items: center;
  gap: 11px;
  flex-wrap: wrap;
  padding: 4px 2px 8px;
  font-size: 9.5px;
  color: var(--dim);
}
.cyc-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.cyc-legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 2px;
  flex: none;
}
.cyc-spacer {
  flex: 1 1 auto;
}
.cyc-phase-note {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 9px;
  white-space: nowrap;
}
.cyc-how-link {
  color: var(--accent);
  font-size: 9.5px;
  text-decoration: none;
  white-space: nowrap;
}
.cyc-how-link:hover {
  text-decoration: underline;
}
</style>
