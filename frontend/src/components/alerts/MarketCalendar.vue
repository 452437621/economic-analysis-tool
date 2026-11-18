<template>
  <section class="card alr-cal-card">
    <header class="card-head">
      <span class="card-title">财经日历</span>
      <span class="card-sub">未来 30 天 · 北京时间</span>
      <div class="card-actions">
        <span
          v-if="feedSource === 'legacy'"
          class="badge badge--sm badge--warn"
          title="新接口 /api/market/calendar 不可用，已回退旧日历；预期 / 前值 / 实际可能缺失"
        >
          旧接口 · 预期/前值暂缺
        </span>
        <span class="badge badge--sm">{{ items.length }} 个事件</span>
        <span class="badge badge--sm badge--warn">{{ tripleStar }} 个三星</span>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="loading" @click="refresh">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </header>

    <div class="card-body alr-cal-body">
      <SkeletonBlock v-if="!feed" :rows="6" :cells="4" :height="14" />

      <div v-else-if="feedNone" class="alr-cal-error">
        <ErrorState :error="feedError ?? '财经日历暂不可用'" @retry="refresh" />
        <p class="alr-cal-hint">
          财经日历接口尚未启用，旧版 /api/calendar 也未返回事件；预期 / 前值 / 实际字段缺失时以「—」显示。
        </p>
      </div>

      <template v-else>
        <div class="alr-cal-table" role="table" aria-label="财经日历">
          <div class="alr-cal-head" role="row">
            <span role="columnheader">日期 / 时间</span>
            <span role="columnheader">国家</span>
            <span role="columnheader">事件</span>
            <span role="columnheader" class="alr-cal-center">重要性</span>
            <span role="columnheader" class="alr-cal-num">预期</span>
            <span role="columnheader" class="alr-cal-num">前值</span>
            <span role="columnheader" class="alr-cal-num">实际</span>
          </div>
          <div
            v-for="item in items"
            :key="item.id"
            class="alr-cal-row"
            :class="rowClass(item.ts)"
            role="row"
            tabindex="0"
            :title="`点击打开市场行情 · ${dayLabel(item.ts)}`"
            @click="openMarket"
            @keydown.enter="openMarket"
          >
            <div class="alr-cal-when">
              <b class="mono">{{ fmtMonthDay(item.ts) }}</b>
              <span>{{ weekdayTime(item.ts) }}</span>
            </div>
            <div class="alr-cal-country">{{ item.country ?? "—" }}</div>
            <div class="alr-cal-event">
              <div class="alr-cal-name"><ZhText :text="item.name" inline /></div>
              <div class="alr-cal-region">{{ item.category ?? "—" }}</div>
            </div>
            <div class="alr-cal-star"><span class="alr-stars">{{ stars(item.importance) }}</span></div>
            <div class="alr-cal-num"><span>预期</span><b class="mono">{{ fmtCalValue(item.forecast, item.unit) }}</b></div>
            <div class="alr-cal-num"><span>前值</span><b class="mono">{{ fmtCalValue(item.previous, item.unit) }}</b></div>
            <div class="alr-cal-num">
              <span>实际</span>
              <b class="mono" :class="{ 'alr-cal-actual': hasValue(item.actual) }">
                {{ fmtCalValue(item.actual, item.unit) }}
              </b>
            </div>
          </div>
          <EmptyState
            v-if="!items.length"
            text="未来 30 天暂无财经事件"
            hint="接口返回为空；预期 / 前值 / 实际缺失时以「—」显示。"
          />
        </div>
      </template>

      <div class="alr-politics">
        <div class="alr-politics-head">
          <span class="alr-politics-title">政治窗口</span>
          <span class="alr-politics-sub">config/cycle.yaml · 30 天内进入高不确定性窗口</span>
          <span class="spacer"></span>
          <span class="badge badge--sm">{{ politicalRows.length }} 个事件</span>
        </div>
        <div v-if="politicalRows.length" class="alr-politics-list">
          <div
            v-for="event in politicalRows"
            :key="`${event.date}-${event.name}`"
            class="alr-pol-row"
            :class="{ 'is-hot': event.days >= 0 && event.days <= 30 }"
          >
            <span class="mono alr-pol-date">{{ shortDate(event.date) }}</span>
            <span class="alr-pol-stars">{{ stars(event.importance) }}</span>
            <span class="alr-pol-name"><ZhText :text="event.name" inline /></span>
            <span class="alr-pol-days mono">{{ daysText(event.days) }}</span>
            <span class="alr-pol-note">{{ event.note }}</span>
          </div>
        </div>
        <EmptyState
          v-else
          text="政治日历为空"
          hint="在 config/cycle.yaml 的 political_calendar 中添加事件。"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { getJson } from "@/api/client";
import { getCalendar } from "@/api/endpoints";
import type { CalendarEvent, CycleCalendarEntry } from "@/api/types";
import { usePolling } from "@/composables/usePolling";
import { fmtTime, stars } from "@/composables/useFormat";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import ZhText from "@/components/ui/ZhText.vue";

