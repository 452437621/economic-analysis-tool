<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">今日 · 交易</div>
        <h1 class="page-h1">
          交易
          <span class="gen-at">（生成于 {{ generatedLabel }}）</span>
        </h1>
      </div>
      <div class="page-actions">
        <button class="btn btn--sm btn--primary" type="button" @click="openCreate">
          <svg class="ic"><use href="#i-plus" /></svg>新建交易
        </button>
        <button class="btn btn--sm" type="button" :disabled="loading" @click="load">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <!-- KPI：总笔数 / 胜率 / 累计盈亏 / 盈亏比 / 累计手续费 -->
    <div class="trd-kpis">
      <section class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-db" /></svg></span>
          <span class="kpi-label">总笔数</span>
        </div>
        <div class="kpi-value">{{ summary ? fmtInt(summary.count) : "—" }}<small>笔</small></div>
        <div class="kpi-sub">
          已平仓 {{ summary ? fmtInt(summary.closed) : "—" }} · 持仓 {{ summary ? fmtInt(summary.open) : "—" }} ·
          计划 {{ summary ? fmtInt(summary.planned) : "—" }}
        </div>
      </section>

      <section class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-target" /></svg></span>
          <span class="kpi-label">胜率</span>
        </div>
        <div class="kpi-value">{{ winRateText }}</div>
        <div class="kpi-sub">
          盈 {{ summary ? fmtInt(summary.wins) : "—" }} · 亏 {{ summary ? fmtInt(summary.losses) : "—" }}（按已平仓）
        </div>
      </section>

      <section class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
          <span class="kpi-label">累计盈亏</span>
        </div>
        <div class="kpi-value" :class="pnlClass(summary?.total_pnl)">
          {{ fmtSigned(summary?.total_pnl, 2) }}
        </div>
        <div class="kpi-sub">均笔 {{ fmtSigned(summary?.avg_pnl, 2) }} · 均盈 {{ fmtSigned(summary?.avg_win, 2) }} · 均亏 {{ fmtSigned(summary?.avg_loss, 2) }}</div>
      </section>

      <section class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-chart" /></svg></span>
          <span class="kpi-label">盈亏比</span>
        </div>
        <div class="kpi-value">{{ fmtNumber(summary?.avg_rr, 2) }}</div>
        <div class="kpi-sub">盈利因子 {{ fmtNumber(summary?.profit_factor, 2) }}（均盈 / 均亏）</div>
      </section>

      <section class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-copy" /></svg></span>
          <span class="kpi-label">累计手续费</span>
        </div>
        <div class="kpi-value">{{ fmtNumber(summary?.total_fee, 2) }}</div>
        <div class="kpi-sub">笔均 {{ avgFeeText }}</div>
      </section>
    </div>

    <!-- 工具栏：搜索 / 品种类型 / 方向 / 状态 / 日期区间 / 重置 -->
    <div class="card toolbar trd-toolbar">
      <div class="tool-row">
        <label class="field field--search">
          <svg class="ic"><use href="#i-search" /></svg>
          <input
            v-model="query"
            type="search"
            placeholder="搜索代码 / 名称 / 策略 / 归因"
            autocomplete="off"
          />
        </label>
        <select v-model="assetClass" class="select" aria-label="品种类型">
          <option value="">全部类型</option>
          <option v-for="item in ASSET_CLASSES" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>
        <select v-model="direction" class="select" aria-label="方向">
          <option value="">全部方向</option>
          <option value="long">做多</option>
          <option value="short">做空</option>
        </select>
        <select v-model="status" class="select" aria-label="状态">
          <option value="">全部状态</option>
          <option v-for="item in STATUSES" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>
        <label class="trd-date">
          <span>日期</span>
          <input v-model="dateFrom" type="date" aria-label="开始日期" />
        </label>
        <label class="trd-date">
          <span>至</span>
          <input v-model="dateTo" type="date" aria-label="结束日期" />
        </label>
        <button class="btn btn--sm btn--ghost" type="button" @click="resetFilters">
          <svg class="ic"><use href="#i-close" /></svg>重置
        </button>
        <div class="tool-right">
          <span class="tool-note">共 {{ total }} 笔 · 第 {{ pageStart }}–{{ pageEnd }} 条</span>
        </div>
      </div>
    </div>

    <!-- 交易记录表 -->
    <div class="card table-card">
      <div class="card-head">
        <span class="card-title">交易记录</span>
        <span class="card-sub">按交易日倒序 · 股票 / 期货 / 期权 / 外汇 / 加密</span>
        <div class="card-actions">
          <span class="badge badge--sm">本页 {{ items.length }} 笔</span>
        </div>
      </div>

      <div v-if="error && items.length" class="trd-banner">
        <svg class="ic"><use href="#i-alert" /></svg>
        <span>刷新失败：{{ errorMessage }}</span>
        <button class="btn btn--sm btn--ghost" type="button" @click="load">重试</button>
      </div>

      <div class="table-wrap trd-wrap">
        <SkeletonBlock v-if="loading && !items.length" :rows="8" :cells="6" />
        <ErrorState v-else-if="error && !items.length" :error="errorMessage" @retry="load" />
        <EmptyState
          v-else-if="!items.length"
          text="还没有交易记录"
          hint="记录一笔计划或已执行交易：品种、方向、价格、仓位与复盘结论都能留在这里。"
        >
          <button class="btn btn--sm btn--primary" type="button" @click="openCreate">
            <svg class="ic"><use href="#i-plus" /></svg>新建交易
          </button>
        </EmptyState>

        <table v-else class="data-table trd-table">
          <thead>
            <tr>
              <th style="width: 92px">交易日期</th>
              <th style="width: 130px">品种</th>
              <th style="width: 56px">类型</th>
              <th style="width: 52px">方向</th>
              <th style="width: 74px">状态</th>
              <th style="width: 84px" class="num">数量（计划 / 实际）</th>
              <th style="width: 82px" class="num">开仓价</th>
              <th style="width: 82px" class="num">平仓价</th>
              <th style="width: 108px" class="num">盈亏</th>
              <th style="width: 62px" class="num">盈亏比</th>
              <th style="width: 118px">策略</th>
              <th style="width: 112px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.id">
              <td class="mono">{{ row.trade_date }}</td>
              <td>
                <span class="sym">{{ row.symbol }}</span>
                <span class="nm trd-name" :title="row.name ?? ''">{{ row.name || "—" }}</span>
              </td>
              <td>
                <span class="badge badge--sm">{{ assetLabel(row.asset_class) }}</span>
              </td>
              <td>
                <span :class="row.direction === 'long' ? 'trd-long' : 'trd-short'">
                  {{ row.direction === "long" ? "做多" : "做空" }}
                </span>
              </td>
              <td>
                <span class="badge badge--sm" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
              </td>
              <td class="num">
                <span class="mono">{{ fmtQty(row.planned_qty) }}</span>
                <span class="trd-sep">/</span>
                <span class="mono">{{ fmtQty(row.filled_qty) }}</span>
              </td>
              <td class="num" :title="`止损 ${fmtPrice(row.stop_price, row.asset_class)} · 止盈 ${fmtPrice(row.target_price, row.asset_class)}`">
                {{ fmtPrice(row.entry_price, row.asset_class) }}
              </td>
              <td class="num">{{ fmtPrice(row.exit_price, row.asset_class) }}</td>
              <td
                class="num trd-pnl"
                :class="pnlClass(row.pnl)"
                :title="`保证金 ${fmtNumber(row.margin, 2)} · 手续费 ${fmtNumber(row.fee, 2)}${row.planned_win_rate !== null ? ` · 预计胜率 ${fmtNumber(row.planned_win_rate * 100, 0)}%` : ''}`"
              >
                <span>{{ fmtSigned(row.pnl, 2) }}</span>
                <small v-if="row.pnl_pct !== null" class="trd-pct">{{ fmtPct(row.pnl_pct * 100, 1) }}</small>
              </td>
              <td class="num">{{ fmtNumber(row.rr, 2) }}</td>
              <td>
                <span class="trd-strategy" :title="row.strategy ?? ''">{{ row.strategy || "—" }}</span>
              </td>
              <td>
                <div class="td-actions">
                  <template v-if="confirmId === row.id">
                    <button
                      class="btn btn--sm btn--ghost trd-danger"
                      type="button"
                      :disabled="deleting"
                      @click="remove(row)"
                    >
                      确认删除
                    </button>
                    <button class="btn btn--sm btn--ghost" type="button" :disabled="deleting" @click="cancelDelete">
                      取消
                    </button>
                  </template>
                  <template v-else>
                    <button class="btn btn--sm btn--ghost" type="button" @click="openEdit(row)">编辑</button>
                    <button class="btn btn--sm btn--ghost trd-danger" type="button" @click="askDelete(row)">
                      删除
                    </button>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="table-foot">
        <span>共 <b>{{ total }}</b> 条 · 第 <b>{{ pageStart }}</b>–<b>{{ pageEnd }}</b> 条</span>
        <span class="spacer"></span>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="offset === 0 || loading" @click="prevPage">
          <svg class="ic"><use href="#i-chevron-left" /></svg>上一页
        </button>
        <span class="mono trd-page">{{ page }} / {{ pageCount }}</span>
        <button
          class="btn btn--sm btn--ghost"
          type="button"
          :disabled="offset + limit >= total || loading"
          @click="nextPage"
        >
          下一页<svg class="ic"><use href="#i-chevron-right" /></svg>
        </button>
      </div>
    </div>

    <TradeFormDrawer
      :open="drawerOpen"
      :trade="editing"
      @close="closeDrawer"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import TradeFormDrawer from "@/components/trades/TradeFormDrawer.vue";
