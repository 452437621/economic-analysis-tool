/** 英文枚举 → 中文展示标签（前端只做展示，不改变后端存储值）。 */

export const ALERT_KIND_LABELS: Record<string, string> = {
  price_move: "价格异动",
  calendar: "日历临近",
  event: "事件驱动",
  plan_risk: "计划风险",
  position_divergence: "持仓分歧",
  stale_quote: "行情过期",
  data_check: "数据质检",
};

export function alertKindLabel(kind: string | null | undefined): string {
  if (!kind) return "未分类";
  return ALERT_KIND_LABELS[kind] ?? kind;
}

export const ALERT_LEVEL_LABELS: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
  info: "提示",
};

export function alertLevelLabel(level: string | null | undefined): string {
  if (!level) return "—";
  return ALERT_LEVEL_LABELS[level] ?? level;
}

export const EVENT_CATEGORY_LABELS: Record<string, string> = {
  labor: "就业",
  inflation: "通胀",
  growth: "增长",
  rates: "利率决议",
  housing: "房地产",
  consumption: "消费",
  manufacturing: "制造业",
  trade: "贸易",
  fiscal: "财政",
  central_bank: "央行",
  energy: "能源",
};

export function eventCategoryLabel(category: string | null | undefined): string {
  if (!category) return "—";
  return EVENT_CATEGORY_LABELS[category] ?? category;
}

export const COUNTRY_LABELS: Record<string, string> = {
  US: "美国",
  CN: "中国",
  EU: "欧元区",
  JP: "日本",
  GB: "英国",
  DE: "德国",
  FR: "法国",
  CA: "加拿大",
  AU: "澳大利亚",
  CH: "瑞士",
  EA: "欧元区",
};

export function countryLabel(code: string | null | undefined): string {
  if (!code) return "—";
  return COUNTRY_LABELS[code.toUpperCase()] ?? code;
}
