<template>
  <section class="card cyc-compass-card">
    <div class="card-head">
      <span class="card-title">周期罗盘 <span class="cyc-card-sub">四象限 · 相位角</span></span>
      <span class="cyc-card-right">状态 <b class="mono">{{ stateText }}</b></span>
    </div>
    <div class="cyc-compass-body">
      <svg
        class="cyc-compass-svg"
        viewBox="0 0 520 280"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        :aria-label="`周期相位罗盘，当前${quadrantName}`"
      >
        <!-- 四象限环（扇区） -->
        <path
          v-for="quad in quads"
          :key="quad.key"
          :d="quad.path"
          class="cyc-quad"
          :class="`cyc-quad--${quad.key}`"
        />
        <text
          v-for="quad in quads"
          :key="`label-${quad.key}`"
          :x="quad.labelX"
          :y="quad.labelY"
          text-anchor="middle"
          class="cyc-quad-label"
          :class="`cyc-quad-label--${quad.key}`"
        >
          {{ quad.label }}
        </text>

        <!-- 坐标轴文字：上通胀 / 右增长 -->
        <text x="260" y="14" text-anchor="middle" class="cyc-axis-text">通胀 ↑</text>
        <text x="260" y="274" text-anchor="middle" class="cyc-axis-text">通缩 ↓</text>
        <text x="8" y="143" text-anchor="start" class="cyc-axis-text">增长 ↓</text>
        <text x="512" y="143" text-anchor="end" class="cyc-axis-text">增长 ↑</text>

        <!-- 外层置信度圆环 -->
        <circle cx="260" cy="140" :r="R_CONF" class="cyc-conf-bg" />
        <template v-if="confArc">
          <path :d="confArc" class="cyc-conf-arc" />
          <circle :cx="confTip.x" :cy="confTip.y" r="2.6" class="cyc-conf-tip" />
        </template>

        <!-- 指针（楔形，按相位角旋转） -->
        <path v-if="available" :d="needlePath" class="cyc-needle" />
        <text
          v-if="available"
          :x="needleTip.x"
          :y="needleTip.y - 7"
          text-anchor="middle"
          class="cyc-needle-label"
        >
          {{ offsetText }}
        </text>

        <!-- 中心盘 -->
        <circle cx="260" cy="140" r="58" class="cyc-core" />
        <text x="260" y="138" text-anchor="middle" class="cyc-center-title">{{ centerTitle }}</text>
        <text x="260" y="158" text-anchor="middle" class="cyc-center-sub">{{ centerSub }}</text>
        <text x="260" y="174" text-anchor="middle" class="cyc-center-tag">{{ centerTag }}</text>
      </svg>

      <div class="cyc-compass-foot">
        <span v-for="item in LEGEND" :key="item.key" class="cyc-legend-item">
          <span class="cyc-legend-dot" :class="`cyc-legend-dot--${item.key}`"></span>{{ item.label }}
        </span>
        <span class="cyc-spacer"></span>
        <span class="cyc-phase-note">{{ phaseNote }}</span>
        <RouterLink class="cyc-how-link" :to="{ path: '/pipeline', query: { code: 'cycle.state.world' } }">
          如何判定 ›
        </RouterLink>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /** 增长分量 0–100（缺失传 null） */
    growth: number | null;
    /** 通胀分量 0–100（缺失传 null） */
    inflation: number | null;
    /** 短周期状态文案（中心标签 / 卡头右侧） */
    state?: string | null;
    /** 综合置信度 0–100（缺失传 null） */
    confidence?: number | null;
  }>(),
  { state: null, confidence: null },
);

/** 罗盘几何：与设计稿 buildCompass() 的参数保持一致。 */
const CX = 260;
const CY = 140;
/** 四象限环的内外半径 */
const R0 = 60;
const R1 = 112;
/** 置信度圆环半径 */
const R_CONF = 122;
/** 指针尖端半径 */
const R_TIP = 106;

interface QuadDef {
  key: string;
  label: string;
  a0: number;
  a1: number;
  mid: number;
}