import { ApiError } from "@/api/client";
import { deleteTrade, listTrades } from "@/api/endpoints";
import type { TradeQuery } from "@/api/endpoints";
import type {
  TradeAssetClass,
  TradeDirection,
  TradeItem,
  TradeStatus,
  TradeSummary,
} from "@/api/types";
import { fmtDateTime, fmtInt, fmtNumber, fmtPct, fmtPrice, fmtSigned } from "@/composables/useFormat";
import { useToast } from "@/stores/toast";

const toast = useToast();

const ASSET_CLASSES: { value: TradeAssetClass; label: string }[] = [
  { value: "futures", label: "期货" },
  { value: "stock", label: "股票" },
  { value: "option", label: "期权" },
  { value: "forex", label: "外汇" },
  { value: "crypto", label: "加密" },
  { value: "other", label: "其他" },
];

const STATUSES: { value: TradeStatus; label: string }[] = [
  { value: "planned", label: "计划" },
  { value: "open", label: "持仓中" },
  { value: "closed", label: "已平仓" },
  { value: "cancelled", label: "已取消" },
];

const ASSET_LABEL: Record<string, string> = Object.fromEntries(
  ASSET_CLASSES.map((item) => [item.value, item.label]),
);
const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  STATUSES.map((item) => [item.value, item.label]),
);

