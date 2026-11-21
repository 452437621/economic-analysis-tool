import { describe, expect, it } from "vitest";
import type { TopicSection } from "@/api/types";
import { averagingColumns, eventTable, tableSpecs, valuationCards } from "./topicNormalize";

function section(data: unknown, id = "table"): TopicSection {
  return { id, label: "表", kind: "table", anchor: id, order: 10, data } as TopicSection;
}

describe("topicNormalize", () => {
  it("normalizes single and multiple tables", () => {
    const single = tableSpecs(
      section({ columns: [{ key: "a", label: "A" }], rows: [{ a: 1 }], note: "n" }),
    );
    expect(single).toHaveLength(1);
    expect(single[0].id).toBe("table");
    expect(single[0].rows[0].a).toBe(1);

    const multi = tableSpecs(
      section({ tables: [{ id: "x", columns: [{ key: "a", label: "A" }], rows: [] }] }),
    );
    expect(multi[0].id).toBe("x");
  });

  it("flattens nested event reactions", () => {
    const table = eventTable({
      rows: [
        { date: "2026-01-01", type: "财报", title: "年报", reaction: { next_day_ret_pct: 1.2, ret_5d_pct: -0.8 } },
      ],
    });
    expect(table.rows[0].next_day).toBe(1.2);
    expect(table.rows[0].five_day).toBe(-0.8);
    expect(table.columns.map((item) => item.key)).toContain("five_day");
  });

  it("derives averaging columns from ratio keys", () => {
    const columns = averagingColumns([{ add_price: 10, cost_25: 1, be_25: 1, rally_25: 1, cost_50: 1 }]);
    expect(columns.map((item) => item.key)).toEqual([
      "add_price",
      "add_vs_current_pct",
      "cost_25",
      "be_25",
      "rally_25",
      "cost_50",
      "be_50",
      "rally_50",
    ]);
  });

  it("builds valuation cards for both adapters", () => {
    const gold = valuationCards({ fair_value: 3000, gap_pct: -2, z_score: -0.3, percentile: 20, window: 750 });
    expect(gold.map((item) => item.key)).toEqual(["fair_value", "gap", "z", "percentile"]);
    const luoyang = valuationCards({
      pe_ttm: 12,
      pb_mrq: 2,
      ps_ttm: 1,
      pe_percentile: { "5y": { pct: 30 } },
      pb_percentile: { "5y": { pct: 40 } },
      ps_percentile: { "5y": { pct: 50 } },
    });
    expect(luoyang[0].value).toBe("12.00x");
    expect(luoyang[0].note).toContain("30%");
  });
});
