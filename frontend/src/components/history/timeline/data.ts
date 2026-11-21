import type { TimelineEra, TimelineEventItem, TimelinePowerPoint } from "@/api/types";
import type {
  CurveDef,
  DisplayEvent,
  EventLayer,
  LaneDef,
  LaneId,
  LayerKey,
  StaticEvent,
} from "./types";

/* ── 设计稿数据常量（index.html:3945-3980） ─────────────────────────── */

export const LAYER_LABEL: Record<EventLayer, string> = {
  empire: "帝国兴衰",
  debt: "债务危机",
  war: "战争与革命",
  tech: "技术革命",
};

export const LAYER_COLOR: Record<EventLayer, string> = {
  empire: "#8FA8C8",
  debt: "#F0544F",
  war: "#F5A524",
  tech: "#2FBF71",
};

export const LAYER_CHIPS: Array<{ key: LayerKey; label: string; color: string }> = [
  { key: "empire", label: "帝国兴衰", color: "#F5A524" },
  { key: "reserve", label: "储备货币", color: "#4CC2FF" },
  { key: "debt", label: "债务危机", color: "#F0544F" },
  { key: "war", label: "战争与革命", color: "#F5A524" },
  { key: "tech", label: "技术革命", color: "#2FBF71" },
];

export const LANES: LaneDef[] = [
  {
    id: "NL",
    name: "荷兰",
    sub: "1580–1815",
    bands: [
      { start: 1580, end: 1700, color: "#2FBF71" },
      { start: 1700, end: 1780, color: "#F5A524" },
      { start: 1780, end: 1815, color: "#F0544F" },
    ],
  },
  {
    id: "UK",
    name: "英国",
    sub: "1688–1970",
    bands: [
      { start: 1688, end: 1815, color: "#2FBF71" },
      { start: 1815, end: 1870, color: "#F5A524" },
      { start: 1870, end: 1945, color: "#F0544F" },
    ],
  },
  {
    id: "US",
    name: "美国",
    sub: "1870–2026",
    bands: [
      { start: 1870, end: 1944, color: "#2FBF71" },
      { start: 1944, end: 2008, color: "#F5A524" },
      { start: 2008, end: 2026, color: "#F0544F" },
    ],
  },
  {
    id: "CN",
    name: "中国",
    sub: "1978–2026",
    bands: [
      { start: 1978, end: 2001, color: "#2FBF71" },
      { start: 2001, end: 2026, color: "#F5A524" },
    ],
  },
];

export const CURVES: CurveDef[] = [
  {
    id: "NL",
    name: "荷兰盾",
    color: "#F5A524",
    peak: 1720,
    peakV: 42,
    points: [
      [1500, 4], [1575, 12], [1600, 18], [1650, 30], [1700, 40], [1720, 42],
      [1750, 38], [1780, 26], [1800, 12], [1850, 4], [1900, 1.5], [2026, 0.5],
    ],
  },
  {
    id: "GB",
    name: "英镑",
    color: "#8FA8C8",
    peak: 1900,
    peakV: 55,
    points: [
      [1500, 1], [1700, 4], [1800, 12], [1815, 22], [1870, 42], [1900, 55],
      [1914, 48], [1930, 38], [1950, 18], [1970, 6], [2000, 3], [2026, 2],
    ],
  },
  {
    id: "US",
    name: "美元",
    color: "#4CC2FF",
    peak: 2000,
    peakV: 58,
    points: [
      [1500, 0], [1870, 2], [1914, 8], [1944, 25], [1950, 40], [1970, 55],
      [1990, 52], [2000, 58], [2010, 52], [2020, 48], [2026, 45],
    ],
  },
  {
    id: "CN",
    name: "人民币",
    color: "#2FBF71",
    peak: 2026,
    peakV: 18,
    points: [
      [1500, 1], [1950, 1], [1978, 1], [2000, 3], [2010, 8], [2020, 14], [2026, 18],
    ],
  },
];

