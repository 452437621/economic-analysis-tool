import { describe, expect, it } from "vitest";
import { formatCell, providerLabel, providerState, signalClass, signalLabel } from "./topicFormat";

describe("topicFormat", () => {
  it("formats table cells by column format", () => {
    expect(formatCell(12.345, { key: "a", label: "A", format: "number", digits: 1 })).toBe("12.3");
    expect(formatCell(12.345, { key: "a", label: "A", format: "signed", digits: 2 })).toBe("+12.35");
    expect(formatCell(-3.2, { key: "a", label: "A", format: "percent", digits: 1 })).toBe("-3.2%");
    expect(formatCell("2026-01-02", { key: "a", label: "A", format: "date" })).toBe("2026-01-02");
    expect(formatCell(null, { key: "a", label: "A" })).toBe("—");
    expect(formatCell(true, { key: "weighted", label: "是否计权" })).toBe("是");
    expect(formatCell("bullish", { key: "direction", label: "方向" })).toBe("利多");
  });

  it("maps signals and providers", () => {
    expect(signalLabel("bullish")).toBe("利多");
    expect(signalClass("bearish")).toBe("badge--down");
    expect(providerLabel("eastmoney_datacenter")).toBe("东财数据中心");
    expect(providerState({ provider: "x", ok: true, records: 12, error: null, checked_at: null }).tone).toBe("badge--up");
    expect(providerState({ provider: "x", ok: false, records: 0, error: "boom", checked_at: null }).label).toBe("失败");
  });
});