const items = ref<TradeItem[]>([]);
const total = ref(0);
const limit = ref(20);
const offset = ref(0);
const summary = ref<TradeSummary | null>(null);
const loading = ref(false);
const error = ref<Error | null>(null);
const fetchedAt = ref("");
const deleting = ref(false);
const confirmId = ref<string | null>(null);

const query = ref("");
const assetClass = ref<"" | TradeAssetClass>("");
const direction = ref<"" | TradeDirection>("");
const status = ref<"" | TradeStatus>("");
const dateFrom = ref("");
const dateTo = ref("");

const drawerOpen = ref(false);
const editing = ref<TradeItem | null>(null);

const errorMessage = computed(() => {
  const err = error.value;
  if (!err) return "";
  const raw = err instanceof Error ? err.message.trim() : String(err);
  // 后端错误体常为 {"detail":"..."}，错误状态里只展示可读部分
  let detail = raw;
  if (raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* 保留原文 */
    }
  }
  if (err instanceof ApiError && err.status === 404) {
    return "接口未找到（404）：后端可能尚未重启并加载 /api/trades";
  }
  return detail ? `加载失败：${detail}` : "加载失败";
});
const pageStart = computed(() => (total.value ? offset.value + 1 : 0));
const pageEnd = computed(() => offset.value + items.value.length);
const page = computed(() => Math.floor(offset.value / limit.value) + 1);
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / limit.value)));

