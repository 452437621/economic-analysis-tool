import { describe, expect, it } from "vitest";
import type { TopicChartSpec } from "@/api/types";
import { HISTORY_RANGES } from "@/stores/history";
import { TOPIC_RANGES, buildTopicChartOption, chartHasData } from "./topicCharts";
import type { GoldPalette } from "./goldCharts";

const palette: GoldPalette = {
  up: "#f00",
  down: "#0f0",
  muted: "#999",
  border: "#333",
  surface: "#111",
  text: "#eee",
  accent: "#09f",
  warn: "#fa0",
  gold: "#db4",
};

function dates(count: number): string[] {
  return Array.from({ length: count }, (_, index) => {
    const day = new Date(Date.UTC(2025, 0, 1 + index));
    return day.toISOString().slice(0, 10);
  });
}

const lineSpec: TopicChartSpec = {
  key: "line",
  title: "线图",
  kind: "line",
  unit: "%",
  dates: dates(300),
  series: [
    { name: "A", values: Array.from({ length: 300 }, (_, index) => index) },
    { name: "B", values: Array.from({ length: 300 }, (_, index) => 300 - index) },
  ],
  hasData: true,
};

describe("topicCharts", () => {
  it("slices every series by the selected range", () => {
    const option = buildTopicChartOption(lineSpec, palette, "1m") as any;
    const visible = option.xAxis.data.length;
    expect(visible).toBeGreaterThan(25);
    expect(visible).toBeLessThan(40);
    expect(option.series[0].data).toHaveLength(visible);
    expect(option.series[1].data).toHaveLength(visible);
  });

  it("builds candlesticks with an optional volume axis", () => {
    const spec: TopicChartSpec = {
      key: "kline",
      title: "K 线",
      kind: "candlestick",
      dates: dates(50),
      ohlc: Array.from({ length: 50 }, () => [1, 2, 0.5, 2.5]),
      series: [{ name: "成交量", type: "bar", axis: 1, values: Array.from({ length: 50 }, () => 100) }],
      hasData: true,
    };
    const option = buildTopicChartOption(spec, palette) as any;
    expect(option.series[0].type).toBe("candlestick");
    expect(option.yAxis).toHaveLength(2);
    expect(option.series[1].yAxisIndex).toBe(1);
  });

  it("applies bands and marks to the first series", () => {
    const spec: TopicChartSpec = {
      ...lineSpec,
      bands: { ok: true, p25: 10, p75: 90 },
      marks: [{ type: "line", value: 50, label: "成本", color: "warn" }],
    };
    const option = buildTopicChartOption(spec, palette) as any;
    expect(option.series[0].markArea).toBeTruthy();
    expect(option.series[0].markLine.data[0].yAxis).toBe(50);
  });

  it("detects empty charts and exposes all shared ranges", () => {
    expect(chartHasData(lineSpec)).toBe(true);
    expect(chartHasData({ ...lineSpec, series: [{ name: "A", values: [null, null] }], hasData: undefined })).toBe(false);
    const values = new Set(TOPIC_RANGES.map((item) => item.value));
    for (const range of HISTORY_RANGES) expect(values.has(range.value)).toBe(true);
  });
});
