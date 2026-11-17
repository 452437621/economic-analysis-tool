<script setup lang="ts">
/**
 * 世界长河 · 帝国兴衰 × 储备货币份额（内联 SVG 手绘时间轴）
 *
 * 这是 `docs/design/mockup-merged/index.html` 中 `#view-history` 时间轴卡片的 1:1 复刻：
 * 几何参数、字号、透明度、颜色、事件形状、图例全部照设计稿（SVG 部分见原型 buildTimeline()
 * 第 3999–4093 行，样式见第 1091–1104 行）。
 *
 * 数据来源优先级：
 *  1. 父级通过 props 传入后端 timeline 接口的真实数据（events / eras / reserve）；
 *  2. 后端不可用或事件无法归属四条泳道时，回落到设计稿的离线数据（LANES / EVENTS / CURVES），
 *     卡片右上角显示「示意数据」徽标，绝不白屏。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import type { TimelineEra, TimelineEventItem, TimelinePowerPoint } from "@/api/types";

/* ── 设计稿几何常量（index.html:3999-4093） ─────────────────────────── */

const H = 420;
const PL = 70;
const LANE_TOP = 122;
const LANE_H = 62;
const LANE_GAP = 6;
const END_YEAR = 2100;
const CURRENT_YEAR = 2026;
const BASE_Y = 100;
const TOP_Y = 32;
const MARK_OFFSET = 44;
/** 事件年份文字（等宽 7.5px）的估算字宽与最小留白，SVG 用户单位。设计稿事件较稀疏，
 *  真实数据更密：贪心排布排不下时只留标记，保证与设计稿同样的可读密度。 */
const LABEL_CHAR_W = 4.7;
const LABEL_PAD = 7;
/** 年份文字与左侧帝国名标签列之间的最小留白，防止 1500 年的标记文字压住「中国」等泳道名。 */
const LABEL_EDGE_GAP = 6;
const ZOOMS: readonly number[] = [1, 1.3, 1.7, 2.2];
const WINDOWS: readonly number[] = [1500, 1700, 1900];

type LaneId = "NL" | "UK" | "US" | "CN";
type LayerKey = "empire" | "reserve" | "debt" | "war" | "tech";
type EventLayer = "empire" | "debt" | "war" | "tech";

/* ── 设计稿数据常量（index.html:3945-3980） ─────────────────────────── */

interface LaneBand {
  start: number;
  end: number;
  color: string;
}

interface LaneDef {
  id: LaneId;
  name: string;
  sub: string;
  bands: LaneBand[];
}

interface CurveDef {
  id: string;
  name: string;
  color: string;
  peak: number;
  peakV: number;
  points: Array<[number, number]>;
}

interface StaticEvent {
  id: string;
  year: number;
  lane: LaneId;
  name: string;
  layer: EventLayer;
  type: string;
  grade: "A" | "B" | "C";
  desc: string;
  source: string;
}

const LAYER_LABEL: Record<EventLayer, string> = {
  empire: "帝国兴衰",
  debt: "债务危机",
  war: "战争与革命",
  tech: "技术革命",
};

const LAYER_COLOR: Record<EventLayer, string> = {
  empire: "#8FA8C8",
  debt: "#F0544F",
  war: "#F5A524",
  tech: "#2FBF71",
};

const LAYER_CHIPS: Array<{ key: LayerKey; label: string; color: string }> = [
  { key: "empire", label: "帝国兴衰", color: "#F5A524" },
  { key: "reserve", label: "储备货币", color: "#4CC2FF" },
  { key: "debt", label: "债务危机", color: "#F0544F" },
  { key: "war", label: "战争与革命", color: "#F5A524" },
  { key: "tech", label: "技术革命", color: "#2FBF71" },
];