const winRateText = computed(() =>
  summary.value ? `${fmtNumber(summary.value.win_rate * 100, 1)}%` : "—",
);
const avgFeeText = computed(() => {
  const current = summary.value;
  if (!current || !current.count) return "—";
  return fmtNumber(current.total_fee / current.count, 2);
});

/** 数据生成时间：最近一次记录更新（无记录时用本次拉取时间），不显示系统当前时间 */
const generatedAt = computed(() => {
  let latest = "";
  for (const row of items.value) {
    const stamp = row.updated_at ?? row.created_at;
    if (stamp && stamp > latest) latest = stamp;
  }
  return latest || fetchedAt.value;
});
/** 后端返回的时间戳为无时区的 UTC ISO 串（如 2026-11-17T15:17:47），若直接按本地解析会偏 8 小时 */
function asUtcIso(stamp: string): string {
  if (!stamp) return "";
  return /(?:z|[+-]\d{2}:?\d{2})$/i.test(stamp) ? stamp : `${stamp}Z`;
}
const generatedLabel = computed(() =>
  generatedAt.value ? fmtDateTime(asUtcIso(generatedAt.value)) : "—",
);

function assetLabel(value: string): string {
  return ASSET_LABEL[value] ?? value;
}

function statusLabel(value: string): string {
  return STATUS_LABEL[value] ?? value;
}

function statusClass(value: string): string {
  if (value === "open") return "badge--accent";
  if (value === "closed") return "badge--live";
  if (value === "cancelled") return "badge--warn";
  return "";
}

// 按需求固定语义：盈亏正绿负红、做多绿做空红（不随「涨跌配色」偏好翻转）
function pnlClass(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) return "flat";
  return value > 0 ? "trd-pos" : "trd-neg";
}

function fmtQty(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return Number.isInteger(value) ? fmtInt(value) : fmtNumber(value, 2);
}

let requestSeq = 0;

function buildQuery(): TradeQuery {
  const params: TradeQuery = {
    limit: limit.value,
    offset: offset.value,
    sort: "trade_date",
    order: "desc",
  };
  const keyword = query.value.trim();
  if (keyword) params.q = keyword;
  if (assetClass.value) params.asset_class = assetClass.value;
  if (direction.value) params.direction = direction.value;
  if (status.value) params.status = status.value;
  if (dateFrom.value) params.date_from = dateFrom.value;
  if (dateTo.value) params.date_to = dateTo.value;
  return params;
}

async function load(): Promise<void> {
  const seq = ++requestSeq;
  loading.value = true;
  error.value = null;
  try {
    const payload = await listTrades(buildQuery());
    if (seq !== requestSeq) return;
    items.value = payload.items;
    total.value = payload.total;
    summary.value = payload.summary;
    fetchedAt.value = new Date().toISOString();
    if (confirmId.value && !payload.items.some((row) => row.id === confirmId.value)) {
      confirmId.value = null;
    }
  } catch (err) {
    if (seq !== requestSeq) return;
    error.value = err instanceof Error ? err : new Error(String(err));
  } finally {
    if (seq === requestSeq) loading.value = false;
  }
}

