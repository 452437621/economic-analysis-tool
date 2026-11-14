<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">{{ todayLabel }} · {{ brief?.trade_date ?? "—" }}</div>
        <h1 class="page-h1">总览 <span class="page-sub">今日主线 · 自选 · 跨资产 · 利率 · 告警</span></h1>
      </div>
      <div class="page-actions">
        <button class="btn btn--sm" type="button" @click="refreshAll">
          <svg class="ic"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <ErrorState v-if="overviewError" class="overview-error" :error="overviewError" @retry="refreshOverview" />

    <!-- 今日主线 + 市场时钟 -->
    <div class="hero-grid">
      <article class="hero">
        <div class="hero-top">
          <span class="badge badge--live"><span class="dot"></span>今日主线</span>
          <span class="hero-date">{{ brief?.trade_date ?? "—" }} {{ weekdayLabel }}</span>
          <span class="badge badge--sm">{{ briefKindLabel }}</span>
          <span class="hero-top-right">
            <svg class="ic" style="width: 11px; height: 11px"><use href="#i-check" /></svg>
            {{ brief ? "简报已生成" : "暂无简报" }}
          </span>
        </div>
        <h2 class="hero-title">{{ heroTitle }}</h2>
        <p class="hero-desc">{{ heroMainline }}</p>
        <div class="hero-tags">
          <span v-for="tag in heroTags" :key="tag.label" class="hero-tag">
            <span>{{ tag.label }}</span>
            <span class="tag-val">{{ tag.value }}</span>
            <span class="tag-delta" :class="tag.trend">{{ tag.delta }}</span>
          </span>
        </div>
        <div class="hero-foot">
          <RouterLink class="btn btn--primary btn--sm" to="/briefs">
            <svg class="ic"><use href="#i-file" /></svg>查看日报
          </RouterLink>
          <a v-if="brief" class="btn btn--sm" :href="briefPrintUrl(brief.id)" target="_blank" rel="noopener">
            <svg class="ic"><use href="#i-print" /></svg>打印
          </a>
          <button v-else class="btn btn--sm" type="button" disabled>
            <svg class="ic"><use href="#i-print" /></svg>打印
          </button>
          <button class="btn btn--sm btn--ghost" type="button" @click="copyMainline">
            <svg class="ic"><use href="#i-copy" /></svg>复制摘要
          </button>
          <span class="hero-meta">
            <template v-if="brief">更新于 {{ fmtTime(brief.created_at, true) }}</template>
            <template v-else>运行 brief_manual 任务后生成</template>
          </span>
        </div>
      </article>

      <aside class="card clock-card">
        <div class="card-head">
          <span class="card-title">市场时钟</span>
          <span class="badge badge--sm" :class="offshoreOpen ? 'badge--live' : ''">
            <span class="dot"></span>{{ offshoreOpen ? "外盘交易中" : "外盘休市" }}
          </span>
          <div class="card-actions"><span class="card-sub">北京 / 伦敦 / 纽约</span></div>
        </div>
        <div class="clock-body">
          <div v-for="zone in clockZones" :key="zone.city" class="clock-row">
            <span class="clock-city">{{ zone.city }}</span>
            <span class="clock-time">{{ zone.time }}</span>
            <span class="clock-session" :class="{ 'is-open': zone.open }">
              <span class="dot"></span>{{ zone.label }}
            </span>
          </div>
        </div>
        <div class="clock-foot">
          <svg class="ic" style="width: 11px; height: 11px"><use href="#i-clock" /></svg>
          <span>{{ countdownLabel }}（21:00）</span>
          <span class="clock-countdown">{{ countdown }}</span>
        </div>
      </aside>
    </div>

    <!-- KPI -->
    <div class="kpi-grid">
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-cpu" /></svg></span>
          <span class="kpi-label">系统状态</span>
          <span class="kpi-flag">
            <span class="badge badge--sm" :class="healthy ? 'badge--live' : 'badge--warn'">
              {{ healthBadgeText }}
            </span>
          </span>
        </div>
        <div class="kpi-value">{{ healthOnline }}<small>{{ healthy ? "在线" : "" }}</small></div>
        <div class="kpi-sub">后端 · 数据库 · 调度器 · {{ healthInfo?.env ?? "local" }}</div>
        <div class="kpi-meter">
          <i :class="healthy ? 'ok' : 'warn'" :style="{ width: healthy ? '100%' : '30%' }"></i>
          <i class="track"></i>
        </div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-chart" /></svg></span>
          <span class="kpi-label">行情覆盖</span>
          <span class="kpi-flag">
            <span class="badge badge--sm" :class="quoteGap ? 'badge--warn' : 'badge--live'">
              {{ quoteGap ? `${quoteGap} 待接入` : "全覆盖" }}
            </span>
          </span>
        </div>
        <div class="kpi-value">{{ snapshotMeta.with_quote ?? "—" }}<small>/ {{ snapshotMeta.count ?? "—" }} 标的</small></div>
        <div class="kpi-sub">覆盖率 {{ coveragePct }} · {{ snapshotMeta.asof ? `更新于 ${fmtTime(snapshotMeta.asof, true)}` : "等待采集" }}</div>
        <div class="kpi-meter">
          <i class="ok" :style="{ width: `${coveragePct}%` }"></i>
          <i class="track"></i>
        </div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-db" /></svg></span>
          <span class="kpi-label">数据量</span>
          <span class="kpi-flag"><span class="badge badge--sm">{{ counts?.market_bars ? "已回补" : "—" }}</span></span>
        </div>
        <div class="kpi-value">{{ fmtInt(counts?.market_bars) }}<small>根日线</small></div>
        <div class="kpi-sub">快照 {{ fmtInt(counts?.quotes) }} · 利率 {{ fmtInt(counts?.macro_observations) }} · 新闻 {{ fmtInt(counts?.documents) }}</div>
        <div class="kpi-meter">
          <i class="ok" style="width: 46%"></i>
          <i class="warn" style="width: 18%"></i>
          <i class="track"></i>
        </div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-tasks" /></svg></span>
          <span class="kpi-label">调度器</span>
          <span class="kpi-flag">
            <span class="badge badge--sm" :class="jobErrors ? 'badge--warn' : 'badge--live'">
              {{ jobErrors ? `${jobErrors} 异常` : "运行中" }}
            </span>
          </span>
        </div>
        <div class="kpi-value">{{ jobsInfo.total }}<small>个任务</small></div>
        <div class="kpi-sub">{{ jobsInfo.next_run ? `下一任务 ${fmtTime(jobsInfo.next_run, true)}` : "等待调度" }}</div>
        <div class="kpi-meter">
          <i class="ok" :style="{ width: jobsInfo.total ? '88%' : '10%' }"></i>
          <i class="track"></i>
        </div>
      </article>
    </div>

    <!-- 重点关注 -->
    <div class="sec-row">
      <h2 class="sec-title">重点关注</h2>
      <span class="sec-count">{{ watchlist.length }}</span>
      <span class="sec-meta">自选标的 · 日涨跌幅、20 日变动与迷你走势 · 点击查看历史</span>
      <div class="sec-actions">
        <button class="link-btn" type="button" @click="watchManagerOpen = true">
          <svg class="ic"><use href="#i-plus" /></svg>自选管理
        </button>
      </div>
    </div>
    <div class="watch-grid">
      <article
        v-for="item in watchlist"
        :key="item.symbol"
        class="card watch-card"
        role="button"
        tabindex="0"
        :title="`${item.name} ${item.symbol} · 点击查看历史走势`"
        @click="openHistory(item)"
        @keydown.enter="openHistory(item)"
      >
        <div class="watch-top">
          <span class="w-name">{{ item.name }}</span>
          <span class="w-code">{{ item.symbol }}</span>
        </div>
        <div class="w-price">
          {{ fmtPrice(item.price, item.asset_class) }}<small v-if="prefs.showUnits && item.unit">{{ item.unit }}</small>
        </div>
        <div class="w-sub">
          <span class="w-chg" :class="trendClass(item.change_pct)">
            {{ (item.change_pct ?? 0) >= 0 ? "▲" : "▼" }} {{ Math.abs(item.change_pct ?? 0).toFixed(2) }}%
          </span>
          <span class="w-20d">
            20日
            <b :class="trendClass(item.change_20d)">{{ fmtSigned(item.change_20d, 1) }}%</b>
          </span>
        </div>
        <div class="w-spark">
          <Sparkline :values="item.spark ?? []" :positive="(item.change_20d ?? 0) >= 0" />
        </div>
      </article>
      <EmptyState v-if="!watchlist.length" text="暂无自选" hint="在 config/default.yaml 配置，或在市场页添加。" />
    </div>

    <!-- 热力图 + 利率 -->
    <div class="overview-row">
      <section class="card">
        <div class="card-head">
          <span class="card-title">跨资产热力图</span>
          <span class="card-sub">日涨跌幅 · {{ snapshot.length }} 个已接入品种 · 按资产类别</span>
          <div class="card-actions">
            <span class="heat-legend"><span>跌</span><span class="legend-bar"></span><span>涨</span></span>
          </div>
        </div>
        <div class="heat-body">
          <div v-for="group in heatGroups" :key="group.label" class="heat-row">
            <span class="heat-label">{{ group.label }}</span>
            <div class="heat-tiles">
              <button
                v-for="tile in group.items"
                :key="tile.item.symbol"
                class="heat-tile"
                :class="heatClass(tile.item.change_pct)"
                :style="heatStyle(tile.item.change_pct)"
                type="button"
                :title="`${tile.item.name} ${fmtPct(tile.item.change_pct)}`"
                @click="openInstrument(tile.item.symbol, tile.item.name)"
              >
                <span class="ht-name">{{ tile.item.name }}</span>
                <span class="ht-pct">{{ fmtPct(tile.item.change_pct) }}</span>
              </button>
            </div>
          </div>
          <EmptyState v-if="!heatGroups.length" text="暂无行情数据" />
        </div>
      </section>

      <aside class="card">
        <div class="card-head">
          <span class="card-title">利率快照</span>
          <span class="card-sub">最新值 · 日变动</span>
          <div class="card-actions">
            <RouterLink class="link-btn" to="/rates">详情</RouterLink>
          </div>
        </div>
        <div class="rates-body">
          <div v-for="row in rateRows" :key="row.code" class="rate-row">
            <span class="rate-name" :class="{ 'is-sub': row.isSub }">{{ row.label }}</span>
            <span class="rate-val">{{ row.value }}</span>
            <span class="rate-chg" :class="row.chgClass">{{ row.chg }}</span>
            <span class="rate-spark"><Sparkline :values="row.spark" :positive="(row.chgValue ?? 0) >= 0" /></span>
          </div>
          <EmptyState v-if="!rateRows.length" text="暂无利率数据" />
        </div>
        <div class="card-foot">利差单位 pp · {{ macroAsOf }} · 点击去利率页查看完整曲线</div>
      </aside>
    </div>

    <!-- 告警 + 日历 -->
    <div class="bottom-grid">
      <section class="card">
        <div class="card-head">
          <span class="card-title">告警</span>
          <span class="badge badge--sm">{{ alertUnread }} 条未确认</span>
          <div class="card-actions">
            <span class="card-sub">阈值 / 利差 / 延迟 / 持仓异动</span>
            <button class="link-btn" type="button" @click="alerts.open = true">全部</button>
          </div>
        </div>
        <div class="alerts-body">
          <div v-for="alert in alertItems.slice(0, 4)" :key="alert.id" class="alert-row">
            <span class="sev" :class="severityClass(alert.level)"></span>
            <div>
              <div class="alert-text">{{ alert.title }}</div>
              <div class="alert-meta">
                <span>{{ alert.kind }}</span>
                <span>{{ alert.message }}</span>
              </div>
            </div>
            <span class="alert-time">{{ fmtTime(alert.created_at, true) }}</span>
          </div>
          <EmptyState v-if="!alertItems.length" text="暂无告警" />
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <span class="card-title">财经日历 · 事件</span>
          <span class="card-sub">未来 14 天</span>
          <div class="card-actions">
            <RouterLink class="link-btn" to="/theses">完整日历</RouterLink>
          </div>
        </div>
        <div class="cal-body">
          <div v-for="event in calendar.slice(0, 4)" :key="event.id" class="cal-row">
            <span class="cal-time">{{ fmtTime(event.ts, true) }}</span>
            <span class="cal-region">{{ event.country ?? "全球" }}</span>
            <span class="cal-name">{{ event.name }}</span>
            <span class="cal-imp">{{ stars(event.importance) }}</span>
          </div>
          <EmptyState v-if="!calendar.length" text="暂无日历数据" />
        </div>
      </section>
    </div>

    <WatchlistManager v-model:open="watchManagerOpen" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import Sparkline from "@/components/ui/Sparkline.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import WatchlistManager from "@/components/domain/WatchlistManager.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtInt, fmtMacro, fmtPct, fmtPrice, fmtSigned, fmtTime, stars, trendClass } from "@/composables/useFormat";
