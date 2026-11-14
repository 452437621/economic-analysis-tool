<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 论点 / 事件 / 新闻 / 日历</div>
        <h1 class="page-h1">
          论点与证据
          <span class="page-sub">论点复核 · 情景概率 · 事件驱动 · 新闻溯源 · 财经日历</span>
        </h1>
      </div>
      <div class="page-actions">
        <button class="btn btn--sm" type="button" @click="refreshAll">
          <svg class="ic"><use href="#i-refresh" /></svg>刷新
        </button>
        <RouterLink class="btn btn--sm" to="/briefs">
          <svg class="ic"><use href="#i-file" /></svg>查看简报
        </RouterLink>
      </div>
    </div>

    <!-- 统计 -->
    <div class="kpi-grid">
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-book" /></svg></span>
          <span class="kpi-label">论点总数</span>
          <span class="kpi-flag"><span class="badge badge--sm">{{ statusSummary }}</span></span>
        </div>
        <div class="kpi-value">{{ theses.length }}<small>条论点</small></div>
        <div class="kpi-sub">{{ watchCount }} 观察 · {{ activeCount }} 进行中 · {{ closedCount }} 已结算/关闭</div>
        <div class="kpi-meter">
          <i class="ok" :style="{ width: barWidth(theses.length ? watchCount / theses.length : 0) }"></i>
          <i :style="{ width: barWidth(theses.length ? activeCount / theses.length : 0) }"></i>
          <i class="track"></i>
        </div>
      </article>

      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-target" /></svg></span>
          <span class="kpi-label">可评分样本</span>
          <span class="kpi-flag"><span class="badge badge--sm">{{ review?.count ?? 0 }} 条论点</span></span>
        </div>
        <div class="kpi-value">{{ review?.scored ?? 0 }}<small>/ {{ review?.count ?? theses.length }} 已结算</small></div>
        <div class="kpi-sub">论点到期后按方向与实际收益结算</div>
        <div class="kpi-meter">
          <i class="warn" :style="{ width: barWidth(scoredRatio) }"></i>
          <i class="track"></i>
        </div>
      </article>

      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-check" /></svg></span>
          <span class="kpi-label">方向命中率</span>
          <span class="kpi-flag"><span class="badge badge--sm">{{ review?.scored ? "已结算" : "待结算" }}</span></span>
        </div>
        <div class="kpi-value">{{ hitRateText }}<small>方向命中</small></div>
        <div class="kpi-sub">{{ review?.scored ? `${review.scored} 条样本` : "暂无已结算样本" }}</div>
        <div class="kpi-meter">
          <i class="ok" :style="{ width: barWidth(review?.hit_rate ?? 0) }"></i>
          <i class="track"></i>
        </div>
      </article>

      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
          <span class="kpi-label">平均收益</span>
          <span class="kpi-flag"><span class="badge badge--sm">{{ review?.scored ? "已结算" : "待结算" }}</span></span>
        </div>
        <div class="kpi-value" :class="avgReturnClass">{{ avgReturnText }}<small>已结算</small></div>
        <div class="kpi-sub">按论点方向计价的平均区间收益</div>
        <div class="kpi-meter">
          <i :class="avgReturnClass === 'down' ? 'warn' : 'ok'" :style="{ width: barWidth(0.6) }"></i>
          <i class="track"></i>
        </div>
      </article>
    </div>

    <!-- 页内 tabs + 筛选 -->
    <section class="card toolbar thesis-toolbar">
      <div class="tool-row">
        <div class="seg">
          <button
            v-for="tabItem in tabs"
            :key="tabItem.key"
            type="button"
            :class="{ active: tab === tabItem.key }"
            @click="tab = tabItem.key"
          >
            {{ tabItem.label }}<span class="tab-count">{{ tabItem.count }}</span>
          </button>
        </div>
        <div class="tool-right">
          <span class="tool-note"><span class="dot dot--live"></span>轮询：论点 / 复核 120s · 事件 / 新闻 60s · 日历 300s</span>
        </div>
      </div>
      <div v-if="tab === 'theses'" class="tool-row">
        <div class="chip-row">
          <button
            v-for="option in statusOptions"
            :key="option.value"
            class="chip"
            :class="{ active: statusFilter === option.value }"
            type="button"
            @click="statusFilter = option.value"
          >
            {{ option.label }}<em>{{ option.count }}</em>
          </button>
        </div>
        <div class="tool-right">
          <span class="tool-note">当前筛选 {{ filteredTheses.length }} 条 · 点击卡片查看情景与失效条件</span>
        </div>
      </div>
    </section>

    <!-- 论点 -->
    <template v-if="tab === 'theses'">
      <section v-if="thesesError && !theses.length" class="card">
        <ErrorState :error="thesesError" @retry="thesesPoll.refresh" />
      </section>
      <section v-else-if="thesesLoading && !theses.length" class="card">
        <div class="card-body"><SkeletonBlock :rows="6" :cells="4" :height="13" /></div>
      </section>
      <section v-else-if="!filteredTheses.length" class="card">
        <EmptyState
          :text="theses.length ? '该状态下暂无论点' : '暂无论点'"
          :hint="theses.length ? '切换状态筛选查看其它论点。' : '运行论点生成任务后，论点与情景会显示在这里。'"
        />
      </section>
      <div v-else class="thesis-list">
        <article v-for="thesis in filteredTheses" :key="thesis.id" class="card thesis-card">
          <div class="t-head">
            <span class="badge badge--sm" :class="thesis.direction === 'long' ? 'badge--up' : 'badge--down'">
              {{ directionLabel(thesis.direction) }}
            </span>
            <h3 class="t-title">{{ thesis.title }}</h3>
            <span class="badge badge--sm" :class="statusBadgeClass(thesis.status)">
              {{ statusLabel(thesis.status) }}
            </span>
          </div>
          <div class="t-meta">
            <span><svg class="ic"><use href="#i-clock" /></svg>{{ thesis.horizon_days }} 日窗口</span>
            <span><svg class="ic"><use href="#i-shield-check" /></svg>证据 {{ thesis.evidence_count }}</span>
            <span class="t-created">{{ fmtDateTime(thesis.created_at) }}</span>
          </div>
          <div class="t-prob">
            <div class="t-prob-label">
              <span>后验概率 <b class="mono">{{ pct(thesis.posterior) }}</b></span>
              <span>先验 <b class="mono">{{ pct(thesis.prior) }}</b></span>
            </div>
            <div class="prob-track"><i :style="{ width: barWidth(clamp01(thesis.posterior)) }"></i></div>
          </div>
          <div v-if="thesis.main_driver" class="t-driver">
            <svg class="ic"><use href="#i-sparkle" /></svg>
            <span>{{ thesis.main_driver }}</span>
          </div>
          <div v-if="thesis.scenarios.length" class="t-scenarios">
            <div v-for="scenario in thesis.scenarios" :key="scenario.name" class="scenario">
              <div class="s-head">
                <span class="s-name">{{ scenario.name }}</span>
                <span class="s-prob mono">{{ pct(scenario.probability) }}</span>
              </div>
              <div class="s-bar"><i :style="{ width: barWidth(clamp01(scenario.probability)) }"></i></div>
              <div v-if="scenario.triggers" class="s-trigger">{{ scenario.triggers }}</div>
            </div>
          </div>
          <div v-if="thesis.invalidation" class="t-invalidation">
            <span class="inv-label"><svg class="ic"><use href="#i-alert" /></svg>失效条件</span>
            <span class="inv-text">{{ thesis.invalidation }}</span>
          </div>
        </article>
      </div>

      <!-- 复核说明 -->
      <section class="card review-card">
        <div class="card-head">
          <span class="card-title">论点复核</span>
          <span class="card-sub">方向命中率与平均收益 · 仅统计已结算论点</span>
          <div class="card-actions">
            <span class="badge badge--sm">{{ review?.scored ?? 0 }} / {{ review?.count ?? theses.length }} 已结算</span>
          </div>
        </div>
        <div class="review-body">
          <div class="review-stats">
            <div class="r-stat">
              <div class="r-num mono">{{ review?.scored ?? 0 }}</div>
              <div class="r-label">可评分样本</div>
            </div>
            <div class="r-stat">
              <div class="r-num mono">{{ hitRateText }}</div>
              <div class="r-label">方向命中率</div>
            </div>
            <div class="r-stat">
              <div class="r-num mono" :class="avgReturnClass">{{ avgReturnText }}</div>
              <div class="r-label">平均收益</div>
            </div>
          </div>
          <p class="review-note">{{ reviewNote }}</p>
          <div v-if="review?.records.length" class="review-records">
            <div v-for="record in review.records.slice(0, 6)" :key="record.id" class="rr-row">
              <span class="rr-symbol mono">{{ record.symbol ?? "—" }}</span>
              <span class="badge badge--sm" :class="record.direction === 'long' ? 'badge--up' : 'badge--down'">
                {{ directionLabel(record.direction) }}
              </span>
              <span class="rr-title">{{ record.title }}</span>
              <span class="rr-since mono">{{ record.since }}</span>
              <span class="rr-return mono" :class="record.return_pct === null ? 'dim' : trendClass(record.return_pct)">
                {{ record.return_pct === null ? "待结算" : fmtPct(record.return_pct) }}
              </span>
              <span class="badge badge--sm" :class="record.hit === null ? '' : record.hit ? 'badge--live' : 'badge--warn'">
                {{ record.hit === null ? "—" : record.hit ? "命中" : "偏离" }}
              </span>
            </div>
          </div>
          <EmptyState v-else text="暂无论点复核记录" hint="论点到期结算后，这里会列出方向命中与区间收益。" />
        </div>
      </section>
    </template>

    <!-- 事件 -->
    <section v-else-if="tab === 'events'" class="card">
      <div class="card-head">
        <span class="card-title">事件驱动</span>
        <span class="card-sub">官方公告与新闻中规则识别 · 按时间倒序</span>
        <div class="card-actions"><span class="badge badge--sm">{{ events.length }} 条</span></div>
      </div>
      <ErrorState v-if="eventsError && !events.length" :error="eventsError" @retry="eventsPoll.refresh" />
      <div v-else-if="eventsLoading && !events.length" class="card-body">
        <SkeletonBlock :rows="6" :cells="3" />
      </div>
      <EmptyState
        v-else-if="!events.length"
        text="暂无事件数据"
        hint="事件由规则从官方公告与新闻中识别，运行采集任务后生成。"
      />
      <div v-else class="event-list">
        <div v-for="event in events" :key="event.id" class="event-row">
          <span class="event-date mono">{{ fmtTime(event.event_date, true) }}</span>
          <span class="badge badge--sm event-type">{{ eventTypeLabel(event.type) }}</span>
          <div class="event-main">
            <div class="event-title">{{ event.title }}</div>
            <div v-if="event.summary" class="event-summary">{{ event.summary }}</div>
          </div>
          <span class="event-tags">
            <span v-for="instrument in event.instruments.slice(0, 3)" :key="instrument" class="badge badge--sm">
              {{ instrument }}
            </span>
            <span v-if="!event.instruments.length" class="dim">关联 —</span>
          </span>
        </div>
      </div>
      <div class="card-foot">
        <span class="dot dot--off"></span>事件暂未关联文档 ID，仅供驱动线索参考（新闻 tab 可打开证据原文）。
      </div>
    </section>

    <!-- 新闻 -->
    <section v-else-if="tab === 'news'" class="card">
      <div class="card-head">
        <span class="card-title">新闻与政策</span>
        <span class="card-sub">官方一手来源 · 点击整行打开证据抽屉（原文 + 断言高亮）</span>
        <div class="card-actions"><span class="badge badge--sm">{{ news.length }} 条</span></div>
      </div>
      <ErrorState v-if="newsError && !news.length" :error="newsError" @retry="newsPoll.refresh" />
      <div v-else-if="newsLoading && !news.length" class="card-body">
        <SkeletonBlock :rows="6" :cells="3" />
      </div>
      <EmptyState v-else-if="!news.length" text="暂无新闻" hint="运行新闻采集任务后，最新官方来源会显示在这里。" />
      <div v-else class="news-list">
        <button v-for="item in news" :key="item.id" class="news-row" type="button" @click="openEvidence(item.id)">
          <span class="news-side">
            <span class="news-source">{{ item.source ?? "未知来源" }}</span>
            <span class="news-time mono">{{ fmtTime(item.published_at, true) }}</span>
          </span>
          <span class="news-main">
            <span class="news-title">{{ item.title }}</span>
            <span v-if="item.summary" class="news-summary">{{ item.summary }}</span>
          </span>
          <span class="news-side-right">
            <span class="badge badge--sm" :class="item.tier === 'S1' ? 'badge--accent' : ''">{{ item.tier ?? "—" }}</span>
            <svg class="ic news-go"><use href="#i-chevron-right" /></svg>
          </span>
        </button>
      </div>
      <div class="card-foot">点击新闻行 → 右侧证据抽屉：文档详情、原文摘录与断言高亮。</div>
    </section>

    <!-- 日历 -->
    <section v-else class="card">
      <div class="card-head">
        <span class="card-title">财经日历</span>
        <span class="card-sub">未来 14 天 · 重要事件与数据发布</span>
        <div class="card-actions"><span class="badge badge--sm">{{ calendar.length }} 项</span></div>
      </div>
      <ErrorState v-if="calendarError && !calendar.length" :error="calendarError" @retry="calendarPoll.refresh" />
      <div v-else-if="calendarLoading && !calendar.length" class="card-body">
        <SkeletonBlock :rows="6" :cells="4" />
      </div>
      <EmptyState v-else-if="!calendar.length" text="暂无日历数据" hint="财经日历源采集后，未来 14 天的重要事件会显示在这里。" />
      <div v-else class="calendar-list">
        <template v-for="group in calendarGroups" :key="group.date">
          <div class="cal-sep">{{ group.date }} · {{ group.weekday }} · {{ group.items.length }} 项</div>
          <div v-for="event in group.items" :key="event.id" class="cal-row">
            <span class="cal-time">{{ fmtTime(event.ts) }}</span>
            <span class="cal-region">{{ event.country ?? "全球" }}</span>
            <span class="cal-cat" :title="event.category ?? ''">{{ event.category ?? "—" }}</span>
            <span class="cal-name" :title="event.name">{{ event.name }}</span>
            <span class="cal-imp" :class="{ high: event.importance >= 3 }">{{ stars(event.importance) }}</span>
          </div>
        </template>
      </div>
      <div class="card-foot">重要性 ●●● 高 / ●●○ 中 / ●○○ 低 · 时间按浏览器本地时区显示。</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import {
  fmtDate,
  fmtDateTime,
  fmtPct,
  fmtTime,
  stars,
  trendClass,
} from "@/composables/useFormat";
import { THESIS_STATUS_LABEL } from "@/utils/market";
import { getCalendar, getEvents, getNews, getTheses, getThesisReview } from "@/api/endpoints";
import type { CalendarEvent, EventItem, NewsItem, Thesis, ThesisReview } from "@/api/types";
import { useEvidenceStore } from "@/stores/evidence";
import { useToast } from "@/stores/toast";

