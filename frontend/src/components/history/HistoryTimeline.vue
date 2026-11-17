<template>
  <section class="card hst-tl-card">
    <div class="card-head">
      <span class="card-title">帝国兴衰 × 储备货币份额</span>
      <span class="card-sub">横向长河 · 事件标注为关键节点，非完整年表</span>
      <div class="card-actions hst-tl-tools">
        <button class="btn btn--sm btn--icon" type="button" title="缩小时间轴（显示更长时段）" @click="zoomOut">
          <svg class="ic"><use href="#i-chevron-left" /></svg>
        </button>
        <span class="hst-zoom-pct mono">{{ zoomPct }}%</span>
        <button class="btn btn--sm btn--icon" type="button" title="放大时间轴（裁到更短时段）" @click="zoomIn">
          <svg class="ic"><use href="#i-chevron-right" /></svg>
        </button>
        <button class="btn btn--sm btn--icon" type="button" title="重置为全部时段" @click="resetView">
          <svg class="ic"><use href="#i-refresh" /></svg>
        </button>
      </div>
    </div>

    <div class="hst-tl-toolbar">
      <div class="seg" role="group" aria-label="时间窗">
        <button
          v-for="item in PRESETS"
          :key="item.label"
          type="button"
          :class="{ active: presetLabel === item.label }"
          @click="applyPreset(item)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="seg" role="group" aria-label="图层过滤">
        <button
          v-for="item in layerFilters"
          :key="item.value"
          type="button"
          :class="{ active: layerFilter === item.value }"
          @click="setLayer(item.value)"
        >
          {{ item.label }}
        </button>
      </div>
      <label class="field hst-search">
        <svg class="ic"><use href="#i-search" /></svg>
        <input v-model="query" type="search" placeholder="按标题搜索事件" aria-label="按标题搜索事件" />
      </label>
    </div>

    <div class="hst-tl-scroll">
      <div class="hst-canvas">
        <div class="hst-plot">
          <div class="hst-eras" aria-hidden="true">
            <div
              v-for="band in eraBands"
              :key="`era-${band.id}`"
              class="hst-era"
              :style="band.style"
            />
          </div>

          <div class="hst-era-ribbon" :style="{ height: `${ribbonHeight}px` }">
            <span
              v-for="band in eraRibbon"
              :key="`rib-${band.id}`"
              class="hst-era-seg"
              :style="{ left: `${band.left}%`, width: `${Math.max(band.width, 1.2)}%`, top: `${band.row * 15}px`, borderColor: band.color }"
              :title="band.title"
            >
              <i :style="{ background: band.color }" />{{ band.name }}
            </span>
          </div>

          <div class="hst-lanes">
            <div v-for="lane in visibleLanes" :key="`lane-${lane.key}`" class="hst-lane" :style="{ height: `${lane.height}px` }">
              <div class="hst-lane-label">
                <b>{{ lane.label }}</b>
                <em>{{ lane.sub }}</em>
              </div>
              <div class="hst-lane-track" @click="onTrackClick">
                <button
                  v-for="dot in lane.dots"
                  :key="dot.item.id"
                  class="hst-ev"
                  :class="{ 'is-on': selectedId === dot.item.id }"
                  type="button"
                  :style="{ left: `${dot.left}%`, top: `${dot.top}px` }"
                  :title="`${dot.item.year} · ${dot.item.title}`"
                  @click.stop="emit('select', dot.item)"
                >
                  <i :style="{ background: dot.color }" />
                  <span class="hst-ev-label">{{ dot.item.year }} · {{ dot.item.title }}</span>
                </button>
              </div>
            </div>
          </div>

          <div class="hst-reserve">
            <svg class="hst-reserve-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <line v-for="y in RESERVE_GRID" :key="`g-${y}`" class="hst-grid-line" x1="0" :y1="y" x2="100" :y2="y" />
              <path
                v-for="series in reserveSeries"
                :key="`line-${series.key}`"
                class="hst-res-line"
                :d="series.d"
                :stroke="series.color"
              />
            </svg>
            <span
              v-for="tick in RESERVE_TICKS"
              :key="`rt-${tick.value}`"
              class="hst-res-tick mono"
              :style="{ top: `${tick.top}%`, transform: tick.transform }"
            >{{ tick.label }}</span>
            <template v-for="series in reserveSeries" :key="`dot-group-${series.key}`">
              <span
                v-for="point in series.points"
                :key="`dot-${series.key}-${point.year}`"
                class="hst-res-dot"
                :style="{ left: `${point.x}%`, top: `${point.y}%`, borderColor: series.color }"
                :title="`${series.label} ${point.year} 年 ${point.value}%`"
              />
            </template>
            <span v-if="!reserveSeries.length" class="hst-reserve-empty">
              该时段无可见储备份额（可能被图例关闭，或该阶段无数据）
            </span>
          </div>

          <div class="hst-axis">
            <span v-for="tick in ticks" :key="`t-${tick}`" class="hst-axis-tick" :style="{ left: `${xPct(tick)}%` }">
              {{ tick }}
            </span>
          </div>

          <div v-if="nowPct !== null" class="hst-now" :style="{ left: `${nowPct}%` }">
            <i class="hst-now-line" />
            <em>当下</em>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!visibleEvents.length" class="hst-tl-empty">
      当前筛选（{{ windowText }}{{ query ? ` · 关键词「${query}」` : "" }}）没有事件，试试切换时间窗或清空搜索。
    </div>

    <div class="hst-era-legend">
      <span v-for="band in eraBands" :key="`el-${band.id}`" class="hst-era-item" :title="band.title">
        <i :style="{ background: band.color }" />
        {{ band.name }}
        <em class="mono">{{ band.rise }}–{{ band.decline }}</em>
      </span>
    </div>

    <div class="card-foot hst-tl-foot">
      <div class="hst-legend">
        <span v-for="item in categoryLegend" :key="`c-${item.key}`" class="hst-legend-item">
          <i :style="{ background: item.color }" />{{ item.label }}
        </span>
        <span class="hst-legend-sep" />
        <button
          v-for="item in reserveOptions"
          :key="`r-${item.key}`"
          class="hst-res-chip"
          :class="{ 'is-off': hiddenReserve.includes(item.key) }"
          type="button"
          :title="`点击切换 ${item.label} 储备份额曲线`"
          @click="toggleReserve(item.key)"
        >
          <i :style="{ background: item.color }" />{{ item.label }}
        </button>
      </div>
      <span class="hst-note">
        {{ windowText }} · {{ visibleEvents.length }} 条 · 储备份额为示意数据，非精确历史序列
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { TimelineEra, TimelineEventItem, TimelinePowerPoint } from "@/api/types";

