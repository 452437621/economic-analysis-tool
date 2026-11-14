<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">工作台 · 行情 · {{ todayLabel }}</div>
        <h1 class="page-h1">
          市场行情
          <span class="page-sub">
            {{ snapshotMeta.with_quote ?? snapshot.length }} / {{ snapshotMeta.count ?? snapshot.length }} 标的已接入 ·
            数据时点 {{ fmtTime(snapshotMeta.asof, true) }}
          </span>
        </h1>
      </div>
      <div class="page-actions">
        <button class="btn btn--sm" type="button" :disabled="snapshotLoading" @click="refreshAll">
          <svg class="ic" :class="{ spin: snapshotLoading }"><use href="#i-refresh" /></svg>刷新行情
        </button>
        <RouterLink class="btn btn--sm btn--primary" to="/system">
          <svg class="ic"><use href="#i-shield-check" /></svg>数据质检
        </RouterLink>
      </div>
    </div>

    <!-- 工具条：搜索 / 内外盘分段 / 类别 chips -->
    <div class="card toolbar">
      <div class="tool-row">
        <label class="field field--search">
          <svg class="ic"><use href="#i-search" /></svg>
          <input
            v-model="query"
            type="search"
            placeholder="搜索代码 / 名称，例如 CU、沪铜"
            autocomplete="off"
          />
        </label>
        <div class="seg" role="group" aria-label="市场范围">
          <button
            v-for="item in SEGMENTS"
            :key="item"
            type="button"
            :class="{ active: segment === item }"
            @click="segment = item"
          >
            {{ item }}
          </button>
        </div>
        <div class="chip-row">
          <button
            v-for="chip in chips"
            :key="chip.key"
            class="chip"
            :class="{ active: category === chip.key }"
            type="button"
            @click="category = chip.key"
          >
            {{ chip.label }}<em>{{ chip.count }}</em>
          </button>
        </div>
        <div class="tool-right">
          <span class="tool-note">{{ filtered.length }} 个品种</span>
          <button class="icon-btn" type="button" title="刷新行情" @click="refreshAll">
            <svg class="ic" :class="{ spin: snapshotLoading }"><use href="#i-refresh" /></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 行情快照：按类别分组 + 表头排序 -->
    <div class="card table-card">
      <div class="card-head">
        <span class="card-title">{{ categoryLabel }}</span>
        <span class="card-sub">共 {{ filtered.length }} 个品种 · {{ groups.length }} 个类别 · 点击行查看历史走势</span>
        <div class="card-actions">
          <span class="badge badge--accent">按 {{ sortLabel }} {{ sortDir === "desc" ? "降序" : "升序" }}</span>
        </div>
      </div>
      <div class="table-wrap">
        <SkeletonBlock v-if="!snapshotLastUpdated && !snapshotError" :rows="8" :cells="6" />
        <ErrorState v-else-if="snapshotError" :error="snapshotError" @retry="refreshSnapshot" />
        <table v-else class="data-table">
          <thead>
            <tr>
              <th style="width: 84px">品种</th>
              <th>名称</th>
              <th class="num" style="width: 136px">
                <button
                  class="th-sort"
                  type="button"
                  :class="{ 'is-sorted': sortKey === 'price' }"
                  @click="toggleSort('price')"
                >
                  最新<svg class="ic"><use href="#i-sort" /></svg>
                  <span class="sort-dir">{{ sortArrow("price") }}</span>
                </button>
              </th>
              <th class="num" style="width: 116px">
                <button
                  class="th-sort"
                  type="button"
                  :class="{ 'is-sorted': sortKey === 'chgAbs' }"
                  @click="toggleSort('chgAbs')"
                >
                  涨跌<svg class="ic"><use href="#i-sort" /></svg>
                  <span class="sort-dir">{{ sortArrow("chgAbs") }}</span>
                </button>
              </th>
              <th class="num" style="width: 172px">
                <button
                  class="th-sort"
                  type="button"
                  :class="{ 'is-sorted': sortKey === 'chg' }"
                  @click="toggleSort('chg')"
                >
                  涨跌幅<svg class="ic"><use href="#i-sort" /></svg>
                  <span class="sort-dir">{{ sortArrow("chg") }}</span>
                </button>
              </th>
              <th style="width: 152px">数据源</th>
              <th style="width: 104px">时点</th>
              <th class="num" style="width: 58px">证据</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in groups" :key="group.key">
              <tr class="group-row">
                <td colspan="8">
                  {{ group.label }}<span class="g-count">{{ group.items.length }} 个品种</span>
                  <span class="g-stat">{{ group.up }} 涨 {{ group.down }} 跌</span>
                </td>
              </tr>
              <tr
                v-for="item in group.items"
                :key="item.symbol"
                class="mkt-row"
                role="button"
                tabindex="0"
                :title="`${item.name}（${item.symbol}）· 点击查看历史走势`"
                @click="openInstrument(item)"
                @keydown.enter="openInstrument(item)"
              >
                <td><span class="sym">{{ item.symbol }}</span></td>
                <td class="nm">{{ item.name }}</td>
                <td class="num">
                  {{ fmtPrice(item.price, item.asset_class) }}<span v-if="prefs.showUnits && unitFor(item)" class="unit">{{ unitFor(item) }}</span>
                </td>
                <td class="num">
                  <span :class="trendClass(changeAbs(item))">{{ changeAbsText(item) }}</span>
                </td>
                <td class="num">
                  <span class="chg-bar">
                    <span class="bar"><i :style="barStyle(item.change_pct)"></i></span>
                    <span :class="trendClass(item.change_pct)">{{ fmtPct(item.change_pct) }}</span>
                  </span>
                </td>
                <td>
                  <span class="src">{{ item.source ?? "—" }}</span>
                  <span
                    v-if="freshnessOf(item).text"
                    class="badge badge--sm src-badge"
                    :class="freshnessClass(item)"
                  >
                    {{ freshnessOf(item).text }}
                  </span>
                </td>
                <td>
                  <span class="tm" :title="fmtDateTime(item.ts)">{{ fmtTime(item.ts, true) }}</span>
                </td>
                <td class="num ev-cell" title="暂无关联证据" @click.stop>
                  <span class="dim">—</span>
                </td>
              </tr>
            </template>
            <tr v-if="!filtered.length">
              <td colspan="8">
                <EmptyState text="没有匹配的品种" hint="清空搜索或切换「全部 / 国内 / 外盘」与类别筛选后重试。" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="table-foot">
        <span>显示 <b>{{ filtered.length }}</b> / <b>{{ snapshot.length }}</b> 条</span>
        <span>·</span>
        <span>排序：{{ sortLabel }} {{ sortDir === "desc" ? "↓" : "↑" }}（分组内）</span>
        <span>·</span>
        <span>{{ sourceCount }} 个数据源</span>
        <span class="spacer"></span>
        <span class="mini-legend">
          <span>上涨 <b class="up">■</b></span>
          <span>下跌 <b class="down">■</b></span>
          <span>时点均为北京时间</span>
        </span>
      </div>
    </div>

    <!-- 持仓结构 -->
    <section class="card table-card block-gap">
      <div class="card-head">
        <span class="card-title">持仓结构</span>
        <span class="card-sub">
          {{ positionsTradeDate ? `数据日期 ${positionsTradeDate} · 会员合计` : "会员合计 · 日频" }}
        </span>
        <div class="card-actions">
          <span class="badge badge--sm">{{ positions.length }} 个品种</span>
        </div>
      </div>
      <div class="table-wrap">
        <SkeletonBlock v-if="!positionsLastUpdated && !positionsError" :rows="6" :cells="6" />
        <ErrorState v-else-if="positionsError" :error="positionsError" @retry="refreshPositions" />
        <table v-else class="data-table">
          <thead>
            <tr>
              <th style="width: 150px">品种</th>
              <th class="num">多头持仓</th>
              <th class="num">空头持仓</th>
              <th class="num">净持仓</th>
              <th class="num">净占比</th>
              <th class="num">多空变化（多 / 空）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in positions" :key="row.product">
              <td>
                <span class="sym">{{ row.product.toUpperCase() }}</span>
                <span class="pos-name nm">{{ row.name }}</span>
              </td>
              <td class="num">{{ fmtInt(row.long_pos) }}</td>
              <td class="num">{{ fmtInt(row.short_pos) }}</td>
              <td class="num" :class="trendClass(row.net_pos)">{{ fmtInt(row.net_pos) }}</td>
              <td class="num" :class="trendClass(row.net_ratio)">{{ netRatioText(row.net_ratio) }}</td>
              <td class="num">
                <span :class="trendClass(row.long_chg)">{{ fmtInt(row.long_chg) }}</span>
                <span class="dim"> / </span>
                <span :class="trendClass(row.short_chg)">{{ fmtInt(row.short_chg) }}</span>
              </td>
            </tr>
            <tr v-if="!positions.length">
              <td colspan="6">
                <EmptyState text="暂无持仓数据" hint="等待 collect_positions 采集任务写入会员持仓排名。" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-foot">
        净持仓 = 多头 − 空头 · 净占比 =（多 − 空）/（多 + 空）· 数据日期 {{ positionsTradeDate ?? "—" }}
      </div>
    </section>

    <!-- 会员持仓 Top20 -->
    <section class="card members-card">
      <div class="card-head">
        <span class="card-title">会员持仓 Top20</span>
        <span class="card-sub">{{ memberSub }}</span>
        <div class="card-actions">
          <select
            v-model="memberProduct"
            class="select member-select"
            :disabled="!positions.length"
            aria-label="切换会员持仓品种"
          >
            <option v-for="row in positions" :key="row.product" :value="row.product">
              {{ row.name }}（{{ row.product.toUpperCase() }}）
            </option>
          </select>
        </div>
      </div>

      <ErrorState v-if="memberError" :error="memberError" @retry="loadMembers" />
      <template v-else>
        <div class="members-body">
          <div class="member-col">
            <div class="member-col-head">
              <span class="member-col-title long">多头持仓 Top20</span>
              <span class="member-col-note">多单 / 增减</span>
            </div>
            <SkeletonBlock v-if="memberLoading && !memberLong.length" :rows="8" :cells="4" />
            <div v-else class="member-list">
              <div v-for="row in memberLong" :key="`long-${row.rank}`" class="member-row">
                <span class="member-rank">{{ row.rank }}</span>
                <span class="member-name" :title="row.member">{{ row.member }}</span>
                <span class="member-pos">{{ fmtInt(row.position) }}</span>
                <span class="member-chg" :class="trendClass(row.change)">{{ fmtInt(row.change) }}</span>
              </div>
              <EmptyState v-if="!memberLong.length" text="暂无多头明细" />
            </div>
          </div>
          <div class="member-col">
            <div class="member-col-head">
              <span class="member-col-title short">空头持仓 Top20</span>
              <span class="member-col-note">空单 / 增减</span>
            </div>
            <SkeletonBlock v-if="memberLoading && !memberShort.length" :rows="8" :cells="4" />
            <div v-else class="member-list">
              <div v-for="row in memberShort" :key="`short-${row.rank}`" class="member-row">
                <span class="member-rank">{{ row.rank }}</span>
                <span class="member-name" :title="row.member">{{ row.member }}</span>
                <span class="member-pos">{{ fmtInt(row.position) }}</span>
                <span class="member-chg" :class="trendClass(row.change)">{{ fmtInt(row.change) }}</span>
              </div>
              <EmptyState v-if="!memberShort.length" text="暂无空头明细" />
            </div>
          </div>
        </div>
        <div class="members-foot">
          <span>数据：上期所 / 郑商所 / 大商所 会员持仓排名（会员合计）· {{ memberTradeDate ?? "—" }}</span>
          <span class="spacer"></span>
          <span>
            净持仓
            <b class="mono" :class="trendClass(selectedPosition?.net_pos)">{{ fmtInt(selectedPosition?.net_pos) }}</b>
            手 · 多空比 <b class="mono">{{ longShortRatio }}</b>
          </span>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import { usePolling } from "@/composables/usePolling";
