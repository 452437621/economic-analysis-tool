<template>
  <section class="card tl-card" aria-labelledby="hst-tl-title">
    <header class="card-head">
      <h2 id="hst-tl-title" class="card-title">
        帝国兴衰 × 储备货币份额
        <span class="sub">横向长河</span>
      </h2>
      <div class="card-actions">
        <span
          v-if="showIllustrative"
          class="badge badge--sm badge--warn"
          :title="illustrativeHint"
        >示意数据</span>
        <div class="tl-tools">
          <button
            class="icon-btn sm"
            type="button"
            aria-label="缩小时间轴"
            title="缩小时间轴"
            :disabled="zoomIndex === 0"
            @click="emit('zoomOut')"
          >
            <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14" /></svg>
          </button>
          <span class="zoom-pct">{{ zoomPercent }}%</span>
          <button
            class="icon-btn sm"
            type="button"
            aria-label="放大时间轴"
            title="放大时间轴"
            :disabled="zoomIndex === ZOOMS.length - 1"
            @click="emit('zoomIn')"
          >
            <svg class="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
          </button>
        </div>
      </div>
    </header>

    <div :ref="scrollEl" class="tl-scroll">
      <svg
        :ref="svgEl"
        :viewBox="`0 0 ${W} ${H}`"
        :width="W"
        :height="H"
        role="img"
        aria-label="1500 至 2100 年荷兰、英国、美国、中国四条帝国兴衰泳道与储备货币份额"
      >
        <rect x="0" y="0" :width="W" :height="H" fill="none" />

        <!-- 2026 之后的推演区间 -->
        <rect
          :x="outYearX"
          y="116"
          :width="Math.max(0, r1(PR - outYearX))"
          height="274"
          fill="#4CC2FF"
          opacity=".035"
          pointer-events="none"
        />

        <!-- 储备货币份额带 -->
        <g v-if="layerState.reserve">
          <rect
            :x="PL"
            y="30"
            :width="PR - PL"
            height="70"
            rx="4"
            fill="#4CC2FF"
            opacity=".035"
            pointer-events="none"
          />
          <text :x="PL - 8" y="55" text-anchor="end" class="tl-reserve-label">储备货币</text>
          <text :x="PL - 8" y="66" text-anchor="end" class="tl-reserve-label">份额（示意）</text>
          <g v-for="curve in renderedCurves" :key="curve.id" pointer-events="none">
            <path :d="curve.area" :fill="curve.color" opacity=".1" pointer-events="none" />
            <path
              :d="curve.line"
              fill="none"
              :stroke="curve.color"
              stroke-width="1.2"
              opacity=".85"
              pointer-events="none"
            />
            <text
              v-if="curve.peakVisible"
              :x="curve.labelX"
              :y="curve.labelY"
              :text-anchor="curve.labelAnchor"
              class="tl-reserve-name"
              :fill="curve.color"
            >{{ curve.name }} {{ curve.peakV }}%</text>
          </g>
        </g>

        <!-- 网格与年份刻度 -->
        <g pointer-events="none">
          <template v-for="tick in ticks" :key="`tick-${tick}`">
            <line class="tl-grid" :x1="r1(xOf(tick))" y1="22" :x2="r1(xOf(tick))" y2="404" />
            <line class="tl-grid" :x1="r1(xOf(tick))" y1="18" :x2="r1(xOf(tick))" y2="22" />
            <text class="tl-axis-text" :x="r1(xOf(tick))" y="14" text-anchor="middle">
              {{ tick }}
            </text>
          </template>
        </g>

        <!-- 四条帝国泳道 -->
        <g v-for="lane in laneRows" :key="lane.id">
          <rect
            class="tl-lane-bg"
            :x="PL"
            :y="lane.ly"
            :width="PR - PL"
            :height="LANE_H"
            rx="3"
          />
          <text class="tl-lane-label" :x="PL - 8" :y="lane.ly + 29" text-anchor="end">
            {{ lane.name }}
          </text>
          <text class="tl-lane-sub" :x="PL - 8" :y="lane.ly + 41" text-anchor="end">
            {{ lane.sub }}
          </text>

          <!-- 崛起 / 顶峰 / 衰落 三段式色带（只画到 2026） -->
          <template v-if="layerState.empire">
            <rect
              v-for="band in lane.bands"
              :key="band.key"
              :x="band.x"
              :y="lane.ly + 4"
              :width="band.width"
              :height="LANE_H - 8"
              rx="3"
              :fill="band.color"
              :opacity="band.opacity"
              pointer-events="none"
            />
          </template>

          <!-- 泳道空白点击：选中该泳道最近的事件 -->
          <rect
            class="tl-lane-hit"
            :x="PL"
            :y="lane.ly"
            :width="PR - PL"
            :height="LANE_H"
            @click="emit('laneClick', lane.id, $event)"
          >
            <title>点击选择{{ lane.name }}泳道最近的事件</title>
          </rect>

          <!-- 事件标记：债务危机菱形 / 战争与革命三角 / 技术革命圆点 / 帝国兴衰圆点 -->
          <g
            v-for="event in lane.events"
            :key="event.key"
            class="tl-ev"
            @click.stop="emit('select', event.item)"
          >
            <title>{{ event.item.year }} · {{ event.item.title }}</title>
            <rect
              class="tl-ev-hit"
              :x="event.x - 11"
              :y="lane.ly"
              width="22"
              :height="LANE_H"
            />
            <line
              v-if="event.showLabel"
              :x1="event.x"
              :y1="event.my + 5"
              :x2="event.x"
              :y2="event.leaderY"
              :stroke="event.color"
              stroke-width=".7"
              opacity=".45"
            />
            <rect
              v-if="event.layer === 'debt'"
              :x="event.x - 3"
              :y="event.my - 3"
              width="6"
              height="6"
              :transform="`rotate(45 ${event.x} ${event.my})`"
              :fill="event.color"
            />
            <path
              v-else-if="event.layer === 'war'"
              :d="`M${event.x} ${event.my - 4}L${event.x + 4} ${event.my + 3}L${event.x - 4} ${event.my + 3}Z`"
              :fill="event.color"
            />
            <circle
              v-else
              :cx="event.x"
              :cy="event.my"
              :r="event.layer === 'tech' ? 2.6 : 3.2"
              :fill="event.color"
            />
            <text
              v-if="event.showLabel"
              class="tl-ev-label"
              :x="event.x"
              :y="event.labelY"
              text-anchor="middle"
            >{{ event.item.year }}</text>
          </g>
        </g>

        <!-- 本期线与脚注 -->
        <line
          :x1="outYearX"
          y1="22"
          :x2="outYearX"
          y2="404"
          stroke="#4CC2FF"
          stroke-width="1"
          stroke-dasharray="3 3"
          opacity=".55"
          pointer-events="none"
        />
        <text class="tl-now-text" :x="r1(outYearX + 5)" y="119">本期 2026</text>
        <text class="tl-axis-text" :x="PL" y="414">
          色带为阶段示意 · 储备份额曲线非精确历史序列
        </text>
      </svg>
    </div>

    <div class="tl-legend">
      <span class="lg"><span class="sw" style="background: rgba(47, 191, 113, .5)"></span>崛起</span>
      <span class="lg"><span class="sw" style="background: rgba(245, 165, 36, .55)"></span>顶峰</span>
      <span class="lg"><span class="sw" style="background: rgba(240, 84, 79, .45)"></span>衰落</span>
      <span class="lg"><span class="sw line" style="background: #4CC2FF"></span>储备份额（示意）</span>
      <span class="lg">
        <span class="sw" style="background: #F0544F; transform: rotate(45deg); width: 7px; height: 7px"></span>债务危机
      </span>
      <span class="lg">
        <span class="sw" style="background: #F5A524; clip-path: polygon(50% 0, 100% 100%, 0 100%); height: 7px"></span>战争与革命
      </span>
      <span class="lg">
        <span class="sw" style="background: #2FBF71; border-radius: 50%; width: 7px; height: 7px"></span>技术革命
      </span>
      <span class="spacer"></span>
      <span>储备份额为示意数据，非精确历史序列</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { TimelineEventItem } from "@/api/types";