type TabKey = "theses" | "events" | "news" | "calendar";

const evidence = useEvidenceStore();
const toast = useToast();

const tab = ref<TabKey>("theses");
const statusFilter = ref<string>("all");

/* ---------- 轮询（论点 / 复核 120s；事件 / 新闻 60s；日历 300s） ---------- */
const thesesPoll = usePolling(() => getTheses(20), { interval: 120000 });
const reviewPoll = usePolling(() => getThesisReview(), { interval: 120000 });
const eventsPoll = usePolling(() => getEvents(24), { interval: 60000 });
const newsPoll = usePolling(() => getNews(20), { interval: 60000 });
const calendarPoll = usePolling(() => getCalendar(14, 40), { interval: 300000 });

const theses = computed<Thesis[]>(() => thesesPoll.data.value?.data ?? []);
const review = computed<ThesisReview | null>(() => reviewPoll.data.value?.data ?? null);
const events = computed<EventItem[]>(() => eventsPoll.data.value?.data ?? []);
const news = computed<NewsItem[]>(() => newsPoll.data.value?.data ?? []);
const calendar = computed<CalendarEvent[]>(() => calendarPoll.data.value?.data ?? []);

const thesesLoading = computed(() => thesesPoll.loading.value || reviewPoll.loading.value);
const thesesError = computed(() => thesesPoll.error.value ?? reviewPoll.error.value);
const eventsLoading = computed(() => eventsPoll.loading.value);
const eventsError = computed(() => eventsPoll.error.value);
const newsLoading = computed(() => newsPoll.loading.value);
const newsError = computed(() => newsPoll.error.value);
const calendarLoading = computed(() => calendarPoll.loading.value);
const calendarError = computed(() => calendarPoll.error.value);

