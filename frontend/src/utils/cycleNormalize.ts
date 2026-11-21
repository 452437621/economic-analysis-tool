/** 周期视图的防御式归一：旧运行记录可能缺字段，模板只读归一后的对象。 */
import type {
  CycleLongCycle,
  CycleShortCycle,
  CycleLiquidity,
  CycleInventory,
  CyclePolitical,
  CycleWorld,
  CycleStage,
} from "@/api/types";

export type RawOf<T> = Partial<T> | null | undefined;

export function asNumber(input: unknown): number | null {
  if (typeof input !== "number" || !Number.isFinite(input)) return null;
  return input;
}

/** 0–100 分量的安全取值；缺失按中性 50 处理 */
export function asScore(input: unknown): number | null {
  const value = asNumber(input);
  if (value === null) return null;
  return Math.max(0, Math.min(100, value));
}

export function asText(input: unknown, fallback = "—"): string {
  if (typeof input !== "string") return fallback;
  const text = input.trim();
  return text || fallback;
}

export interface SafeLongCycle {
  phase: string;
  phase_id: string;
  score: number | null;
  band: [number, number] | null;
  bandText: string;
  position: number | null;
  positionPct: number | null;
  meaning: string;
  asset: string;
  confidence: number | null;
  next_phase: string | null;
  exit_condition: string;
  hysteresis_held: boolean;
}

export interface SafeShortCycle {
  state: string;
  raw_state: string;
  hysteresis_held: boolean;
  variables: { growth: number | null; inflation: number | null; liq: number | null; d12: number | null };
  meaning: string;
  confidence: number | null;
  growth_12m_change: number | null;
}

export interface SafeLiquidity {
  available: boolean;
  state: string;
  score: number | null;
  meaning: string;
  confidence: number | null;
  evidence: string;
}

export interface SafeInventory {
  state: string;
  degraded: boolean;
  degrade_reason: string | null;
  meaning: string | null;
  confidence: number | null;
}

export interface SafeNearestEvent {
  name: string;
  date: string;
  note: string;
}

export interface SafePolitical {
  window: string;
  nearest: SafeNearestEvent | null;
  days_to_nearest: number | null;
}

export interface SafePowerComponent {
  id: string;
  name: string;
  value: number;
  weight: number;
}

export interface SafeStage {
  id: string;
  name: string;
  stage: number | null;
  stage_name: string;
  confidence: number | null;
  reason: string;
  falsifier: string;
}

export function normalizeLongCycle(raw: RawOf<CycleLongCycle>): SafeLongCycle {
  const band = Array.isArray(raw?.band) ? raw.band : null;
  const bandStart = asNumber(band?.[0]);
  const bandEnd = asNumber(band?.[1]);
  const position = asNumber(raw?.position);
  return {
    phase: asText(raw?.phase, "未知阶段"),
    phase_id: asText(raw?.phase_id, "unknown"),
    score: asScore(raw?.score),
    band: bandStart !== null && bandEnd !== null ? [bandStart, bandEnd] : null,
    bandText: bandStart !== null && bandEnd !== null ? `${bandStart}–${bandEnd}` : "—",
    position,
    positionPct: position === null ? null : Math.max(0, Math.min(100, Math.round(position * 100))),
    meaning: asText(raw?.meaning, "长债务周期阶段含义缺失（该运行记录未返回 meaning）。"),
    asset: asText(raw?.asset, "—"),
    confidence: asNumber(raw?.confidence),
    next_phase: typeof raw?.next_phase === "string" ? raw.next_phase : null,
    exit_condition: asText(raw?.exit_condition, "—"),
    hysteresis_held: raw?.hysteresis_held === true,
  };
}

export function normalizeShortCycle(raw: RawOf<CycleShortCycle>): SafeShortCycle {
  const variables = (raw?.variables ?? {}) as Partial<CycleShortCycle["variables"]>;
  return {
    state: asText(raw?.state, "未知状态"),
    raw_state: asText(raw?.raw_state, "—"),
    hysteresis_held: raw?.hysteresis_held === true,
    variables: {
      growth: asNumber(variables.growth),
      inflation: asNumber(variables.inflation),
      liq: asNumber(variables.liq),
      d12: asNumber(variables.d12),
    },
    meaning: asText(raw?.meaning, "短周期含义缺失（该运行记录未返回 meaning）。"),
    confidence: asNumber(raw?.confidence),
    growth_12m_change: asNumber(raw?.growth_12m_change),
  };
}

export function normalizeLiquidity(raw: RawOf<CycleLiquidity>): SafeLiquidity {
  return {
    available: raw?.available !== false,
    state: asText(raw?.state, "未知"),
    score: asScore(raw?.score),
    meaning: asText(raw?.meaning, "流动性判定缺失（该运行记录未返回）。"),
    confidence: asNumber(raw?.confidence),
    evidence: asText(raw?.evidence, "—"),
  };
}

export function normalizeInventory(raw: RawOf<CycleInventory>): SafeInventory {
  return {
    state: asText(raw?.state, "未知"),
    degraded: raw?.degraded === true,
    degrade_reason: typeof raw?.degrade_reason === "string" ? raw.degrade_reason : null,
    meaning: typeof raw?.meaning === "string" ? raw.meaning : null,
    confidence: asNumber(raw?.confidence),
  };
}

export function normalizePolitical(raw: RawOf<CyclePolitical>): SafePolitical {
  const nearest = raw?.nearest as { name?: unknown; date?: unknown; note?: unknown } | null | undefined;
  return {
    window: asText(raw?.window, "窗口未知"),
    nearest: nearest
      ? {
          name: asText(nearest.name, "临近事件"),
          date: asText(nearest.date, "—"),
          note: asText(nearest.note, "—"),
        }
      : null,
    days_to_nearest: asNumber(raw?.days_to_nearest),
  };
}

export function normalizePowerComponent(item: Partial<CycleWorld["power_index"]["components"][number]>): SafePowerComponent {
  return {
    id: asText(item.id, "—"),
    name: asText(item.name, "未命名分项"),
    value: Math.max(2, Math.min(100, Math.round(asNumber(item.value) ?? 0))),
    weight: (asNumber(item.weight) ?? 0) * 100,
  };
}

export function normalizeStage(stage: Partial<CycleStage>): SafeStage {
  return {
    id: asText(stage.id, "—"),
    name: asText(stage.name, "未命名秩序"),
    stage: asNumber(stage.stage),
    stage_name: asText(stage.stage_name, "—"),
    confidence: asNumber(stage.confidence),
    reason: asText(stage.reason, "—"),
    falsifier: asText(stage.falsifier, "—"),
  };
}
