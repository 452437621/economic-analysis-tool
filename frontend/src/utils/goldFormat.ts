/** 黄金研判的展示格式化（信号 / 数据源 / 因子数值 / 时效）。 */
import type { GoldFactor } from "@/api/types";
import { fmtDate, fmtMacro } from "@/composables/useFormat";

/* ---------- 常量映射 ---------- */
export const SIGNAL_LABELS: Record<string, string> = {
  bullish: "利多",
  bearish: "利空",
  neutral: "中性",
  unavailable: "待接入",
};
export const SIGNAL_BADGES: Record<string, string> = {
  bullish: "badge--up",
  bearish: "badge--down",
  neutral: "",
  unavailable: "",
};
export const GROUP_ICONS: Record<string, string> = {
  central_bank: "#i-shield-check",
  etf: "#i-layers",
  lease: "#i-rates",
  inventory: "#i-db",
  market_maker: "#i-users",
  price: "#i-chart",
};
export const PROVIDER_LABELS: Record<string, string> = {
  lbma: "LBMA 伦敦金库",
  wgc_etf: "WGC 全球 ETF",
  wgc_cbd: "WGC 全球央行储备",
  cftc: "CFTC COT",
  cftc_bpr: "CFTC 银行参与报告",
  sge_lease: "上金所黄金租借费率",
  metalcharts: "MetalCharts · COMEX 库存",
  shfe_stock: "上期所黄金仓单",
  eastmoney: "东方财富 · 中国央行",
  derived: "本地派生",
};
export const FREQ_LABELS: Record<string, string> = { d: "日频", w: "周频", m: "月频", q: "季频" };

export function signalLabel(signal: string): string {
  return SIGNAL_LABELS[signal] ?? signal ?? "—";
}
export function signalClass(signal: string): string {
  return SIGNAL_BADGES[signal] ?? "";
}
export function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}
export function freqLabel(freq: string): string {
  return FREQ_LABELS[freq] ?? freq ?? "—";
}
export function factorDigits(value: number): number {
  const abs = Math.abs(value);
  if (abs >= 10000) return 0;
  if (abs >= 1000) return 1;
  return 2;
}
export function factorValueText(factor: GoldFactor): string {
  if (factor.value === null || !Number.isFinite(factor.value)) return "—";
  return fmtMacro(factor.value, factor.unit, factorDigits(factor.value));
}

/** provider.checked_at 后端为无时区 UTC（如 2026-11-14T14:32:52），补 Z 后再格式化。 */
export function providerTime(iso: string | null): string | null {
  if (!iso) return null;
  if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(iso)) return iso;
  return `${iso}Z`;
}

/** 各频率因子的「过旧」阈值（天）：日频 5、周频 12、月频 50、季频 130 */
const STALE_DAYS: Record<string, number> = { d: 5, w: 12, m: 50, q: 130 };

/** 距今天数：按自然日取 UTC 差值，避免时区与夏令时造成 ±1 天误差 */
export function daysSince(date: string | null | undefined): number | null {
  if (!date) return null;
  const target = new Date(date);
  if (Number.isNaN(target.getTime())) return null;
  const now = new Date();
  const from = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate());
  const to = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((to - from) / 86400000);
}

export function factorAsOfText(factor: GoldFactor): string {
  if (!factor.as_of) return "—";
  const days = daysSince(factor.as_of) ?? 0;
  const day = fmtDate(factor.as_of).slice(5);
  return days <= 0 ? `${day} 当日` : `${day}·${days}天`;
}

export function isFactorStale(factor: GoldFactor): boolean {
  const days = daysSince(factor.as_of);
  if (days === null) return false;
  return days > (STALE_DAYS[(factor.freq || "d").toLowerCase()] ?? 7);
}

export function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}