import {
  fmtDate,
  fmtDateTime,
  fmtInt,
  fmtPct,
  fmtPrice,
  fmtSigned,
  fmtTime,
  freshness,
  priceDigits,
  trendClass,
} from "@/composables/useFormat";
import {
  MARKET_FILTERS,
  isDomestic,
} from "@/utils/market";
import {
  getPositionMembers,
  getPositions,
  getSnapshot,
} from "@/api/endpoints";
import type {
  ApiMeta,
  PositionMember,
  PositionRow,
  SnapshotItem,
} from "@/api/types";
import { usePrefsStore } from "@/stores/prefs";
import { useHistoryStore } from "@/stores/history";
import { useToast } from "@/stores/toast";

const prefs = usePrefsStore();
const historyStore = useHistoryStore();
const toast = useToast();
const route = useRoute();

/* ---------- 行情快照 ---------- */
const {
  data: snapshotPayload,
  loading: snapshotLoading,
  error: snapshotError,
  lastUpdated: snapshotLastUpdated,
  refresh: refreshSnapshot,
} = usePolling(getSnapshot, {
  interval: () => prefs.refreshInterval * 1000,
});

const snapshot = computed<SnapshotItem[]>(() => snapshotPayload.value?.data ?? []);
const snapshotMeta = computed<ApiMeta>(() => snapshotPayload.value?.meta ?? {});