const LANES: LaneDef[] = [
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

const CURVES: CurveDef[] = [
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

const STATIC_EVENTS: StaticEvent[] = [
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

const LANE_POWER: Record<LaneId, { power: string; name: string }> = {
  NL: { power: "netherlands", name: "荷兰" },
  UK: { power: "uk", name: "英国" },
  US: { power: "usa", name: "美国" },
  CN: { power: "china", name: "中国" },
};

const STATIC_LAYER_CODE: Record<EventLayer, "L" | "B" | "S" | "E"> = {
  empire: "L",
  debt: "S",
  war: "B",
  tech: "E",
};

/* ── 组件接口 ───────────────────────────────────────────────────────── */

interface Props {
  /** 后端 timeline overview 的事件列表 */
  events?: TimelineEventItem[];
  /** 后端霸权分期，仅用于事件缺 power 时的泳道归属兜底 */
  eras?: TimelineEra[];
  /** 后端储备份额序列（powers.reserve） */
  reserve?: TimelinePowerPoint[];
}

const props = withDefaults(defineProps<Props>(), {
  events: () => [],
  eras: () => [],
  reserve: () => [],
});

const emit = defineEmits<{
  (event: "select", item: TimelineEventItem): void;
}>();

/* ── 状态 ───────────────────────────────────────────────────────────── */

const scrollEl = ref<HTMLDivElement | null>(null);
const svgEl = ref<SVGSVGElement | null>(null);
const contentWidth = ref(0);
const windowStart = ref<number>(WINDOWS[0]);
const zoomIndex = ref(0);
const lastSelectedId = ref<string | null>(null);

const layerState = reactive<Record<LayerKey, boolean>>({
  empire: true,
  reserve: true,
  debt: true,
  war: true,
  tech: true,
});

/* ── 画布尺寸（原型：W = round(可视宽 × zoom)，H = 420） ─────────────── */

const zoom = computed(() => ZOOMS[zoomIndex.value] ?? 1);

const canvasWidth = computed(() => {
  // 与原型一致：画布宽度 = 可视宽度（-8 gutter）× zoom，容器过窄时才退回 320 下限，
  // 即 zoom=100% 时整幅 1500–2100 铺满容器、无需横向滚动。
  const base = contentWidth.value > 320 ? contentWidth.value - 8 : 320;
  return Math.round(base * zoom.value);
});

const W = canvasWidth;
const PR = computed(() => W.value - 12);

const r1 = (value: number) => Math.round(value * 10) / 10;

const xOf = (year: number) =>
  PL + ((year - windowStart.value) / (END_YEAR - windowStart.value)) * (PR.value - PL);

/** 储备份额 → 画布 y（baseY=100 为 0%，topY=32 为 100%） */
const yOfReserve = (value: number) => BASE_Y - (value / 100) * (BASE_Y - TOP_Y);

const outYearX = computed(() => r1(xOf(CURRENT_YEAR)));

const ticks = computed<number[]>(() => {
  const first = Math.ceil(windowStart.value / 50) * 50;
  const list: number[] = [];
  for (let year = first; year <= END_YEAR; year += 50) list.push(year);
  return list;
});

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

const laneOf = (item: TimelineEventItem): LaneId | null => {
  const power = (item.power ?? "").toLowerCase();
  if (power) return POWER_LANE[power] ?? null;
  const era = (props.eras ?? []).find(
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

const layerOf = (item: TimelineEventItem): EventLayer => {
  const category = (item.category ?? "").toLowerCase();
  if (category === "politics" && WAR_KEYWORDS.test(item.title)) return "war";
  return CATEGORY_LAYER[category] ?? "empire";
};

interface DisplayEvent {
  id: string;
  year: number;
  lane: LaneId;
  layer: EventLayer;
  item: TimelineEventItem;
}

const apiEvents = computed<DisplayEvent[]>(() => {
  const rows: DisplayEvent[] = [];
  for (const item of props.events ?? []) {
    const lane = laneOf(item);
    if (!lane) continue;
    rows.push({ id: item.id, year: item.year, lane, layer: layerOf(item), item });
  }
  return rows.sort((a, b) => a.year - b.year || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
});

const staticItem = (event: StaticEvent): TimelineEventItem & { source_text: string } => ({
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

const staticDisplay = computed<DisplayEvent[]>(() =>
  STATIC_EVENTS.map((event) => ({
    id: event.id,
    year: event.year,
    lane: event.lane,
    layer: event.layer,
    item: staticItem(event),
  })),
);

/** 后端事件映射到四条泳道后为空 → 用设计稿离线数据复刻这张图 */
const usingStaticEvents = computed(() => apiEvents.value.length === 0);

const allEvents = computed<DisplayEvent[]>(() =>
  usingStaticEvents.value ? staticDisplay.value : apiEvents.value,
);

/* ── 储备份额曲线：真实序列覆盖四国才整组替换，否则用设计稿示意值 ────── */

const CURRENCY_POWER: Record<string, string> = {
  NL: "nlg",
  GB: "gbp",
  US: "usd",
  CN: "cny",
};

const reserveRows = (power: string) =>
  (props.reserve ?? []).filter((row) => row.power.toLowerCase() === power);

const hasRealReserveSeries = computed(() =>
  CURVES.every((curve) => reserveRows(CURRENCY_POWER[curve.id] ?? "").length >= 2),
);

const curveSeries = computed<CurveDef[]>(() => {
  if (!hasRealReserveSeries.value) return CURVES;
  return CURVES.map((curve) => {
    const points = reserveRows(CURRENCY_POWER[curve.id] ?? "")
      .map((row) => [row.year, row.value] as [number, number])
      .sort((a, b) => a[0] - b[0]);
    const peak = points.reduce((best, row) => (row[1] > best[1] ? row : best), points[0]);
    return { ...curve, points, peak: peak[0], peakV: Math.round(peak[1]) };
  });
});

const showIllustrative = computed(() => usingStaticEvents.value || !hasRealReserveSeries.value);

const illustrativeHint = computed(() =>
  usingStaticEvents.value
    ? "timeline 接口暂无可用事件，当前用设计稿离线数据绘制"
    : "powers.reserve 观测点不足以覆盖荷兰盾 / 英镑 / 美元 / 人民币四条序列，储备份额曲线用设计稿示意值",
);

/** 逐年线性插值，首点前取首值、末点后取末值（原型 curveVal，index.html:3987-3997） */
const curveVal = (points: Array<[number, number]>, year: number): number => {
  if (!points.length) return 0;
  if (year <= points[0][0]) return points[0][1];
  for (let index = 1; index < points.length; index += 1) {
    if (year <= points[index][0]) {
      const prev = points[index - 1];
      const next = points[index];
      const t = (year - prev[0]) / (next[0] - prev[0]);
      return prev[1] + t * (next[1] - prev[1]);
    }
  }
  return points[points.length - 1][1];
};

interface RenderedCurve {
  id: string;
  name: string;
  color: string;
  line: string;
  area: string;
  peakVisible: boolean;
  peakV: number;
  labelX: number;
  labelY: number;
  labelAnchor: "start" | "end";
}

const renderedCurves = computed<RenderedCurve[]>(() =>
  curveSeries.value.map((curve) => {
    let path = "";
    let firstX = 0;
    for (let year = windowStart.value; year <= CURRENT_YEAR; year += 2) {
      const px = r1(xOf(year));
      const py = r1(yOfReserve(curveVal(curve.points, year)));
      if (!path) {
        path = `M${px} ${py}`;
        firstX = px;
      } else {
        path += `L${px} ${py}`;
      }
    }
    const area = `${path}L${r1(xOf(CURRENT_YEAR))} ${BASE_Y}L${firstX} ${BASE_Y}Z`;
    const peakVisible = curve.peak >= windowStart.value;
    const lx = xOf(curve.peak);
    const labelAnchor: "start" | "end" = lx > PR.value - 56 ? "end" : "start";
    return {
      id: curve.id,
      name: curve.name,
      color: curve.color,
      line: path,
      area,
      peakVisible,
      peakV: curve.peakV,
      labelX: r1(labelAnchor === "end" ? lx - 3 : lx + 3),
      labelY: r1(yOfReserve(curve.peakV) - 4),
      labelAnchor,
    };
  }),
);

/* ── 泳道 / 色带 / 事件标记 ─────────────────────────────────────────── */

interface RenderedBand {
  key: string;
  x: number;
  width: number;
  color: string;
  opacity: string;
}

interface RenderedEvent {
  key: string;
  x: number;
  my: number;
  labelY: number;
  leaderY: number;
  showLabel: boolean;
  layer: EventLayer;
  color: string;
  item: TimelineEventItem;
}

interface RenderedLane {
  id: LaneId;
  name: string;
  sub: string;
  ly: number;
  bands: RenderedBand[];
  events: RenderedEvent[];
}

const laneRows = computed<RenderedLane[]>(() =>
  LANES.map((lane, laneIndex) => {
    const ly = LANE_TOP + laneIndex * (LANE_H + LANE_GAP);
    const bands: RenderedBand[] = [];
    if (layerState.empire) {
      lane.bands.forEach((band, bandIndex) => {
        const from = Math.max(band.start, windowStart.value);
        const to = Math.min(band.end, CURRENT_YEAR);
        if (to <= from) return;
        bands.push({
          key: `${lane.id}-band-${bandIndex}`,
          x: r1(xOf(from)),
          width: r1(xOf(to) - xOf(from)),
          color: band.color,
          opacity: band.color === "#F5A524" ? ".34" : ".26",
        });
      });
    }
    const visible = allEvents.value.filter(
      (event) => event.lane === lane.id && layerState[event.layer] && event.year >= windowStart.value,
    );
    const labelEnd: [number, number] = [-Infinity, -Infinity];
    const events: RenderedEvent[] = visible.map((event, index) => {
      const x = r1(xOf(event.year));
      const my = ly + MARK_OFFSET;
      const labelY = index % 2 === 0 ? ly + 27 : ly + 59;
      const row = index % 2;
      /* 真实事件远密于设计稿（22 条）：按文字实际宽度贪心排布，排不下就只留标记；
         贴近左侧帝国名标签列时也不画，避免与泳道名重叠。 */
      const halfWidth = (String(event.year).length * LABEL_CHAR_W) / 2;
      const showLabel =
        x - halfWidth >= Math.max(labelEnd[row] + LABEL_PAD, PL + LABEL_EDGE_GAP);
      if (showLabel) labelEnd[row] = x + halfWidth;
      return {
        key: `${event.id}-${index}`,
        x,
        my,
        labelY,
        leaderY: labelY > my ? labelY - 9 : labelY + 7,
        showLabel,
        layer: event.layer,
        color: LAYER_COLOR[event.layer],
        item: event.item,
      };
    });
    return { id: lane.id, name: lane.name, sub: lane.sub, ly, bands, events };
  }),
);

/* ── 交互 ───────────────────────────────────────────────────────────── */

const measure = () => {
  const el = scrollEl.value;
  if (!el) return;
  const width = el.clientWidth - 8;
  if (width > 0) contentWidth.value = width;
};

let observer: ResizeObserver | null = null;

const scrollRatio = () => {
  const el = scrollEl.value;
  if (!el) return 0;
  const max = el.scrollWidth - el.clientWidth;
  return max > 0 ? el.scrollLeft / max : 0;
};

const restoreScroll = async (ratio: number) => {
  await nextTick();
  const el = scrollEl.value;
  if (!el) return;
  el.scrollLeft = ratio * Math.max(0, el.scrollWidth - el.clientWidth);
};

const select = (item: TimelineEventItem) => {
  lastSelectedId.value = item.id;
  emit("select", item);
};

const visibleEvents = () =>
  allEvents.value.filter((event) => event.year >= windowStart.value && layerState[event.layer]);

/** 时间窗切换后，若当前选中事件落在窗外，就改选首个可见事件（原型行为） */
const ensureVisibleSelection = () => {
  const current = allEvents.value.find((event) => event.id === lastSelectedId.value);
  if (current && current.year >= windowStart.value) return;
  const first = visibleEvents()[0];
  if (first) select(first.item);
};

const setWindow = (year: number) => {
  if (windowStart.value === year) return;
  const ratio = scrollRatio();
  windowStart.value = year;
  void restoreScroll(ratio);
  ensureVisibleSelection();
};

const toggleLayer = (key: LayerKey) => {
  layerState[key] = !layerState[key];
};

const zoomIn = () => {
  if (zoomIndex.value >= ZOOMS.length - 1) return;
  const ratio = scrollRatio();
  zoomIndex.value += 1;
  void restoreScroll(ratio);
};

const zoomOut = () => {
  if (zoomIndex.value <= 0) return;
  const ratio = scrollRatio();
  zoomIndex.value -= 1;
  void restoreScroll(ratio);
};

const onLaneClick = (lane: LaneId, event: MouseEvent) => {
  const svg = svgEl.value;
  if (!svg) return;
  const box = svg.getBoundingClientRect();
  if (!box.width) return;
  const relX = ((event.clientX - box.left) / box.width) * W.value;
  const px = Math.min(PR.value, Math.max(PL, relX));
  const year = windowStart.value + ((px - PL) / (PR.value - PL)) * (END_YEAR - windowStart.value);
  let best: DisplayEvent | null = null;
  for (const item of visibleEvents()) {
    if (item.lane !== lane) continue;
    if (!best || Math.abs(item.year - year) < Math.abs(best.year - year)) best = item;
  }
  if (best) select(best.item);
};

onMounted(() => {
  measure();
  if (typeof ResizeObserver !== "undefined" && scrollEl.value) {
    observer = new ResizeObserver(() => measure());
    observer.observe(scrollEl.value);
  }
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});
</script>

<template>
  <div class="hst-tl">
    <!-- 时间窗 / 图层筛选条（原型 index.html:2728-2745） -->
    <div class="card filterbar">
      <span class="filter-label">时间窗</span>
      <div class="seg" role="group" aria-label="时间窗">
        <button
          v-for="item in WINDOWS"
          :key="item"
          type="button"
          :class="{ active: windowStart === item }"
          :aria-pressed="windowStart === item"
          @click="setWindow(item)"
        >
          {{ item }}–2100
        </button>
      </div>
      <span class="divider-v"></span>
      <span class="filter-label">图层</span>
      <div class="chip-group">
        <button
          v-for="layer in LAYER_CHIPS"
          :key="layer.key"
          type="button"
          class="chip-toggle"
          :class="{ on: layerState[layer.key] }"
          :aria-pressed="layerState[layer.key]"
          @click="toggleLayer(layer.key)"
        >
          <span class="ct-dot" :style="{ background: layer.color }"></span>{{ layer.label }}
        </button>
      </div>
      <span class="filter-hint">事件标注为关键节点，非完整年表</span>
    </div>

    <div class="grid-history">
      <section class="card tl-card" aria-labelledby="hst-tl-title">
        <header class="card-head">
          <h2 id="hst-tl-title" class="card-title">
            帝国兴衰 × 储备货币份额
            <span class="sub">横向长河</span>
          </h2>
          <div class="card-actions">
            <span
              v-if="showIllustrative"
              class="badge badge--sm badge--warn"
              :title="illustrativeHint"
            >示意数据</span>
            <div class="tl-tools">
              <button
                class="icon-btn sm"
                type="button"
                aria-label="缩小时间轴"
                title="缩小时间轴"
                :disabled="zoomIndex === 0"
                @click="zoomOut"
              >
                <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14" /></svg>
              </button>
              <span class="zoom-pct">{{ Math.round(ZOOMS[zoomIndex] * 100) }}%</span>
              <button
                class="icon-btn sm"
                type="button"
                aria-label="放大时间轴"
                title="放大时间轴"
                :disabled="zoomIndex === ZOOMS.length - 1"
                @click="zoomIn"
              >
                <svg class="ic" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>
              </button>
            </div>
          </div>
        </header>

        <div ref="scrollEl" class="tl-scroll">
          <svg
            ref="svgEl"
            :viewBox="`0 0 ${W} ${H}`"
            :width="W"
            :height="H"
            role="img"
            aria-label="1500 至 2100 年荷兰、英国、美国、中国四条帝国兴衰泳道与储备货币份额"
          >
            <rect x="0" y="0" :width="W" :height="H" fill="none" />

            <!-- 2026 之后的推演区间 -->
            <rect
              :x="outYearX"
              y="116"
              :width="Math.max(0, r1(PR - outYearX))"
              height="274"
              fill="#4CC2FF"
              opacity=".035"
              pointer-events="none"
            />

            <!-- 储备货币份额带 -->
            <g v-if="layerState.reserve">
              <rect
                :x="PL"
                y="30"
                :width="PR - PL"
                height="70"
                rx="4"
                fill="#4CC2FF"
                opacity=".035"
                pointer-events="none"
              />
              <text :x="PL - 8" y="55" text-anchor="end" class="tl-reserve-label">储备货币</text>
              <text :x="PL - 8" y="66" text-anchor="end" class="tl-reserve-label">份额（示意）</text>
              <g v-for="curve in renderedCurves" :key="curve.id" pointer-events="none">
                <path :d="curve.area" :fill="curve.color" opacity=".1" pointer-events="none" />
                <path
                  :d="curve.line"
                  fill="none"
                  :stroke="curve.color"
                  stroke-width="1.2"
                  opacity=".85"
                  pointer-events="none"
                />
                <text
                  v-if="curve.peakVisible"
                  :x="curve.labelX"
                  :y="curve.labelY"
                  :text-anchor="curve.labelAnchor"
                  class="tl-reserve-name"
                  :fill="curve.color"
                >{{ curve.name }} {{ curve.peakV }}%</text>
              </g>
            </g>

            <!-- 网格与年份刻度 -->
            <g pointer-events="none">
              <template v-for="tick in ticks" :key="`tick-${tick}`">
                <line class="tl-grid" :x1="r1(xOf(tick))" y1="22" :x2="r1(xOf(tick))" y2="404" />
                <line class="tl-grid" :x1="r1(xOf(tick))" y1="18" :x2="r1(xOf(tick))" y2="22" />
                <text class="tl-axis-text" :x="r1(xOf(tick))" y="14" text-anchor="middle">
                  {{ tick }}
                </text>
              </template>
            </g>

            <!-- 四条帝国泳道 -->
            <g v-for="lane in laneRows" :key="lane.id">
              <rect
                class="tl-lane-bg"
                :x="PL"
                :y="lane.ly"
                :width="PR - PL"
                :height="LANE_H"
                rx="3"
              />
              <text class="tl-lane-label" :x="PL - 8" :y="lane.ly + 29" text-anchor="end">
                {{ lane.name }}
              </text>
              <text class="tl-lane-sub" :x="PL - 8" :y="lane.ly + 41" text-anchor="end">
                {{ lane.sub }}
              </text>

              <!-- 崛起 / 顶峰 / 衰落 三段式色带（只画到 2026） -->
              <template v-if="layerState.empire">
                <rect
                  v-for="band in lane.bands"
                  :key="band.key"
                  :x="band.x"
                  :y="lane.ly + 4"
                  :width="band.width"
                  :height="LANE_H - 8"
                  rx="3"
                  :fill="band.color"
                  :opacity="band.opacity"
                  pointer-events="none"
                />
              </template>

              <!-- 泳道空白点击：选中该泳道最近的事件 -->
              <rect
                class="tl-lane-hit"
                :x="PL"
                :y="lane.ly"
                :width="PR - PL"
                :height="LANE_H"
                @click="onLaneClick(lane.id, $event)"
              >
                <title>点击选择{{ lane.name }}泳道最近的事件</title>
              </rect>

              <!-- 事件标记：债务危机菱形 / 战争与革命三角 / 技术革命圆点 / 帝国兴衰圆点 -->
              <g
                v-for="event in lane.events"
                :key="event.key"
                class="tl-ev"
                @click.stop="select(event.item)"
              >
                <title>{{ event.item.year }} · {{ event.item.title }}</title>
                <rect
                  class="tl-ev-hit"
                  :x="event.x - 11"
                  :y="lane.ly"
                  width="22"
                  :height="LANE_H"
                />
                <line
                  v-if="event.showLabel"
                  :x1="event.x"
                  :y1="event.my + 5"
                  :x2="event.x"
                  :y2="event.leaderY"
                  :stroke="event.color"
                  stroke-width=".7"
                  opacity=".45"
                />
                <rect
                  v-if="event.layer === 'debt'"
                  :x="event.x - 3"
                  :y="event.my - 3"
                  width="6"
                  height="6"
                  :transform="`rotate(45 ${event.x} ${event.my})`"
                  :fill="event.color"
                />
                <path
                  v-else-if="event.layer === 'war'"
                  :d="`M${event.x} ${event.my - 4}L${event.x + 4} ${event.my + 3}L${event.x - 4} ${event.my + 3}Z`"
                  :fill="event.color"
                />
                <circle
                  v-else
                  :cx="event.x"
                  :cy="event.my"
                  :r="event.layer === 'tech' ? 2.6 : 3.2"
                  :fill="event.color"
                />
                <text
                  v-if="event.showLabel"
                  class="tl-ev-label"
                  :x="event.x"
                  :y="event.labelY"
                  text-anchor="middle"
                >{{ event.item.year }}</text>
              </g>
            </g>

            <!-- 本期线与脚注 -->
            <line
              :x1="outYearX"
              y1="22"
              :x2="outYearX"
              y2="404"
              stroke="#4CC2FF"
              stroke-width="1"
              stroke-dasharray="3 3"
              opacity=".55"
              pointer-events="none"
            />
            <text class="tl-now-text" :x="r1(outYearX + 5)" y="119">本期 2026</text>
            <text class="tl-axis-text" :x="PL" y="414">
              色带为阶段示意 · 储备份额曲线非精确历史序列
            </text>
          </svg>
        </div>

        <div class="tl-legend">
          <span class="lg"><span class="sw" style="background: rgba(47, 191, 113, .5)"></span>崛起</span>
          <span class="lg"><span class="sw" style="background: rgba(245, 165, 36, .55)"></span>顶峰</span>
          <span class="lg"><span class="sw" style="background: rgba(240, 84, 79, .45)"></span>衰落</span>
          <span class="lg"><span class="sw line" style="background: #4CC2FF"></span>储备份额（示意）</span>
          <span class="lg">
            <span class="sw" style="background: #F0544F; transform: rotate(45deg); width: 7px; height: 7px"></span>债务危机
          </span>
          <span class="lg">
            <span class="sw" style="background: #F5A524; clip-path: polygon(50% 0, 100% 100%, 0 100%); height: 7px"></span>战争与革命
          </span>
          <span class="lg">
            <span class="sw" style="background: #2FBF71; border-radius: 50%; width: 7px; height: 7px"></span>技术革命
          </span>
          <span class="spacer"></span>
          <span>储备份额为示意数据，非精确历史序列</span>
        </div>
      </section>

      <!-- 右侧「事件详情」由父级传入，保持设计稿 292px 右栏位置 -->
      <slot />
    </div>
  </div>
</template>

<style scoped>
.hst-tl {
  min-width: 0;
}

/* 筛选条（原型 index.html:477-480） */
.filterbar {
  display: flex;
  align-items: center;
  gap: 11px;
  flex-wrap: wrap;
  padding: 7px 12px;
  margin-top: 10px;
}
.filter-label {
  font-size: 9.5px;
  color: var(--dim);
  letter-spacing: 0.5px;
  white-space: nowrap;
}
.filter-hint {
  margin-left: auto;
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.divider-v {
  width: 1px;
  height: 18px;
  background: var(--border);
  flex: none;
}
.chip-group {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}
.chip-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--dim);
  font-size: 10.5px;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.12s, border-color 0.12s, background 0.12s;
}
.chip-toggle:hover {
  color: var(--muted);
  border-color: var(--border-strong);
}
.chip-toggle .ct-dot {
  width: 6px;
  height: 6px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.7;
}
.chip-toggle.on {
  color: var(--accent);
  border-color: var(--accent-line);
  background: var(--accent-weak);
}
.chip-toggle.on .ct-dot {
  opacity: 1;
}

/* 时间轴卡片 + 右侧详情（原型 index.html:483-491） */
.grid-history {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 292px;
  gap: 10px;
  margin-top: 10px;
  align-items: start;
}
.tl-card {
  overflow: hidden;
  min-width: 0;
}
.card-title .sub {
  margin-left: 7px;
  font-size: 10px;
  font-weight: 400;
  color: var(--dim);
  letter-spacing: 0;
}
.tl-tools {
  display: flex;
  align-items: center;
  gap: 5px;
}
.icon-btn.sm {
  width: 26px;
  height: 26px;
  border-radius: 7px;
}
.icon-btn.sm svg {
  width: 14px;
  height: 14px;
}
.icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.zoom-pct {
  min-width: 34px;
  text-align: center;
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--muted);
}
.tl-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 4px;
}
.tl-scroll svg {
  display: block;
}
.tl-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 6px 12px 9px;
  border-top: 1px dashed var(--border);
  font-size: 9px;
  color: var(--dim);
}
.tl-legend .lg {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.tl-legend .sw {
  width: 12px;
  height: 7px;
  border-radius: 2px;
}
.tl-legend .sw.line {
  height: 2px;
  border-radius: 1px;
}
.tl-legend .spacer {
  flex: 1 1 auto;
}

/* SVG 手绘元素（原型 index.html:1092-1104） */
.tl-lane-bg {
  fill: var(--surface-2);
  opacity: 0.45;
}
.tl-grid {
  stroke: var(--border);
  stroke-width: 1;
}
.tl-axis-text {
  fill: var(--dim);
  font-family: var(--mono);
  font-size: 9px;
}
.tl-lane-label {
  fill: var(--muted);
  font-size: 11px;
  font-weight: 650;
}
.tl-lane-sub {
  fill: var(--dim);
  font-family: var(--mono);
  font-size: 7.5px;
}
.tl-reserve-label {
  fill: var(--dim);
  font-size: 8px;
}
.tl-reserve-name {
  font-size: 7.5px;
  font-weight: 600;
  font-family: var(--mono);
}
.tl-ev {
  cursor: pointer;
}
.tl-ev .tl-ev-label {
  fill: var(--muted);
  font-family: var(--mono);
  font-size: 7.5px;
  transition: fill 0.12s;
}
.tl-ev:hover .tl-ev-label {
  fill: var(--accent);
}
.tl-ev-hit {
  fill: transparent;
}
.tl-lane-hit {
  fill: transparent;
  cursor: crosshair;
}
.tl-now-text {
  fill: var(--accent);
  font-family: var(--mono);
  font-size: 8px;
}

@media (max-width: 1240px) {
  .grid-history {
    grid-template-columns: minmax(0, 1fr) 260px;
  }
}
@media (max-width: 1024px) {
  .grid-history {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
