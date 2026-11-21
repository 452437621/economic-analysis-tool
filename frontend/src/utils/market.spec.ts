import { describe, expect, it } from "vitest";
import {
  ASSET_CLASS_LABEL,
  DOMESTIC_EXCHANGES,
  MARKET_FILTERS,
  SNAPSHOT_CATEGORIES,
  isDomestic,
} from "./market";

describe("market utils", () => {
  it("classifies domestic exchanges and symbols", () => {
    expect(isDomestic({ exchange: "SHFE", symbol: "AU" })).toBe(true);
    expect(isDomestic({ exchange: "INE", symbol: "SC" })).toBe(true);
    expect(isDomestic({ exchange: "CME", symbol: "000300" })).toBe(true);
    expect(isDomestic({ exchange: "CME", symbol: "GC" })).toBe(false);
    expect(isDomestic({ symbol: "XAUUSD" })).toBe(false);
  });

  it("keeps snapshot categories and filters internally consistent", () => {
    const keys = SNAPSHOT_CATEGORIES.map((category) => category.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(SNAPSHOT_CATEGORIES.every((category) => category.symbols.length > 0)).toBe(true);
    expect(MARKET_FILTERS[0]).toMatchObject({ key: "all", symbols: [] });
    expect(MARKET_FILTERS.flatMap((filter) => filter.symbols)).toContain("XAUUSD");
  });

  it("maps domestic exchanges and asset class labels", () => {
    expect(DOMESTIC_EXCHANGES.has("CZCE")).toBe(true);
    expect(ASSET_CLASS_LABEL.metal).toBe("金属");
    expect(ASSET_CLASS_LABEL.equity).toBe("权益");
  });
});
