<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="history.open" class="hist-wrap" @click.self="history.close()">
        <div class="hist-panel" role="dialog" aria-modal="true" aria-label="历史走势">
          <div class="hist-head">
            <div class="hist-title-wrap">
              <div class="hist-title">{{ history.name }}<span class="hist-key">（{{ history.key }}）</span></div>
              <div class="hist-meta">
                {{ history.loading ? "加载中…" : metaText }}
              </div>
            </div>
            <div class="hist-ranges">
              <button
                v-for="item in HISTORY_RANGES"
                :key="item.value"
                type="button"
                :class="{ active: history.range === item.value }"
                @click="history.setRange(item.value)"
              >
                {{ item.label }}
              </button>
            </div>
            <button class="icon-btn" type="button" aria-label="关闭" @click="history.close()">
              <svg class="ic"><use href="#i-close" /></svg>
            </button>
          </div>
          <div class="hist-body">
            <ErrorState v-if="history.error" :error="history.error" @retry="reload" />
            <template v-else>
              <EChart :option="chartOption" :height="320" :loading="history.loading" />
              <div v-if="history.stats" class="hist-stats">
                <span>最新 <b>{{ valueText(history.stats.last) }}</b></span>
                <span>{{ history.rangeLabel }}变化 <b>{{ signed(history.stats.diff) }}{{ unitSuffix }}</b></span>
                <span>区间涨跌 <b>{{ signed(history.stats.pct) }}%</b></span>
                <span>区间低 / 高 <b>{{ valueText(history.stats.min) }} / {{ valueText(history.stats.max) }}</b></span>
                <span>样本 <b>{{ history.stats.count }}</b></span>
                <span>区间 <b>{{ fmtDate(history.stats.from.toISOString()) }} ~ {{ fmtDate(history.stats.to.toISOString()) }}</b></span>
              </div>
            </template>
          </div>
          <div class="hist-foot">
            <span class="hint">{{ history.kind === "instrument" ? "日线收盘价" : "宏观序列观测值" }} · 数据来自本地数据库</span>
            <span class="spacer"></span>
            <button class="btn btn--sm btn--ghost" type="button" @click="history.close()">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue";
import type { EChartsOption } from "echarts";
import EChart from "@/components/charts/EChart.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import { HISTORY_RANGES, useHistoryStore } from "@/stores/history";
import { usePrefsStore } from "@/stores/prefs";
import { fmtDate } from "@/composables/useFormat";

const history = useHistoryStore();
const prefs = usePrefsStore();

/** ECharts 不解析 CSS 变量：从当前主题计算真实色值（切主题/涨跌色时自动重算）。 */
function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

const palette = computed(() => {
  // 显式依赖，主题或涨跌配色变化时重算图表
  void prefs.resolvedTheme;
  void prefs.updown;
  const up = cssVar("--up", "#F0544F");
  const down = cssVar("--down", "#2FBF71");
  return {
    upColor: prefs.updown === "green" ? down : up,
    downColor: prefs.updown === "green" ? up : down,
    muted: cssVar("--muted", "#93A4B8"),
    border: cssVar("--border", "rgba(148,163,184,.22)"),
    surface: cssVar("--surface", "#111721"),
    text: cssVar("--text", "#E6EDF5"),
    surface2: cssVar("--surface-2", "#172030"),
  };
});

const unitSuffix = computed(() => {
  if (history.unit === "%") return "pp";
  if (history.unit === "pp") return "pp";
  return history.unit ? ` ${history.unit}` : "";
});

const metaText = computed(() => {
  if (!history.stats) return history.error ?? "暂无数据";
  return `${history.stats.count} 个点 · ${fmtDate(history.stats.from.toISOString())} ~ ${fmtDate(history.stats.to.toISOString())}`;
});

function valueText(value: number): string {
  const text = Number(value).toFixed(2);
  if (history.unit === "%") return `${text}%`;
  if (history.unit === "pp") return `${text}pp`;
  return history.unit ? `${text} ${history.unit}` : text;
}

