<template>
  <div class="view active">
    <div class="page-head hst-head">
      <div class="hst-head-text">
        <div class="page-eyebrow">研究分析 · 世界长河</div>
        <h1 class="page-h1">世界长河 · 帝国与储备货币的更替</h1>
        <p class="hst-sub">1500–2100 · 四条帝国泳道 × 五类历史图层 · 点击任意年份或事件查看影响</p>
        <span class="gen-at">（生成于 {{ generatedLabel }}）</span>
      </div>
      <div class="page-actions hst-head-actions">
        <span class="badge badge--sm">示意数据</span>
        <span class="badge badge--sm">来源：达利欧《原则》</span>
        <span v-if="payload?.asof" class="badge badge--sm mono">数据日 {{ fmtDate(payload.asof) }}</span>
        <span v-if="payload?.status" class="badge badge--sm" :class="statusBadgeClass(payload.status)">{{ statusText(payload.status) }}</span>
        <button class="btn btn--sm" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中…" : "重新入库" }}
        </button>
      </div>
    </div>

    <SkeletonBlock v-if="!payload && loading" :rows="7" :cells="3" :height="16" />
    <template v-else>
      <ErrorState v-if="!payload && error" :error="error" @retry="refresh" />

      <div v-if="payload" class="kpi-grid">
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

      <HistoryTimelineChart :events="events" :eras="eras" :reserve="reservePoints" @select="openEvent">
        <HistoryEventDetail
          :event="selected"
          :related="relatedEvents"
          @close="clearSelection"
          @select="openEvent"
          @expand="detailOpen = true"
        />
      </HistoryTimelineChart>

      <template v-if="payload">
      <Drawer
        :open="detailOpen"
        title="事件详情"
        :sub="detailDrawerSub"
        @close="detailOpen = false"
      >
        <HistoryEventDetail
          :event="selected"
          :related="relatedEvents"
          :embedded="true"
          @close="detailOpen = false"
          @select="openEvent"
        />
      </Drawer>

      <section class="card">
        <div class="card-head">
          <span class="card-title">周期对照表</span>
          <span class="card-sub">每轮霸权的崛起 / 黄金期 / 转折 / 衰落与当前阶段 · 黄金期、转折、当前阶段由 timeline 数据集提供，未返回时显示「—」；短句为示意，不构成精确分期</span>
        </div>
        <div class="card-body">
          <EmptyState
            v-if="!eras.length"
            text="还没有霸权分期数据"
            hint="分期来自 timeline 数据集（eras 表）；执行「重新入库」抽取后出现。分期本身是叙事判断（C 级），不会由价格数据自动生成。"
          />
          <div v-else class="table-wrap hst-table-wrap">
            <table class="data-table hst-era-table">
              <thead>
                <tr>
                  <th>时期 / 国家（起止）</th>
                  <th>黄金期</th>
                  <th>转折</th>
                  <th>储备货币</th>
                  <th>当前阶段</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="era in eras" :key="era.id" :class="{ 'hst-era-now': era.id === currentEra?.id }">
                  <td>
                    <div class="hst-era-name">
                      <i :style="{ background: eraColor(era, eras.indexOf(era)) }" />
                      {{ era.name }}
                      <span v-if="era.id === currentEra?.id" class="badge badge--sm badge--accent">当前</span>
                    </div>
                    <div class="hst-era-range mono">{{ era.rise }}–{{ era.decline }}</div>
                  </td>
                  <td>
                    <span :class="{ 'hst-missing': !era.golden_age }">{{ fieldText(era.golden_age) }}</span>
                    <em v-if="era.peak" class="hst-era-note">峰值 {{ era.peak }}</em>
                  </td>
                  <td :class="{ 'hst-missing': !era.turning }">{{ fieldText(era.turning) }}</td>
                  <td class="hst-era-reserve">{{ era.reserve }}</td>
                  <td :class="{ 'hst-missing': !era.current_stage }">{{ era.current_stage || "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <div class="hst-grid-2">
        <section class="card">
          <div class="card-head">
            <span class="card-title">当下坐标 · 六维对照</span>
            <span class="card-sub">把今天的读数放到历史锚点上比较；锚点本身来自叙事分期（C 级）</span>
          </div>
          <div class="card-body">
            <div class="hst-table-wrap">
              <EmptyState
                v-if="!dimensions.length"
                text="还没有当下坐标"
                hint="六维对照来自 timeline 推导（position.value.dimensions）；需先跑「重新入库」让 timeline run 读取 cycle 结果，两者都有数据后才会生成。"
              />
              <div v-else class="hst-dim-table">
                <div class="hst-dim-head">
                  <span>维度</span>
                  <span>历史锚点</span>
                  <span>当前</span>
                  <span>判断</span>
                  <span>证据级</span>
                </div>
                <div v-for="dim in dimensions" :key="dim.dimension" class="hst-dim-row">
                  <div class="hst-dim-name">{{ dim.dimension }}</div>
                  <div class="hst-dim-anchor">{{ dim.anchor }}</div>
                  <div class="hst-dim-cur">
                    <b class="mono">{{ dim.current }}</b>
                    <span class="hst-dim-bar">
                      <i :style="{ width: `${dimBar(dim.value)}%` }" />
                    </span>
                  </div>
                  <div class="hst-dim-judge">{{ dim.judgment }}</div>
                  <span class="badge badge--sm" :class="gradeClass(dim.grade)">{{ dim.grade }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <span class="card-title">历史类比</span>
            <span class="card-sub">相似度来自公开叙事对照，非量化匹配</span>
          </div>
          <div class="card-body">
            <EmptyState
              v-if="!analogs.length"
              text="暂无历史类比"
              hint="类比由 timeline 推导给出（position.value.analogs），依赖周期引擎的历史阶段读数；周期数据缺失时这里留空，不用占位叙事填空。"
            />
            <div v-else class="hst-analog-grid">
              <article v-for="analog in analogs" :key="analog.id" class="hst-analog">
                <div class="hst-analog-head">
                  <span class="hst-analog-name">{{ analog.name }}</span>
                  <span class="hst-analog-sim mono">{{ Math.round(analog.similarity * 100) }}%</span>
                </div>
                <div class="hst-analog-bar"><i :style="{ width: `${Math.round(analog.similarity * 100)}%` }" /></div>
                <div class="hst-analog-block">
                  <span class="hst-analog-tag hst-analog-tag--same">相似</span>
                  <span>{{ analog.similar.join("；") }}</span>
                </div>
                <div class="hst-analog-block">
                  <span class="hst-analog-tag hst-analog-tag--diff">不同</span>
                  <span>{{ analog.different.join("；") }}</span>
                </div>
              </article>
            </div>
          </div>
        </section>
      </div>

      <section class="card">
        <div class="card-head">
          <span class="card-title">十条历史规律</span>
          <span class="card-sub">每条都必须可观测、可证伪；「可计算」列说明如何落到本系统指标</span>
        </div>
        <div class="card-body">
          <EmptyState
            v-if="!lessons.length"
            text="还没有历史规律"
            hint="十条规律写在 timeline 数据集里（lesson 表），「重新入库」会随事件一起抽取；它们是对史料的归纳，不是模型训练产物。"
          />
          <div v-else class="hst-law-grid">
            <article v-for="lesson in lessons" :key="lesson.id" class="hst-law">
              <div class="hst-law-head">
                <span class="hst-law-num mono">{{ lesson.id }}</span>
                <span class="hst-law-name">{{ lesson.name }}</span>
              </div>
              <p class="hst-law-mech">{{ lesson.mechanism }}</p>
              <p class="hst-law-calc"><span>可计算</span>{{ lesson.computable }}</p>
            </article>
          </div>
        </div>
      </section>

      <p v-if="payload.degraded && payload.degraded_reasons.length" class="hst-degraded">
        <b>降级说明</b>
        {{ payload.degraded_reasons.slice(0, 4).map((item) => item.message).join("；") }}
      </p>
      <p class="hst-foot">
        口径声明：年表为 1500–2026 精选事件（非全集），A 级事件附公开来源；霸权分期与历史类同为叙事判断（C/D 级），用于辅助定位而非预测。
        运行 {{ payload.run_id ? payload.run_id.slice(0, 8) : "—" }}
      </p>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import EmptyState from "@/components/ui/EmptyState.vue";
import Drawer from "@/components/ui/Drawer.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import HistoryTimelineChart from "@/components/history/HistoryTimelineChart.vue";
import HistoryEventDetail from "@/components/history/HistoryEventDetail.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtInt, fmtNumber } from "@/composables/useFormat";
import { getTimelineOverview, runTimeline } from "@/api/endpoints";
import type {
  TimelineAnalog,
  TimelineDimension,
  TimelineEra,
  TimelineEventItem,
  TimelineLesson,
  TimelineOverview,
} from "@/api/types";

/** 本地扩展：后端并行开发中的新字段用可选链兜底，不改 api/types.ts。
 *  后端 golden_age / turning 目前是 [起, 止] 年份数组，也可能是字符串，统一用 fieldText 兜底。 */
type EraSpan = string | number | Array<string | number> | null;

interface EraExtended extends TimelineEra {
  golden_age?: EraSpan;
  turning?: EraSpan;
  current_stage?: string | null;
}

const { data, error, loading, refresh } = usePolling<TimelineOverview>(getTimelineOverview, {
  interval: 300_000,
});

const route = useRoute();
const router = useRouter();

const payload = computed(() => data.value);
const counts = computed(
  () => payload.value?.counts ?? { events: 0, eras: 0, lessons: 0, grades: {}, layers: {} },
);
const eras = computed<EraExtended[]>(() => (payload.value?.eras ?? []) as EraExtended[]);
const lessons = computed<TimelineLesson[]>(() => payload.value?.lessons ?? []);
const events = computed<TimelineEventItem[]>(() => payload.value?.events ?? []);
const reservePoints = computed(() => payload.value?.powers.reserve ?? []);
const dimensions = computed<TimelineDimension[]>(() => payload.value?.position?.value.dimensions ?? []);
const analogs = computed<TimelineAnalog[]>(() => payload.value?.position?.value.analogs ?? []);
const currentEra = computed<TimelineEra | null>(() => eras.value[eras.value.length - 1] ?? null);

const usdShare = computed(() => {
  const rows = reservePoints.value.filter((item) => item.power.toLowerCase() === "usd");
  return rows.length ? rows[rows.length - 1] : null;
});

/* ── 事件选中 / ?event= 深链 ─────────────────────────────────────────── */

const running = ref(false);
const selected = ref<TimelineEventItem | null>(null);
const detailOpen = ref(false);

/** timeline 接口生成时间；不做浏览器时间回退。 */
const generatedLabel = computed(() => {
  const iso = payload.value?.generated_at;
  return iso ? fmtDateTime(iso) : "—";
});

const detailDrawerSub = computed(() => {
  if (selected.value) return `${selected.value.year} 年 · ${selected.value.title}`;
  return "未选中事件";
});

const syncQuery = (id: string | null) => {
  const current = typeof route.query.event === "string" ? route.query.event : null;
  if (current === id) return;
  const query: Record<string, string | null | Array<string | null>> = { ...route.query };
  if (id) query.event = id;
  else delete query.event;
  void router.replace({ query });
};

const openEvent = (item: TimelineEventItem) => {
  selected.value = item;
  syncQuery(item.id);
};

const clearSelection = () => {
  selected.value = null;
  syncQuery(null);
};

watch(
  () => [events.value, route.query.event] as const,
  ([list, eventId]) => {
    if (typeof eventId === "string" && eventId) {
      const hit = list.find((item) => item.id === eventId);
      if (hit) selected.value = hit;
      return;
    }
    if (selected.value) selected.value = null;
  },
  { immediate: true },
);

const relatedEvents = computed<TimelineEventItem[]>(() => {
  if (!selected.value) return [];
  const { year, id } = selected.value;
  return events.value
    .filter((item) => item.id !== id && Math.abs(item.year - year) <= 20)
    .sort((a, b) => a.year - b.year)
    .slice(0, 6);
});

/* ── 时间轴辅助 ──────────────────────────────────────────────────────── */

const ERA_COLORS: Record<string, string> = {
  china_ming: "#2FBF71",
  iberia: "#F5A524",
  netherlands: "#A78BFA",
  uk: "#F0544F",
  usa: "#4CC2FF",
  multipolar: "#94A3B8",
};
const ERA_PALETTE = ["#4CC2FF", "#2FBF71", "#F5A524", "#A78BFA", "#F0544F", "#38BDF8"];

const eraColor = (era: TimelineEra, index: number) =>
  ERA_COLORS[era.id] ?? ERA_PALETTE[index % ERA_PALETTE.length];

const fieldText = (value: EraSpan | undefined) => {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) {
    const parts = value.filter((part) => part !== null && part !== undefined && part !== "");
    return parts.length ? parts.join("–") : "—";
  }
  return String(value);
};

const dimBar = (value: number | null) => {
  if (value === null || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, value));
};

const gradeClass = (grade: string | null | undefined) => {
  if (grade === "A") return "badge--accent";
  if (grade === "B") return "badge--live";
  if (grade === "C" || grade === "D") return "badge--warn";
  return "";
};

const statusText = (status: string | null) => {
  if (status === "ok") return "已入库";
  if (status === "degraded") return "部分降级";
  return status ?? "—";
};

const statusBadgeClass = (status: string | null) => {
  if (status === "ok") return "badge--live";
  if (status === "degraded") return "badge--warn";
  return "";
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

/* ── 图表：GDP 份额与储备份额已并入世界长河时间轴（HistoryTimelineChart） ── */
</script>

<style scoped>
.hst-head {
  flex-wrap: wrap;
}
.hst-head-text {
  min-width: 0;
}
.hst-sub {
  margin-top: 2px;
  font-size: 10.5px;
  color: var(--muted);
}
.hst-head-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}
.hst-grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 10px;
  margin-top: 10px;
}
.hst-table-wrap {
  overflow-x: hidden;
}
.hst-era-table thead th {
  white-space: nowrap;
}
.hst-era-table tbody td {
  white-space: normal;
  vertical-align: top;
  padding-top: 7px;
  padding-bottom: 7px;
  line-height: 1.5;
  font-size: 11px;
}
.hst-era-table tbody tr.hst-era-now td {
  background: color-mix(in srgb, var(--accent) 7%, transparent);
}
.hst-era-table tbody tr.hst-era-now td:first-child {
  box-shadow: inset 2px 0 0 var(--accent);
}
.hst-era-name {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text);
}
.hst-era-name i {
  width: 3px;
  height: 12px;
  border-radius: 2px;
}
.hst-era-range {
  margin-top: 1px;
  font-size: 9.5px;
  color: var(--dim);
}
.hst-era-note {
  display: block;
  margin-top: 1px;
  font-style: normal;
  font-size: 9px;
  color: var(--dim);
}
.hst-era-reserve {
  max-width: 210px;
}
.hst-missing {
  color: var(--dim);
}
.hst-dim-table {
  min-width: 0;
}
.hst-dim-head,
.hst-dim-row {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1.45fr) minmax(0, 1.15fr) minmax(0, 1.5fr) 52px;
  gap: 10px;
  align-items: start;
  padding: 7px 2px;
  border-bottom: 1px solid var(--border);
}
.hst-dim-head {
  padding-top: 0;
  padding-bottom: 5px;
  border-bottom: 1px solid var(--border-strong);
  font-size: 9.5px;
  color: var(--dim);
  letter-spacing: 0.3px;
}
.hst-dim-row:last-child {
  border-bottom: 0;
}
.hst-dim-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
}
.hst-dim-cur b {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hst-dim-bar {
  display: block;
  height: 3px;
  margin-top: 3px;
  border-radius: 999px;
  background: var(--surface-2);
  overflow: hidden;
}
.hst-dim-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}
.hst-dim-judge,
.hst-dim-anchor {
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--muted);
}
.hst-dim-anchor {
  color: var(--dim);
}
.hst-analog-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.hst-analog {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.hst-analog-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.hst-analog-name {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text);
}
.hst-analog-sim {
  font-size: 12px;
  font-weight: 650;
  color: var(--accent);
}
.hst-analog-bar {
  height: 3px;
  margin: 5px 0 7px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.hst-analog-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}