import { SNAPSHOT_CATEGORIES } from "@/utils/market";
import { briefPrintUrl, getOverview } from "@/api/endpoints";
import type { Brief, SnapshotItem, WatchlistItem } from "@/api/types";
import { usePrefsStore } from "@/stores/prefs";
import { useHealthStore } from "@/stores/health";
import { useAlertsStore } from "@/stores/alerts";
import { useHistoryStore } from "@/stores/history";
import { useToast } from "@/stores/toast";

const prefs = usePrefsStore();
const health = useHealthStore();
const alerts = useAlertsStore();
const historyStore = useHistoryStore();
const toast = useToast();

const watchManagerOpen = ref(false);

/* ---------- 主数据源：GET /api/overview（单请求聚合） ---------- */
const {
  data: overview,
  error: overviewError,
  loading: overviewLoading,
  refresh: refreshOverview,
} = usePolling(getOverview, {
  interval: () => prefs.refreshInterval * 1000,
});

const brief = computed<Brief | null>(() => overview.value?.brief ?? null);
const snapshot = computed<SnapshotItem[]>(() => overview.value?.snapshot?.data ?? []);
const snapshotMeta = computed(() => overview.value?.snapshot?.meta ?? {});
const watchlist = computed<WatchlistItem[]>(() => overview.value?.watchlist?.data ?? []);
const macroRows = computed(() => overview.value?.macro?.latest ?? []);
const rateSparks = computed<Record<string, number[]>>(() => overview.value?.macro?.sparks ?? {});
const alertItems = computed(() => overview.value?.alerts?.items ?? []);
const alertUnread = computed(() => overview.value?.alerts?.unread ?? 0);
const calendar = computed(() => overview.value?.calendar ?? []);
const jobsInfo = computed(
  () => overview.value?.jobs ?? { total: 0, failed: 0, scheduler_running: false, next_run: null },
);
const healthInfo = computed(() => overview.value?.health ?? null);
const healthy = computed(() => healthInfo.value?.status === "ok");

