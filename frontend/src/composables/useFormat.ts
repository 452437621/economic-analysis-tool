/** 统一的数值 / 时间 / 涨跌格式化（避免各视图各写一套）。 */

export function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtInt(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return Math.round(value).toLocaleString("en-US");
}

/** 价格位数：汇率 4/3 位，千元以上 1 位，其余 2 位（与旧版一致） */
export function priceDigits(value: number | null | undefined, assetClass?: string | null): number {
  if (value === null || value === undefined) return 2;
  if (assetClass === "fx") return value < 10 ? 4 : 3;
  return value >= 1000 ? 1 : 2;
}

export function fmtPrice(value: number | null | undefined, assetClass?: string | null): string {
  return fmtNumber(value, priceDigits(value, assetClass));
}

/** 涨跌幅字符串：+1.23% / -0.45% / — */
export function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${Number(value).toFixed(digits)}%`;
}

export function fmtSigned(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${Number(value).toFixed(digits)}`;
}

/** 涨跌样式类：up / down / flat */
export function trendClass(value: number | null | undefined): "up" | "down" | "flat" {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** 时间：HH:mm；withDate=true 时 MM-DD HH:mm */
export function fmtTime(iso: string | null | undefined, withDate = false): string {
  const date = toDate(iso);
  if (!date) return "—";
  const options: Intl.DateTimeFormatOptions = withDate
    ? { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }
    : { hour: "2-digit", minute: "2-digit", hour12: false };
  return date.toLocaleString("zh-CN", options).replace(/\//g, "-");
}

export function fmtDateTime(iso: string | null | undefined): string {
  const date = toDate(iso);
  if (!date) return "—";
  return date
    .toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
    .replace(/\//g, "-");
}

export function fmtDate(iso: string | null | undefined): string {
  const date = toDate(iso);
  if (!date) return "—";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

/** 宏观值格式化：unit=% 加 %，unit=pp 加 pp，金额单位则加空格 + 单位 */
export function fmtMacro(value: number | null | undefined, unit?: string | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const text = Number(value).toFixed(digits);
  if (!unit) return text;
  if (unit === "%") return `${text}%`;
  if (unit === "pp") return `${text}pp`;
  return `${text} ${unit}`;
}

export function fmtAgo(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 90) return `${Math.max(0, Math.round(seconds))} 秒前`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} 分钟前`;
  if (seconds < 129600) return `${Math.round(seconds / 3600)} 小时前`;
  return `${Math.round(seconds / 86400)} 天前`;
}

/** 是否处于交易时段（北京时间，周一至周五 09:00–15:05 / 21:00–23:00） */
export function inTradingSession(now: Date = new Date()): boolean {
  const day = now.getDay();
  if (day === 0 || day === 6) return false;
  const minutes = now.getHours() * 60 + now.getMinutes();
  return (minutes >= 540 && minutes <= 905) || (minutes >= 1260 && minutes <= 1380);
}

/** 数据新鲜度徽标文案与级别（旧版 staleBadge） */
export function freshness(
  staleSec: number | null | undefined,
  delaySec: number | null | undefined,
): { text: string; level: "ok" | "warn" | "plain" } {
  if (staleSec === null || staleSec === undefined) return { text: "", level: "plain" };
  const delay = delaySec ?? 0;
  if (delay >= 600) return { text: `延迟 ${Math.round(delay / 60)}m`, level: "plain" };
  if (staleSec <= 1800) return { text: "实时", level: "ok" };
  return inTradingSession() ? { text: "未更新", level: "warn" } : { text: "已收盘", level: "plain" };
}

export function stars(importance: number | null | undefined): string {
  return "●".repeat(Math.max(1, Math.min(3, importance ?? 1)));
}
