/** 专题研判通用展示格式化（表格、信号、数据源）。 */
import type { TopicProvider, TopicTableColumn } from "@/api/types";
import { fmtDate, fmtDateTime, fmtNumber, fmtPct, fmtSigned } from "@/composables/useFormat";

export const TOPIC_SIGNAL_LABELS: Record<string, string> = {
  bullish: "利多",
  bearish: "利空",
  neutral: "中性",
  unavailable: "待接入",
};

export const TOPIC_SIGNAL_BADGES: Record<string, string> = {
  bullish: "badge--up",
  bearish: "badge--down",
  neutral: "",
  unavailable: "",
};

const PROVIDER_LABELS: Record<string, string> = {
  lbma: "LBMA 伦敦金库",
  wgc_etf: "WGC 全球 ETF",
  wgc_cbd: "WGC 全球央行储备",
  cftc: "CFTC COT",
  cftc_bpr: "CFTC 银行参与报告",
  sge_lease: "上金所黄金租借费率",
  metalcharts: "MetalCharts · COMEX 库存",
  shfe_stock: "上期所黄金仓单",
  eastmoney: "东方财富",
  eastmoney_push2his: "东财行情",
  eastmoney_datacenter: "东财数据中心",
  eastmoney_fflow: "东财资金流",
  eastmoney_notice: "东财公告",
  eastmoney_report: "东财研报",
  eastmoney_quote: "东财快照",
  derived: "本地派生",
  sina: "新浪财经",
  "eastmoney+sina": "东财 + 新浪",
};

export function signalLabel(signal: string): string {
  return TOPIC_SIGNAL_LABELS[signal] ?? signal ?? "—";
}

export function signalClass(signal: string): string {
  return TOPIC_SIGNAL_BADGES[signal] ?? "";
}

export function providerLabel(provider: string | null | undefined): string {
  if (!provider) return "—";
  return PROVIDER_LABELS[provider] ?? provider;
}

export function providerTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const normalized = /[zZ]$|[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  return fmtDateTime(normalized);
}

export function providerState(provider: TopicProvider): { label: string; tone: string } {
  if (provider.ok) return { label: `${provider.records} 条`, tone: "badge--up" };
  return { label: provider.error ? "失败" : "无数据", tone: "badge--warn" };
}

/** 表格单元格式化：后端给原始数值，列定义决定展示口径。 */
export function formatCell(value: unknown, column: TopicTableColumn): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (column.key === "direction" && typeof value === "string") return signalLabel(value);
  const digits = column.digits ?? 2;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    switch (column.format) {
      case "percent":
        return fmtPct(value, digits);
      case "signed":
        return fmtSigned(value, digits);
      case "money":
        return fmtNumber(value, digits);
      case "number":
        return fmtNumber(value, digits);
      case "date":
        return fmtDate(new Date(value).toISOString());
      default:
        return fmtNumber(value, digits);
    }
  }
  if (column.format === "date") return fmtDate(String(value));
  if (column.format === "percent" && typeof value === "string" && !value.includes("%")) {
    return `${value}%`;
  }
  return String(value);
}

export function formatValue(value: number | null | undefined, unit?: string | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const text = fmtNumber(value, digits);
  return unit ? `${text} ${unit}` : text;
}
