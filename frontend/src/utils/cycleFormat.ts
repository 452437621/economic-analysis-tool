/** 周期视图的展示格式化（读数 / 证据 / 时效 / 预警）。 */
import type { CycleAlert, CycleIndicator, CycleReadingCard } from "@/api/types";
import { fmtDate, fmtNumber, fmtSigned, fmtTime } from "@/composables/useFormat";

export interface KpiView {
  id: string;
  label: string;
  value: string;
  unit: string;
  z: number | null;
  zClass: string;
  missing: boolean;
  reason: string | null;
  source: string | null;
  evidence: string;
  deltaText: string;
  deltaClass: "up" | "down" | "flat";
  spark: string;
  sparkColor: string;
  tooltip: string;
}

const SCORE_LABEL: Record<string, string> = {
  DMI: "债务动量",
  GROWTH: "增长",
  INFLATION: "通胀",
  LIQUIDITY: "流动性",
  ECI: "外部秩序",
  ICI: "内部秩序",
};

export function scoreLabel(score: string | null): string {
  if (!score) return "—";
  return SCORE_LABEL[score] ?? score;
}

const EVIDENCE_TEXT: Record<string, string> = {
  E1: "本地序列可回算（权重 1.0）",
  E2: "官方数据、人工录入口径（权重 0.95）",
  E3: "估算 / 代理指标（权重 0.75）",
  E4: "人工研判，无自动来源（权重 0.50）",
};

export function evidenceTone(evidence: string | null): string {
  if (evidence === "E1") return "badge--live";
  if (evidence === "E2") return "badge--accent";
  if (evidence === "E3") return "badge--warn";
  if (evidence === "E4") return "badge--down";
  return "";
}

export function evidenceTitle(evidence: string | null): string {
  if (!evidence) return "后端未给出证据等级：该指标无法按等级折算权重";
  return EVIDENCE_TEXT[evidence] ?? `未识别的证据等级 ${evidence}`;
}

export function staleTone(days: number): string {
  if (days >= 90) return "badge--down";
  if (days > 30) return "badge--warn";
  return "";
}

export function staleTitle(row: CycleIndicator): string {
  if (row.stale_days === null) return "后端未给出 stale_days";
  const days = row.stale_days;
  const level = days >= 90 ? "超过 90 天，观测已明显过期" : days > 30 ? "超过 30 天，建议更新观测" : "在 30 天以内";
  return `观测日 ${fmtDate(row.asof)}，已 ${days} 天未更新（${level}）。`;
}

/** 通用进度条宽度（0–100，缺失给最小宽度），避免任何 NaN 写入 style */
export function barWidth(value: number | null | undefined, min = 2): number {
  if (value === null || value === undefined || !Number.isFinite(value)) return min;
  return Math.max(min, Math.min(100, Math.round(value)));
}

/** 比例 → 百分比文案（0.71 → 71%），缺失显示 — */
export function ratioText(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

export function sevClass(severity: CycleAlert["severity"]): string {
  return severity === "high" ? "high" : severity === "medium" ? "mid" : severity === "low" ? "low" : "unknown";
}

export function sevLabel(severity: CycleAlert["severity"]): string {
  return severity === "high" ? "高" : severity === "medium" ? "中" : severity === "low" ? "低" : "未知";
}

export function alertValue(alert: CycleAlert): string {
  if (alert.value === null || !Number.isFinite(alert.value)) return "—";
  return `${fmtNumber(alert.value, 2)}${alert.unit ?? ""}`;
}

export function alertThreshold(alert: CycleAlert): string {
  const op = alert.op ? String(alert.op) : "—";
  const threshold = fmtNumber(alert.threshold, 2);
  return `阈值 ${op} ${threshold}${alert.unit ?? ""}`;
}

export function alertAsOf(alert: CycleAlert): string {
  if (!alert.asof) return "—";
  return alert.asof.length <= 10 ? fmtDate(alert.asof) : fmtTime(alert.asof, true);
}

/** 30 点序列压进 120×24 折线；后端 spark 可能以小数或 ×100 基点存放，只做相对归一。 */
export function sparkPolyline(points: CycleReadingCard["spark"]): string {
  const list = Array.isArray(points) ? points : [];
  const values = list
    .map((point) => (point && typeof point === "object" ? point.value : null))
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = 120 / (values.length - 1);
  return values
    .map((value, index) => `${(index * step).toFixed(1)},${(22 - ((value - min) / span) * 20).toFixed(1)}`)
    .join(" ");
}

export function deltaTone(delta: number | null): "up" | "down" | "flat" {
  if (delta === null || !Number.isFinite(delta) || delta === 0) return "flat";
  return delta > 0 ? "up" : "down";
}

export function directionArrow(score: number | null): string {
  if (score === null) return "—";
  return score >= 50 ? "↑" : "↓";
}

export type Tone = "ok" | "warn" | "up" | "down" | "accent" | "plain";

export const PHASE_TONE: Record<string, Tone> = {
  normal: "ok",
  bubble_early: "ok",
  bubble_late: "warn",
  top: "warn",
  deflationary: "up",
  printing: "warn",
  debasement: "up",
};

export const SHORT_TONE: Record<string, Tone> = {
  复苏: "ok",
  过热: "warn",
  放缓: "plain",
  衰退: "up",
  萧条: "up",
};

export const LIQ_TONE: Record<string, Tone> = { 宽松: "ok", 中性: "plain", 收紧: "warn" };

export function toneClass(tone: Tone): string {
  if (tone === "ok") return "badge--live";
  if (tone === "warn") return "badge--warn";
  if (tone === "up") return "badge--up";
  if (tone === "down") return "badge--down";
  if (tone === "accent") return "badge--accent";
  return "";
}

export function runTone(status: string): string {
  return status === "ok" ? "badge--live" : status === "failed" ? "badge--up" : "badge--warn";
}

export function runText(status: string): string {
  return status === "ok" ? "运行成功" : status === "failed" ? "运行失败" : "部分降级";
}