interface MarketCalendarItem {
  id?: string | number | null;
  ts?: string | null;
  name?: string | null;
  category?: string | null;
  country?: string | null;
  importance?: number | null;
  forecast?: number | string | null;
  previous?: number | string | null;
  actual?: number | string | null;
  unit?: string | null;
}

interface MarketCalendarResponse {
  items?: MarketCalendarItem[] | null;
}

interface CalendarRow {
  id: string;
  ts: string;
  name: string;
  category: string | null;
  country: string | null;
  importance: number;
  forecast: number | string | null;
  previous: number | string | null;
  actual: number | string | null;
  unit: string | null;
}

type CalendarSource = "market" | "legacy" | "none";

interface CalendarFeed {
  items: CalendarRow[];
  source: CalendarSource;
  error: string | null;
}

const props = defineProps<{
  political: CycleCalendarEntry[];
}>();

const router = useRouter();

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function toRow(item: MarketCalendarItem): CalendarRow {
  return {
    id: String(item.id ?? `${item.ts ?? ""}-${item.name ?? ""}`),
    ts: item.ts ?? "",
    name: item.name ?? "—",
    category: item.category ?? null,
    country: item.country ?? null,
    importance: typeof item.importance === "number" ? item.importance : 1,
    forecast: item.forecast ?? null,
    previous: item.previous ?? null,
    actual: item.actual ?? null,
    unit: item.unit ?? null,
  };
}

function legacyToRow(event: CalendarEvent): CalendarRow {
  return {
    id: event.id,
    ts: event.ts,
    name: event.name,
    category: event.category ?? null,
    country: event.country ?? null,
    importance: event.importance ?? 1,
    forecast: null,
    previous: null,
    actual: null,
    unit: null,
  };
}

function normalize(items: CalendarRow[]): CalendarRow[] {
  return items
    .filter((row) => row.ts !== "" && !Number.isNaN(new Date(row.ts).getTime()))
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
}

async function fetchFeed(): Promise<CalendarFeed> {
  try {
    const response = await getJson<MarketCalendarResponse>("/api/market/calendar", { params: { days: 30 } });
    return { items: normalize((response.items ?? []).map(toRow)), source: "market", error: null };
  } catch (marketError) {
    try {
      const legacy = await getCalendar({ days: 30, limit: 60 });
      return { items: normalize(legacy.data.map(legacyToRow)), source: "legacy", error: null };
    } catch (legacyError) {
      return {
        items: [],
        source: "none",
        error: `财经日历接口不可用（${errorText(marketError)}）；旧日历接口亦失败（${errorText(legacyError)}）`,
      };
    }
  }
}

const { data: feed, loading, refresh } = usePolling<CalendarFeed>(fetchFeed, { interval: 300_000 });

const feedSource = computed<CalendarSource>(() => feed.value?.source ?? "none");
const feedNone = computed(() => feedSource.value === "none");
const feedError = computed(() => feed.value?.error ?? null);
const items = computed<CalendarRow[]>(() => feed.value?.items ?? []);
const tripleStar = computed(() => items.value.filter((item) => item.importance >= 3).length);