interface Props {
  eras: TimelineEra[];
  events: TimelineEventItem[];
  reserve: TimelinePowerPoint[];
  selectedId?: string | null;
}

const props = withDefaults(defineProps<Props>(), { selectedId: null });

const emit = defineEmits<{
  (event: "select", item: TimelineEventItem): void;
  (event: "select-year", year: number): void;
}>();

/* ── 时间窗 / zoom ───────────────────────────────────────────────────── */

interface WindowRange {
  from: number;
  to: number;
}

const BASE_FROM = 1400;
const BASE_TO = 2100;
const BASE_SPAN = 530;
const MIN_SPAN = 40;

const PRESETS: Array<WindowRange & { label: string }> = [
  { label: "1500–1800", from: 1500, to: 1800 },
  { label: "1800–1914", from: 1800, to: 1914 },
  { label: "1914–1991", from: 1914, to: 1991 },
  { label: "1991–2026", from: 1991, to: 2026 },
  { label: "全部", from: 1500, to: 2030 },
];

const view = ref<WindowRange>({ from: 1500, to: 2030 });
const presetLabel = ref("全部");

const span = computed(() => Math.max(view.value.to - view.value.from, 1));
const windowText = computed(() => `${view.value.from}–${view.value.to}`);
const zoomPct = computed(() => Math.round((BASE_SPAN / span.value) * 100));

const xPct = (year: number) => {
  const raw = ((year - view.value.from) / span.value) * 100;
  return Math.max(0, Math.min(100, raw));
};

