import type { TimelineEventItem } from "@/api/types";

export type LaneId = "NL" | "UK" | "US" | "CN";
export type LayerKey = "empire" | "reserve" | "debt" | "war" | "tech";
export type EventLayer = "empire" | "debt" | "war" | "tech";

export interface LaneBand {
  start: number;
  end: number;
  color: string;
}

export interface LaneDef {
  id: LaneId;
  name: string;
  sub: string;
  bands: LaneBand[];
}

export interface CurveDef {
  id: string;
  name: string;
  color: string;
  peak: number;
  peakV: number;
  points: Array<[number, number]>;
}

export interface StaticEvent {
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

export interface DisplayEvent {
  id: string;
  year: number;
  lane: LaneId;
  layer: EventLayer;
  item: TimelineEventItem;
}

export interface RenderedCurve {
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

export interface RenderedBand {
  key: string;
  x: number;
  width: number;
  color: string;
  opacity: string;
}

export interface RenderedEvent {
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

export interface RenderedLane {
  id: LaneId;
  name: string;
  sub: string;
  ly: number;
  bands: RenderedBand[];
  events: RenderedEvent[];
}
