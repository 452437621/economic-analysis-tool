<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研判 · 世界长河 · 1500 – 2026</div>
        <h1 class="page-h1">
          世界长河
          <span class="page-sub">五百年霸权更替与货币秩序 —— 把今天放进历史，而不是把历史套在今天</span>
        </h1>
      </div>
      <div class="page-actions">
        <span v-if="payload?.asof" class="badge badge--sm">数据日 {{ fmtDate(payload.asof) }}</span>
        <span v-if="payload" class="badge badge--sm">{{ fmtInt(counts.events) }} 条事件</span>
        <span v-if="payload?.status" class="badge badge--sm">{{ statusText(payload.status) }}</span>
        <button class="btn btn--sm" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中…" : "重新入库" }}
        </button>
      </div>
    </div>

    <SkeletonBlock v-if="!payload && loading" :rows="7" :cells="3" :height="16" />
    <ErrorState v-else-if="!payload && error" :error="error" @retry="refresh" />

    <template v-else-if="payload">
      <div class="kpi-grid">
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-branch" /></svg></span>
            <span class="kpi-label">事件年表</span>
            <span class="kpi-flag badge badge--sm">1500–2026</span>
          </div>
          <div class="kpi-value">{{ fmtInt(counts.events) }}<small>条精选</small></div>
          <div class="kpi-sub">
            证据 A {{ fmtInt(counts.grades.A ?? 0) }} · B {{ fmtInt(counts.grades.B ?? 0) }} · C {{ fmtInt(counts.grades.C ?? 0) }}
          </div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-target" /></svg></span>
            <span class="kpi-label">霸权周期</span>
            <span class="kpi-flag badge badge--sm badge--warn">第 {{ eras.length }} 轮</span>
          </div>
          <div class="kpi-value">{{ currentEra?.name ?? "—" }}</div>
          <div class="kpi-sub">储备货币 {{ currentEra?.reserve ?? "—" }} · 历史平均约 100 年一轮</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-rates" /></svg></span>
            <span class="kpi-label">美元储备份额</span>
            <span class="kpi-flag badge badge--sm">{{ usdShare ? `${fmtNumber(usdShare.value, 1)}%` : "—" }}</span>
          </div>
          <div class="kpi-value">{{ usdShare ? fmtNumber(usdShare.value, 1) : "—" }}<small>% 全球外汇储备</small></div>
          <div class="kpi-sub">{{ usdShare ? `${usdShare.year} 年` : "" }} · 1999 年前后约 71%，下滑是二十多年趋势而非单季事件</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-layers" /></svg></span>
            <span class="kpi-label">历史类比（样本内）</span>
            <span class="kpi-flag badge badge--sm">{{ analogs.length }} 组</span>
          </div>
          <div class="kpi-value">
            {{ analogs.length ? Math.round(analogs[0].similarity * 100) : "—" }}<small>% 最相似</small>
          </div>
          <div class="kpi-sub">{{ analogs[0]?.name ?? "—" }} · 相似≠相同，结论按叙事判断（D 级）使用</div>
        </article>
      </div>

      <section class="card">
        <div class="card-head">
          <span class="card-title">时间轴 · 四层泳道</span>
          <span class="card-sub">点按事件查看摘要与来源；色带为霸权时期（含货币与教训）</span>
          <div class="card-actions tl-actions">
            <div class="seg">
              <button
                v-for="item in layerFilters"
                :key="item.value"
                class="seg-btn"
                :class="{ 'is-on': layerFilter === item.value }"
                type="button"
                @click="layerFilter = item.value"
              >
                {{ item.label }}
              </button>
            </div>
            <div class="seg">
              <button
                v-for="item in windows"
                :key="item.label"
                class="seg-btn"
                :class="{ 'is-on': windowLabel === item.label }"
                type="button"
                @click="applyWindow(item)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>
        </div>
        <div class="card-body">
          <div class="timeline" :style="{ '--lane-count': lanes.length }">
            <div class="era-bands">
              <div
                v-for="(era, index) in eras"
                :key="era.id"
                class="era-band"
                :class="`era-band--${index % 4}`"
                :style="eraStyle(era)"
                :title="`${era.name} · ${era.rise}–${era.decline} · 储备货币 ${era.reserve}`"
              />
            </div>
            <div class="lanes">
              <div v-for="lane in lanes" :key="lane.key" class="lane">
                <span class="lane-label">{{ lane.label }}</span>
                <div class="lane-track">
                  <button
                    v-for="dot in lane.dots"
                    :key="dot.id"
                    class="tl-dot"
                    :class="[`tl-dot--${dot.layer}`, { 'is-active': selected?.id === dot.id }]"
                    type="button"
                    :style="dot.style"
                    :title="`${dot.year} · ${dot.title}`"
                    @click="selected = dot"
                  >
                    <span class="tl-dot-core" />
                  </button>
                </div>
              </div>
            </div>
            <div class="axis">
              <span v-for="tick in ticks" :key="tick" class="axis-tick" :style="{ left: yearPercent(Number(tick)) + '%' }">
                {{ tick }}
              </span>
            </div>
          </div>
          <div class="tl-legend">
            <span v-for="item in lanes" :key="`lg-${item.key}`" class="tl-legend-item">
              <i class="tl-legend-dot" :class="`tl-dot--${item.key}`" />{{ item.label }}（{{ item.dots.length }}）
            </span>
            <span class="tl-legend-note">当前窗口 {{ window.from }}–{{ window.to }} · 共 {{ visibleEvents.length }} 条</span>
          </div>
          <div class="era-legend">
            <span v-for="(era, index) in eras" :key="`e-${era.id}`" class="era-legend-item">
              <i class="era-legend-chip" :class="`era-band--${index % 4}`" />
              {{ era.name }}
              <em>{{ era.rise }}–{{ era.decline }}</em>
            </span>
          </div>
        </div>
      </section>

      <div class="grid-2">
        <section class="card">
          <div class="card-head">
            <span class="card-title">实力份额 · GDP 占比</span>
            <span class="card-sub">Maddison Project 2023；1500–1870 为粗略估计（B/C 级）</span>
          </div>
          <div class="card-body">
            <EChart :option="gdpOption" :height="260" />
            <div class="chart-note">
              实力领先储备货币 30–50 年：经济份额先转移，货币与金融中心随后。图中早期数据为学界估计，不宜过度解读小数点。
            </div>
          </div>
        </section>
        <section class="card">
          <div class="card-head">
            <span class="card-title">储备货币份额</span>
            <span class="card-sub">IMF COFER；1913 年前数据为研究者估计（B/C 级）</span>
          </div>
          <div class="card-body">
            <EChart :option="reserveOption" :height="260" />
            <div class="chart-note">
              储备货币更替先慢后快：英镑 1913 年仍占约 64%，美元到 1944 年才被制度确认。单季份额波动不构成「崩塌」。
            </div>
          </div>
        </section>
      </div>

      <div class="grid-2">
        <section class="card">
          <div class="card-head">
            <span class="card-title">当下坐标 · 五维对照</span>
            <span class="card-sub">把今天的读数放到历史锚点上比较；锚点本身来自叙事分期（C 级）</span>
          </div>
          <div class="card-body">
            <div class="dim-table">
              <div v-for="dim in dimensions" :key="dim.dimension" class="dim-row">
                <div class="dim-head">
                  <span class="dim-name">{{ dim.dimension }}</span>
                  <span class="dim-value">{{ dim.current }}</span>
                  <span class="badge badge--sm" :class="gradeClass(dim.grade)">{{ dim.grade }}</span>
                </div>
                <div class="dim-judge">{{ dim.judgment }}</div>
                <div class="dim-anchor">历史锚点：{{ dim.anchor }}</div>
              </div>
            </div>
          </div>
        </section>
        <section class="card">
          <div class="card-head">
            <span class="card-title">历史类比</span>
            <span class="card-sub">相似度来自公开叙事对照，非量化匹配</span>
          </div>
          <div class="card-body analog-list">
            <article v-for="analog in analogs" :key="analog.id" class="analog">
              <div class="analog-head">
                <span class="analog-name">{{ analog.name }}</span>
                <span class="analog-sim">{{ Math.round(analog.similarity * 100) }}%</span>
              </div>
              <div class="analog-bar"><i :style="{ width: `${analog.similarity * 100}%` }" /></div>
              <div class="analog-block">
                <span class="analog-tag analog-tag--same">相似</span>
                <span>{{ analog.similar.join("；") }}</span>
              </div>
              <div class="analog-block">
                <span class="analog-tag analog-tag--diff">不同</span>
                <span>{{ analog.different.join("；") }}</span>
              </div>
            </article>
          </div>
        </section>
      </div>

      <section class="card">
        <div class="card-head">
          <span class="card-title">霸权更替</span>
          <span class="card-sub">每轮霸权的崛起、顶点、衰退与遗留教训</span>
        </div>
        <div class="card-body">
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>时期</th>
                  <th>崛起</th>
                  <th>顶点</th>
                  <th>衰退</th>
                  <th>储备货币</th>
                  <th>创新 / 制度</th>
                  <th>教训</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="era in eras" :key="era.id">
                  <td class="mono">{{ era.name }}</td>
                  <td class="mono">{{ era.rise }}</td>
                  <td class="mono">{{ era.peak }}</td>
                  <td class="mono">{{ era.decline }}</td>
                  <td>{{ era.reserve }}</td>
                  <td>{{ era.innovation }}</td>
                  <td class="era-lesson">{{ era.lesson }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <span class="card-title">十条历史规律</span>
          <span class="card-sub">每条都必须可观测、可证伪；「可计算」列说明如何落到本系统指标</span>
        </div>
        <div class="card-body">
          <div class="lesson-grid">
            <article v-for="lesson in lessons" :key="lesson.id" class="lesson">
              <div class="lesson-head">
                <span class="badge badge--sm">{{ lesson.id }}</span>
                <span class="lesson-name">{{ lesson.name }}</span>
              </div>
              <p class="lesson-mech">{{ lesson.mechanism }}</p>
              <p class="lesson-calc"><span>可计算</span>{{ lesson.computable }}</p>
            </article>
          </div>
        </div>
      </section>

      <p v-if="payload.degraded && payload.degraded_reasons.length" class="degraded-note">
        <b>降级说明</b>
        {{ payload.degraded_reasons.slice(0, 4).map((item) => item.message).join("；") }}
      </p>
      <p class="foot-note">
        口径声明：年表为 1500–2026 精选事件（非全集），A 级事件附公开来源；霸权分期与历史类同为叙事判断（C/D 级），用于辅助定位而非预测。
        运行 {{ payload.run_id ? payload.run_id.slice(0, 8) : "—" }} · 生成于 {{ payload.generated_at.slice(0, 16).replace("T", " ") }}
      </p>
    </template>

    <Teleport to="body">
      <div v-if="selected" class="event-mask" @click.self="selected = null">
        <aside class="event-drawer">
          <header class="event-head">
            <button class="icon-btn event-close" type="button" aria-label="关闭" @click="selected = null">
              <svg class="ic"><use href="#i-close" /></svg>
            </button>
            <div class="event-head-text">
              <div class="event-eyebrow">
                {{ selected.year }}<template v-if="selected.month">-{{ String(selected.month).padStart(2, "0") }}</template>
                · {{ selected.layer_label }}
              </div>
              <h2 class="event-title">{{ selected.title }}</h2>
            </div>
          </header>
          <div class="event-body">
            <div class="event-badges">
              <span class="badge badge--sm">{{ selected.category_label }}</span>
              <span v-if="selected.power_label" class="badge badge--sm">{{ selected.power_label }}</span>
              <span class="badge badge--sm" :class="gradeClass(selected.evidence_grade)">
                证据 {{ selected.evidence_grade }}
              </span>
            </div>
            <section class="event-section">
              <h3>发生了什么</h3>
              <p>{{ selected.summary || "该事件暂无摘要，请查看来源。" }}</p>
            </section>
            <section class="event-section">
              <h3>为什么影响今天</h3>
              <p>
                这一条被归入「{{ selected.layer_label }}」层与「{{ selected.category_label }}」类。它记录的是机制的重复，而不是事件的重复：
                读历史时优先看触发条件、约束与参与者反应，再对照当下是否同构。
              </p>
            </section>
            <section class="event-section">
              <h3>来源与口径</h3>
              <p v-if="selected.source_url" class="event-source">
                <a :href="selected.source_url" target="_blank" rel="noreferrer noopener">{{ selected.source_url }}</a>
              </p>
              <p v-else>该事件为叙事判断（C 级），未附单一来源，请结合多份史料交叉核对。</p>
              <p class="event-muted">事件编号 {{ selected.id }} · 年表为精选，不作为完整性证明。</p>
            </section>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import type { EChartsOption } from "echarts";
import EChart from "@/components/charts/EChart.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtInt, fmtNumber } from "@/composables/useFormat";
import { getTimelineOverview, runTimeline } from "@/api/endpoints";
import type {
  TimelineAnalog,
  TimelineDimension,
  TimelineEra,
  TimelineEventItem,
  TimelineLesson,
  TimelineOverview,
} from "@/api/types";

const { data, error, loading, refresh } = usePolling<TimelineOverview>(getTimelineOverview, {
  interval: 300_000,
});

const running = ref(false);
const selected = ref<TimelineEventItem | null>(null);
const layerFilter = ref("all");
const windowLabel = ref("全部");

const route = useRoute();

const payload = computed(() => data.value);
const counts = computed(
  () => payload.value?.counts ?? { events: 0, eras: 0, lessons: 0, grades: {}, layers: {} },
);
const eras = computed<TimelineEra[]>(() => payload.value?.eras ?? []);
const lessons = computed<TimelineLesson[]>(() => payload.value?.lessons ?? []);
const events = computed<TimelineEventItem[]>(() => payload.value?.events ?? []);
const dimensions = computed<TimelineDimension[]>(() => payload.value?.position?.value.dimensions ?? []);
const analogs = computed<TimelineAnalog[]>(() => payload.value?.position?.value.analogs ?? []);
const currentEra = computed(() => eras.value[eras.value.length - 1] ?? null);

const usdShare = computed(() => {
  const rows = (payload.value?.powers.reserve ?? []).filter((item) => item.power.toLowerCase() === "usd");
  return rows.length ? rows[rows.length - 1] : null;
});

const LANE_DEFS = [
  { key: "L", label: "长周期" },
  { key: "B", label: "大周期" },
  { key: "S", label: "短周期" },
  { key: "E", label: "事件冲击" },
] as const;

const layerFilters = [
  { value: "all", label: "全部" },
  ...LANE_DEFS.map((item) => ({ value: item.key, label: item.label })),
];

const windows = [
  { label: "全部", from: 1500, to: 2030 },
  { label: "1500–1800", from: 1500, to: 1800 },
  { label: "1800–1914", from: 1800, to: 1914 },
  { label: "1914–1991", from: 1914, to: 1991 },
  { label: "1991–2026", from: 1991, to: 2026 },
];

const window = ref({ from: 1500, to: 2030 });

const applyWindow = (item: { label: string; from: number; to: number }) => {
  window.value = { from: item.from, to: item.to };
  windowLabel.value = item.label;
};

const yearPercent = (year: number) => {
  const span = window.value.to - window.value.from || 1;
  return Math.max(0, Math.min(100, ((year - window.value.from) / span) * 100));
};

watch(
  () => [events.value.length, route.query.event],
  () => {
    const id = route.query.event;
    if (typeof id !== "string" || !id) return;
    const hit = events.value.find((item) => item.id === id);
    if (hit) selected.value = hit;
  },
  { immediate: true },
);

const visibleEvents = computed(() => {
  const from = window.value.from;
  const to = window.value.to;
  return events.value.filter((item) => item.year >= from && item.year <= to);
});

const lanes = computed(() =>
  LANE_DEFS.map((def) => {
    const rows = visibleEvents.value
      .filter((item) => item.layer === def.key && (layerFilter.value === "all" || layerFilter.value === def.key))
      .slice()
      .sort((a, b) => a.year - b.year);
    const subRowEnds: number[] = [];
    const dots = rows.map((item) => {
      const x = yearPercent(item.year);
      let row = subRowEnds.findIndex((end) => x - end > 2.6);
      if (row === -1) {
        row = subRowEnds.length;
        subRowEnds.push(x);
      } else {
        subRowEnds[row] = x;
      }
      return {
        ...item,
        style: {
          left: `${x}%`,
          top: `${8 + row * 13}px`,
        },
      };
    });
    return { ...def, dots };
  }),
);

const ticks = computed(() => {
  const from = window.value.from;
  const to = window.value.to;
  const step = (to - from) / 4;
  return [from, from + step, from + step * 2, from + step * 3, to].map((value) => Math.round(value));
});

const eraStyle = (era: TimelineEra) => {
  const left = yearPercent(era.rise);
  const right = yearPercent(era.decline);
  return { left: `${left}%`, width: `${Math.max(right - left, 1.5)}%` };
};

const gradeClass = (grade: string | null | undefined) => {
  if (grade === "A") return "badge--accent";
  if (grade === "B") return "badge--live";
  if (grade === "C") return "badge--warn";
  if (grade === "D") return "badge--warn";
  return "";
};

const statusText = (status: string | null) => {
  if (status === "ok") return "已入库";
  if (status === "degraded") return "部分降级";
  return status ?? "—";
};

const recalc = async () => {
  running.value = true;
  try {
    await runTimeline();
    await refresh();
  } finally {
    running.value = false;
  }
};

/* ── 图表：GDP 份额与储备份额 ─────────────────────────────────────────── */

const GDP_POWERS = ["china", "india", "usa", "uk", "netherlands"] as const;
const GDP_COLORS: Record<string, string> = {
  china: "#F0544F",
  india: "#F5A524",
  usa: "#4CC2FF",
  uk: "#2FBF71",
  netherlands: "#A78BFA",
};

const reservePowers = computed(() => {
  const rows = payload.value?.powers.reserve ?? [];
  return Array.from(new Set(rows.map((item) => item.power)));
});
const RESERVE_COLORS: Record<string, string> = {
  usd: "#4CC2FF",
  gbp: "#F0544F",
  eur: "#2FBF71",
  cny: "#F5A524",
};

const lineOption = (
  points: Array<{ power: string; power_label: string; year: number; value: number }>,
  powers: readonly string[],
  colors: Record<string, string>,
  unit: string,
): EChartsOption => {
  const years = Array.from(new Set(points.map((item) => item.year))).sort((a, b) => a - b);
  const labelOf = (power: string) => points.find((item) => item.power === power)?.power_label ?? power;
  return {
    grid: { left: 44, right: 16, top: 28, bottom: 30 },
    tooltip: { trigger: "axis", valueFormatter: (value) => `${value}${unit}` },
    legend: { top: 0, right: 0, textStyle: { color: "#93A4B8", fontSize: 10 }, itemWidth: 10, itemHeight: 8 },
    xAxis: {
      type: "category",
      data: years,
      axisLine: { lineStyle: { color: "rgba(148,163,184,.25)" } },
      axisLabel: { color: "#64748B", fontSize: 10 },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#64748B", fontSize: 10, formatter: `{value}${unit}` },
      splitLine: { lineStyle: { color: "rgba(148,163,184,.10)" } },
    },
    series: powers.map((power, index) => ({
      name: labelOf(power),
      type: "line" as const,
      smooth: true,
      symbol: "circle",
      symbolSize: 4,
      connectNulls: false,
      lineStyle: { width: index === 0 ? 2.2 : 1.6, color: colors[power] ?? "#93A4B8" },
      itemStyle: { color: colors[power] ?? "#93A4B8" },
      data: years.map((year) => points.find((item) => item.power === power && item.year === year)?.value ?? null),
    })),
  };
};

const gdpOption = computed<EChartsOption>(() =>
  lineOption(
    (payload.value?.powers.gdp ?? []).filter((item) => (GDP_POWERS as readonly string[]).includes(item.power)),
    GDP_POWERS,
    GDP_COLORS,
    "%",
  ),
);

const reserveOption = computed<EChartsOption>(() =>
  lineOption(
    payload.value?.powers.reserve ?? [],
    reservePowers.value,
    RESERVE_COLORS,
    "%",
  ),
);
</script>

<style scoped>
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
@media (max-width: 1180px) {
  .grid-2 {
    grid-template-columns: minmax(0, 1fr);
  }
}

.tl-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.seg {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.seg-btn {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 10px;
  padding: 4px 8px;
  cursor: pointer;
  white-space: nowrap;
}
.seg-btn + .seg-btn {
  border-left: 1px solid var(--border);
}
.seg-btn.is-on {
  background: rgba(76, 194, 255, 0.12);
  color: var(--text);
}

.timeline {
  position: relative;
  padding: 22px 0 22px 92px;
}
.era-bands {
  position: absolute;
  left: 92px;
  right: 0;
  top: 0;
  height: 20px;
  pointer-events: none;
}
.era-band {
  position: absolute;
  top: 0;
  height: 16px;
  border-radius: 3px;
  opacity: 0.32;
}
.era-band--0 {
  background: #4cc2ff;
}
.era-band--1 {
  background: #f5a524;
}
.era-band--2 {
  background: #a78bfa;
}
.era-band--3 {
  background: #2fbf71;
}
.era-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin-top: 2px;
  padding-left: 92px;
  font-size: 9.5px;
  color: var(--muted);
}
.era-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
}
.era-legend-item em {
  color: var(--dim);
  font-style: normal;
  font-family: var(--mono);
  font-size: 9px;
}
.era-legend-chip {
  width: 12px;
  height: 7px;
  border-radius: 2px;
  opacity: 0.55;
}
.era-legend-chip.era-band--0 {
  background: #4cc2ff;
}
.era-legend-chip.era-band--1 {
  background: #f5a524;
}
.era-legend-chip.era-band--2 {
  background: #a78bfa;
}
.era-legend-chip.era-band--3 {
  background: #2fbf71;
}

