<template>
  <div class="cyc-retain-grid">
    <section class="card">
      <div class="card-head">
        <span class="card-title">六分量罗盘</span>
        <span class="cyc-card-sub">0–100 归一：越高代表压力/强度越大</span>
        <div class="card-actions">
          <span class="cyc-card-sub">{{ fmtInt(indicatorsCount) }} 个指标参与</span>
        </div>
      </div>
      <div class="card-body cyc-six-body">
        <svg class="cyc-six-svg" viewBox="0 0 260 260" role="img" aria-label="六分量罗盘">
          <circle v-for="ring in rings" :key="ring" cx="130" cy="130" :r="ring" class="cyc-six-ring" />
          <line
            v-for="axis in axes"
            :key="axis.key"
            x1="130"
            y1="130"
            :x2="axis.tipX"
            :y2="axis.tipY"
            class="cyc-six-axis"
          />
          <polygon :points="polygon" class="cyc-six-shape" />
          <circle
            v-for="axis in axes"
            :key="`dot-${axis.key}`"
            :cx="axis.pointX"
            :cy="axis.pointY"
            r="2.6"
            class="cyc-six-dot"
          />
          <text
            v-for="axis in axes"
            :key="`label-${axis.key}`"
            :x="axis.labelX"
            :y="axis.labelY"
            :text-anchor="axis.anchor"
            class="cyc-six-label"
          >
            {{ axis.label }}
          </text>
          <text x="130" y="126" text-anchor="middle" class="cyc-six-center">{{ long.phase }}</text>
          <text x="130" y="142" text-anchor="middle" class="cyc-six-center-sub">DMI {{ fmtNumber(long.score, 1) }}</text>
        </svg>
        <ul class="cyc-six-legend">
          <li v-for="axis in axes" :key="`legend-${axis.key}`" class="cyc-six-legend-row">
            <span class="cyc-six-legend-name">{{ axis.label }}</span>
            <span class="cyc-six-legend-bar"><i :style="{ width: `${Math.max(2, Math.min(100, axis.value))}%` }"></i></span>
            <b class="mono">{{ fmtNumber(axis.value, 1) }}</b>
            <em class="mono">{{ fmtNumber(axis.confidence, 2) }}</em>
          </li>
        </ul>
      </div>
      <div class="card-foot">
        <span>压力类：DMI / ICI / ECI 越高，债务、内部秩序、外部秩序越紧张。</span>
        <span class="mono">DMI {{ fmtNumber(long.score, 1) }} · 滞回 {{ long.hysteresis_held ? "保持" : "无" }}</span>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <span class="card-title">五层周期</span>
        <span class="cyc-card-sub">嵌套定位 · 每层给出当前状态与含义</span>
      </div>
      <div class="card-body cyc-layer-list">
        <div class="cyc-layer-row">
          <div class="cyc-layer-head">
            <span class="cyc-layer-name">长债务周期</span>
            <span class="badge badge--sm" :class="longToneClass">{{ long.phase }}</span>
            <span class="cyc-layer-val mono">{{ fmtNumber(long.score, 1) }}</span>
          </div>
          <div class="cyc-bar">
            <i :style="{ width: `${barWidth(long.position === null ? null : long.position * 100)}%` }"></i>
          </div>
          <p class="cyc-layer-meaning">{{ long.meaning }}</p>
          <p class="cyc-layer-meta">下一阶段：{{ long.next_phase ?? "—" }} · {{ long.exit_condition }}</p>
        </div>
        <div class="cyc-layer-row">
          <div class="cyc-layer-head">
            <span class="cyc-layer-name">短债务周期</span>
            <span class="badge badge--sm" :class="shortToneClass">{{ short.state }}</span>
            <span v-if="short.hysteresis_held" class="badge badge--sm badge--warn">二次确认中</span>
            <span class="cyc-layer-val mono">{{ fmtNumber(short.confidence, 2) }}</span>
          </div>
          <p class="cyc-layer-meaning">{{ short.meaning }}</p>
          <p class="cyc-layer-meta">
            原始命中：{{ short.raw_state }} · 增长 {{ fmtNumber(short.variables.growth, 1) }} / 通胀
            {{ fmtNumber(short.variables.inflation, 1) }}
          </p>
        </div>
        <div class="cyc-layer-row">
          <div class="cyc-layer-head">
            <span class="cyc-layer-name">库存周期</span>
            <span class="badge badge--sm">{{ inventory.state }}</span>
            <span v-if="inventory.degraded" class="badge badge--sm badge--warn">代理口径</span>
            <span class="cyc-layer-val mono">{{ fmtNumber(inventory.confidence, 2) }}</span>
          </div>
          <p class="cyc-layer-meaning">{{ inventory.meaning ?? "—" }}</p>
          <p class="cyc-layer-meta">{{ inventory.degrade_reason ?? "使用库存与价格动量的合成口径。" }}</p>
        </div>
        <div class="cyc-layer-row">
          <div class="cyc-layer-head">
            <span class="cyc-layer-name">信用 / 流动性</span>
            <span class="badge badge--sm" :class="liquidityToneClass">{{ liq.state }}</span>
            <span class="cyc-layer-val mono">{{ fmtNumber(liq.score, 1) }}</span>
          </div>
          <p class="cyc-layer-meaning">{{ liq.meaning }}</p>
          <p class="cyc-layer-meta">证据 {{ liq.evidence }} · 置信 {{ fmtNumber(liq.confidence, 2) }}</p>
        </div>
        <div class="cyc-layer-row">
          <div class="cyc-layer-head">
            <span class="cyc-layer-name">政治 / 事件窗口</span>
            <span class="badge badge--sm" :class="political.window === '高不确定性窗口' ? 'badge--warn' : ''">
              {{ political.window }}
            </span>
            <span class="cyc-layer-val mono">{{ political.days_to_nearest ?? "—" }}<small>天</small></span>
          </div>
          <p class="cyc-layer-meaning">{{ political.nearest?.name ?? "无临近事件" }}</p>
          <p class="cyc-layer-meta">
            {{
              political.nearest
                ? `${political.nearest.date} · ${political.nearest.note}`
                : "政治日历为空，请检查 config/cycle.yaml。"
            }}
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { fmtInt, fmtNumber } from "@/composables/useFormat";
import type { SafeInventory, SafeLiquidity, SafeLongCycle, SafePolitical, SafeShortCycle } from "@/utils/cycleNormalize";
import { barWidth } from "@/utils/cycleFormat";

