import type {
  CurveDef,
  DisplayEvent,
  EventLayer,
  LaneDef,
  LayerKey,
  RenderedCurve,
  RenderedLane,
} from "./types";

/* ── 设计稿几何常量（index.html:3999-4093） ─────────────────────────── */

export const H = 420;
export const PL = 70;
export const LANE_TOP = 122;
export const LANE_H = 62;
export const LANE_GAP = 6;
export const END_YEAR = 2100;
export const CURRENT_YEAR = 2026;
export const BASE_Y = 100;
export const TOP_Y = 32;
export const MARK_OFFSET = 44;
/** 事件年份文字（等宽 7.5px）的估算字宽与最小留白，SVG 用户单位。设计稿事件较稀疏，
 *  真实数据更密：贪心排布排不下时只留标记，保证与设计稿同样的可读密度。 */
const LABEL_CHAR_W = 4.7;
const LABEL_PAD = 7;
/** 年份文字与左侧帝国名标签列之间的最小留白，防止 1500 年的标记文字压住「中国」等泳道名。 */
const LABEL_EDGE_GAP = 6;
export const ZOOMS: readonly number[] = [1, 1.3, 1.7, 2.2];
export const WINDOWS: readonly number[] = [1500, 1700, 1900];

export const r1 = (value: number) => Math.round(value * 10) / 10;

/** 与原型一致：画布宽度 = 可视宽度（-8 gutter）× zoom，容器过窄时才退回 320 下限。 */
export function canvasWidth(contentWidth: number, zoom: number): number {
  const base = contentWidth > 320 ? contentWidth - 8 : 320;
  return Math.round(base * zoom);
}

export const xOf = (year: number, windowStart: number, PR: number) =>
  PL + ((year - windowStart) / (END_YEAR - windowStart)) * (PR - PL);

/** 储备份额 → 画布 y（baseY=100 为 0%，topY=32 为 100%） */
export const yOfReserve = (value: number) => BASE_Y - (value / 100) * (BASE_Y - TOP_Y);

export function ticksFor(windowStart: number): number[] {
  const first = Math.ceil(windowStart / 50) * 50;
  const list: number[] = [];
  for (let year = first; year <= END_YEAR; year += 50) list.push(year);
  return list;
}

/** 逐年线性插值，首点前取首值、末点后取末值（原型 curveVal，index.html:3987-3997） */
export const curveVal = (points: Array<[number, number]>, year: number): number => {
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

export function buildRenderedCurves(
  curveSeries: CurveDef[],
  windowStart: number,
  PR: number,
): RenderedCurve[] {
  return curveSeries.map((curve) => {
    let path = "";
    let firstX = 0;
    for (let year = windowStart; year <= CURRENT_YEAR; year += 2) {
      const px = r1(xOf(year, windowStart, PR));
      const py = r1(yOfReserve(curveVal(curve.points, year)));
      if (!path) {
        path = `M${px} ${py}`;
        firstX = px;
      } else {
        path += `L${px} ${py}`;
      }
    }
    const area = `${path}L${r1(xOf(CURRENT_YEAR, windowStart, PR))} ${BASE_Y}L${firstX} ${BASE_Y}Z`;
    const peakVisible = curve.peak >= windowStart;
    const lx = xOf(curve.peak, windowStart, PR);
    const labelAnchor: "start" | "end" = lx > PR - 56 ? "end" : "start";
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
  });
}

export function buildLaneRows(
  lanes: LaneDef[],
  windowStart: number,
  layerState: Record<LayerKey, boolean>,
  allEvents: DisplayEvent[],
  PR: number,
  layerColor: Record<EventLayer, string>,
): RenderedLane[] {
  return lanes.map((lane, laneIndex) => {
    const ly = LANE_TOP + laneIndex * (LANE_H + LANE_GAP);
    const bands = [] as RenderedLane["bands"];
    if (layerState.empire) {
      lane.bands.forEach((band, bandIndex) => {
        const from = Math.max(band.start, windowStart);
        const to = Math.min(band.end, CURRENT_YEAR);
        if (to <= from) return;
        bands.push({
          key: `${lane.id}-band-${bandIndex}`,
          x: r1(xOf(from, windowStart, PR)),
          width: r1(xOf(to, windowStart, PR) - xOf(from, windowStart, PR)),
          color: band.color,
          opacity: band.color === "#F5A524" ? ".34" : ".26",
        });
      });
    }
    const visible = allEvents.filter(
      (event) => event.lane === lane.id && layerState[event.layer] && event.year >= windowStart,
    );
    const labelEnd: [number, number] = [-Infinity, -Infinity];
    const events = visible.map((event, index) => {
      const x = r1(xOf(event.year, windowStart, PR));
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
        layer: event.layer as EventLayer,
        color: layerColor[event.layer],
        item: event.item,
      };
    });
    return { id: lane.id, name: lane.name, sub: lane.sub, ly, bands, events };
  });
}