.lanes {
  position: relative;
}
.lane {
  position: relative;
  height: 46px;
  border-top: 1px dashed var(--border);
}
.lane:last-child {
  border-bottom: 1px dashed var(--border);
}
.lane-label {
  position: absolute;
  left: -92px;
  top: 12px;
  width: 84px;
  text-align: right;
  font-size: 10px;
  color: var(--muted);
}
.lane-track {
  position: absolute;
  inset: 0;
}

.tl-dot {
  position: absolute;
  width: 11px;
  height: 11px;
  margin-left: -5.5px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  z-index: 2;
}
.tl-dot-core {
  display: block;
  width: 7px;
  height: 7px;
  margin: 2px;
  border-radius: 50%;
  background: #4cc2ff;
  box-shadow: 0 0 0 3px rgba(76, 194, 255, 0.14);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.tl-dot:hover .tl-dot-core,
.tl-dot.is-active .tl-dot-core {
  transform: scale(1.35);
  box-shadow: 0 0 0 4px rgba(76, 194, 255, 0.24);
}
.tl-dot--B .tl-dot-core {
  background: #f5a524;
  box-shadow: 0 0 0 3px rgba(245, 165, 36, 0.14);
}
.tl-dot--S .tl-dot-core {
  background: #2fbf71;
  box-shadow: 0 0 0 3px rgba(47, 191, 113, 0.14);
}
.tl-dot--E .tl-dot-core {
  background: #f0544f;
  box-shadow: 0 0 0 3px rgba(240, 84, 79, 0.14);
}

.axis {
  position: absolute;
  left: 92px;
  right: 0;
  bottom: 0;
  height: 16px;
}
.axis-tick {
  position: absolute;
  transform: translateX(-50%);
  font-size: 9px;
  color: var(--dim);
  font-family: var(--mono);
}

.tl-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  padding-left: 92px;
  font-size: 10px;
  color: var(--muted);
}
.tl-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.tl-legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #4cc2ff;
}
.tl-legend-dot.tl-dot--B {
  background: #f5a524;
}
.tl-legend-dot.tl-dot--S {
  background: #2fbf71;
}
.tl-legend-dot.tl-dot--E {
  background: #f0544f;
}
.tl-legend-note {
  margin-left: auto;
  color: var(--dim);
}

