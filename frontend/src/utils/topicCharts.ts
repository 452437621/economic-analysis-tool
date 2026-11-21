/** 专题图表的 ECharts option 构建（后端给数据，前端给主题）。 */
import type { EChartsOption } from "echarts";
import type { TopicChartSpec } from "@/api/types";
import { buildGoldPalette, type GoldPalette } from "@/utils/goldCharts";

export type TopicRange = "1m" | "3m" | "6m" | "1y" | "2y" | "3y" | "5y" | "all";

export const TOPIC_RANGES: Array<{ value: TopicRange; label: string }> = [
  { value: "1m", label: "1月" },
  { value: "3m", label: "3月" },
  { value: "6m", label: "6月" },
  { value: "1y", label: "1年" },
  { value: "2y", label: "2年" },
  { value: "3y", label: "3年" },
  { value: "5y", label: "5年" },
  { value: "all", label: "全部" },
];

const RANGE_DAYS: Record<Exclude<TopicRange, "all">, number> = {
  "1m": 31,
  "3m": 92,
  "6m": 183,
  "1y": 366,
  "2y": 731,
  "3y": 1096,
  "5y": 1826,
};

export function topicPalette(updown: "red" | "green"): GoldPalette {
  return buildGoldPalette(updown);
}

function rangeStart(dates: string[], range: TopicRange): number {
  if (range === "all" || !dates.length) return 0;
  const days = RANGE_DAYS[range as Exclude<TopicRange, "all">] ?? 366;
  const last = new Date(dates[dates.length - 1]).getTime();
  if (!Number.isFinite(last)) return 0;
  const cutoff = last - days * 86400_000;
  const index = dates.findIndex((item) => new Date(item).getTime() >= cutoff);
  return index < 0 ? 0 : index;
}

function numberAxis(unit: string | undefined, palette: GoldPalette): Record<string, unknown> {
  return {
    type: "value",
    scale: true,
    axisLabel: {
      formatter: (value: number) => {
        if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(1)}万`;
        if (Math.abs(value) >= 100) return value.toFixed(0);
        return value.toFixed(2);
      },
      color: palette.muted,
      fontSize: 10,
    },
    splitLine: { lineStyle: { color: "rgba(148,163,184,.12)" } },
    name: unit,
    nameTextStyle: { color: palette.muted, fontSize: 10 },
  };
}

function markColor(name: string | undefined, palette: GoldPalette): string {
  if (name === "warn") return palette.warn;
  if (name === "up") return palette.up;
  if (name === "down") return palette.down;
  return palette.accent;
}

export function chartHasData(spec: TopicChartSpec): boolean {
  if (typeof spec.hasData === "boolean") return spec.hasData;
  if (spec.kind === "candlestick") {
    return (spec.ohlc ?? []).some((row) => row.some((value) => value != null));
  }
  return (spec.series ?? []).some((item) => item.values.some((value) => value != null));
}

export function buildTopicChartOption(
  spec: TopicChartSpec,
  palette: GoldPalette,
  range: TopicRange = "1y",
): EChartsOption {
  const dates = spec.dates ?? [];
  const start = rangeStart(dates, range);
  const visibleDates = dates.slice(start);
  const seriesList: Array<Record<string, unknown>> = [];
  const axes: Array<Record<string, unknown>> = [];

  const addMarks = (target: Record<string, unknown>) => {
    if (!spec.marks?.length) return;
    target.markLine = {
      silent: true,
      symbol: "none",
      label: { color: palette.muted, fontSize: 9, formatter: "{b}" },
      data: spec.marks.map((mark) => ({
        yAxis: mark.value,
        name: mark.label ?? "",
        lineStyle: { color: markColor(mark.color, palette), type: "dashed", width: 1 },
      })),
    };
  };

  const addBands = (target: Record<string, unknown>) => {
    const bands = spec.bands;
    if (!bands?.ok) return;
    const low = bands.p25 ?? bands.p10;
    const high = bands.p75 ?? bands.p90;
    if (low == null || high == null) return;
    target.markArea = {
      silent: true,
      itemStyle: { color: palette.accent, opacity: 0.08 },
      label: { show: false },
      data: [[{ yAxis: low }, { yAxis: high }]],
    };
  };

  if (spec.kind === "candlestick") {
    const ohlc = (spec.ohlc ?? []).slice(start);
    axes.push(numberAxis(spec.unit, palette));
    const hasVolume = (spec.series ?? []).some((item) => item.type === "bar" && item.axis === 1);
    if (hasVolume) axes.push({ ...numberAxis("成交量", palette), splitLine: { show: false } });
    const candle: Record<string, unknown> = {
      name: "K 线",
      type: "candlestick",
      data: ohlc,
      itemStyle: {
        color: palette.up,
        color0: palette.down,
        borderColor: palette.up,
        borderColor0: palette.down,
      },
    };
    addMarks(candle);
    seriesList.push(candle);
    for (const item of spec.series ?? []) {
      seriesList.push({
        name: item.name,
        type: item.type ?? "bar",
        yAxisIndex: item.axis ?? 0,
        data: item.values.slice(start),
        itemStyle: { color: palette.muted, opacity: 0.5 },
        barMaxWidth: 8,
      });
    }
  } else {
    const axisCount = Math.max(1, ...(spec.series ?? []).map((item) => (item.axis ?? 0) + 1));
    for (let index = 0; index < axisCount; index += 1) {
      axes.push(numberAxis(index === 0 ? spec.unit : "", palette));
    }
    (spec.series ?? []).forEach((item, index) => {
      const series: Record<string, unknown> = {
        name: item.name,
        type: item.type ?? (spec.kind === "bar" ? "bar" : "line"),
        yAxisIndex: item.axis ?? 0,
        data: item.values.slice(start),
        showSymbol: false,
        connectNulls: true,
        lineStyle: { width: 1.7 },
        barMaxWidth: 10,
      };
      if ((item.type ?? "line") === "line") {
        series.areaStyle = index === 0 && axisCount === 1 ? { opacity: 0.06 } : undefined;
      }
      if (index === 0) {
        addMarks(series);
        addBands(series);
      }
      seriesList.push(series);
    });
  }

  return {
    animationDuration: 320,
    grid: {
      left: 48,
      right: axes.length > 1 ? 56 : 16,
      // Reserve a legend row so it never sits on the top y-axis tick or axis name.
      top: 38,
      bottom: dates.length > 160 ? 44 : 24,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: spec.kind === "candlestick" ? "cross" : "line" },
      backgroundColor: palette.surface,
      borderColor: palette.border,
      textStyle: { color: palette.text, fontSize: 11 },
      valueFormatter: (value: unknown) =>
        typeof value === "number" ? value.toFixed(2) : String(value ?? "—"),
    },
    legend: {
      top: 3,
      left: "center",
      itemGap: 18,
      textStyle: { color: palette.muted, fontSize: 10, padding: [0, 0, 0, 2] },
      itemWidth: 12,
      itemHeight: 6,
    },
    xAxis: {
      type: "category",
      data: visibleDates,
      boundaryGap: spec.kind === "candlestick" || spec.kind === "bar",
      axisLabel: { color: palette.muted, fontSize: 9, hideOverlap: true },
      axisLine: { lineStyle: { color: palette.border } },
    },
    yAxis: axes,
    dataZoom:
      dates.length > 240
        ? [
            { type: "inside", start: 0, end: 100 },
            { type: "slider", height: 14, bottom: 2, borderColor: palette.border, fillerColor: "rgba(76,194,255,.12)" },
          ]
        : [],
    series: seriesList,
  } as EChartsOption;
}