const clampRange = (next: WindowRange): WindowRange => {
  const years = Math.max(MIN_SPAN, Math.min(BASE_SPAN, Math.round(next.to - next.from)));
  let from = Math.round(next.from);
  let to = from + years;
  if (from < BASE_FROM) {
    from = BASE_FROM;
    to = from + years;
  }
  if (to > BASE_TO) {
    to = BASE_TO;
    from = to - years;
  }
  return { from, to };
};

const setSpan = (years: number) => {
  const center = (view.value.from + view.value.to) / 2;
  view.value = clampRange({ from: center - years / 2, to: center + years / 2 });
  presetLabel.value = "";
};

const zoomIn = () => setSpan(span.value * 0.7);
const zoomOut = () => setSpan(span.value / 0.7);
const resetView = () => applyPreset(PRESETS[PRESETS.length - 1]);

const applyPreset = (item: WindowRange & { label: string }) => {
  view.value = { from: item.from, to: item.to };
  presetLabel.value = item.label;
};

/* ── 图层过滤 / 搜索 ─────────────────────────────────────────────────── */

const LANES = [
  { key: "L", label: "长周期", sub: "债务与秩序" },
  { key: "B", label: "大周期", sub: "霸权更替" },
  { key: "S", label: "短周期", sub: "危机与政策" },
  { key: "E", label: "事件冲击", sub: "战争与革命" },
] as const;

type LayerKey = (typeof LANES)[number]["key"];
type LayerFilter = "all" | LayerKey;

const layerFilters: Array<{ value: LayerFilter; label: string }> = [
  { value: "all", label: "全部" },
  ...LANES.map((item) => ({ value: item.key, label: item.label })),
];

const layerFilter = ref<LayerFilter>("all");
const query = ref("");

const setLayer = (value: LayerFilter) => {
  layerFilter.value = value;
};

/* ── 颜色 ────────────────────────────────────────────────────────────── */

const CATEGORY_COLORS: Record<string, string> = {
  economy: "#4CC2FF",
  finance: "#2FBF71",
  monetary: "#F5A524",
  politics: "#A78BFA",
  war: "#F0544F",
  trade: "#38BDF8",
  cycle: "#F472B6",
  tech: "#22D3EE",
};

const PALETTE = ["#4CC2FF", "#2FBF71", "#F5A524", "#A78BFA", "#F0544F", "#38BDF8"];

const categoryColor = (category: string): string => {
  if (CATEGORY_COLORS[category]) return CATEGORY_COLORS[category];
  const hash = Array.from(category).reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return PALETTE[hash % PALETTE.length];
};

const ERA_COLORS: Record<string, string> = {
  china_ming: "#2FBF71",
  iberia: "#F5A524",
  netherlands: "#A78BFA",
  uk: "#F0544F",
  usa: "#4CC2FF",
  multipolar: "#94A3B8",
};

const RESERVE_META: Record<string, { label: string; color: string }> = {
  usd: { label: "美元", color: "#4CC2FF" },
  gbp: { label: "英镑", color: "#F0544F" },
  eur: { label: "欧元", color: "#2FBF71" },
  cny: { label: "人民币", color: "#F5A524" },
};

const RESERVE_ORDER = ["usd", "gbp", "eur", "cny"];
const RESERVE_GRID = [0, 50, 100];
/** 储备份额纵轴刻度：数值 100% 在顶部（SVG y=0），0% 在底部。 */
const RESERVE_TICKS = RESERVE_GRID.map((value) => ({
  value,
  top: 100 - value,
  label: `${value}%`,
  transform: value === 100 ? "translateY(2px)" : value === 0 ? "translateY(-100%)" : "translateY(-50%)",
}));

/* ── 事件泳道（泳道内去重叠） ────────────────────────────────────────── */

interface Dot {
  item: TimelineEventItem;
  left: number;
  top: number;
  color: string;
}

interface Lane {
  key: LayerKey;
  label: string;
  sub: string;
  height: number;
  dots: Dot[];
}

const ROW_HEIGHT = 15;
const MIN_GAP = 2.2;

const filteredEvents = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  return props.events.filter((item) => {
    if (layerFilter.value !== "all" && item.layer !== layerFilter.value) return false;
    if (keyword && !item.title.toLowerCase().includes(keyword)) return false;
    return true;
  });
});

