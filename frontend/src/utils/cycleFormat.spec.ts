import { describe, expect, it } from "vitest";
import { scoreLabel } from "./cycleFormat";

describe("cycleFormat.scoreLabel", () => {
  it("uses the cycle config's internal/external order labels", () => {
    expect(scoreLabel("ICI")).toBe("内部秩序");
    expect(scoreLabel("ECI")).toBe("外部秩序");
    expect(scoreLabel("GROWTH")).toBe("增长");
  });

  it("falls back to the raw code and handles null", () => {
    expect(scoreLabel("UNKNOWN")).toBe("UNKNOWN");
    expect(scoreLabel(null)).toBe("—");
  });
});
