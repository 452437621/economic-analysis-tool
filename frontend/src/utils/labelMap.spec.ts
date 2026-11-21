import { describe, expect, it } from "vitest";
import {
  ALERT_KIND_LABELS,
  alertKindLabel,
  alertLevelLabel,
  countryLabel,
  eventCategoryLabel,
} from "./labelMap";

describe("labelMap", () => {
  it("maps alert kinds with a fallback", () => {
    expect(ALERT_KIND_LABELS.price_move).toBe("价格异动");
    expect(alertKindLabel("price_move")).toBe("价格异动");
    expect(alertKindLabel("custom_kind")).toBe("custom_kind");
    expect(alertKindLabel(null)).toBe("未分类");
  });

  it("maps alert levels", () => {
    expect(alertLevelLabel("high")).toBe("高");
    expect(alertLevelLabel("unknown")).toBe("unknown");
    expect(alertLevelLabel(undefined)).toBe("—");
  });

  it("maps event categories", () => {
    expect(eventCategoryLabel("central_bank")).toBe("央行");
    expect(eventCategoryLabel("other")).toBe("other");
    expect(eventCategoryLabel("")).toBe("—");
  });

  it("maps country codes case-insensitively", () => {
    expect(countryLabel("us")).toBe("美国");
    expect(countryLabel("EA")).toBe("欧元区");
    expect(countryLabel("ZZ")).toBe("ZZ");
    expect(countryLabel(null)).toBe("—");
  });
});
