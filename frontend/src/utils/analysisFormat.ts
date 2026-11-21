/** 分析引擎视图的展示格式化（方法 / 运行 / 证据 / 风向 / 相关性 / 异动）。 */
import type { GoldFactor, Regime, V2Run } from "@/api/types";
import { fmtInt, fmtNumber } from "@/composables/useFormat";

export function toNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function gradeClass(grade: string): string {
  const key = (grade || "").toUpperCase();
  if (key === "E1") return "ana-grade--e1";
  if (key === "E2") return "ana-grade--e2";
  if (key === "E3") return "ana-grade--e3";
  if (key === "E4") return "ana-grade--e4";
  return "ana-grade--other";
}

export function methodKindText(kind: string | null | undefined): string {
  if (!kind) return "—";
  const labels: Record<string, string> = { model: "模型", pipeline: "流水线", ingest: "采集", dataset: "数据集" };
  return labels[kind] ?? kind;
}

export function shaText(sha: string | null | undefined): string {
  if (!sha) return "—";
  return sha.slice(0, 8);
}

export function runStatusText(status: string): string {
  if (status === "ok") return "成功";
  if (status === "degraded") return "降级";
  if (status === "failed") return "失败";
  if (status === "running") return "运行中";
  return status || "—";
}

export function runStatusClass(status: string): string {
  if (status === "ok") return "badge--live";
  if (status === "degraded") return "badge--warn";
  if (status === "failed") return "badge--down";
  return "";
}

/** 运行摘要：取 summary 里前 4 个标量键值，拼成「键 值」芯片 */
export function summaryChips(run: V2Run): string[] {
  const summary = run.summary;
  if (!summary) return [];
  const chips: string[] = [];
  for (const [key, raw] of Object.entries(summary)) {
    if (chips.length >= 4) break;
    if (raw === null || raw === undefined) continue;
    if (typeof raw === "object") continue;
    const value = typeof raw === "number" ? fmtInt(raw) : String(raw);
    chips.push(`${key} ${value}`);
  }
  return chips;
}

export function qualityKindText(kind: string): string {
  const labels: Record<string, string> = {
    freshness: "新鲜度",
    coverage: "覆盖率",
    continuity: "连续性",
    reconcile: "对账",
  };
  return labels[kind] ?? kind;
}

export function countryLabel(country: string): string {
  if (country === "US") return "美国";
  if (country === "CN") return "中国";
  return country;
}

export function regimeScores(regime: Regime): Array<{ label: string; score: number; z: number | null }> {
  return [
    { label: "增长", score: regime.growth_score, z: regime.growth_z ?? null },
    { label: "通胀", score: regime.inflation_score, z: regime.inflation_z ?? null },
    { label: "流动", score: regime.liquidity_score, z: null },
  ];
}

export function scoreWidth(score: number | null): string {
  const value = Math.max(0, Math.min(100, score ?? 0));
  return `${value}%`;
}

export function windBadgeClass(label: string): string {
  if (label === "进攻") return "badge--up";
  if (label === "避险") return "badge--down";
  return "";
}

export function corrWidth(corr: number | null): string {
  return `${Math.max(3, Math.min(100, Math.abs(corr ?? 0) * 100))}%`;
}

export function corrLevel(avg: number | null): { text: string; cls: string } {
  if (avg === null) return { text: "—", cls: "" };
  if (avg >= 0.4) return { text: "联动偏高", cls: "badge--warn" };
  if (avg >= 0.25) return { text: "联动中等", cls: "badge--accent" };
  return { text: "联动偏弱", cls: "" };
}

export function trendLabel(trend: string): string {
  if (trend === "up") return "上行";
  if (trend === "down") return "下行";
  if (trend === "mixed") return "震荡";
  return trend || "—";
}

export function trendBadgeClass(trend: string): string {
  if (trend === "up") return "badge--up";
  if (trend === "down") return "badge--down";
  return "";
}

export function goldFactorValue(factor: GoldFactor): string {
  if (factor.value === null || factor.value === undefined) return "—";
  const digits = factor.unit === "%" ? 2 : Math.abs(factor.value) >= 1000 ? 0 : 2;
  const text = fmtNumber(factor.value, digits);
  if (factor.unit === "%") return `${text}%`;
  return factor.unit ? `${text} ${factor.unit}` : text;
}

export function goldSignalText(signal: string): string {
  if (signal === "bullish") return "利多";
  if (signal === "bearish") return "利空";
  if (signal === "neutral") return "中性";
  return "—";
}

export function goldSignalClass(signal: string): string {
  if (signal === "bullish") return "badge--up";
  if (signal === "bearish") return "badge--down";
  return "";
}