export const STATIC_EVENTS: StaticEvent[] = [
  { id: "nl1580", year: 1580, lane: "NL", name: "荷兰独立", layer: "empire", type: "帝国崛起", grade: "A", desc: "尼德兰北部七省脱离西班牙统治，独立战争胜利为海上贸易与金融创新打开空间。", source: "荷兰国立档案馆 · 乌得勒支联盟（离线原型）" },
  { id: "nl1602", year: 1602, lane: "NL", name: "VOC 成立", layer: "tech", type: "金融与技术革命", grade: "A", desc: "荷兰东印度公司成立，发行可转让股份，现代资本市场与股份制公司由此成型。", source: "VOC 公司档案 · 1602 年特许状（离线原型）" },
  { id: "uk1688", year: 1688, lane: "UK", name: "光荣革命", layer: "war", type: "政治革命", grade: "A", desc: "议会主权确立，国债市场与英格兰银行随后建立，为英国财政—军事国家奠基。", source: "英国议会档案 · 权利法案（离线原型）" },
  { id: "uk1712", year: 1712, lane: "UK", name: "蒸汽机商业化", layer: "tech", type: "技术革命", grade: "B", desc: "纽科门蒸汽机用于矿井排水，煤炭—蒸汽动力组合开启第一次工业革命的前奏。", source: "英国工程史档案 · 1712 年专利（离线原型）" },
  { id: "nl1780", year: 1780, lane: "NL", name: "荷兰顶峰", layer: "empire", type: "帝国顶峰", grade: "A", desc: "阿姆斯特丹仍是欧洲信贷中心，但英荷战争暴露海军与财政的相对衰落。", source: "荷兰东印度公司档案 · 1780 年（离线原型）" },
  { id: "nl1795", year: 1795, lane: "NL", name: "巴达维亚共和国", layer: "debt", type: "债务与秩序转折", grade: "B", desc: "法国革命军入侵，荷兰共和国解体；资本外流与债务负担加速金融中心向伦敦转移。", source: "海牙国家档案馆 · 1795 年（离线原型）" },
  { id: "uk1815", year: 1815, lane: "UK", name: "滑铁卢与金本位", layer: "war", type: "战争与货币秩序", grade: "A", desc: "拿破仑战争结束，英国国债市场与金本位制度巩固，英镑成为事实上的储备货币。", source: "英格兰银行档案 · 1815 年（离线原型）" },
  { id: "uk1870", year: 1870, lane: "UK", name: "英国顶峰", layer: "empire", type: "帝国顶峰", grade: "A", desc: "工业、贸易、海军与金融四位一体，英镑与金本位覆盖全球主要贸易网络。", source: "英国国家档案馆 · 1870 年贸易统计（离线原型）" },
  { id: "uk1914", year: 1914, lane: "UK", name: "一战爆发", layer: "war", type: "战争与秩序转折", grade: "A", desc: "战争动员与金本位中断，英国从净债权国转为债务国，帝国成本开始反噬。", source: "英国财政部档案 · 1914 年（离线原型）" },
  { id: "uk1945", year: 1945, lane: "UK", name: "二战结束", layer: "war", type: "战争与秩序重构", grade: "A", desc: "布雷顿森林体系确立美元中心地位，英镑区收缩，英国让出储备货币主导权。", source: "布雷顿森林会议档案 · 1944（离线原型）" },
  { id: "us1870", year: 1870, lane: "US", name: "美国工业崛起", layer: "tech", type: "技术革命", grade: "A", desc: "铁路、钢铁与电力推动美国成为最大工业经济体，为后续金融霸权提供实体基础。", source: "美国人口普查 · 1870 年工业统计（离线原型）" },
  { id: "us1944", year: 1944, lane: "US", name: "布雷顿森林", layer: "empire", type: "货币体系奠基", grade: "A", desc: "美元与黄金挂钩、其他货币与美元挂钩，美国取得储备货币与规则制定权。", source: "布雷顿森林会议档案 · 1944（离线原型）" },
  { id: "us1946", year: 1946, lane: "US", name: "ENIAC 与计算革命", layer: "tech", type: "技术革命", grade: "B", desc: "通用电子计算机问世，半导体—软件—互联网的长周期技术扩散由此启动。", source: "美国陆军档案 · ENIAC（离线原型）" },
  { id: "us1971", year: 1971, lane: "US", name: "尼克松冲击", layer: "debt", type: "货币体系转折", grade: "A", desc: "关闭黄金窗口，美元与黄金脱钩，布雷顿森林体系解体；全球进入浮动汇率与信用货币时代。", source: "美联储历史档案 · 1971-08-15 讲话（离线原型）" },
  { id: "us2008", year: 2008, lane: "US", name: "全球金融危机", layer: "debt", type: "债务危机", grade: "A", desc: "次贷危机引爆全球金融体系，量化宽松成为常态，央行资产负债表扩张开启新阶段。", source: "美联储金融稳定报告 · 2008（离线原型）" },
  { id: "us2020", year: 2020, lane: "US", name: "无限量宽松", layer: "debt", type: "债务货币化", grade: "A", desc: "疫情冲击下财政与货币协同扩张，债务 / GDP 跳升，现代货币理论从边缘进入政策实践。", source: "美国财政部 · 2020 年财政数据（离线原型）" },
  { id: "cn1978", year: 1978, lane: "CN", name: "改革开放", layer: "empire", type: "国家崛起", grade: "A", desc: "市场化改革与对外开放启动，中国逐步嵌入全球贸易与产业链分工体系。", source: "中国国家统计局 · 1978 年（离线原型）" },
  { id: "cn2001", year: 2001, lane: "CN", name: "加入 WTO", layer: "empire", type: "全球化转折", grade: "A", desc: "中国加入世界贸易组织，出口与制造业份额快速上升，全球供应链重心东移。", source: "WTO 入世议定书 · 2001（离线原型）" },
  { id: "cn2010", year: 2010, lane: "CN", name: "第二大经济体", layer: "empire", type: "实力转折", grade: "A", desc: "中国 GDP 超过日本成为全球第二，储备与债权规模扩大，人民币国际化起步。", source: "世界银行 WDI · 2010（离线原型）" },
  { id: "us2026", year: 2026, lane: "US", name: "本期定位（美国）", layer: "empire", type: "长债务周期晚期", grade: "B", desc: "债务货币化与秩序重构并行：实际利率高企、曲线陡峭化、金价与实际利率背离。", source: "EPIC 周期引擎 · R-2026.11（本地）" },
  { id: "cn2026", year: 2026, lane: "CN", name: "本期定位（中国）", layer: "debt", type: "通缩化债", grade: "B", desc: "地产调整与地方债务约束并存，低通胀与宽货币组合延续，中美利差深度倒挂。", source: "EPIC 周期引擎 · R-2026.11（本地）" },
];

