import type { QualityRow } from "@/api/types";

/**
 * 质检「明细 / 处置」单行文本：失败行的处置合并到同一行，供表格单行省略。
 * 通过行不展示处置；detail 为空时回退为 —。
 */
export function qualityDetailLine(
  row: Pick<QualityRow, "detail" | "remediation" | "passed">,
): string {
  const detail = row.detail ?? "—";
  if (!row.passed && row.remediation) {
    return `${detail} · 处置：${row.remediation}`;
  }
  return detail;
}
