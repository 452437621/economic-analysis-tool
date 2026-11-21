/** 黄金研判的 ECharts 配置构建（颜色从 CSS 变量计算，参考 HistoryModal）。 */
import type { EChartsOption } from "echarts";
import type { GoldSeriesPoint } from "@/api/types";
import { fmtDate, fmtInt, fmtNumber } from "@/composables/useFormat";
import { cutByRange, type HistoryRange } from "@/stores/history";

export const GOLD_PRICE_LABEL = "伦敦金价";

export function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export interface GoldPalette {
  up: string;
  down: string;
  muted: string;
  border: string;
  surface: string;
  text: string;
  accent: string;
  warn: string;
  gold: string;
}

export function buildGoldPalette(updown: "red" | "green"): GoldPalette {
  const upRaw = cssVar("--up", "#F0544F");
  const downRaw = cssVar("--down", "#2FBF71");
  return {
    up: updown === "green" ? downRaw : upRaw,
    down: updown === "green" ? upRaw : downRaw,
    muted: cssVar("--muted", "#93A4B8"),
    border: cssVar("--border", "rgba(148,163,184,.22)"),
    surface: cssVar("--surface", "#111721"),
    text: cssVar("--text", "#E6EDF5"),
    accent: cssVar("--accent", "#4CC2FF"),
    warn: cssVar("--warn", "#F5A524"),
    gold: cssVar("--gold", "#E7B84B"),
  };
}

export interface SeriesSpec {
  code: string;
  label: string;
  color: string;
  axis?: number;
  format: (value: number) => string;
}
export interface AxisSpec {
  format: (value: number) => string;
}
export interface ChartCard {
  key: string;
  title: string;
  unit: string;
  wide?: boolean;
  height: number;
  codes: string[];
  legend: Array<{ label: string; cls: string; available: boolean }>;
  note: string;
  emptyText: string;
  emptyHint: string;
  option: EChartsOption;
  hasData: boolean;
  meta: string;
}

export function seriesPoints(
  code: string,
  series: Record<string, GoldSeriesPoint[]> | undefined,
  range: HistoryRange,
): Array<{ t: number; v: number }> {
  const raw = series?.[code] ?? [];
  const points: Array<{ t: number; v: number }> = [];
  for (const point of raw) {
    const time = new Date(point.t).getTime();
    if (Number.isFinite(time) && Number.isFinite(point.v)) points.push({ t: time, v: point.v });
  }
  return cutByRange(points.sort((a, b) => a.t - b.t), range);
}

export function buildChartOption(
  specs: SeriesSpec[],
  axes: AxisSpec[],
  palette: GoldPalette,
  series: Record<string, GoldSeriesPoint[]> | undefined,
  range: HistoryRange,
  zeroLine = false,
): EChartsOption {
  const colors = palette;
  const formatters = new Map<string, (value: number) => string>();
  const seriesList = specs.map((spec) => {
    formatters.set(spec.label, spec.format);
    const points = seriesPoints(spec.code, series, range);
    const singleAxis = spec.axis === undefined;
    return {
      name: spec.label,
      type: "line" as const,
      yAxisIndex: spec.axis ?? 0,
      data: points.map((point) => [point.t, point.v]),
      showSymbol: points.length <= 2,
      symbolSize: 5,
      connectNulls: true,
      lineStyle: { color: spec.color, width: 1.7 },
      itemStyle: { color: spec.color },
      areaStyle: singleAxis ? { color: spec.color, opacity: 0.07 } : undefined,
      markLine:
        zeroLine && singleAxis
          ? {
              silent: true,
              symbol: "none" as const,
              label: { show: false },
              lineStyle: { color: colors.border, type: "dashed" as const },
              data: [{ yAxis: 0 }],
            }
          : undefined,
    };
  });
  return {
    animationDuration: 350,
    grid: { left: 48, right: axes.length > 1 ? 46 : 16, top: 14, bottom: 26 },
    tooltip: {
      trigger: "axis",
      backgroundColor: colors.surface,
      borderColor: colors.border,
      textStyle: { color: colors.text, fontSize: 11 },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? (params as unknown[]) : [params];
        if (!list.length) return "";
        const first = list[0] as { axisValue?: number | string } | undefined;
        const time = Number(first?.axisValue);
        const lines: string[] = [];
        if (Number.isFinite(time)) lines.push(fmtDate(new Date(time).toISOString()));
        for (const raw of list) {
          const item = raw as { seriesName?: string; value?: unknown; marker?: string };
          const pair = Array.isArray(item.value) ? (item.value as [number, number]) : null;
          const value = pair ? Number(pair[1]) : Number(item.value);
          const format = formatters.get(item.seriesName ?? "") ?? ((input: number) => fmtNumber(input, 2));
          lines.push(`${item.marker ?? ""}${item.seriesName ?? ""} ${format(value)}`);
        }
        return lines.join("<br/>");
      },
    },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { show: false },
      axisLabel: { color: colors.muted, fontSize: 9, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: axes.map((axis) => ({
      type: "value",
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: colors.border, opacity: 0.55 } },
      axisLabel: { color: colors.muted, fontSize: 9, formatter: (value: number) => axis.format(value) },
    })),
    series: seriesList,
  } as EChartsOption;
}