/* ---------- 统计 ---------- */
const watchCount = computed(() => theses.value.filter((item) => item.status === "watch").length);
const activeCount = computed(() => theses.value.filter((item) => item.status === "active").length);
const closedCount = computed(
  () => theses.value.filter((item) => ["confirmed", "invalidated", "closed"].includes(item.status)).length,
);
const statusSummary = computed(() => {
  if (!theses.value.length) return "暂无";
  if (activeCount.value) return `${activeCount.value} 条进行中`;
  return `${watchCount.value} 条观察`;
});
const scoredRatio = computed(() => {
  const total = review.value?.count ?? theses.value.length;
  if (!total) return 0;
  return (review.value?.scored ?? 0) / total;
});

const hitRateText = computed(() => {
  const value = review.value?.hit_rate;
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
});
const avgReturnText = computed(() => fmtPct(review.value?.avg_return_pct));
const avgReturnClass = computed(() => {
  const value = review.value?.avg_return_pct;
  if (value === null || value === undefined) return "flat";
  return trendClass(value);
});
const reviewNote = computed(() => {
  const current = review.value;
  if (!current) return "复核数据加载中：可评分样本、方向命中率与平均收益会在论点结算后更新。";
  if (!current.scored) {
    return `当前 ${current.count} 条论点全部待结算（可评分样本 ${current.scored}），命中率与平均收益暂不可用；论点到期后按方向与实际区间收益结算，仅统计已结算样本。`;
  }
  return `已结算 ${current.scored} / ${current.count} 条，方向命中率 ${hitRateText.value}，平均收益 ${avgReturnText.value}；未结算论点不计入命中率，避免样本偏差。`;
});