function signed(value: number): string {
  return `${value > 0 ? "+" : ""}${Number(value).toFixed(2)}`;
}

const chartOption = computed<EChartsOption>(() => {
  const points = history.visiblePoints;
  const colors = palette.value;
  if (!points.length) {
    return { series: [] } as EChartsOption;
  }
  const dates = points.map((point) => fmtDate(new Date(point.t).toISOString()));
  const values = points.map((point) => point.v);
  const rising = values[values.length - 1] >= values[0];
  const color = rising ? colors.upColor : colors.downColor;
  return {
    animationDuration: 350,
    grid: { left: 54, right: 20, top: 16, bottom: 44 },
    tooltip: {
      trigger: "axis",
      backgroundColor: colors.surface,
      borderColor: colors.border,
      textStyle: { color: colors.text, fontSize: 11 },
      valueFormatter: (value) => valueText(Number(value)),
    },
    xAxis: {
      type: "category",
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.muted, fontSize: 9, hideOverlap: true },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      splitLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.muted, fontSize: 9, formatter: (value: number) => valueText(value) },
    },
    dataZoom: [
      { type: "inside", throttle: 40 },
      {
        type: "slider",
        height: 14,
        bottom: 8,
        borderColor: "transparent",
        backgroundColor: colors.surface2,
        dataBackground: { lineStyle: { color: colors.muted, opacity: 0.4 }, areaStyle: { color: colors.muted, opacity: 0.12 } },
        selectedDataBackground: { lineStyle: { color: colors.upColor }, areaStyle: { color: colors.upColor, opacity: 0.12 } },
      },
    ],
    series: [
      {
        type: "line",
        data: values,
        showSymbol: false,
        smooth: false,
        lineStyle: { color, width: 1.8 },
        areaStyle: { color, opacity: 0.1 },
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: colors.muted, type: "dashed", opacity: 0.45 },
          data: [{ type: "average", label: { show: false } }],
        },
      },
    ],
  } as EChartsOption;
});

function reload(): void {
  if (history.key) void history.openHistory(history.kind, history.key, history.name, history.unit);
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") history.close();
}

watch(
  () => history.open,
  (open) => {
    document.body.style.overflow = open ? "hidden" : "";
    if (open) document.addEventListener("keydown", onKeydown);
    else document.removeEventListener("keydown", onKeydown);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  document.body.style.overflow = "";
  document.removeEventListener("keydown", onKeydown);
});
</script>

<style scoped>
.hist-wrap {
  position: fixed;
  inset: 0;
  z-index: 75;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(3, 7, 12, 0.58);
  backdrop-filter: blur(2px);
}
.hist-panel {
  width: min(1080px, 96vw);
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  box-shadow: var(--shadow-pop);
}
.hist-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.hist-title-wrap {
  min-width: 0;
}
.hist-title {
  font-size: 14px;
  font-weight: 650;
}
.hist-key {
  color: var(--dim);
  font-size: 11px;
  font-family: var(--mono);
  font-weight: 400;
}
.hist-meta {
  margin-top: 2px;
  font-size: 10px;
  color: var(--dim);
  font-family: var(--mono);
}
.hist-ranges {
  margin-left: auto;
  display: flex;
  gap: 3px;
}
.hist-ranges button {
  height: 25px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10.5px;
  cursor: pointer;
}
.hist-ranges button:hover {
  color: var(--text);
}
.hist-ranges button.active {
  color: var(--accent);
  border-color: var(--accent-line);
  background: var(--accent-weak);
}
.hist-body {
  padding: 8px 12px 0;
  overflow-y: auto;
}
.hist-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  padding: 6px 10px 12px;
  font-size: 10.5px;
  color: var(--dim);
}
.hist-stats b {
  color: var(--text);
  font-family: var(--mono);
  font-weight: 600;
}
.hist-foot {
  display: flex;
  align-items: center;
  padding: 9px 16px;
  border-top: 1px solid var(--border);
}
.hint {
  font-size: 10px;
  color: var(--dim);
}
.spacer {
  flex: 1;
}
</style>
