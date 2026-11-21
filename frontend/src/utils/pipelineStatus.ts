import type { V2Run, V2Step } from "@/api/types";

export type NodeStatus = "ok" | "degraded" | "failed" | "pending";
export type NodeId = "ingest" | "quality" | "feature" | "cycle" | "scenario" | "publish";

export interface PipeNode {
  id: NodeId;
  name: string;
  en: string;
  status: NodeStatus;
  steps: V2Step[];
  durationMs: number | null;
  errorCount: number;
  degradedCount: number;
}

export const NODE_DEFS: Array<{ id: NodeId; name: string; en: string; match: string[] }> = [
  { id: "ingest", name: "采集", en: "ingest", match: ["load_bars", "load_panel", "load_cycle", "load"] },
  {
    id: "quality",
    name: "质检",
    en: "quality",
    match: ["align_calendar", "quality", "degrade", "sync_principles", "check_principles"],
  },
  {
    id: "feature",
    name: "特征",
    en: "feature",
    match: [
      "indicators",
      "read_indicators",
      "regimes",
      "wind",
      "correlation",
      "attribution",
      "analogs",
      "leadlag",
      "events",
      "calendar_study",
    ],
  },
  {
    id: "cycle",
    name: "周期引擎",
    en: "cycle-engine",
    match: ["composite_scores", "phases", "sustainability", "world_order", "history"],
  },
  { id: "scenario", name: "情景", en: "scenario", match: ["scenarios", "alerts"] },
  { id: "publish", name: "输出", en: "publish", match: ["derive", "finish", "publish"] },
];

/** 契约外步骤的兜底归并：先按关键词，再按步骤 kind。 */
const NODE_ALIASES: Array<{ id: NodeId; keywords: string[] }> = [
  { id: "ingest", keywords: ["load", "collect", "fetch", "seed"] },
  { id: "quality", keywords: ["clean", "validate", "align", "reconcile", "freshness"] },
  {
    id: "feature",
    keywords: [
      "indicator",
      "regime",
      "wind",
      "correlation",
      "attribution",
      "leadlag",
      "event",
      "study",
      "analog",
    ],
  },
  { id: "cycle", keywords: ["composite", "phase", "sustainability", "world_order", "history", "read_cycle"] },
  { id: "scenario", keywords: ["scenario", "alert"] },
  { id: "publish", keywords: ["derive", "finish", "publish", "score"] },
];

/** 步骤 kind → 节点：步骤名完全在契约外时按类型归并。 */
const KIND_NODE: Record<string, NodeId> = {
  fetch: "ingest",
  ingest: "ingest",
  transform: "quality",
  compute: "feature",
  derive: "publish",
  publish: "publish",
};

/** 同名步骤在特定运行类型下归到不同节点（例如 cycle 运行里的 analogs 属于周期引擎）。 */
const RUN_KIND_OVERRIDES: Record<string, Record<string, NodeId>> = {
  cycle: { analogs: "cycle", alerts: "scenario" },
};

export function stepNode(step: V2Step, runKind?: string | null): NodeId | null {
  const name = (step.name || "").toLowerCase().trim();
  const last = name.split(".").pop() ?? name;
  const override = runKind ? RUN_KIND_OVERRIDES[runKind]?.[last] : undefined;
  if (override) return override;
  for (const def of NODE_DEFS) {
    if (def.match.includes(last)) return def.id;
  }
  for (const alias of NODE_ALIASES) {
    if (alias.keywords.some((keyword) => name.includes(keyword))) return alias.id;
  }
  return KIND_NODE[(step.kind || "").toLowerCase()] ?? null;
}

export function nodeStatus(
  nodeSteps: V2Step[],
  run: V2Run | null,
  def: { id: NodeId; match: string[] },
): NodeStatus {
  if (!nodeSteps.length) return run?.status === "failed" ? "failed" : "pending";
  if (nodeSteps.some((step) => step.status === "failed" || !!step.error)) return "failed";
  const softBad = nodeSteps.some((step) => step.status !== "ok");
  const reasonHit =
    run?.degraded_reasons.some((reason) => {
      const text = `${reason.code} ${reason.message}`.toLowerCase();
      return text.includes(def.id) || def.match.some((name) => text.includes(name));
    }) ?? false;
  return softBad || reasonHit ? "degraded" : "ok";
}

export function buildNodes(steps: V2Step[], run: V2Run | null): PipeNode[] {
  const grouped = new Map<NodeId, V2Step[]>();
  for (const def of NODE_DEFS) grouped.set(def.id, []);
  let cursor: NodeId = "ingest";
  for (const step of steps) {
    const id = stepNode(step, run?.kind);
    if (id) cursor = id;
    grouped.get(cursor)?.push(step);
  }
  return NODE_DEFS.map((def) => {
    const nodeSteps = (grouped.get(def.id) ?? []).slice().sort((a, b) => a.seq - b.seq);
    const durationMs = nodeSteps.reduce<number | null>((total, step) => {
      if (typeof step.duration_ms !== "number" || !Number.isFinite(step.duration_ms)) return total;
      return (total ?? 0) + step.duration_ms;
    }, null);
    return {
      id: def.id,
      name: def.name,
      en: def.en,
      status: nodeStatus(nodeSteps, run, def),
      steps: nodeSteps,
      durationMs,
      errorCount: nodeSteps.filter((step) => step.status === "failed" || !!step.error).length,
      degradedCount: nodeSteps.filter((step) => step.status !== "ok" && step.status !== "failed").length,
    };
  });
}

export function runStatusText(status: string | null | undefined): string {
  if (status === "ok") return "成功";
  if (status === "running") return "运行中";
  if (status === "degraded") return "降级完成";
  if (status === "failed") return "失败";
  return status ?? "—";
}

export function runBadgeClass(status: string | null | undefined): string {
  if (status === "failed") return "badge--warn";
  if (status === "degraded") return "badge--accent";
  return "badge--live";
}

export function statusTone(status: string | null | undefined): string {
  if (status === "failed") return "bad";
  if (status === "degraded") return "warn";
  if (status === "running") return "live";
  if (status === "ok") return "ok";
  return "muted";
}

export function stepTone(step: V2Step): string {
  if (step.status === "failed" || step.error) return "pipe-step-tone--bad";
  if (step.status !== "ok") return "pipe-step-tone--warn";
  return "pipe-step-tone--ok";
}

export function gradeClass(grade: string): string {
  if (grade === "E4") return "badge--warn";
  if (grade === "E3") return "badge--accent";
  return "badge--live";
}

export function confidencePct(confidence: number | null): string {
  if (confidence === null || !Number.isFinite(confidence)) return "—";
  return `${Math.round(confidence * 100)}%`;
}

export function confidenceLabel(confidence: number | null): string {
  if (confidence === null || !Number.isFinite(confidence)) return "—";
  if (confidence >= 0.8) return "很可能";
  if (confidence >= 0.65) return "较可能";
  if (confidence >= 0.5) return "可能存在";
  if (confidence >= 0.35) return "证据不足";
  return "无法判断";
}

export function fmtDuration(ms: number | null | undefined): string {
  if (typeof ms !== "number" || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)} s`;
}

export function shortId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

export function errorText(error: Error | null): string {
  return error ? error.message : "";
}

export function prettyJson(value: Record<string, unknown> | null): string {
  if (!value) return "未记录";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