import { H, LANE_H, PL, ZOOMS, r1 } from "@/components/history/timeline/geometry";
import type {
  LaneId,
  LayerKey,
  RenderedCurve,
  RenderedLane,
} from "@/components/history/timeline/types";

const props = defineProps<{
  scrollEl: (el: unknown) => void;
  svgEl: (el: unknown) => void;
  w: number;
  pr: number;
  outYearX: number;
  ticks: number[];
  xOf: (year: number) => number;
  renderedCurves: RenderedCurve[];
  laneRows: RenderedLane[];
  layerState: Record<LayerKey, boolean>;
  showIllustrative: boolean;
  illustrativeHint: string;
  zoomIndex: number;
  zoomPercent: number;
}>();

const W = computed(() => props.w);
const PR = computed(() => props.pr);

const emit = defineEmits<{
  select: [item: TimelineEventItem];
  laneClick: [lane: LaneId, event: MouseEvent];
  zoomIn: [];
  zoomOut: [];
}>();
</script>

<style scoped>
.tl-card {
  overflow: hidden;
  min-width: 0;
}
.card-title .sub {
  margin-left: 7px;
  font-size: 10px;
  font-weight: 400;
  color: var(--dim);
  letter-spacing: 0;
}
.tl-tools {
  display: flex;
  align-items: center;
  gap: 5px;
}
.icon-btn.sm {
  width: 26px;
  height: 26px;
  border-radius: 7px;
}
.icon-btn.sm svg {
  width: 14px;
  height: 14px;
}
.icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.zoom-pct {
  min-width: 34px;
  text-align: center;
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--muted);
}
.tl-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 4px;
}
.tl-scroll svg {
  display: block;
}
.tl-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 6px 12px 9px;
  border-top: 1px dashed var(--border);
  font-size: 9px;
  color: var(--dim);
}
.tl-legend .lg {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.tl-legend .sw {
  width: 12px;
  height: 7px;
  border-radius: 2px;
}
.tl-legend .sw.line {
  height: 2px;
  border-radius: 1px;
}
.tl-legend .spacer {
  flex: 1 1 auto;
}

/* SVG 手绘元素（原型 index.html:1092-1104） */
.tl-lane-bg {
  fill: var(--surface-2);
  opacity: 0.45;
}
.tl-grid {
  stroke: var(--border);
  stroke-width: 1;
}
.tl-axis-text {
  fill: var(--dim);
  font-family: var(--mono);
  font-size: 9px;
}
.tl-lane-label {
  fill: var(--muted);
  font-size: 11px;
  font-weight: 650;
}
.tl-lane-sub {
  fill: var(--dim);
  font-family: var(--mono);
  font-size: 7.5px;
}
.tl-reserve-label {
  fill: var(--dim);
  font-size: 8px;
}
.tl-reserve-name {
  font-size: 7.5px;
  font-weight: 600;
  font-family: var(--mono);
}
.tl-ev {
  cursor: pointer;
}
.tl-ev .tl-ev-label {
  fill: var(--muted);
  font-family: var(--mono);
  font-size: 7.5px;
  transition: fill 0.12s;
}
.tl-ev:hover .tl-ev-label {
  fill: var(--accent);
}
.tl-ev-hit {
  fill: transparent;
}
.tl-lane-hit {
  fill: transparent;
  cursor: crosshair;
}
.tl-now-text {
  fill: var(--accent);
  font-family: var(--mono);
  font-size: 8px;
}
</style>