const SEGMENTS = ["全部", "国内", "外盘"] as const;
type Segment = (typeof SEGMENTS)[number];

const query = ref("");
const segment = ref<Segment>("全部");
const category = ref("all");

/** symbol → 类别 key（来自 MARKET_FILTERS，与原型 chip 顺序一致） */
const CATEGORY_CHIPS = MARKET_FILTERS.filter((chip) => chip.key !== "all");
const categoryOf = new Map<string, string>();
for (const chip of CATEGORY_CHIPS) {
  for (const symbol of chip.symbols) {
    if (!categoryOf.has(symbol)) categoryOf.set(symbol, chip.key);
  }
}

/** 单位：真实响应无 unit 字段，按品种 / 币种映射（价格展示用） */
const UNIT_BY_SYMBOL: Record<string, string> = {
  AU: "元/克",
  AG: "元/千克",
  GC: "美元/盎司",
  SI: "美元/盎司",
  XAUUSD: "美元/盎司",
  CU: "元/吨",
  AL: "元/吨",
  ZN: "元/吨",
  NI: "元/吨",
  HG: "美元/吨",
  AL_LME: "美元/吨",
  ZN_LME: "美元/吨",
  NI_LME: "美元/吨",
  CL: "美元/桶",
  BZ: "美元/桶",
  SC: "元/桶",
  I: "元/吨",
  M: "元/吨",
  P: "元/吨",
  CF: "元/吨",
  SR: "元/吨",
  DXY: "点",
  "000300": "点",
  SPX: "点",
  NDX: "点",
  DJIA: "点",
  HSI: "点",
  "603993": "元/股",
};