const visibleEvents = computed(() =>
  filteredEvents.value.filter((item) => item.year >= view.value.from && item.year <= view.value.to),
);

const lanes = computed<Lane[]>(() =>
  LANES.map((def) => {
    const rows = visibleEvents.value
      .filter((item) => item.layer === def.key)
      .slice()
      .sort((a, b) => a.year - b.year || a.title.localeCompare(b.title, "zh-Hans-CN"));
    const rowEnds: number[] = [];
    const dots: Dot[] = rows.map((item) => {
      const x = xPct(item.year);
      let row = rowEnds.findIndex((end) => x - end > MIN_GAP);
      if (row === -1) {
        row = rowEnds.length;
        rowEnds.push(x);
      } else {
        rowEnds[row] = x;
      }
      return { item, left: x, top: 8 + row * ROW_HEIGHT, color: categoryColor(item.category) };
    });
    const maxRow = dots.reduce((max, dot) => Math.max(max, Math.round((dot.top - 8) / ROW_HEIGHT)), -1);
    return {
      key: def.key,
      label: def.label,
      sub: def.sub,
      dots,
      height: Math.max(34, 14 + (maxRow + 1) * ROW_HEIGHT + 6),
    };
  }),
);

const visibleLanes = computed(() =>
  lanes.value.filter((lane) => layerFilter.value === "all" || lane.key === layerFilter.value),
);

const categoryLegend = computed(() => {
  const map = new Map<string, string>();
  for (const item of props.events) {
    if (!map.has(item.category)) map.set(item.category, item.category_label);
  }
  return Array.from(map, ([key, label]) => ({ key, label, color: categoryColor(key) }));
});

/* ── 帝国色带 ────────────────────────────────────────────────────────── */

const eraBands = computed(() =>
  props.eras
    .map((era, index) => {
      const left = xPct(Math.max(era.rise, view.value.from));
      const right = xPct(Math.min(era.decline, view.value.to));
      const color = ERA_COLORS[era.id] ?? PALETTE[index % PALETTE.length];
      return {
        id: era.id,
        name: era.name,
        rise: era.rise,
        decline: era.decline,
        color,
        left,
        width: right - left,
        style: {
          left: `${left}%`,
          width: `${Math.max(right - left, 0.5)}%`,
          borderLeftColor: color,
          background: `linear-gradient(180deg, color-mix(in srgb, ${color} 16%, transparent) 0%, color-mix(in srgb, ${color} 5%, transparent) 45%, transparent 72%)`,
        },
        title: `${era.name} ${era.rise}–${era.decline}｜顶峰 ${era.peak}｜储备货币 ${era.reserve}`,
      };
    })
    .filter((band) => band.width > 0.3),
);

/** 顶部帝国名条：同一个时代的色带互相重叠，按贪心分行避免文字互相覆盖。 */
const eraRibbon = computed(() => {
  const rows: Array<Array<{ left: number; width: number }>> = [];
  return eraBands.value.map((band) => {
    let row = 0;
    for (;;) {
      const rowSegs = rows[row] ?? [];
      if (!rowSegs.some((seg) => seg.left < band.left + band.width && band.left < seg.left + seg.width)) {
        rows[row] = [...rowSegs, { left: band.left, width: band.width }];
        break;
      }
      row += 1;
    }
    return { ...band, row };
  });
});

const ribbonHeight = computed(
  () => Math.max(1, new Set(eraRibbon.value.map((band) => band.row)).size) * 15,
);

/* ── 储备货币份额曲线（0–100 压缩在底部 20% 区域） ───────────────────── */

const hiddenReserve = ref<string[]>([]);

const toggleReserve = (key: string) => {
  hiddenReserve.value = hiddenReserve.value.includes(key)
    ? hiddenReserve.value.filter((item) => item !== key)
    : [...hiddenReserve.value, key];
};

