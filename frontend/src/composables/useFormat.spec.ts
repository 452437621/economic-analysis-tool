import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fmtAgo,
  fmtDate,
  fmtInt,
  fmtMacro,
  fmtNumber,
  fmtPct,
  fmtPrice,
  fmtRatioPct,
  fmtSigned,
  freshness,
  inTradingSession,
  priceDigits,
  stars,
  trendClass,
} from "./useFormat";

afterEach(() => {
  vi.useRealTimers();
});

describe("useFormat", () => {
  it("formats numbers with fixed digits and dashes for invalid input", () => {
    expect(fmtNumber(1234.5, 2)).toBe("1,234.50");
    expect(fmtNumber(null)).toBe("—");
    expect(fmtNumber(Number.NaN)).toBe("—");
    expect(fmtInt(1234.6)).toBe("1,235");
  });

  it("chooses price digits by asset class and magnitude", () => {
    expect(priceDigits(5, "fx")).toBe(4);
    expect(priceDigits(120, "fx")).toBe(3);
    expect(priceDigits(1000)).toBe(1);
    expect(priceDigits(12.3)).toBe(2);
    expect(fmtPrice(999.5)).toBe("999.50");
  });

  it("formats percentages, ratios and signs", () => {
    expect(fmtPct(1.234)).toBe("+1.23%");
    expect(fmtPct(-0.5)).toBe("-0.50%");
    expect(fmtPct(0)).toBe("0.00%");
    expect(fmtPct(undefined)).toBe("—");
    expect(fmtSigned(2.5)).toBe("+2.50");
    expect(fmtRatioPct(0.123, 1)).toBe("12.3%");
  });

  it("maps values to trend classes", () => {
    expect(trendClass(1)).toBe("up");
    expect(trendClass(-1)).toBe("down");
    expect(trendClass(0)).toBe("flat");
    expect(trendClass(null)).toBe("flat");
  });

  it("formats macros, elapsed time and dates", () => {
    expect(fmtMacro(1.5, "%")).toBe("1.50%");
    expect(fmtMacro(2, "pp")).toBe("2.00pp");
    expect(fmtMacro(10, "bn")).toBe("10.00 bn");
    expect(fmtMacro(null, "bn")).toBe("—");
    expect(fmtAgo(30)).toBe("30 秒前");
    expect(fmtAgo(120)).toBe("2 分钟前");
    expect(fmtAgo(7200)).toBe("2 小时前");
    expect(fmtAgo(null)).toBe("—");
    expect(fmtDate("2026-03-05T12:00:00")).toBe("2026-03-05");
  });

  it("detects Beijing trading sessions", () => {
    // 2026-03-06 是周五，2026-03-07 是周六。
    expect(inTradingSession(new Date(2026, 2, 6, 10, 0))).toBe(true);
    expect(inTradingSession(new Date(2026, 2, 6, 16, 0))).toBe(false);
    expect(inTradingSession(new Date(2026, 2, 6, 22, 0))).toBe(true);
    expect(inTradingSession(new Date(2026, 2, 7, 10, 0))).toBe(false);
  });

  it("describes freshness badges deterministically", () => {
    expect(freshness(null, 0)).toEqual({ text: "", level: "plain" });
    expect(freshness(60, 0)).toEqual({ text: "实时", level: "ok" });
    expect(freshness(60, 700)).toEqual({ text: "延迟 12m", level: "plain" });

    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 2, 7, 10, 0)); // 周六
    expect(freshness(3600, 0)).toEqual({ text: "已收盘", level: "plain" });
    vi.setSystemTime(new Date(2026, 2, 6, 10, 0)); // 周五交易时段
    expect(freshness(3600, 0)).toEqual({ text: "未更新", level: "warn" });
  });

  it("renders importance stars within one to three", () => {
    expect(stars(0)).toBe("●");
    expect(stars(1)).toBe("●");
    expect(stars(3)).toBe("●●●");
    expect(stars(null)).toBe("●");
  });
});