function unitFor(item: SnapshotItem): string {
  const known = UNIT_BY_SYMBOL[item.symbol];
  if (known) return known;
  if (item.asset_class === "fx") return "";
  if (item.asset_class === "equity") return item.currency === "CNY" ? "元/股" : "";
  if (item.asset_class === "energy") return item.currency === "CNY" ? "元/桶" : "美元/桶";
  if (item.asset_class === "metal" || item.asset_class === "agri" || item.asset_class === "black") {
    return item.currency === "CNY" ? "元/吨" : "美元/吨";
  }
  return "";
}

/** 绝对涨跌 = 最新 − 昨收（两者都有值时） */
function changeAbs(item: SnapshotItem): number | null {
  if (item.price === null || item.price === undefined) return null;
  if (item.prev_close === null || item.prev_close === undefined) return null;
  return item.price - item.prev_close;
}

function changeAbsText(item: SnapshotItem): string {
  const diff = changeAbs(item);
  if (diff === null) return "—";
  return fmtSigned(diff, priceDigits(item.price, item.asset_class));
}

/** 幅度条：按 |pct| / 3 归一化，颜色使用涨跌 CSS 变量 */
function barStyle(pct: number | null | undefined): Record<string, string> {
  const value = typeof pct === "number" && Number.isFinite(pct) ? pct : 0;
  const width = Math.min(Math.abs(value) / 3, 1) * 100;
  const color = value > 0 ? "var(--up-color)" : value < 0 ? "var(--down-color)" : "var(--dim)";
  return { width: `${width.toFixed(1)}%`, background: color };
}

function freshnessOf(item: SnapshotItem): { text: string; level: "ok" | "warn" | "plain" } {
  return freshness(item.stale_sec, item.delay_sec);
}

