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

/** 调度作业英文名 → 操作按钮中文短标签（完整英文名保留在按钮 title 中）。 */
export const JOB_LABELS: Record<string, string> = {
  // 数据采集 / 质检 / 修复
  collect_daily_bars: "补日线",
  collect_rates: "补利率",
  collect_macro: "补宏观",
  collect_quotes: "补快照",
  collect_calendar: "补日历",
  collect_news: "补新闻",
  check_data_quality: "复检",
  repair_data: "修复",
  backfill_history: "回填历史",
  // 分析 / 决策 / 产出
  analyze: "分析",
  cycle: "周期",
  decide: "决策",
  brief_manual: "手动简报",
  // 验收自检中可能出现在操作列的作业
  collect_bodies: "补原文",
  extract_claims: "抽断言",
  brief_premarket: "盘前简报",
  theses: "论点",
  schedule_check: "调度检查",
};

export function jobLabel(name: string | null | undefined): string {
  if (!name) return "—";
  return JOB_LABELS[name] ?? name;
}
