<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 利率 · {{ todayLabel }}</div>
        <h1 class="page-h1">
          利率与流动性
          <span class="page-sub">{{ rows.length }} 个序列 · 更新于 {{ latestAsOfText }}</span>
        </h1>
      </div>
      <div class="page-actions">
        <button class="btn btn--sm" type="button" :disabled="macroLoading" @click="refreshAll">
          <svg class="ic" :class="{ spin: macroLoading }"><use href="#i-refresh" /></svg>刷新
        </button>
        <RouterLink class="btn btn--sm btn--ghost" to="/analysis">
          <svg class="ic"><use href="#i-activity" /></svg>分析引擎
        </RouterLink>
      </div>
    </div>

    <!-- 空态 / 错误态 / 骨架 -->
    <section v-if="!rows.length" class="card">
      <SkeletonBlock v-if="!macroLastUpdated && !macroError" :rows="6" :cells="4" />
      <ErrorState v-else-if="macroError" :error="macroError" @retry="refreshLatest" />
      <EmptyState v-else text="暂无利率数据" hint="等待 collect_rates 采集任务写入宏观序列后刷新。" />
    </section>

    <template v-else>
      <!-- SOFR / EFFR 利差：醒目卡片 -->
      <section
        v-if="spread"
        class="card spread-card"
        role="button"
        tabindex="0"
        :title="`${spreadRow?.name ?? 'SOFR − EFFR 利差'}（${spreadRow?.code ?? 'SOFR_EFFR'}）· 点击查看历史走势`"
        @click="openSpread"
        @keydown.enter="openSpread"
      >
        <div class="spread-main">
          <div class="spread-label">
            <svg class="ic"><use href="#i-rates" /></svg>
            SOFR − EFFR 利差
            <span class="badge badge--sm" :class="spread.zoneClass">{{ spread.zone }}</span>
          </div>
          <div class="spread-value mono" :class="spread.trend">
            {{ spread.valueText }}<small>{{ spread.unit }}</small>
          </div>
          <div class="spread-chg">
            日变动 <b class="mono" :class="spread.chgTrend">{{ spread.chgText }}</b>
            <span class="dim"> · 观测 {{ spread.updatedText }}</span>
          </div>
        </div>
        <div class="spread-side">
          <div class="spread-row">
            <span class="sr-label">SOFR <em>隔夜担保融资利率</em></span>
            <b class="mono">{{ sofrText }}</b>
          </div>
          <div class="spread-row">
            <span class="sr-label">EFFR <em>有效联邦基金利率</em></span>
            <b class="mono">{{ effrText }}</b>
          </div>
          <p class="spread-note">{{ spread.note }}</p>
        </div>
      </section>

      <!-- 按 MACRO_GROUPS 分组的序列卡片 -->
      <div class="macro-groups">
        <section
          v-for="(group, index) in groups"
          :key="group.label"
          class="card macro-group"
          :class="{ 'macro-group--wide': index === 0 }"
        >
          <div class="card-head">
            <span class="card-title">{{ group.label }}</span>
            <span class="card-sub">{{ group.rows.length }} 个序列</span>
            <div class="card-actions"><span class="card-sub">最新值 · 日变动</span></div>
          </div>
          <div class="macro-items">
            <button
              v-for="row in group.rows"
              :key="row.code"
              class="macro-item"
              type="button"
              :title="`${row.name}（${row.code}）· 点击查看历史走势`"
              @click="openMacro(row)"
            >
              <span class="mi-top">
                <span class="mi-name">{{ row.label }}<em v-if="row.freq" class="mi-freq">{{ row.freq }}</em></span>
                <span class="mi-code">{{ row.code }}</span>
              </span>
              <span class="mi-value-row">
                <span class="mi-value">{{ fmtMacro(row.value, row.unit) }}</span>
                <span class="mi-asof" :class="{ 'mi-asof--stale': daysAgo(row) > 5 }">{{ asOfText(row) }}</span>
              </span>
              <span class="mi-bottom">
                <span class="mi-chg" :class="changeClass(row.code)">{{ changeText(row.code) }}</span>
                <span class="mi-spark">
                  <Sparkline
                    v-if="sparkOf(row.code).length > 1"
                    :values="sparkOf(row.code)"
                    :positive="sparkPositive(row.code)"
                  />
                </span>
              </span>
            </button>
          </div>
        </section>
      </div>

      <div class="card macro-foot">
        <svg class="ic"><use href="#i-info" /></svg>
        <span>
          收益率单位 %，利差单位 pp；日变动按最近两个观测值计算，{{ seriesNote }}；点击任一序列打开历史走势，
          区间切换（1月 / 3月 / 6月 / 1年…）在弹窗内完成。
        </span>
        <span class="spacer"></span>
        <span class="macro-foot-meta">{{ seriesLoading ? "序列加载中…" : `${readySeriesCount} / ${SERIES_CODES.length} 已就绪` }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import Sparkline from "@/components/ui/Sparkline.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtMacro, fmtNumber, fmtSigned, fmtTime, trendClass } from "@/composables/useFormat";
import { MACRO_GROUPS } from "@/utils/market";
import { getMacroLatest, getMacroSeries } from "@/api/endpoints";
import type { MacroLatestItem, MacroSeriesResponse } from "@/api/types";
import { useHistoryStore } from "@/stores/history";
import { useToast } from "@/stores/toast";

const historyStore = useHistoryStore();
const toast = useToast();

/* ---------- 最新值（60s 轮询） ---------- */
const {
  data: macroPayload,
  loading: macroLoading,
  error: macroError,
  lastUpdated: macroLastUpdated,
  refresh: refreshLatest,
} = usePolling(getMacroLatest, { interval: 60000 });

const rows = computed<MacroLatestItem[]>(() => macroPayload.value?.data ?? []);
const byCode = computed(() => new Map(rows.value.map((row) => [row.code, row])));

const latestAsOfText = computed(() => {
  const latest = rows.value.reduce((max, row) => (row.ts > max ? row.ts : max), "");
  return latest ? fmtTime(latest, true) : "—";
});

function daysAgo(row: MacroLatestItem): number {
  if (!row.ts) return 0;
  const date = new Date(row.ts);
  if (Number.isNaN(date.getTime())) return 0;
  const now = new Date();
  const target = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((today - target) / 86400000);
}

function asOfText(row: MacroLatestItem): string {
  if (!row.ts) return "无数据";
  const day = fmtDate(row.ts).slice(5);
  const days = daysAgo(row);
  return days <= 0 ? `${day} 当日` : `${day}（${days} 天前）`;
}

const todayLabel = computed(() => {
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${fmtDate(new Date().toISOString())} ${weekdays[new Date().getDay()]}`;
});

/* ---------- 日变动 / 迷你走势：仅 10 个主要序列（避免 22 个全量请求） ---------- */
const SERIES_CODES = [
  "SOFR",
  "EFFR",
  "SOFR_EFFR",
  "US2Y",
  "US10Y",
  "US30Y",
  "CN2Y",
  "CN10Y",
  "JP10Y",
  "DE10Y",
] as const;

const seriesMap = ref<Record<string, number[]>>({});
const seriesLoading = ref(false);
const seriesFailed = ref(0);

async function loadSeries(): Promise<void> {
  seriesLoading.value = true;
  try {
    const results = await Promise.allSettled(
      SERIES_CODES.map(async (code): Promise<{ code: string; values: number[] }> => {
        const payload: MacroSeriesResponse = await getMacroSeries(code, 10);
        const values = payload.data
          .map((point) => Number(point.value))
          .filter((value) => Number.isFinite(value));
        return { code, values };
      }),
    );
    const next: Record<string, number[]> = {};
    let failed = 0;
    for (const result of results) {
      if (result.status === "fulfilled") next[result.value.code] = result.value.values;
      else failed += 1;
    }
    seriesMap.value = { ...seriesMap.value, ...next };
    seriesFailed.value = failed;
  } finally {
    seriesLoading.value = false;
  }
}

function sparkOf(code: string): number[] {
  return seriesMap.value[code] ?? [];
}

function changeOf(code: string): number | null {
  const values = sparkOf(code);
  if (values.length < 2) return null;
  const last = values[values.length - 1];
  const previous = values[values.length - 2];
  const diff = last - previous;
  return Number.isFinite(diff) ? Number(diff.toFixed(2)) : null;
}

function changeText(code: string): string {
  const change = changeOf(code);
  if (change === null) return "—";
  const row = byCode.value.get(code);
  const suffix =
    row?.unit === "%" || row?.unit === "pp" ? "pp" : row?.unit ? ` ${row.unit}` : "";
  return `${fmtSigned(change, 2)}${suffix}`;
}

function changeClass(code: string): string {
  return trendClass(changeOf(code));
}

function sparkPositive(code: string): boolean | null {
  const change = changeOf(code);
  if (change === null) return null;
  return change > 0;
}

const readySeriesCount = computed(() => Object.keys(seriesMap.value).length);

const seriesNote = computed(() => {
  const total = SERIES_CODES.length;
  if (!readySeriesCount.value) return `覆盖 ${total} 个主要序列（加载中或请求失败）`;
  if (seriesFailed.value) {
    return `覆盖 ${readySeriesCount.value} / ${total} 个主要序列（${seriesFailed.value} 个拉取失败）`;
  }
  return `覆盖 ${readySeriesCount.value} / ${total} 个主要序列`;
});

/* ---------- SOFR / EFFR 利差卡片 ---------- */
const spreadRow = computed(() => byCode.value.get("SOFR_EFFR"));
const sofrRow = computed(() => byCode.value.get("SOFR"));
const effrRow = computed(() => byCode.value.get("EFFR"));

interface SpreadView {
  valueText: string;
  unit: string;
  trend: "up" | "down" | "flat";
  zone: string;
  zoneClass: string;
  chgText: string;
  chgTrend: "up" | "down" | "flat";
  note: string;
  updatedText: string;
}

const spread = computed<SpreadView | null>(() => {
  const row = spreadRow.value;
  if (!row) return null;
  const value = Number(row.value);
  const change = changeOf(row.code);
  const above = value > 0.005;
  const below = value < -0.005;
  return {
    valueText: fmtNumber(value, 2),
    unit: row.unit || "pp",
    trend: trendClass(value),
    zone: above ? "偏紧" : below ? "偏松" : "持平",
    zoneClass: above ? "badge--up" : below ? "badge--down" : "",
    chgText: changeText(row.code),
    chgTrend: trendClass(change),
    note: above
      ? `SOFR 高于 EFFR ${fmtSigned(value, 2)}pp：隔夜回购融资成本高于有效联邦基金利率，银行准备金边际偏紧。`
      : below
        ? `SOFR 低于 EFFR ${fmtSigned(value, 2)}pp：隔夜融资成本低于有效联邦基金利率，流动性边际宽松。`
        : "SOFR 与 EFFR 基本持平：隔夜资金面平稳，利差无方向性信号。",
    updatedText: fmtTime(row.ts, true),
  };
});

const sofrText = computed(() =>
  sofrRow.value ? fmtMacro(sofrRow.value.value, sofrRow.value.unit) : "—",
);
const effrText = computed(() =>
  effrRow.value ? fmtMacro(effrRow.value.value, effrRow.value.unit) : "—",
);

/* ---------- 分组 ---------- */
interface MacroItemRow extends MacroLatestItem {
  label: string;
  freq: string;
}

function displayLabel(name: string, code: string): { label: string; freq: string } {
  let text = name.replace(new RegExp(`[（(]${code}[）)]`, "i"), "").trim();
  let freq = "";
  const match = text.match(/[（(](周度|月度|季度|年度)[）)]\s*$/);
  if (match) {
    freq = match[1].replace("度", "");
    text = text.slice(0, match.index).trim();
  }
  return { label: text || name, freq };
}

const groups = computed(() =>
  MACRO_GROUPS.map((group) => ({
    label: group.label,
    rows: group.codes
      .map((code) => byCode.value.get(code))
      .filter((row): row is MacroLatestItem => Boolean(row))
      .map((row): MacroItemRow => ({ ...row, ...displayLabel(row.name, row.code) })),
  })).filter((group) => group.rows.length > 0),
);

/* ---------- 交互 ---------- */
function openMacro(row: MacroItemRow): void {
  void historyStore.openHistory("macro", row.code, row.name, row.unit);
}

function openSpread(): void {
  const row = spreadRow.value;
  if (!row) return;
  void historyStore.openHistory("macro", row.code, row.name, row.unit);
}

function refreshAll(): void {
  void refreshLatest();
  void loadSeries();
  toast.info("正在刷新利率与流动性数据");
}

onMounted(() => {
  void loadSeries();
});
</script>

<style scoped>
/* ---------- 利差醒目卡片 ---------- */
.spread-card {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  overflow: hidden;
  margin-bottom: 2px;
  cursor: pointer;
  background:
    radial-gradient(520px 180px at 0% 0%, var(--accent-weak), transparent 70%),
    var(--surface);
  transition: border-color 0.12s ease;
}
.spread-card:hover {
  border-color: var(--accent-line);
}
.spread-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.spread-main {
  min-width: 0;
  padding: 12px 16px 13px;
  border-right: 1px solid var(--border);
}
.spread-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 0.3px;
}
.spread-label .ic {
  width: 12px;
  height: 12px;
  color: var(--accent);
}
.spread-label .badge {
  margin-left: 4px;
}
.spread-value {
  margin-top: 3px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -1px;
  white-space: nowrap;
}
.spread-value small {
  margin-left: 3px;
  font-family: var(--sans);
  font-size: 12px;
  font-weight: 500;
  color: var(--dim);
  letter-spacing: 0;
}
.spread-chg {
  margin-top: 2px;
  font-size: 10.5px;
  color: var(--dim);
}
.spread-chg b {
  font-weight: 650;
}
.spread-side {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  min-width: 0;
  padding: 10px 16px 11px;
}
.spread-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 2px 0;
  border-bottom: 1px dashed var(--border);
}
.spread-row b {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 650;
}
.sr-label {
  font-size: 10.5px;
  color: var(--muted);
  letter-spacing: 0.3px;
}
.sr-label em {
  margin-left: 4px;
  font-style: normal;
  font-size: 9px;
  color: var(--dim);
}
.spread-note {
  margin: 6px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--dim);
}

/* ---------- 分组卡片 ---------- */
.macro-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}
.macro-group {
  min-width: 0;
}
.macro-group--wide {
  grid-column: 1 / -1;
}
.macro-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  gap: 7px;
  padding: 9px 11px 11px;
}
.macro-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 7px 9px 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.12s ease,
    background 0.12s ease,
    transform 0.12s ease;
}
.macro-item:hover {
  border-color: var(--accent-line);
  background: color-mix(in srgb, var(--surface-2) 62%, var(--surface-3));
  transform: translateY(-1px);
}
.mi-top {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.mi-name {
  min-width: 0;
  font-size: 11px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mi-freq {
  margin-left: 3px;
  padding: 0 3px;
  border: 1px solid var(--border);
  border-radius: 3px;
  font-style: normal;
  font-size: 8.5px;
  color: var(--dim);
  vertical-align: 1px;
}
.mi-code {
  margin-left: auto;
  flex: none;
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}
.mi-value-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.mi-asof {
  margin-left: auto;
  flex: none;
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}
.mi-asof--stale {
  color: var(--warn-color, #d08700);
}
.mi-value {
  font-family: var(--mono);
  font-size: 16px;
  font-weight: 680;
  line-height: 1.15;
  letter-spacing: -0.3px;
  white-space: nowrap;
}
.mi-bottom {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 16px;
}
.mi-chg {
  font-family: var(--mono);
  font-size: 9.5px;
  font-weight: 600;
  white-space: nowrap;
}
.mi-spark {
  flex: 1 1 auto;
  min-width: 0;
  height: 16px;
  opacity: 0.85;
}

/* ---------- 页脚说明 ---------- */
.macro-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 8px 13px;
  font-size: 10px;
  color: var(--dim);
}
.macro-foot .ic {
  flex: none;
  width: 12px;
  height: 12px;
  color: var(--accent);
}
.macro-foot .spacer {
  flex: 1;
}
.macro-foot-meta {
  font-family: var(--mono);
  white-space: nowrap;
}
</style>