function barWidth(ratio: number): string {
  return `${Math.max(0, Math.min(1, ratio)) * 100}%`;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function pct(value: number): string {
  return `${Math.round(clamp01(value) * 100)}%`;
}

/* ---------- tabs / 筛选 ---------- */
const tabs = computed<Array<{ key: TabKey; label: string; count: number }>>(() => [
  { key: "theses", label: "论点", count: theses.value.length },
  { key: "events", label: "事件", count: events.value.length },
  { key: "news", label: "新闻", count: news.value.length },
  { key: "calendar", label: "日历", count: calendar.value.length },
]);

const STATUS_ORDER = ["watch", "active", "confirmed", "invalidated", "closed"];

const statusOptions = computed<Array<{ value: string; label: string; count: number }>>(() => {
  const counts = new Map<string, number>();
  for (const thesis of theses.value) counts.set(thesis.status, (counts.get(thesis.status) ?? 0) + 1);
  const options: Array<{ value: string; label: string; count: number }> = [
    { value: "all", label: "全部", count: theses.value.length },
  ];
  for (const status of STATUS_ORDER) {
    const count = counts.get(status) ?? 0;
    if (count) options.push({ value: status, label: THESIS_STATUS_LABEL[status] ?? status, count });
  }
  for (const [status, count] of counts) {
    if (!STATUS_ORDER.includes(status)) {
      options.push({ value: status, label: THESIS_STATUS_LABEL[status] ?? status, count });
    }
  }
  return options;
});

const filteredTheses = computed<Thesis[]>(() => {
  if (statusFilter.value === "all") return theses.value;
  return theses.value.filter((thesis) => thesis.status === statusFilter.value);
});

/* ---------- 标签映射 ---------- */
function directionLabel(direction: string): string {
  if (direction === "long") return "看多";
  if (direction === "short") return "看空";
  return direction;
}

function statusLabel(status: string): string {
  return THESIS_STATUS_LABEL[status] ?? status;
}

function statusBadgeClass(status: string): string {
  if (status === "confirmed") return "badge--live";
  if (status === "invalidated") return "badge--down";
  if (status === "active") return "badge--accent";
  if (status === "watch") return "";
  return "";
}

function eventTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    supply: "供给",
    geopolitical: "地缘",
    monetary: "货币",
    monetary_policy: "货币政策",
    data: "数据",
    data_release: "数据发布",
    trade: "贸易",
    policy: "政策",
  };
  return labels[type] ?? type;
}