interface Axis {
  key: string;
  label: string;
  value: number;
  confidence: number;
  tipX: number;
  tipY: number;
  pointX: number;
  pointY: number;
  labelX: number;
  labelY: number;
  anchor: string;
}

defineProps<{
  long: SafeLongCycle;
  short: SafeShortCycle;
  liq: SafeLiquidity;
  inventory: SafeInventory;
  political: SafePolitical;
  indicatorsCount: number;
  rings: number[];
  axes: Axis[];
  polygon: string;
  longToneClass: string;
  shortToneClass: string;
  liquidityToneClass: string;
}>();
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-retain-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
}
.cyc-six-body {
  display: grid;
  grid-template-columns: minmax(0, 220px) minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}
.cyc-six-svg {
  width: 100%;
  max-height: 240px;
}
.cyc-six-ring {
  fill: none;
  stroke: color-mix(in srgb, var(--muted) 18%, transparent);
  stroke-dasharray: 2 3;
}
.cyc-six-axis {
  stroke: color-mix(in srgb, var(--muted) 22%, transparent);
}
.cyc-six-shape {
  fill: color-mix(in srgb, var(--accent) 20%, transparent);
  stroke: var(--accent);
  stroke-width: 1.4;
}
.cyc-six-dot {
  fill: var(--accent);
}
.cyc-six-label {
  font-size: 8.5px;
  fill: var(--muted);
  font-family: var(--sans);
}
.cyc-six-center {
  font-size: 11px;
  fill: var(--text);
  font-weight: 600;
}
.cyc-six-center-sub {
  font-size: 8.5px;
  fill: var(--dim);
  font-family: var(--mono);
}
.cyc-six-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.cyc-six-legend-row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) 34px 32px;
  gap: 6px;
  align-items: center;
  font-size: 9px;
  color: var(--muted);
}
.cyc-six-legend-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-six-legend-bar {
  height: 5px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-six-legend-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
}
.cyc-six-legend-row b {
  font-size: 9px;
  text-align: right;
  color: var(--text);
}
.cyc-six-legend-row em {
  font-size: 8px;
  color: var(--dim);
  font-style: normal;
  text-align: right;
}
.cyc-layer-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cyc-layer-row {
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border);
}
.cyc-layer-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
.cyc-layer-head {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.cyc-layer-name {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
}
.cyc-layer-val {
  margin-left: auto;
  font-size: 11px;
  color: var(--muted);
}
.cyc-layer-val small {
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
.cyc-bar {
  margin-top: 6px;
  height: 5px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 40%, var(--warn)));
}
@media (max-width: 1279px) {
  .cyc-retain-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 1023px) {
  .cyc-six-body {
    grid-template-columns: minmax(0, 1fr);
  }
  .cyc-six-svg {
    max-height: 220px;
  }
}
</style>