.hst-analog-block {
  display: flex;
  gap: 5px;
  margin-top: 5px;
  font-size: 10px;
  line-height: 1.55;
  color: var(--muted);
}
.hst-analog-tag {
  flex: none;
  font-size: 8.5px;
  padding: 0 4px;
  border-radius: 4px;
  border: 1px solid var(--border);
  align-self: flex-start;
}
.hst-analog-tag--same {
  color: var(--down-color);
  border-color: color-mix(in srgb, var(--down) 36%, transparent);
}
.hst-analog-tag--diff {
  color: var(--warn);
  border-color: color-mix(in srgb, var(--warn) 40%, transparent);
}
.hst-law-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.hst-law {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.hst-law-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.hst-law-num {
  flex: none;
  font-size: 9.5px;
  color: var(--accent);
  letter-spacing: 0.4px;
}
.hst-law-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.35;
}
.hst-law-mech {
  margin-top: 5px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--muted);
}
.hst-law-calc {
  margin-top: 6px;
  font-size: 9.5px;
  line-height: 1.5;
  color: var(--dim);
}
.hst-law-calc span {
  margin-right: 4px;
  padding: 0 4px;
  border-radius: 4px;
  border: 1px solid var(--border);
  font-size: 8.5px;
  color: var(--muted);
}
.hst-degraded {
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 32%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--warn) 8%, transparent);
  font-size: 10px;
  line-height: 1.6;
  color: var(--muted);
}
.hst-degraded b {
  margin-right: 6px;
  color: var(--warn);
}
.hst-foot {
  margin-top: 8px;
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
.spin {
  animation: hst-spin 0.9s linear infinite;
}
@keyframes hst-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1240px) {
  .hst-grid-2 {
    grid-template-columns: minmax(0, 1fr);
  }
  .hst-law-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .hst-analog-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 1024px) {
  .hst-grid-2 {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
