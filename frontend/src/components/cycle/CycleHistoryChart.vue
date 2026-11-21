<template>
  <section class="card cyc-history-card">
    <div class="card-head">
      <span class="card-title">分量历史轨迹</span>
      <span class="cyc-card-sub">{{ historyMonths.length }} 个月 · 月度末值 · 覆盖不足的分量留空</span>
      <div class="card-actions"><span class="cyc-card-sub mono">{{ historyRange }}</span></div>
    </div>
    <EChart v-if="chartHasData" :option="chartOption" :height="240" />
    <EmptyState v-else text="暂无历史轨迹" hint="至少有 24 个月数据后才会生成月度序列。" />
    <div class="card-foot">
      <span>历史轨迹用于判断「现在与过去哪里相似」，不作为拐点预测。</span>
      <span class="mono">样本从 {{ historyMonths[0] ?? "—" }} 起</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { EChartsOption } from "echarts";
import EChart from "@/components/charts/EChart.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { CycleHistory } from "@/api/types";
import type { RawOf } from "@/utils/cycleNormalize";

const props = defineProps<{
  history: RawOf<CycleHistory>;
  historyMonths: string[];
  historyRange: string;
}>();

const chartHasData = computed(() => {
  const series = props.history?.series;
  if (!series || typeof series !== "object") return false;
  return Object.values(series).some((points) => (Array.isArray(points) ? points : []).some((point) => point !== null));
});

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const chosen = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return chosen || fallback;
}

const CHART_COLORS: Record<string, string> = {
  DMI: "#F5A524",
  GROWTH: "#4CC2FF",
  INFLATION: "#F0544F",
  LIQUIDITY: "#2FBF71",
};

/** 序列语义色统一走 CSS 变量，保证深色 / 浅色主题下轨迹颜色一致可读。 */
const CHART_COLOR_VARS: Record<string, string> = {
  DMI: "--warn",
  GROWTH: "--accent",
  INFLATION: "--up",
  LIQUIDITY: "--down",
};

const chartOption = computed<EChartsOption>(() => {
  const months = props.historyMonths;
  const seriesData = (props.history?.series ?? {}) as Record<string, unknown>;
  const pointsOf = (key: string): Array<number | null> => {
    const raw = seriesData[key];
    return Array.isArray(raw) ? (raw as Array<number | null>) : [];
  };
  const keys = ["DMI", "GROWTH", "INFLATION", "LIQUIDITY"].filter((key) =>
    pointsOf(key).some((point) => point !== null),
  );
  return {
    grid: { left: 42, right: 16, top: 26, bottom: 28 },
    tooltip: {
      trigger: "axis",
      backgroundColor: cssVar("--surface-2", "#172030"),
      borderColor: cssVar("--border-strong", "#223047"),
      textStyle: { color: cssVar("--text", "#E6EDF5"), fontSize: 11 },
    },
    legend: {
      top: 2,
      left: 8,
      itemWidth: 10,
      itemHeight: 2,
      textStyle: { color: cssVar("--muted", "#93A4B8"), fontSize: 10 },
    },
    xAxis: {
      type: "category",
      data: months,
      axisLine: { lineStyle: { color: cssVar("--border", "rgba(148,163,184,.2)") } },
      axisLabel: {
        color: cssVar("--dim", "#64748B"),
        fontSize: 9,
        interval: Math.max(0, Math.floor(months.length / 6) - 1),
      },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: cssVar("--border", "rgba(148,163,184,.12)") } },
      axisLabel: { color: cssVar("--dim", "#64748B"), fontSize: 9 },
    },
    series: keys.map((key) => {
      const color = cssVar(CHART_COLOR_VARS[key] ?? "--accent", CHART_COLORS[key] ?? "#4CC2FF");
      return {
        name: key,
        type: "line" as const,
        data: pointsOf(key),
        smooth: true,
        connectNulls: false,
        showSymbol: false,
        lineStyle: { width: 1.6, color },
        itemStyle: { color },
      };
    }),
  };
});
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-history-card {
  margin-top: 10px;
}
</style>