const reserveOptions = computed(() => {
  const keys = Array.from(new Set(props.reserve.map((point) => point.power.toLowerCase())));
  const ordered = [...RESERVE_ORDER.filter((key) => keys.includes(key)), ...keys.filter((key) => !RESERVE_ORDER.includes(key))];
  return ordered.map((key) => {
    const point = props.reserve.find((row) => row.power.toLowerCase() === key);
    return {
      key,
      label: RESERVE_META[key]?.label ?? point?.power_label ?? key.toUpperCase(),
      color: RESERVE_META[key]?.color ?? "#93A4B8",
    };
  });
});

const reserveSeries = computed(() => {
  const byPower = new Map<string, Array<{ year: number; value: number }>>();
  for (const point of props.reserve) {
    const key = point.power.toLowerCase();
    const rows = byPower.get(key) ?? [];
    rows.push({ year: point.year, value: point.value });
    byPower.set(key, rows);
  }
  return reserveOptions.value
    .filter((option) => !hiddenReserve.value.includes(option.key))
    .map((option) => {
      const points = (byPower.get(option.key) ?? [])
        .filter((point) => point.year >= view.value.from && point.year <= view.value.to)
        .sort((a, b) => a.year - b.year)
        .map((point) => ({
          year: point.year,
          value: point.value,
          x: xPct(point.year),
          y: 100 - Math.max(0, Math.min(100, point.value)),
        }));
      const d = points
        .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
        .join(" ");
      return { ...option, points, d };
    })
    .filter((series) => series.points.length > 0);
});

/* ── 坐标轴 ──────────────────────────────────────────────────────────── */

const TICK_STEPS = [5, 10, 20, 25, 50, 100];

const tickStep = computed(() => TICK_STEPS.find((step) => span.value / step <= 8) ?? 100);

const ticks = computed(() => {
  const step = tickStep.value;
  const first = Math.ceil(view.value.from / step) * step;
  const out: number[] = [];
  for (let year = first; year <= view.value.to; year += step) out.push(year);
  return out;
});

const nowPct = computed(() => {
  const year = new Date().getFullYear();
  return year >= view.value.from && year <= view.value.to ? xPct(year) : null;
});

const onTrackClick = (event: MouseEvent) => {
  const el = event.currentTarget as HTMLElement | null;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0) return;
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  emit("select-year", Math.round(view.value.from + ratio * span.value));
};
</script>