/** 角度定义：0° = 正上方（通胀↑），顺时针增长；90° = 右（增长↑）。 */
const QUADS: QuadDef[] = [
  { key: "hot", label: "过热", a0: 3, a1: 87, mid: 45 },
  { key: "recovery", label: "复苏", a0: 93, a1: 177, mid: 135 },
  { key: "recession", label: "衰退", a0: 183, a1: 267, mid: 225 },
  { key: "stagflation", label: "滞胀", a0: 273, a1: 357, mid: 315 },
];

const LEGEND = [
  { key: "recovery", label: "复苏" },
  { key: "hot", label: "过热" },
  { key: "stagflation", label: "滞胀" },
  { key: "recession", label: "衰退" },
] as const;

function polar(radius: number, deg: number): { x: number; y: number } {
  const rad = (deg * Math.PI) / 180;
  return {
    x: round(CX + radius * Math.sin(rad)),
    y: round(CY - radius * Math.cos(rad)),
  };
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

function sectorPath(a0: number, a1: number): string {
  const outer0 = polar(R1, a0);
  const outer1 = polar(R1, a1);
  const inner0 = polar(R0, a0);
  const inner1 = polar(R0, a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return [
    `M ${outer0.x} ${outer0.y}`,
    `A ${R1} ${R1} 0 ${large} 1 ${outer1.x} ${outer1.y}`,
    `L ${inner1.x} ${inner1.y}`,
    `A ${R0} ${R0} 0 ${large} 0 ${inner0.x} ${inner0.y}`,
    "Z",
  ].join(" ");
}

const quads = QUADS.map((quad) => {
  const point = polar(86, quad.mid);
  return {
    ...quad,
    path: sectorPath(quad.a0, quad.a1),
    labelX: point.x,
    labelY: round(point.y + 3.5),
  };
});

function clamp(value: number | null | undefined): number {
  if (value === null || value === undefined || !Number.isFinite(value)) return 50;
  return Math.max(0, Math.min(100, value));
}

const available = computed<boolean>(
  () =>
    props.growth !== null &&
    props.inflation !== null &&
    Number.isFinite(props.growth) &&
    Number.isFinite(props.inflation),
);

/** 相位角：0° 指向通胀↑，90° 指向增长↑，顺时针推进。 */
const angle = computed<number>(() => {
  const growth = clamp(props.growth) - 50;
  const inflation = clamp(props.inflation) - 50;
  if (growth === 0 && inflation === 0) return 0;
  const raw = (Math.atan2(growth, inflation) * 180) / Math.PI;
  return (raw + 360) % 360;
});

const currentQuad = computed<QuadDef>(() => {
  const deg = angle.value;
  return QUADS.find((quad) => deg >= quad.a0 - 3 && deg <= quad.a1 + 3) ?? QUADS[0];
});

const quadrantName = computed<string>(() => (available.value ? currentQuad.value.label : "数据缺失"));

const stateText = computed<string>(() => {
  const text = (props.state ?? "").trim();
  return text || "—";
});

const offset = computed<number>(() => {
  const raw = angle.value - currentQuad.value.mid;
  // 归一到 −180…180，避免跨 0/360 时出现 ±350°
  return Math.round(((raw + 540) % 360) - 180);
});

const offsetText = computed<string>(() => `${offset.value >= 0 ? "+" : ""}${offset.value}°`);

function neighborName(step: number): string {
  const index = QUADS.findIndex((quad) => quad.key === currentQuad.value.key);
  const next = QUADS[(index + step + QUADS.length) % QUADS.length];
  return next?.label ?? "—";
}

const phaseNote = computed<string>(() => {
  if (!available.value) return "相位数据缺失";
  if (offset.value === 0) return `位于${currentQuad.value.label}象限中心`;
  const side = offset.value > 0 ? neighborName(1) : neighborName(-1);
  return `${offsetText.value} 偏${side}`;
});

const confidencePct = computed<number | null>(() => {
  const raw = props.confidence;
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return null;
  return Math.max(0, Math.min(100, Math.round(raw)));
});

const confArc = computed<string | null>(() => {
  const pct = confidencePct.value;
  if (pct === null || pct <= 0) return null;
  const deg = Math.min(359.9, (pct / 100) * 360);
  const start = polar(R_CONF, 0);
  const end = polar(R_CONF, deg);
  return `M ${start.x} ${start.y} A ${R_CONF} ${R_CONF} 0 ${deg > 180 ? 1 : 0} 1 ${end.x} ${end.y}`;
});

const confTip = computed(() => {
  const pct = confidencePct.value ?? 0;
  return polar(R_CONF, Math.min(359.9, (pct / 100) * 360));
});

const needleTip = computed(() => polar(R_TIP, angle.value));

const needlePath = computed<string>(() => {
  const tip = needleTip.value;
  const left = polar(9, angle.value - 90);
  const right = polar(9, angle.value + 90);
  return `M ${tip.x} ${tip.y} L ${left.x} ${left.y} L ${right.x} ${right.y} Z`;
});

const centerTitle = computed<string>(() => (available.value ? currentQuad.value.label : "—"));

const centerSub = computed<string>(() =>
  confidencePct.value === null ? "置信度 —" : `置信度 ${confidencePct.value}%`,
);

const centerTag = computed<string>(() =>
  available.value ? `短周期 · ${stateText.value}` : "相位数据缺失",
);
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
  height: 334px;
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
  overflow: visible;
}

/* 四象限环 */
.cyc-quad {
  fill-opacity: 0.18;
  stroke: var(--bg);
  stroke-width: 1.2;
}
.cyc-quad--hot {
  fill: var(--warn);
}
.cyc-quad--recovery {
  fill: var(--down);
}
.cyc-quad--stagflation {
  fill: var(--up);
}
.cyc-quad--recession {
  fill: var(--accent);
}
.cyc-quad-label {
  font-family: var(--sans);
  font-size: 10px;
  font-weight: 600;
  opacity: 0.78;
}
.cyc-quad-label--hot {
  fill: var(--warn);
}
.cyc-quad-label--recovery {
  fill: var(--down);
}
.cyc-quad-label--stagflation {
  fill: var(--up);
}
.cyc-quad-label--recession {
  fill: var(--accent);
}

/* 坐标轴文字 */
.cyc-axis-text {
  font-family: var(--mono);
  font-size: 9px;
  fill: var(--muted);
  letter-spacing: 0.4px;
}

/* 置信度圆环 */
.cyc-conf-bg {
  fill: none;
  stroke: var(--border);
  stroke-width: 3;
}
.cyc-conf-arc {
  fill: none;
  stroke: var(--accent);
  stroke-width: 3;
  stroke-linecap: round;
}
.cyc-conf-tip {
  fill: var(--accent);
}

/* 指针与中心盘 */
.cyc-needle {
  fill: var(--accent);
  opacity: 0.92;
}
.cyc-needle-label {
  font-family: var(--mono);
  font-size: 9px;
  fill: var(--accent);
}
.cyc-core {
  fill: var(--surface);
  stroke: var(--border-strong);
}
.cyc-center-title {
  font-family: var(--sans);
  font-size: 21px;
  font-weight: 700;
  fill: var(--text);
}
.cyc-center-sub {
  font-family: var(--mono);
  font-size: 10px;
  fill: var(--muted);
}
.cyc-center-tag {
  font-family: var(--sans);
  font-size: 8px;
  fill: var(--dim);
}

/* 底部图例 */
.cyc-compass-foot {
  flex: none;
  display: flex;
  align-items: center;
  gap: 11px;
  flex-wrap: wrap;
  padding: 0 2px 8px;
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
.cyc-legend-dot--hot {
  background: var(--warn);
}
.cyc-legend-dot--recovery {
  background: var(--down);
}
.cyc-legend-dot--stagflation {
  background: var(--up);
}
.cyc-legend-dot--recession {
  background: var(--accent);
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

@media (max-width: 1023px) {
  .cyc-compass-card {
    height: auto;
    min-height: 318px;
  }
}
</style>