export const LANE_POWER: Record<LaneId, { power: string; name: string }> = {
  NL: { power: "netherlands", name: "荷兰" },
  UK: { power: "uk", name: "英国" },
  US: { power: "usa", name: "美国" },
  CN: { power: "china", name: "中国" },
};

export const STATIC_LAYER_CODE: Record<EventLayer, "L" | "B" | "S" | "E"> = {
  empire: "L",
  debt: "S",
  war: "B",
  tech: "E",
};

/* ── 事件 → 四条泳道（真实数据优先，无法归属则丢弃，不伪造） ──────────── */

const POWER_LANE: Record<string, LaneId> = {
  netherlands: "NL",
  nl: "NL",
  uk: "UK",
  gb: "UK",
  britain: "UK",
  england: "UK",
  usa: "US",
  us: "US",
  united_states: "US",
  china: "CN",
  cn: "CN",
  prc: "CN",
};

const ERA_LANE: Record<string, LaneId> = {
  netherlands: "NL",
  uk: "UK",
  usa: "US",
  china: "CN",
  china_ming: "CN",
  multipolar: "US",
};

/** 当前主导帝国泳道（仅在事件既无 power、又无分期命中时兜底） */
const dominantLane = (year: number): LaneId | null => {
  if (year >= 1870) return "US";
  if (year >= 1688) return "UK";
  if (year >= 1580) return "NL";
  return null;
};