export const contractsAxis = (value: number): string => {
  if (Math.abs(value) >= 1000) return `${Math.round(value / 1000)}k`;
  return fmtNumber(value, 0);
};

export function buildGoldChartCards(params: {
  series: Record<string, GoldSeriesPoint[]> | undefined;
  range: HistoryRange;
  overlays: Record<string, boolean>;
  palette: GoldPalette;
}): ChartCard[] {
  const { series, range, overlays, palette: colors } = params;
  const swapAvailable = seriesPoints("COT_SWAP_NET", series, range).length > 0;
  const priceAvailable = seriesPoints("GOLD_PRICE_USD", series, range).length > 0;
  const priceSpec = (axis: number): SeriesSpec => ({
    code: "GOLD_PRICE_USD",
    label: GOLD_PRICE_LABEL,
    color: colors.gold,
    axis,
    format: (value) => `${fmtNumber(value, 1)} 美元/盎司`,
  });
  const priceLegend = { label: GOLD_PRICE_LABEL, cls: "lg-g", available: priceAvailable };
  const cardCodes = (key: string, base: string[]): string[] =>
    overlays[key] ? [...base, "GOLD_PRICE_USD"] : base;
  const cardLegend = (
    key: string,
    base: Array<{ label: string; cls: string; available: boolean }>,
  ): Array<{ label: string; cls: string; available: boolean }> =>
    overlays[key] ? [...base, priceLegend] : base;
  const cardOption = (
    key: string,
    specs: SeriesSpec[],
    axes: AxisSpec[],
    zeroLine = false,
  ): EChartsOption => {
    if (!overlays[key]) return buildChartOption(specs, axes, colors, series, range, zeroLine);
    return buildChartOption(
      [...specs, priceSpec(axes.length)],
      [...axes, { format: (value) => fmtNumber(value, 0) }],
      colors,
      series,
      range,
      zeroLine,
    );
  };
  const cards: Array<Omit<ChartCard, "hasData" | "meta">> = [
    {
      key: "price-real",
      title: "美债 10Y 实际利率",
      unit: "%",
      wide: true,
      height: 250,
      codes: cardCodes("price-real", ["US10Y_REAL"]),
      legend: cardLegend("price-real", [{ label: "10Y 实际利率", cls: "lg-a", available: true }]),
      note: overlays["price-real"] ? "" : "可叠加金价对比",
      emptyText: "暂无实际利率序列",
      emptyHint: "等待黄金采集任务写入利率数据，或切换更长的时间范围。",
      option: cardOption(
        "price-real",
        [
          {
            code: "US10Y_REAL",
            label: "10Y 实际利率",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 2)}%`,
          },
        ],
        [{ format: (value) => `${fmtNumber(value, 1)}%` }],
      ),
    },
    {
      key: "etf-tonnes",
      title: "全球黄金 ETF 持仓",
      unit: "吨",
      height: 230,
      codes: cardCodes("etf-tonnes", ["ETF_GLOBAL_TONNES"]),
      legend: cardLegend("etf-tonnes", [{ label: "ETF 持仓", cls: "lg-a", available: true }]),
      note: "",
      emptyText: "暂无 ETF 持仓序列",
      emptyHint: "WGC 全球黄金 ETF 数据未采集，或当前时间范围无数据。",
      option: cardOption(
        "etf-tonnes",
        [
          {
            code: "ETF_GLOBAL_TONNES",
            label: "ETF 持仓",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 0)} 吨`,
          },
        ],
        [{ format: (value) => fmtNumber(value, 0) }],
      ),
    },
    {
      key: "lbma-tonnes",
      title: "伦敦金库黄金库存",
      unit: "吨",
      height: 230,
      codes: cardCodes("lbma-tonnes", ["LBMA_GOLD_TONNES"]),
      legend: cardLegend("lbma-tonnes", [{ label: "金库库存", cls: "lg-a", available: true }]),
      note: "",
      emptyText: "暂无伦敦金库库存序列",
      emptyHint: "LBMA 月度库存数据未采集，或当前时间范围无数据。",
      option: cardOption(
        "lbma-tonnes",
        [
          {
            code: "LBMA_GOLD_TONNES",
            label: "金库库存",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 0)} 吨`,
          },
        ],
        [{ format: (value) => fmtNumber(value, 0) }],
      ),
    },
    {
      key: "cftc-net",
      title: "CFTC 持仓（管理基金 / 掉期商）",
      unit: "张",
      height: 230,
      codes: cardCodes("cftc-net", ["COT_MONEY_NET", "COT_SWAP_NET"]),
      legend: cardLegend("cftc-net", [
        { label: "管理基金净持仓", cls: "lg-a", available: true },
        { label: "掉期商净持仓", cls: "lg-m", available: swapAvailable },
      ]),
      note: swapAvailable ? "" : "掉期商序列缺失",
      emptyText: "暂无 CFTC 持仓序列",
      emptyHint: "等待 CFTC COT 采集写入数据，或当前时间范围无数据。",
      option: cardOption(
        "cftc-net",
        [
          {
            code: "COT_MONEY_NET",
            label: "管理基金净持仓",
            color: colors.accent,
            format: (value) => `${fmtInt(value)} 张`,
          },
          {
            code: "COT_SWAP_NET",
            label: "掉期商净持仓",
            color: colors.muted,
            format: (value) => `${fmtInt(value)} 张`,
          },
        ],
        [{ format: contractsAxis }],
        true,
      ),
    },
    {
      key: "cn-premium",
      title: "上海金溢价",
      unit: "%",
      height: 230,
      codes: cardCodes("cn-premium", ["CN_GOLD_PREMIUM_PCT"]),
      legend: cardLegend("cn-premium", [{ label: "上海金溢价", cls: "lg-a", available: true }]),
      note: "",
      emptyText: "暂无上海金溢价序列",
      emptyHint: "等待沪金与伦敦金折算价序列写入，或当前时间范围无数据。",
      option: cardOption(
        "cn-premium",
        [
          {
            code: "CN_GOLD_PREMIUM_PCT",
            label: "上海金溢价",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 2)}%`,
          },
        ],
        [{ format: (value) => `${fmtNumber(value, 2)}%` }],
        true,
      ),
    },
  ];
  return cards.map((card) => {
    const hasData = card.codes.some((code) => seriesPoints(code, series, range).length > 0);
    const primary = seriesPoints(card.codes[0], series, range);
    let meta = "暂无数据";
    if (primary.length) {
      const latest = Math.max(...card.codes.flatMap((code) => seriesPoints(code, series, range).map((point) => point.t)));
      meta = `${primary.length} 点 · 更新 ${fmtDate(new Date(latest).toISOString())}`;
    }
    return { ...card, hasData, meta };
  });
}