.chart-note {
  margin-top: 6px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--muted);
}

.dim-table {
  display: grid;
  gap: 8px;
}
.dim-row {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.dim-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.dim-name {
  font-size: 11px;
  color: var(--text);
}
.dim-value {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--accent);
  margin-left: auto;
}
.dim-judge {
  margin-top: 3px;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.55;
}
.dim-anchor {
  margin-top: 2px;
  font-size: 9.5px;
  color: var(--dim);
}

.analog-list {
  display: grid;
  gap: 10px;
}
.analog {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.analog-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.analog-name {
  font-size: 11px;
  color: var(--text);
}
.analog-sim {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 11px;
  color: var(--warn);
}
.analog-bar {
  height: 3px;
  margin: 5px 0 7px;
  border-radius: 2px;
  background: var(--surface-3);
  overflow: hidden;
}
.analog-bar i {
  display: block;
  height: 100%;
  background: var(--warn);
}
.analog-block {
  display: flex;
  gap: 6px;
  margin-top: 3px;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.5;
}
.analog-tag {
  flex: none;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 9px;
  line-height: 14px;
}
.analog-tag--same {
  background: rgba(76, 194, 255, 0.14);
  color: var(--accent);
}
.analog-tag--diff {
  background: rgba(240, 84, 79, 0.14);
  color: var(--up);
}

.era-lesson {
  max-width: 320px;
  white-space: normal;
  font-size: 10px;
  line-height: 1.5;
  color: var(--muted);
}

.lesson-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
@media (max-width: 1100px) {
  .lesson-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
.lesson {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.lesson-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.lesson-name {
  font-size: 11px;
  color: var(--text);
}
.lesson-mech {
  margin: 5px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--muted);
}
.lesson-calc {
  margin: 4px 0 0;
  font-size: 9.5px;
  line-height: 1.5;
  color: var(--dim);
}
.lesson-calc span {
  margin-right: 5px;
  color: var(--accent);
}

.degraded-note {
  margin: 10px 0 0;
  padding: 8px 10px;
  border: 1px solid rgba(245, 165, 36, 0.35);
  border-radius: 8px;
  background: rgba(245, 165, 36, 0.08);
  font-size: 10px;
  line-height: 1.6;
  color: var(--warn);
}
.foot-note {
  margin: 8px 0 0;
  font-size: 9.5px;
  line-height: 1.7;
  color: var(--dim);
}

/* 抽屉 */
.event-mask {
  position: fixed;
  inset: 0;
  z-index: 80;
  background: rgba(3, 7, 12, 0.55);
  display: flex;
  justify-content: flex-end;
}
.event-drawer {
  width: 560px;
  max-width: 92vw;
  height: 100%;
  background: var(--surface);
  border-left: 1px solid var(--border-strong);
  display: flex;
  flex-direction: column;
  box-shadow: -18px 0 40px rgba(0, 0, 0, 0.45);
}
.event-head {
  position: relative;
  padding: 18px 56px 14px 18px;
  border-bottom: 1px solid var(--border);
}
.event-head-text {
  min-width: 0;
}
.event-close {
  position: absolute;
  top: 12px;
  right: 12px;
}
.event-eyebrow {
  font-size: 10px;
  color: var(--dim);
  font-family: var(--mono);
}
.event-title {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.55;
}
.event-body {
  flex: 1;
  overflow: auto;
  padding: 14px 18px 24px;
}
.event-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.event-section {
  margin-top: 16px;
}
.event-section h3 {
  margin: 0 0 6px;
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
}
.event-section p {
  margin: 0;
  font-size: 11px;
  line-height: 1.75;
  color: var(--muted);
}
.event-source a {
  color: var(--accent);
  word-break: break-all;
}
.event-muted {
  margin-top: 6px !important;
  font-size: 9.5px !important;
  color: var(--dim) !important;
}
</style>