export const laneOf = (item: TimelineEventItem, eras: TimelineEra[]): LaneId | null => {
  const power = (item.power ?? "").toLowerCase();
  if (power) return POWER_LANE[power] ?? null;
  const era = (eras ?? []).find(
    (row) => item.year >= row.rise && item.year <= row.decline && ERA_LANE[row.id],
  );
  if (era) return ERA_LANE[era.id] ?? null;
  return dominantLane(item.year);
};

const CATEGORY_LAYER: Record<string, EventLayer> = {
  empire: "empire",
  war: "war",
  tech: "tech",
  finance: "debt",
  monetary: "debt",
  cycle: "debt",
  debt: "debt",
  politics: "empire",
  economy: "empire",
  trade: "empire",
};

/** 政治类事件里带战争 / 革命 / 条约语义的，按设计稿归入「战争与革命」图层。 */
const WAR_KEYWORDS = /战争|革命|条约|和约|独立|违约/;

export const layerOf = (item: TimelineEventItem): EventLayer => {
  const category = (item.category ?? "").toLowerCase();
  if (category === "politics" && WAR_KEYWORDS.test(item.title)) return "war";
  return CATEGORY_LAYER[category] ?? "empire";
};

export const staticItem = (event: StaticEvent): TimelineEventItem & { source_text: string } => ({
  id: event.id,
  year: event.year,
  month: null,
  title: event.name,
  category: event.layer,
  category_label: event.type,
  layer: STATIC_LAYER_CODE[event.layer],
  layer_label: LAYER_LABEL[event.layer],
  evidence_grade: event.grade,
  power: LANE_POWER[event.lane].power,
  power_label: LANE_POWER[event.lane].name,
  summary: event.desc,
  source_url: null,
  source_text: event.source,
});

export const buildStaticDisplay = (): DisplayEvent[] =>
  STATIC_EVENTS.map((event) => ({
    id: event.id,
    year: event.year,
    lane: event.lane,
    layer: event.layer,
    item: staticItem(event),
  }));

export function buildApiEvents(events: TimelineEventItem[], eras: TimelineEra[]): DisplayEvent[] {
  const rows: DisplayEvent[] = [];
  for (const item of events ?? []) {
    const lane = laneOf(item, eras);
    if (!lane) continue;
    rows.push({ id: item.id, year: item.year, lane, layer: layerOf(item), item });
  }
  return rows.sort((a, b) => a.year - b.year || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

/* ── 储备份额曲线：真实序列覆盖四国才整组替换，否则用设计稿示意值 ────── */

const CURRENCY_POWER: Record<string, string> = {
  NL: "nlg",
  GB: "gbp",
  US: "usd",
  CN: "cny",
};

export const reserveRows = (reserve: TimelinePowerPoint[], power: string) =>
  (reserve ?? []).filter((row) => row.power.toLowerCase() === power);

export const hasRealReserveSeries = (reserve: TimelinePowerPoint[]): boolean =>
  CURVES.every((curve) => reserveRows(reserve, CURRENCY_POWER[curve.id] ?? "").length >= 2);

export function buildCurveSeries(reserve: TimelinePowerPoint[]): CurveDef[] {
  if (!hasRealReserveSeries(reserve)) return CURVES;
  return CURVES.map((curve) => {
    const points = reserveRows(reserve, CURRENCY_POWER[curve.id] ?? "")
      .map((row) => [row.year, row.value] as [number, number])
      .sort((a, b) => a[0] - b[0]);
    const peak = points.reduce((best, row) => (row[1] > best[1] ? row : best), points[0]);
    return { ...curve, points, peak: peak[0], peakV: Math.round(peak[1]) };
  });
}