/* ---------- 日历分组 ---------- */
const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

const calendarGroups = computed<Array<{ date: string; weekday: string; items: CalendarEvent[] }>>(() => {
  const groups: Array<{ date: string; weekday: string; items: CalendarEvent[] }> = [];
  for (const event of calendar.value) {
    const date = fmtDate(event.ts);
    const parsed = new Date(event.ts);
    const weekday = Number.isNaN(parsed.getTime()) ? "" : WEEKDAYS[parsed.getDay()] ?? "";
    const last = groups[groups.length - 1];
    if (last && last.date === date) last.items.push(event);
    else groups.push({ date, weekday, items: [event] });
  }
  return groups;
});

/* ---------- 交互 ---------- */
function openEvidence(documentId: string): void {
  void evidence.show(documentId);
}

function refreshAll(): void {
  void Promise.all([
    thesesPoll.refresh(),
    reviewPoll.refresh(),
    eventsPoll.refresh(),
    newsPoll.refresh(),
    calendarPoll.refresh(),
  ]);
  toast.info("已刷新论点与证据数据");
}
</script>

<style scoped>
/* tabs 计数 */
.seg button .tab-count {
  margin-left: 5px;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.seg button.active .tab-count { color: var(--accent); }

.thesis-toolbar { padding: 8px 12px; }
.thesis-toolbar .tool-right { margin-left: auto; }
.thesis-toolbar .tool-note { white-space: nowrap; }

/* ---------- 论点卡 ---------- */
.thesis-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.thesis-card { padding: 11px 13px 12px; min-width: 0; display: flex; flex-direction: column; gap: 7px; }
.t-head { display: flex; align-items: flex-start; gap: 7px; }
.t-title {
  flex: 1;
  min-width: 0;
  font-size: 12.5px;
  font-weight: 650;
  line-height: 1.42;
  letter-spacing: .1px;
}
.t-meta { display: flex; align-items: center; gap: 12px; font-size: 9.5px; color: var(--dim); }
.t-meta span { display: inline-flex; align-items: center; gap: 3px; }
.t-meta svg { width: 10px; height: 10px; }
.t-created { margin-left: auto; font-family: var(--mono); }

.t-prob { display: flex; flex-direction: column; gap: 3px; }
.t-prob-label { display: flex; align-items: baseline; justify-content: space-between; font-size: 9.5px; color: var(--dim); }
.t-prob-label b { color: var(--text); font-size: 11px; }
.prob-track { height: 4px; border-radius: 999px; background: var(--surface-2); overflow: hidden; }
.prob-track i { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 55%, var(--warn))); }

