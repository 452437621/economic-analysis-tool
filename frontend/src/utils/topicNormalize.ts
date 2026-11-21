/** 把后端各 kind 的松散 payload 归一化为渲染器直接可用的形状。 */
import type {
  LuoyangScenario,
  TopicChartSpec,
  TopicEventsData,
  TopicEventRow,
  TopicKpi,
  TopicScenariosData,
  TopicSection,
  TopicTableColumn,
  TopicTableSpec,
  TopicValuationData,
} from "@/api/types";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

/** Gold emits one table per section; Luoyang emits `{tables:[...]}`. */
export function tableSpecs(section: TopicSection): TopicTableSpec[] {
  const data = asRecord(section.data);
  const tables = data.tables;
  if (Array.isArray(tables)) {
    return tables.map((item, index) => {
      const table = asRecord(item);
      return {
        id: String(table.id ?? `${section.id}-${index}`),
        title: String(table.title ?? section.label),
        columns: (table.columns as TopicTableColumn[]) ?? [],
        rows: (table.rows as Array<Record<string, unknown>>) ?? [],
        note: typeof table.note === "string" ? table.note : undefined,
      };
    });
  }
  if (Array.isArray(data.columns) && Array.isArray(data.rows)) {
    return [
      {
        id: section.id,
        title: section.label,
        columns: data.columns as TopicTableColumn[],
        rows: data.rows as Array<Record<string, unknown>>,
        note: typeof data.note === "string" ? data.note : undefined,
      },
    ];
  }
  return [];
}

export function eventTable(data: unknown): TopicTableSpec {
  const payload = data as TopicEventsData | null;
  const rows: TopicEventRow[] = (payload?.rows ?? []).map((row) => ({
    ...row,
    next_day: row.next_day ?? row.reaction?.next_day_ret_pct ?? null,
    five_day: row.five_day ?? row.reaction?.ret_5d_pct ?? null,
  }));
  const columns: TopicTableColumn[] = payload?.columns?.length
    ? payload.columns
    : [
        { key: "date", label: "日期" },
        { key: "type", label: "类型" },
        { key: "title", label: "事件", wrap: true },
        { key: "next_day", label: "次日", align: "right", format: "signed", digits: 2 },
        { key: "five_day", label: "5 日", align: "right", format: "signed", digits: 2 },
      ];
  return { id: "events", title: "事件", columns, rows, note: payload?.note };
}

export function kpiItems(data: unknown): TopicKpi[] {
  return (asRecord(data).items as TopicKpi[]) ?? [];
}

export function chartSpecs(data: unknown): TopicChartSpec[] {
  return (asRecord(data).charts as TopicChartSpec[]) ?? [];
}

/** Build averaging-table columns from ``cost_25/be_25/rally_25`` keys. */
export function averagingColumns(rows: Array<Record<string, unknown>>): TopicTableColumn[] {
  const first = rows[0] ?? {};
  const ratios = Object.keys(first)
    .map((key) => /^cost_(\d+)$/.exec(key)?.[1])
    .filter((value): value is string => Boolean(value))
    .map(Number)
    .sort((a, b) => a - b);
  const columns: TopicTableColumn[] = [
    { key: "add_price", label: "补仓价", align: "right", format: "number", digits: 2 },
    { key: "add_vs_current_pct", label: "距现价", align: "right", format: "signed", digits: 2 },
  ];
  for (const ratio of ratios) {
    columns.push(
      { key: `cost_${ratio}`, label: `${ratio}% 后成本`, align: "right", format: "number", digits: 3 },
      { key: `be_${ratio}`, label: `${ratio}% 后回本`, align: "right", format: "number", digits: 3 },
      { key: `rally_${ratio}`, label: `${ratio}% 后需涨`, align: "right", format: "signed", digits: 2 },
    );
  }
  return columns;
}

export interface ScenarioCard {
  key: "bear" | "base" | "bull";
  label: string;
  scenario: LuoyangScenario | null;
}

export function scenarioCards(data: unknown): ScenarioCard[] {
  const payload = data as TopicScenariosData | null;
  const scenarios = payload?.scenarios ?? {};
  return (["bear", "base", "bull"] as const).map((key) => ({
    key,
    label: scenarios[key]?.label ?? { bear: "熊市", base: "基准", bull: "牛市" }[key],
    scenario: scenarios[key] ?? null,
  }));
}

export interface ValuationCard {
  key: string;
  label: string;
  value: string;
  note: string;
}

export function valuationCards(data: unknown): ValuationCard[] {
  const payload = (data ?? {}) as TopicValuationData;
  if (payload.history || payload.fair_value != null) {
    return [
      {
        key: "fair_value",
        label: "模型公允价",
        value: payload.fair_value != null ? payload.fair_value.toFixed(0) : "—",
        note: payload.window ? `滚动 ${payload.window} 日` : "实际利率模型",
      },
      {
        key: "gap",
        label: "现价偏离",
        value: payload.gap_pct != null ? `${payload.gap_pct > 0 ? "+" : ""}${payload.gap_pct.toFixed(1)}%` : "—",
        note: "正值表示高于公允价",
      },
      {
        key: "z",
        label: "残差 z",
        value: payload.z_score != null ? payload.z_score.toFixed(2) : "—",
        note: "极端值提示均值回归",
      },
      {
        key: "percentile",
        label: "残差分位",
        value: payload.percentile != null ? `${payload.percentile.toFixed(0)}%` : "—",
        note: "历史残差位置",
      },
    ];
  }
  const cards: ValuationCard[] = [];
  for (const [key, label] of [
    ["pe", "PE(TTM)"],
    ["pb", "PB(MRQ)"],
    ["ps", "PS(TTM)"],
  ] as const) {
    const value =
      key === "pe" ? payload.pe_ttm ?? null : key === "pb" ? payload.pb_mrq ?? null : payload.ps_ttm ?? null;
    const pct = (payload[`${key}_percentile`] ?? {})["5y"]?.pct ?? null;
    cards.push({
      key,
      label,
      value: value != null ? `${value.toFixed(2)}x` : "—",
      note: pct != null ? `5 年分位 ${pct.toFixed(0)}%` : "样本不足",
    });
  }
  return cards;
}