const politicalRows = computed<Array<CycleCalendarEntry & { days: number }>>(() => {
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return props.political
    .filter((entry) => !Number.isNaN(new Date(entry.date).getTime()))
    .map((entry) => {
      const date = new Date(entry.date);
      const day = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
      return { ...entry, days: Math.round((day - today) / 86_400_000) };
    })
    .sort((a, b) => a.days - b.days);
});

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function fmtMonthDay(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "—";
  return `${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

function weekdayTime(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "—";
  return `${WEEKDAYS[date.getDay()]} ${fmtTime(ts)}`;
}

function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function dayDiff(ts: string): number {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return 0;
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const day = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.round((day - today) / 86_400_000);
}

function rowClass(ts: string): Record<string, boolean> {
  const diff = dayDiff(ts);
  return { "is-soon": diff >= 0 && diff <= 30, "is-past": diff < 0 };
}

function dayLabel(ts: string): string {
  const diff = dayDiff(ts);
  if (diff < 0) return `已过 ${Math.abs(diff)} 天`;
  if (diff === 0) return "今天";
  return `${diff} 天后`;
}

function daysText(days: number): string {
  if (days < 0) return `已过 ${Math.abs(days)} 天`;
  if (days === 0) return "今天";
  return `${days} 天`;
}

function hasValue(value: unknown): boolean {
  return value !== null && value !== undefined && value !== "";
}

/** 兼容 number / 已带单位的字符串；缺失字段统一显示「—」。 */
function fmtCalValue(value: number | string | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    const text = value.toFixed(2);
    if (!unit) return text;
    if (unit === "%") return `${text}%`;
    if (unit === "pp") return `${text}pp`;
    return `${text} ${unit}`;
  }
  return value;
}

function openMarket(): void {
  void router.push("/market");
}
</script>

<style scoped>
.alr-cal-card {
  overflow: hidden;
}

.alr-cal-body {
  padding: 0;
}

.alr-cal-table {
  display: flex;
  flex-direction: column;
}

.alr-cal-head,
.alr-cal-row {
  display: grid;
  grid-template-columns:
    minmax(0, 84px) minmax(0, 48px) minmax(0, 1fr) minmax(0, 48px)
    minmax(0, 68px) minmax(0, 68px) minmax(0, 68px);
  gap: 10px;
  align-items: center;
  padding: 0 13px;
}

.alr-cal-head {
  height: 28px;
  font-size: 9.5px;
  letter-spacing: 0.4px;
  color: var(--dim);
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.alr-cal-row {
  min-height: 40px;
  border-top: 1px dashed var(--border);
  cursor: pointer;
  outline-offset: -2px;
}

.alr-cal-row:hover {
  background: color-mix(in srgb, var(--accent) 4%, transparent);
}

.alr-cal-row.is-past {
  opacity: 0.5;
}

.alr-cal-row.is-soon {
  background: linear-gradient(90deg, color-mix(in srgb, var(--warn) 6%, transparent), transparent 55%);
}

.alr-cal-when b {
  display: block;
  font-family: var(--mono);
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
}

.alr-cal-when span {
  display: block;
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}

.alr-cal-row.is-soon .alr-cal-when b {
  color: var(--warn);
}

.alr-cal-country {
  min-width: 0;
  font-size: 10px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alr-cal-event {
  min-width: 0;
}

.alr-cal-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alr-cal-region {
  margin-top: 1px;
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alr-cal-star {
  text-align: center;
}

.alr-stars {
  font-size: 8px;
  letter-spacing: 1px;
  color: var(--warn);
  white-space: nowrap;
}

.alr-cal-center {
  text-align: center;
}

.alr-cal-num {
  text-align: right;
  min-width: 0;
}

.alr-cal-num span {
  display: block;
  font-size: 7.5px;
  color: var(--dim);
}

.alr-cal-num b {
  display: block;
  font-family: var(--mono);
  font-size: 9.5px;
  font-weight: 500;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alr-cal-num b.alr-cal-actual {
  color: var(--text);
  font-weight: 650;
}

.alr-cal-error {
  padding: 10px 13px 0;
}

.alr-cal-hint {
  margin: 0 0 8px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--dim);
}

.alr-politics {
  padding: 9px 13px 11px;
  border-top: 1px solid var(--border);
  margin-top: 4px;
}

.alr-politics-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}

.alr-politics-title {
  font-size: 10.5px;
  font-weight: 650;
  color: var(--muted);
  white-space: nowrap;
}

.alr-politics-sub {
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alr-politics-head .spacer {
  flex: 1;
}

.alr-politics-list {
  display: flex;
  flex-direction: column;
}

.alr-pol-row {
  display: grid;
  grid-template-columns: 40px 40px minmax(0, 1fr) 74px minmax(0, 0.9fr);
  gap: 8px;
  align-items: center;
  padding: 4px 6px;
  border-bottom: 1px dashed var(--border);
  font-size: 10px;
  color: var(--muted);
  border-radius: 5px;
}

.alr-pol-row:last-child {
  border-bottom: 0;
}

.alr-pol-row.is-hot {
  background: color-mix(in srgb, var(--warn) 7%, transparent);
}

.alr-pol-date {
  font-size: 10px;
  color: var(--accent);
  white-space: nowrap;
}

.alr-pol-stars {
  font-size: 8px;
  letter-spacing: 1px;
  color: var(--warn);
  white-space: nowrap;
}

.alr-pol-name,
.alr-pol-note {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alr-pol-note {
  font-size: 9px;
  color: var(--dim);
}

.alr-pol-days {
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
  text-align: right;
}

.alr-pol-row.is-hot .alr-pol-days {
  color: var(--warn);
}

@media (max-width: 1100px) {
  .alr-cal-head,
  .alr-cal-row {
    grid-template-columns:
      minmax(0, 74px) minmax(0, 42px) minmax(0, 1fr) minmax(0, 40px)
      minmax(0, 58px) minmax(0, 58px) minmax(0, 58px);
    gap: 7px;
    padding: 0 10px;
  }

  .alr-pol-row {
    grid-template-columns: 36px 34px minmax(0, 1fr) 66px;
  }

  .alr-pol-note {
    display: none;
  }
}

@media (max-width: 760px) {
  .alr-cal-head,
  .alr-cal-row {
    grid-template-columns:
      minmax(0, 68px) minmax(0, 36px) minmax(0, 1fr) minmax(0, 34px)
      minmax(0, 52px) minmax(0, 52px) minmax(0, 52px);
    gap: 5px;
    padding: 0 9px;
  }
}
</style>