const healthBadgeText = computed(() => {
  if (healthy.value) return "正常";
  if (healthInfo.value) return "降级";
  return overviewLoading.value ? "连接中" : "未连接";
});

/** 系统自检项：后端 / 数据库 / 调度器 / 行情 / 新闻 / 日线 */
const healthChecks = computed(() => {
  const info = healthInfo.value;
  if (!info) return { passed: 0, total: 6 };
  const counts = info.counts;
  const checks = [
    info.status === "ok",
    Boolean(info.database?.ok),
    Boolean(info.scheduler?.running),
    (counts?.quotes ?? 0) > 0,
    (counts?.documents ?? 0) > 0,
    (counts?.market_bars ?? 0) > 0,
  ];
  return { passed: checks.filter(Boolean).length, total: checks.length };
});

const healthOnline = computed(() =>
  healthy.value ? `${healthChecks.value.passed} / ${healthChecks.value.total}` : "—",
);

const counts = computed(() => healthInfo.value?.counts);
const quoteGap = computed(() => {
  const total = snapshotMeta.value.count ?? 0;
  const quoted = snapshotMeta.value.with_quote ?? 0;
  return total ? total - quoted : 0;
});
const coveragePct = computed(() => {
  const total = snapshotMeta.value.count ?? 0;
  if (!total) return 0;
  return Math.round(((snapshotMeta.value.with_quote ?? 0) / total) * 100);
});
const jobErrors = computed(() => jobsInfo.value.failed ?? 0);