<style scoped>
.hst-tl-card {
  min-width: 0;
}
.hst-tl-tools {
  gap: 5px;
}
.hst-zoom-pct {
  min-width: 40px;
  text-align: center;
  font-size: 10px;
  color: var(--muted);
}
.hst-tl-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 13px;
  border-bottom: 1px solid var(--border);
}
.hst-tl-toolbar .hst-search {
  margin-left: auto;
  width: 210px;
  max-width: 100%;
}
.hst-tl-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 10px 13px 2px;
}
.hst-canvas {
  position: relative;
  min-width: 880px;
  padding-left: 92px;
}
.hst-plot {
  position: relative;
}
.hst-eras {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
.hst-era {
  position: absolute;
  top: 0;
  bottom: 0;
  border-left: 1px solid;
  border-radius: 2px;
}
.hst-lanes {
  position: relative;
  z-index: 1;
}
.hst-era-ribbon {
  position: relative;
  z-index: 2;
  margin-bottom: 5px;
}
.hst-era-seg {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 3px;
  height: 13px;
  padding: 0 4px;
  overflow: hidden;
  border-top: 1px solid;
  border-radius: 2px;
  background: color-mix(in srgb, var(--surface) 72%, transparent);
  color: var(--dim);
  font-size: 8.5px;
  line-height: 1;
  white-space: nowrap;
  text-overflow: ellipsis;
  cursor: default;
}
.hst-era-seg i {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 1px;
}
.hst-lane {
  position: relative;
}
.hst-lane + .hst-lane {
  border-top: 1px dashed var(--border);
}
.hst-lane-label {
  position: absolute;
  left: -92px;
  top: 5px;
  width: 84px;
  text-align: right;
  line-height: 1.25;
}
.hst-lane-label b {
  display: block;
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
}
.hst-lane-label em {
  display: block;
  font-style: normal;
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}
.hst-lane-track {
  position: relative;
  height: 100%;
  cursor: crosshair;
}
.hst-ev {
  position: absolute;
  width: 11px;
  height: 11px;
  margin-left: -5.5px;
  padding: 0;
  border: 0;
  background: none;
  cursor: pointer;
  z-index: 2;
}
.hst-ev i {
  display: block;
  width: 7px;
  height: 7px;
  margin: 2px;
  border-radius: 2px;
  box-shadow: 0 0 0 1.5px var(--surface);
  transition: transform 0.12s ease;
}
.hst-ev:hover i,
.hst-ev:focus-visible i {
  transform: scale(1.35);
}
.hst-ev.is-on i {
  box-shadow: 0 0 0 2px var(--accent);
}
.hst-ev-label {
  display: none;
  position: absolute;
  left: 50%;
  top: 13px;
  transform: translateX(-50%);
  padding: 2px 6px;
  border: 1px solid var(--border-strong);
  border-radius: 5px;
  background: var(--surface-2);
  color: var(--text);
  font-size: 9.5px;
  line-height: 1.3;
  white-space: nowrap;
  z-index: 10;
  pointer-events: none;
  box-shadow: var(--shadow);
}
.hst-ev:hover .hst-ev-label,
.hst-ev:focus-visible .hst-ev-label {
  display: block;
}
.hst-reserve {
  position: relative;
  z-index: 1;
  height: 92px;
  margin-top: 8px;
  border-top: 1px dashed var(--border);
}
.hst-reserve-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.hst-grid-line {
  stroke: var(--border);
  stroke-dasharray: 3 4;
  vector-effect: non-scaling-stroke;
}
.hst-res-tick {
  position: absolute;
  left: 2px;
  font-size: 8px;
  line-height: 1;
  color: var(--dim);
  pointer-events: none;
}
.hst-res-line {
  fill: none;
  stroke-width: 1.6;
  stroke-linejoin: round;
  stroke-linecap: round;
  vector-effect: non-scaling-stroke;
}
.hst-res-dot {
  position: absolute;
  width: 5px;
  height: 5px;
  border: 1.5px solid;
  border-radius: 50%;
  background: var(--surface);
  transform: translate(-50%, -50%);
}
.hst-reserve-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: var(--dim);
}
.hst-axis {
  position: relative;
  height: 26px;
  margin-top: 2px;
}
.hst-axis-tick {
  position: absolute;
  top: 5px;
  transform: translateX(-50%);
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.hst-now {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 3;
  pointer-events: none;
}
.hst-now-line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 0;
  border-left: 1px dashed var(--accent);
  opacity: 0.5;
}
.hst-now em {
  position: absolute;
  bottom: 2px;
  left: 0;
  transform: translateX(-50%);
  font-style: normal;
  font-size: 8.5px;
  color: var(--accent);
  white-space: nowrap;
}
.hst-tl-empty {
  padding: 10px 13px 12px;
  font-size: 10.5px;
  color: var(--muted);
}
.hst-era-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  padding: 0 13px 8px;
}
.hst-era-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 9.5px;
  color: var(--muted);
  cursor: default;
}
.hst-era-item i {
  width: 3px;
  height: 11px;
  border-radius: 2px;
}
.hst-era-item em {
  font-style: normal;
  font-size: 8.5px;
  color: var(--dim);
}
.hst-tl-foot {
  flex-wrap: wrap;
  gap: 8px;
}
.hst-legend {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.hst-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9.5px;
  color: var(--muted);
}
.hst-legend-item i {
  width: 6px;
  height: 6px;
  border-radius: 2px;
}
.hst-legend-sep {
  width: 1px;
  height: 12px;
  background: var(--border);
}
.hst-res-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 18px;
  padding: 0 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 9.5px;
  cursor: pointer;
}
.hst-res-chip i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.hst-res-chip:hover {
  color: var(--text);
  border-color: var(--border-strong);
}
.hst-res-chip.is-off {
  opacity: 0.4;
  text-decoration: line-through;
}
.hst-note {
  margin-left: auto;
  font-size: 9.5px;
  color: var(--dim);
}

@media (max-width: 1240px) {
  .hst-tl-toolbar .hst-search {
    margin-left: 0;
    width: 100%;
  }
}
</style>