.t-driver { display: flex; align-items: flex-start; gap: 5px; font-size: 10.5px; line-height: 1.5; color: var(--muted); }
.t-driver svg { width: 11px; height: 11px; margin-top: 2px; color: var(--accent); }
.t-driver span { min-width: 0; }

.t-scenarios { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.scenario {
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: color-mix(in srgb, var(--surface-2) 55%, transparent);
  padding: 6px 8px 7px;
}
.s-head { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; }
.s-name { font-size: 10px; font-weight: 600; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s-prob { font-size: 11px; font-weight: 650; color: var(--text); }
.s-bar { height: 3px; margin: 4px 0 4px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.s-bar i { display: block; height: 100%; border-radius: 999px; background: var(--accent); opacity: .75; }
.s-trigger { font-size: 9.5px; line-height: 1.5; color: var(--dim); }

.t-invalidation {
  margin-top: 1px;
  padding-top: 7px;
  border-top: 1px dashed var(--border);
  display: flex;
  gap: 7px;
  font-size: 10px;
  line-height: 1.55;
}
.inv-label { flex: none; display: inline-flex; align-items: flex-start; gap: 3px; color: var(--warn); font-weight: 600; }
.inv-label svg { width: 10px; height: 10px; margin-top: 2px; }
.inv-text { color: var(--muted); }

/* ---------- 复核 ---------- */
.review-card { margin-top: 10px; }
.review-body { padding: 11px 13px 13px; }
.review-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.r-stat {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface-2) 55%, transparent);
  padding: 8px 10px;
}
.r-num { font-size: 19px; font-weight: 680; letter-spacing: -.4px; line-height: 1.15; }
.r-label { margin-top: 1px; font-size: 9.5px; color: var(--dim); }
.review-note { margin-top: 9px; font-size: 10.5px; line-height: 1.65; color: var(--muted); max-width: 900px; }

.review-records { margin-top: 9px; border-top: 1px solid var(--border); }
.rr-row {
  display: grid;
  grid-template-columns: 56px 44px minmax(0, 1fr) 78px 68px 44px;
  gap: 8px;
  align-items: center;
  height: 27px;
  border-bottom: 1px dashed var(--border);
  font-size: 10.5px;
}
.rr-row:last-child { border-bottom: 0; }
.rr-symbol { color: var(--accent); font-size: 10px; }
.rr-title { color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rr-since { color: var(--dim); font-size: 9.5px; }
.rr-return { text-align: right; font-size: 10.5px; font-weight: 600; }

/* ---------- 事件 ---------- */
.event-list { padding: 2px 13px 4px; }
.event-row {
  display: grid;
  grid-template-columns: 78px 62px minmax(0, 1fr) auto;
  gap: 9px;
  align-items: start;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}
.event-row:last-child { border-bottom: 0; }
.event-date { font-size: 9.5px; color: var(--accent); padding-top: 2px; white-space: nowrap; }
.event-type { margin-top: 1px; }
.event-main { min-width: 0; }
.event-title { font-size: 11.5px; line-height: 1.45; color: var(--text); }
.event-summary { margin-top: 1px; font-size: 9.5px; line-height: 1.5; color: var(--dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event-tags { display: flex; gap: 4px; flex-wrap: nowrap; padding-top: 1px; font-size: 9.5px; }

/* ---------- 新闻 ---------- */
.news-list { padding: 2px 13px 4px; }
.news-row {
  width: 100%;
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr) 74px;
  gap: 10px;
  align-items: center;
  padding: 6px 4px;
  border: 0;
  border-bottom: 1px dashed var(--border);
  background: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
  border-radius: 5px;
  transition: background .12s;
}
.news-row:last-child { border-bottom: 0; }
.news-row:hover { background: color-mix(in srgb, var(--surface-2) 65%, transparent); }
.news-side { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.news-source { font-size: 10px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.news-time { font-size: 9px; color: var(--dim); }
.news-main { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.news-title { font-size: 11.5px; line-height: 1.45; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.news-summary { font-size: 9.5px; line-height: 1.45; color: var(--dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.news-side-right { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.news-go { width: 11px; height: 11px; color: var(--dim); }

/* ---------- 日历 ---------- */
.calendar-list { padding: 1px 13px 4px; }
.calendar-list .cal-sep { margin-top: 4px; }
.calendar-list .cal-row {
  grid-template-columns: 48px 40px 86px minmax(0, 1fr) auto;
  height: 26px;
}
.cal-cat { font-size: 9.5px; color: var(--dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* 窄屏兜底 */
@media (max-width: 1180px) {
  .thesis-list { grid-template-columns: 1fr; }
}
</style>