function freshnessClass(item: SnapshotItem): string {
  const level = freshnessOf(item).level;
  if (level === "ok") return "badge--live";
  if (level === "warn") return "badge--warn";
  return "";
}

/* ---------- 筛选 / 排序 ---------- */
const chipBase = computed<SnapshotItem[]>(() => {
  const text = query.value.trim().toLowerCase();
  return snapshot.value.filter((item) => {
    if (segment.value === "国内" && !isDomestic(item)) return false;
    if (segment.value === "外盘" && isDomestic(item)) return false;
    if (text && !`${item.symbol} ${item.name}`.toLowerCase().includes(text)) return false;
    return true;
  });
});

const chips = computed(() =>
  MARKET_FILTERS.map((chip) => ({
    key: chip.key,
    label: chip.label,
    count:
      chip.key === "all"
        ? chipBase.value.length
        : chipBase.value.filter((item) => categoryOf.get(item.symbol) === chip.key).length,
  })),
);

const filtered = computed<SnapshotItem[]>(() =>
  chipBase.value.filter((item) => {
    if (category.value === "all") return true;
    return categoryOf.get(item.symbol) === category.value;
  }),
);

type SortKey = "price" | "chgAbs" | "chg";

const sortKey = ref<SortKey>("chg");
const sortDir = ref<"asc" | "desc">("desc");

const sortLabel = computed(
  () => ({ price: "最新", chgAbs: "涨跌", chg: "涨跌幅" })[sortKey.value],
);

function sortValue(item: SnapshotItem): number | null {
  if (sortKey.value === "price") return item.price ?? null;
  if (sortKey.value === "chgAbs") return changeAbs(item);
  return item.change_pct ?? null;
}

function sortItems(items: SnapshotItem[]): SnapshotItem[] {
  const direction = sortDir.value === "desc" ? -1 : 1;
  return items.slice().sort((a, b) => {
    const left = sortValue(a);
    const right = sortValue(b);
    if (left === null && right === null) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    return (left - right) * direction;
  });
}

function toggleSort(key: SortKey): void {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === "desc" ? "asc" : "desc";
  } else {
    sortKey.value = key;
    sortDir.value = "desc";
  }
}

function sortArrow(key: SortKey): string {
  if (sortKey.value !== key) return "";
  return sortDir.value === "desc" ? "↓" : "↑";
}

const groups = computed(() => {
  const result: Array<{
    key: string;
    label: string;
    items: SnapshotItem[];
    up: number;
    down: number;
  }> = [];
  const used = new Set<string>();
  for (const chip of CATEGORY_CHIPS) {
    const items = filtered.value.filter((item) => categoryOf.get(item.symbol) === chip.key);
    if (!items.length) continue;
    items.forEach((item) => used.add(item.symbol));
    result.push({
      key: chip.key,
      label: chip.label,
      items: sortItems(items),
      up: items.filter((item) => (item.change_pct ?? 0) > 0).length,
      down: items.filter((item) => (item.change_pct ?? 0) < 0).length,
    });
  }
  const rest = filtered.value.filter((item) => !used.has(item.symbol));
  if (rest.length) {
    result.push({
      key: "other",
      label: "其他",
      items: sortItems(rest),
      up: rest.filter((item) => (item.change_pct ?? 0) > 0).length,
      down: rest.filter((item) => (item.change_pct ?? 0) < 0).length,
    });
  }
  return result;
});

const categoryLabel = computed(
  () =>
    MARKET_FILTERS.find((chip) => chip.key === category.value)?.label === "全部"
      ? "全部品种"
      : (MARKET_FILTERS.find((chip) => chip.key === category.value)?.label ?? "全部品种"),
);

const sourceCount = computed(() => new Set(filtered.value.map((item) => item.source ?? "—")).size);