const todayLabel = computed(() => {
  const date = new Date();
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
});
const weekdayLabel = computed(() => {
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return weekdays[new Date().getDay()];
});

/* ---------- 主线解析（从简报 Markdown 提取标题与一句话主线） ---------- */
function stripInline(text: string): string {
  return text
    .replace(/`\[D:[0-9a-f]{32}\]`/g, "")
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .trim();
}

const heroTitle = computed(() => {
  if (!brief.value?.markdown) return "暂无简报 · 等待生成今日主线";
  const lines = brief.value.markdown.split("\n");
  const mainline = lines.find((line) => line.startsWith("> "));
  const heading = lines.find((line) => /^#\s+/.test(line));
  const clean = (text: string) =>
    stripInline(text)
      .replace(/（自动摘要[^）]*）/g, "")
      .replace(/（置信度[^）]*）/g, "")
      .trim();
  if (mainline) {
    const text = stripInline(mainline.replace(/^>\s*/, ""));
    const parts = text.split(/[：:]/);
    if (parts.length > 1) return clean(parts.slice(1).join("："));
    return clean(text);
  }
  return heading ? clean(heading.replace(/^#\s+/, "")) : "今日暂无主线判断";
});

const heroMainline = computed(() => {
  if (!brief.value?.markdown) return "运行 brief_manual 任务后，这里会展示当日主线判断与证据摘要。";
  const lines = brief.value.markdown.split("\n");
  const paragraphs = lines.filter(
    (line) => line.trim() && !line.startsWith("#") && !line.startsWith("|") && !line.startsWith(">") && !line.startsWith("-"),
  );
  return stripInline(paragraphs[0] ?? "简报已生成，点击「查看日报」阅读全文。").slice(0, 160);
});

const briefKindLabel = computed(() => {
  if (!brief.value) return "暂无简报";
  const labels: Record<string, string> = { manual: "手动简报", daily: "日报", weekly: "周报", monthly: "月报" };
  return labels[brief.value.kind] ?? brief.value.kind;
});

const heroTags = computed(() => {
  const bySymbol = new Map(snapshot.value.map((item) => [item.symbol, item]));
  const pick = (symbol: string) => bySymbol.get(symbol);
  const tags: Array<{ label: string; value: string; delta: string; trend: string }> = [];
  const upCount = snapshot.value.filter((item) => (item.change_pct ?? 0) > 0).length;
  const downCount = snapshot.value.filter((item) => (item.change_pct ?? 0) < 0).length;
  tags.push({ label: "上涨 / 下跌", value: `${upCount} / ${downCount}`, delta: `共 ${snapshot.value.length} 个`, trend: "flat" });
  for (const symbol of ["DXY", "AU", "CU", "SC", "603993"]) {
    const item = pick(symbol);
    if (!item || item.price == null) continue;
    const change = item.change_pct ?? 0;
    tags.push({
      label: item.name,
      value: fmtPrice(item.price, item.asset_class),
      delta: `${change >= 0 ? "▲" : "▼"} ${Math.abs(change).toFixed(2)}%`,
      trend: trendClass(change),
    });
    if (tags.length >= 5) break;
  }
  return tags;
});

/* ---------- 市场时钟 ---------- */
const clockZones = computed(() => {
  const now = new Date();
  const format = (timeZone: string) =>
    now.toLocaleTimeString("zh-CN", { timeZone, hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const beijingHour = Number(
    now.toLocaleString("en-GB", { timeZone: "Asia/Shanghai", hour: "2-digit", hour12: false }),
  );
  const weekday = now.getDay();
  const domesticOpen =
    weekday >= 1 &&
    weekday <= 5 &&
    ((beijingHour >= 9 && beijingHour < 11) ||
      (beijingHour >= 13 && beijingHour < 15) ||
      beijingHour >= 21);
  return [
    { city: "北京", time: format("Asia/Shanghai"), open: domesticOpen, label: domesticOpen ? "内盘 · 交易中" : "内盘 · 已收盘" },
    { city: "伦敦", time: format("Europe/London"), open: offshoreOpen.value, label: offshoreOpen.value ? "外盘 · 交易中" : "外盘 · 休市" },
    { city: "纽约", time: format("America/New_York"), open: offshoreOpen.value, label: offshoreOpen.value ? "外盘 · 交易中" : "外盘 · 休市" },
  ];
});

const offshoreOpen = computed(() => {
  const utcHour = new Date().getUTCHours();
  const day = new Date().getUTCDay();
  if (day === 0 || day === 6) return false;
  return utcHour >= 7 && utcHour < 21;
});

const countdownLabel = computed(() => {
  const beijingHour = Number(
    new Date().toLocaleString("en-GB", { timeZone: "Asia/Shanghai", hour: "2-digit", hour12: false }),
  );
  return beijingHour >= 21 || beijingHour < 3 ? "距 收盘" : "距离 夜盘开盘";
});

const countdown = computed(() => {
  const now = new Date();
  const beijing = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Shanghai" }));
  const target = new Date(beijing);
  target.setHours(21, 0, 0, 0);
  if (beijing.getHours() >= 21) target.setDate(target.getDate() + 1);
  const diff = Math.max(0, target.getTime() - beijing.getTime());
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
});

/* ---------- 热力图 ---------- */
const heatGroups = computed(() => {
  const groups: Array<{ label: string; items: Array<{ item: SnapshotItem }> }> = [];
  const used = new Set<string>();
  for (const category of SNAPSHOT_CATEGORIES) {
    const items = category.symbols
      .map((symbol) => snapshot.value.find((item) => item.symbol === symbol))
      .filter((item): item is SnapshotItem => Boolean(item));
    if (!items.length) continue;
    items.forEach((item) => used.add(item.symbol));
    groups.push({ label: category.label, items: items.map((item) => ({ item })) });
  }
  const rest = snapshot.value.filter((item) => !used.has(item.symbol));
  if (rest.length) groups.push({ label: "其他", items: rest.map((item) => ({ item })) });
  return groups;
});

function heatClass(change: number | null | undefined): string {
  const value = Math.abs(change ?? 0);
  if (value >= 2) return "strong";
  return "";
}

function heatStyle(change: number | null | undefined): Record<string, string> {
  const value = Math.max(-6, Math.min(6, change ?? 0));
  const intensity = Math.min(0.9, Math.abs(value) / 5 + 0.08);
  const color = value >= 0 ? `var(--up)` : `var(--down)`;
  if (!change) return { background: "var(--surface-2)" };
  return {
    background: `color-mix(in srgb, ${color} ${Math.round(intensity * 100)}%, var(--surface-2))`,
  };
}

/* ---------- 利率快照（macro.latest + macro.sparks） ---------- */
const RATE_CODES = [
  { code: "SOFR", label: "SOFR" },
  { code: "EFFR", label: "EFFR" },
  { code: "SOFR_EFFR", label: "SOFR−EFFR", isSub: true },
  { code: "US2Y", label: "US 2Y" },
  { code: "US10Y", label: "US 10Y" },
  { code: "US30Y", label: "US 30Y" },
  { code: "CN10Y", label: "CN 10Y" },
  { code: "JP10Y", label: "JP 10Y" },
  { code: "DE10Y", label: "DE 10Y" },
  { code: "FR10Y", label: "FR 10Y" },
];

const rateRows = computed(() => {
  const byCode = new Map(macroRows.value.map((row) => [row.code, row]));
  const rows: Array<{
    code: string;
    label: string;
    isSub?: boolean;
    value: string;
    chg: string;
    chgValue: number | null;
    chgClass: string;
    spark: number[];
  }> = [];
  for (const meta of RATE_CODES) {
    const row = byCode.get(meta.code);
    if (!row) continue;
    const series = rateSparks.value[meta.code] ?? [];
    const previous = series.length > 1 ? series[series.length - 2] : null;
    const chgValue = previous === null ? null : Number((row.value - previous).toFixed(2));
    rows.push({
      code: meta.code,
      label: meta.label,
      isSub: meta.isSub,
      value: fmtMacro(row.value, row.unit === "%" ? "%" : null),
      chg: chgValue === null ? "—" : fmtSigned(chgValue, 2),
      chgValue,
      chgClass: trendClass(chgValue),
      spark: series,
    });
  }
  return rows;
});

const macroAsOf = computed(() => macroRows.value[0]?.ts ?? overview.value?.asof ?? "");

/* ---------- 交互 ---------- */
function openHistory(item: WatchlistItem): void {
  void historyStore.openHistory("instrument", item.symbol, item.name);
}

function openInstrument(symbol: string, name: string): void {
  void historyStore.openHistory("instrument", symbol, name);
}

function severityClass(level: string): string {
  if (level === "critical") return "sev--critical";
  if (level === "warn") return "sev--warn";
  return "sev--info";
}

async function copyMainline(): Promise<void> {
  const text = `${heroTitle.value}\n${heroMainline.value}`;
  try {
    await navigator.clipboard.writeText(text);
    toast.ok("主线摘要已复制");
  } catch {
    toast.warn("浏览器拒绝剪贴板访问");
  }
}

function refreshAll(): void {
  void Promise.all([refreshOverview(), health.refresh(), alerts.refresh()]);
  toast.info("已刷新总览数据");
}

onMounted(() => {
  if (new URLSearchParams(location.search).get("watch") === "1") watchManagerOpen.value = true;
});
</script>

<style scoped>
.watch-card {
  cursor: pointer;
}
.dim {
  color: var(--dim);
}
.overview-error {
  margin: 0 0 8px;
}
</style>
