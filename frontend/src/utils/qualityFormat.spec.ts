import { describe, expect, it } from "vitest";
import { qualityDetailLine } from "./qualityFormat";

describe("qualityDetailLine", () => {
  it("combines detail and remediation for failed rows", () => {
    expect(
      qualityDetailLine({
        passed: false,
        detail: "覆盖率不足",
        remediation: "运行 collect_daily_bars",
      }),
    ).toBe("覆盖率不足 · 处置：运行 collect_daily_bars");
  });

  it("omits remediation for passed rows", () => {
    expect(
      qualityDetailLine({
        passed: true,
        detail: "对账一致",
        remediation: "无需处理",
      }),
    ).toBe("对账一致");
  });

  it("falls back to an em dash", () => {
    expect(
      qualityDetailLine({ passed: false, detail: null, remediation: null }),
    ).toBe("—");
  });
});