const todayLabel = computed(() => {
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${fmtDate(new Date().toISOString())} ${weekdays[new Date().getDay()]}`;
});

/* ---------- 持仓结构 / 会员持仓 ---------- */
const {
  data: positionsPayload,
  loading: positionsLoading,
  error: positionsError,
  lastUpdated: positionsLastUpdated,
  refresh: refreshPositions,
} = usePolling(getPositions, { interval: 300000 });

const positions = computed<PositionRow[]>(() => positionsPayload.value?.data ?? []);
const positionsTradeDate = computed(() => positionsPayload.value?.trade_date ?? null);

/** 净占比：net_ratio 为小数，转成百分比展示 */
function netRatioText(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return "—";
  return fmtPct(ratio * 100, 1);
}

const memberProduct = ref("");
const members = ref<PositionMember[]>([]);
const memberTradeDate = ref<string | null>(null);
const memberLoading = ref(false);
const memberError = ref<Error | null>(null);

const memberLong = computed(() => members.value.filter((row) => row.side === "long"));
const memberShort = computed(() => members.value.filter((row) => row.side === "short"));

const selectedPosition = computed<PositionRow | undefined>(() =>
  positions.value.find((row) => row.product === memberProduct.value),
);

const memberSub = computed(() => {
  const name = selectedPosition.value?.name ?? "";
  const code = memberProduct.value ? memberProduct.value.toUpperCase() : "—";
  return `${name}（${code}）· ${memberTradeDate.value ?? "—"} · 净持仓 = 多 − 空`;
});

const longShortRatio = computed(() => {
  const row = selectedPosition.value;
  if (!row || !row.short_pos) return "—";
  return (row.long_pos / row.short_pos).toFixed(2);
});

async function loadMembers(): Promise<void> {
  const product = memberProduct.value;
  if (!product) return;
  memberLoading.value = true;
  memberError.value = null;
  try {
    const payload = await getPositionMembers(product, 20);
    members.value = payload.data ?? [];
    memberTradeDate.value = payload.trade_date;
  } catch (err) {
    memberError.value = err instanceof Error ? err : new Error(String(err));
  } finally {
    memberLoading.value = false;
  }
}

watch(
  positions,
  (list) => {
    if (!list.length) return;
    const exists = list.some((row) => row.product === memberProduct.value);
    if (exists) return;
    const preferred = list.find((row) => row.product.toLowerCase() === "au");
    memberProduct.value = preferred?.product ?? list[0].product;
  },
  { immediate: true },
);

watch(memberProduct, (product, previous) => {
  if (!product || product === previous) return;
  members.value = [];
  memberTradeDate.value = null;
  void loadMembers();
});

/* ---------- 历史走势 ---------- */
function openInstrument(item: SnapshotItem): void {
  void historyStore.openHistory("instrument", item.symbol, item.name);
}

/** 命令面板跳转 /market?symbol=AU 时自动打开该标的历史走势 */
let handledQuerySymbol = "";
watch(
  [() => route.query.symbol, snapshot],
  () => {
    const raw = route.query.symbol;
    const symbol = typeof raw === "string" ? raw.trim() : "";
    if (!symbol) return;
    if (handledQuerySymbol && handledQuerySymbol.toLowerCase() === symbol.toLowerCase()) return;
    const matched = snapshot.value.find(
      (item) =>
        item.symbol.toLowerCase() === symbol.toLowerCase() ||
        item.name.toLowerCase() === symbol.toLowerCase(),
    );
    if (!matched && !snapshot.value.length) return;
    handledQuerySymbol = matched?.symbol ?? symbol;
    void historyStore.openHistory("instrument", matched?.symbol ?? symbol, matched?.name ?? symbol);
  },
  { immediate: true },
);

/* ---------- 刷新 ---------- */
function refreshAll(): void {
  void refreshSnapshot();
  void refreshPositions();
  if (memberProduct.value) void loadMembers();
  toast.info("正在刷新行情与持仓数据");
}
</script>

<style scoped>
.mkt-row {
  cursor: pointer;
}
.mkt-row:focus-visible td {
  background: var(--accent-weak);
}
.unit {
  margin-left: 3px;
  font-family: var(--sans);
  font-size: 9px;
  color: var(--dim);
}
.sort-dir {
  display: inline-block;
  width: 9px;
  font-family: var(--mono);
  font-size: 9px;
  line-height: 1;
}
.src-badge {
  margin-left: 5px;
}
.ev-cell {
  cursor: default;
}
.pos-name {
  margin-left: 6px;
  font-size: 11px;
}
.block-gap {
  margin-top: 10px;
}
.member-select {
  height: 26px;
  padding: 0 22px 0 8px;
  font-size: 10.5px;
  background-position: calc(100% - 11px) 10px, calc(100% - 7px) 10px;
}
.member-name {
  min-width: 0;
}
</style>