let searchTimer: number | undefined;
watch(query, () => {
  if (searchTimer) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    offset.value = 0;
    void load();
  }, 300);
});

watch([assetClass, direction, status, dateFrom, dateTo], () => {
  offset.value = 0;
  void load();
});

function resetFilters(): void {
  query.value = "";
  assetClass.value = "";
  direction.value = "";
  status.value = "";
  dateFrom.value = "";
  dateTo.value = "";
  offset.value = 0;
  void load();
}

function prevPage(): void {
  if (offset.value === 0) return;
  offset.value = Math.max(0, offset.value - limit.value);
  void load();
}

function nextPage(): void {
  if (offset.value + limit.value >= total.value) return;
  offset.value += limit.value;
  void load();
}

function openCreate(): void {
  editing.value = null;
  drawerOpen.value = true;
}

function openEdit(row: TradeItem): void {
  editing.value = row;
  drawerOpen.value = true;
}

function closeDrawer(): void {
  drawerOpen.value = false;
  editing.value = null;
}

async function onSaved(item: TradeItem): Promise<void> {
  const wasEdit = Boolean(editing.value);
  drawerOpen.value = false;
  editing.value = null;
  toast.ok(wasEdit ? `已更新交易 ${item.symbol}` : `已添加交易 ${item.symbol}`);
  await load();
}

function askDelete(row: TradeItem): void {
  confirmId.value = row.id;
}

function cancelDelete(): void {
  confirmId.value = null;
}

async function remove(row: TradeItem): Promise<void> {
  if (deleting.value) return;
  deleting.value = true;
  try {
    await deleteTrade(row.id);
    confirmId.value = null;
    if (items.value.length === 1 && offset.value > 0) {
      offset.value = Math.max(0, offset.value - limit.value);
    }
    await load();
    toast.ok(`已删除交易 ${row.symbol}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    toast.bad(`删除失败：${message}`);
  } finally {
    deleting.value = false;
  }
}

onMounted(() => void load());
onBeforeUnmount(() => {
  if (searchTimer) window.clearTimeout(searchTimer);
});
</script>

<style scoped>
.trd-kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-top: 8px;
}

.trd-kpis .kpi {
  min-width: 0;
}

.trd-toolbar {
  margin-top: 10px;
}

.trd-date {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control, 8px);
  background: var(--surface-2);
  font-size: 10px;
  color: var(--dim);
}

.trd-date input {
  width: 112px;
  border: 0;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 11px;
  outline: none;
}

.trd-date input::-webkit-calendar-picker-indicator {
  cursor: pointer;
  opacity: 0.6;
}

.trd-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 13px;
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--up) 8%, transparent);
  color: var(--muted);
  font-size: 10.5px;
}

.trd-banner .ic {
  width: 13px;
  height: 13px;
  color: var(--warn);
}

.trd-wrap {
  max-height: calc(100vh - 438px);
  min-height: 200px;
}

.trd-table {
  /* 12 列压到一屏内：止损/止盈并入开仓价 tooltip，保证金/手续费/预计胜率并入盈亏 tooltip，
     避免 1440 宽下横向滚动把「盈亏 / 操作」挤出可视区。 */
  min-width: 1050px;
}

.trd-name {
  margin-left: 6px;
}

.trd-sep {
  margin: 0 1px;
  color: var(--dim);
}

.trd-pnl span {
  font-family: var(--mono);
}

.trd-pct {
  display: block;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.1;
}

.trd-strategy {
  display: inline-block;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
  color: var(--muted);
}

/* 固定语义：做多绿 / 做空红；盈利绿 / 亏损红 */
.trd-long,
.trd-pos {
  color: var(--ok);
}

.trd-short,
.trd-neg {
  color: var(--up);
}

.trd-danger {
  color: var(--up);
}

.trd-page {
  font-size: 10px;
  color: var(--muted);
}

@media (max-width: 1180px) {
  .trd-kpis {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .trd-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
