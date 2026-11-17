<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">
          内容 · 简报 · 真实历史期次 ·
          {{ brief ? `生成于 ${fmtDateTime(brief.created_at)}` : "等待生成" }}
        </div>
        <h1 class="page-h1">简报与日志 <span class="page-sub">{{ pageSub }}</span></h1>
      </div>
      <div class="page-actions">
        <a v-if="brief" class="btn btn--sm" :href="briefMarkdownUrl(brief.id)" download>
          <svg class="ic"><use href="#i-download" /></svg>导出 Markdown
        </a>
        <button v-else class="btn btn--sm" type="button" disabled>
          <svg class="ic"><use href="#i-download" /></svg>导出 Markdown
        </button>
        <a v-if="brief" class="btn btn--sm" :href="briefPrintUrl(brief.id)" target="_blank" rel="noopener">
          <svg class="ic"><use href="#i-external" /></svg>服务端打印版
        </a>
        <button v-else class="btn btn--sm" type="button" disabled>
          <svg class="ic"><use href="#i-external" /></svg>服务端打印版
        </button>
        <button class="btn btn--sm btn--primary" type="button" :disabled="!brief" @click="printBrief">
          <svg class="ic"><use href="#i-print" /></svg>打印 / PDF
        </button>
      </div>
    </div>

    <!-- 工具条：日报 / 周报 / 月报 + 期次（真实上一期 / 下一期） -->
    <section class="card brief-toolbar">
      <div class="seg">
        <button
          v-for="option in KIND_TABS"
          :key="option.value"
          type="button"
          :class="{ active: kind === option.value }"
          @click="setKind(option.value)"
        >
          {{ option.label }}<span class="tab-count">{{ kindCounts[option.value] }}</span>
        </button>
      </div>
      <div class="brief-date-nav">
        <button
          class="btn btn--icon btn--sm"
          type="button"
          :title="prevTitle"
          :disabled="!prevId || loading"
          @click="goPrev"
        >
          <svg class="ic" :class="{ spin: navLoading === 'prev' }"><use href="#i-chevron-left" /></svg>
        </button>
        <span class="date-chip">{{ brief?.trade_date ?? "—" }} <span>{{ weekdayLabel }}</span></span>
        <button
          class="btn btn--icon btn--sm"
          type="button"
          :title="nextTitle"
          :disabled="!nextId || loading"
          @click="goNext"
        >
          <svg class="ic" :class="{ spin: navLoading === 'next' }"><use href="#i-chevron-right" /></svg>
        </button>
        <span v-if="issueNo" class="issue-pos">第 {{ issueNo }} / {{ issueTotal }} 期</span>
        <button
          class="btn btn--sm btn--ghost"
          type="button"
          :disabled="loading"
          title="回到本组最新一期"
          @click="goLatest"
        >
          <svg class="ic"><use href="#i-refresh" /></svg>最新
        </button>
      </div>
      <select
        v-if="issueHistory.length"
        class="select issue-select"
        :value="brief?.id ?? ''"
        :disabled="loading"
        title="按期次跳转（本组历史）"
        @change="onSelectIssue"
      >
        <option v-for="(row, index) in issueHistory" :key="row.id" :value="row.id">
          {{ issueTotal - index }}. {{ row.trade_date }} · {{ kindLabel(row.kind) }} ·
          {{ fmtInt(row.chars) }} 字
        </option>
      </select>
      <div class="tool-right">
        <span class="tool-note">
          <span class="dot dot--live"></span>真实历史期次 · 上一期 / 下一期读取同组相邻简报
        </span>
        <button class="btn btn--sm" type="button" :disabled="!brief?.markdown" @click="copyFull">
          <svg class="ic"><use href="#i-copy" /></svg>复制全文
        </button>
      </div>
    </section>

    <!-- 状态：加载 / 错误 / 空 -->
    <section v-if="loading && !brief" class="card">
      <div class="card-body"><SkeletonBlock :rows="10" :cells="2" :height="12" /></div>
    </section>
    <section v-else-if="error && !brief" class="card">
      <ErrorState :error="error" @retry="reload" />
    </section>
    <section v-else-if="!brief" class="card">
      <EmptyState :text="emptyText" :hint="emptyHint">
        <RouterLink class="btn btn--sm" style="margin-top: 6px" to="/system">
          <svg class="ic"><use href="#i-tasks" /></svg>去系统页运行任务
        </RouterLink>
      </EmptyState>
    </section>
    <section v-else-if="!brief.markdown" class="card">
      <EmptyState text="简报正文为空" hint="该期简报只有元数据，重新运行 brief_manual 任务可生成正文。" />
    </section>

    <!-- 三栏阅读器 -->
    <div v-else class="brief-layout">
      <aside class="card toc-card">
        <div class="toc-title">文内目录</div>
        <button
          v-for="heading in rendered?.headings ?? []"
          :key="heading.id"
          class="toc-item"
          :class="{ active: activeHeadingId === heading.id }"
          type="button"
          :title="heading.label"
          @click="scrollToHeading(heading.id)"
        >
          <span class="toc-num">{{ heading.num }}</span>
          <span class="toc-label">{{ heading.label }}</span>
        </button>
        <div v-if="!rendered?.headings.length" class="toc-empty">暂无二级标题</div>
        <div class="toc-foot">
          证据引用 <b>{{ rendered?.evidenceCount ?? 0 }}</b> 处<br />
          本期字数 <b>{{ fmtInt(rendered?.chars ?? 0) }}</b><br />
          目录区块 <b>{{ rendered?.headings.length ?? 0 }}</b> 节<br />
          阅读约 <b>{{ rendered?.minutes ?? 1 }}</b> 分钟
        </div>
      </aside>

      <article class="card article">
        <div class="article-inner">
          <div class="article-eyebrow">
            <span class="badge badge--accent badge--sm">{{ kindLabel(brief.kind) }}</span>
            <span>{{ brief.trade_date }} {{ weekdayLabel }}</span>
            <span class="m-dot"></span>
            <span class="mono">{{ brief.id.slice(0, 8) }}</span>
            <span class="m-dot"></span>
            <span>分析引擎 · {{ brief.kind }}</span>
            <span class="spacer"></span>
            <a class="link-btn" :href="briefPrintUrl(brief.id)" target="_blank" rel="noopener">
              服务端打印版<svg class="ic"><use href="#i-external" /></svg>
            </a>
          </div>
          <h1>{{ rendered?.title ?? "简报正文" }}</h1>
          <div class="article-meta">
            <span>生成于 {{ fmtTime(brief.created_at, true) }}</span>
            <span class="m-dot"></span>
            <span>{{ fmtInt(rendered?.chars ?? 0) }} 字</span>
            <span class="m-dot"></span>
            <span>阅读约 {{ rendered?.minutes ?? 1 }} 分钟</span>
            <span class="m-dot"></span>
            <span>证据 {{ rendered?.evidenceCount ?? 0 }} 条</span>
            <span class="m-dot"></span>
            <span class="up">{{ updownLabel }}</span>
            <span class="spacer"></span>
            <button class="link-btn print-hide" type="button" @click="copyFull">
              <svg class="ic"><use href="#i-copy" /></svg>复制全文
            </button>
          </div>
          <div ref="articleRef" class="md-body" v-html="safeHtml" @click="onArticleClick"></div>
          <div v-if="!safeHtml" class="md-empty">正文渲染为空，请检查简报内容。</div>
          <div class="article-foot">
            本期数据来自 EPIC 数据层；正文中的「证据」按钮可打开右侧抽屉查看原文与断言高亮。
            简报由分析引擎生成，仅供个人研究参考，不构成投资建议。
          </div>
        </div>
      </article>

      <aside class="brief-aside">
        <div class="card aside-card">
          <div class="aside-title">本期概览</div>
          <div class="meta-grid">
            <div class="meta-cell"><div class="meta-num">{{ fmtInt(rendered?.chars ?? 0) }}</div><div class="meta-label">字数</div></div>
            <div class="meta-cell"><div class="meta-num">{{ rendered?.evidenceCount ?? 0 }}</div><div class="meta-label">证据引用</div></div>
            <div class="meta-cell"><div class="meta-num">{{ rendered?.headings.length ?? 0 }}</div><div class="meta-label">目录区块</div></div>
            <div class="meta-cell"><div class="meta-num">{{ relatedWatch.length }}</div><div class="meta-label">关联标的</div></div>
          </div>
        </div>

        <div class="card aside-card">
          <div class="aside-title">关联标的 · 自选前 5</div>
          <button
            v-for="item in relatedWatch"
            :key="item.symbol"
            class="aside-link aside-link--btn"
            type="button"
            :title="`${item.name} ${item.symbol} · 点击查看历史走势`"
            @click="openInstrument(item)"
          >
            <span>{{ item.name }}</span>
            <span :class="trendClass(item.change_pct)">{{ fmtPct(item.change_pct) }}</span>
          </button>
          <div v-if="!relatedWatch.length" class="aside-empty">暂无自选标的</div>
        </div>

        <div class="card aside-card">
          <div class="aside-title">关联证据 · 本期引用</div>
          <button
            v-for="ref in evidenceRefs"
            :key="ref.id"
            class="aside-link aside-link--btn"
            type="button"
            :title="`打开证据原文 · ${ref.label}`"
            @click="evidence.show(ref.id)"
          >
            <span class="mono evidence-ref">{{ ref.id.slice(0, 8) }}</span>
            <span class="dim">{{ ref.label }}</span>
          </button>
          <div v-if="!evidenceRefs.length" class="aside-empty">本期未引用可追溯证据</div>
        </div>

        <div class="card aside-card">
          <div class="aside-title">导出与分享</div>
          <div class="export-row">
            <a class="btn btn--sm" :href="briefMarkdownUrl(brief.id)" download>
              <svg class="ic"><use href="#i-download" /></svg>Markdown
            </a>
            <button class="btn btn--sm" type="button" @click="printBrief">
              <svg class="ic"><use href="#i-print" /></svg>PDF
            </button>
          </div>
          <a class="btn btn--sm aside-print" :href="briefPrintUrl(brief.id)" target="_blank" rel="noopener">
            <svg class="ic"><use href="#i-external" /></svg>服务端打印版
          </a>
          <div class="token-note">打印样式仅输出正文；服务端打印版在新标签页打开，可另存为 PDF。</div>
        </div>
      </aside>
    </div>

    <!-- 交易记录 -->
        <section class="card">
      <div class="card-head">
        <span class="card-title">交易记录</span>
        <span class="card-sub">已独立为单独页面：股票 / 期货等多品种的交易计划、执行与复盘</span>
        <div class="card-actions">
          <RouterLink class="btn btn--sm btn--ghost" to="/trades">
            <svg class="ic"><use href="#i-book" /></svg>打开交易
          </RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDateTime, fmtInt, fmtPct, fmtTime, trendClass } from "@/composables/useFormat";
import {
  briefMarkdownUrl,
  briefPrintUrl,
  getBrief,
  getBriefKinds,
  getBriefList,
  getLatestBrief,
  getWatchlist,
} from "@/api/endpoints";
import type { Brief, BriefSummary, WatchlistItem } from "@/api/types";
import { useEvidenceStore } from "@/stores/evidence";
import { useHistoryStore } from "@/stores/history";
import { usePrefsStore } from "@/stores/prefs";
import { useToast } from "@/stores/toast";

type BriefKind = "daily" | "weekly" | "monthly";

interface TocItem {
  id: string;
  label: string;
  num: string;
}

interface RenderedBrief {
  title: string;
  headings: TocItem[];
  evidenceCount: number;
  chars: number;
  minutes: number;
}

interface RenderResult {
  html: string;
  meta: RenderedBrief;
}

const KIND_TABS: Array<{ value: BriefKind; label: string }> = [
  { value: "daily", label: "日报" },
  { value: "weekly", label: "周报" },
  { value: "monthly", label: "月报" },
];

/** 每类最多拉取的历史条数（后端 /api/briefs 上限 50） */
const HISTORY_LIMIT = 50;

const KIND_LABEL: Record<string, string> = {
  daily: "日报",
  weekly: "周报",
  monthly: "月报",
  manual: "手动简报",
  premarket: "盘前简报",
  postmarket: "盘后简报",
};

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

const EVIDENCE_RE = /\[D:([0-9a-f]{32})\]/gi;
const EVIDENCE_EXACT_RE = /^\[D:([0-9a-f]{32})\]$/i;
const INLINE_RE = /\[D:([0-9a-f]{32})\]|([+-]\d+(?:\.\d+)?%)/gi;
const NUMERIC_CELL_RE = /^[+\-−]?[\d,]+(?:\.\d+)?%?$/;

const route = useRoute();
const router = useRouter();
const evidence = useEvidenceStore();
const historyStore = useHistoryStore();
const prefs = usePrefsStore();
const toast = useToast();

const kind = ref<BriefKind>("daily");
const brief = ref<Brief | null>(null);
const loading = ref(false);
const error = ref<Error | null>(null);
const safeHtml = ref("");

/** 关联证据：优先读 brief.evidence_ids（后端 A10 扩展），否则从正文 .ev-link[data-doc] 抽取 */
const evidenceRefs = computed<Array<{ id: string; label: string }>>(() => {
  const fromBrief = (brief.value as unknown as { evidence_ids?: string[] } | null)?.evidence_ids ?? [];
  const seen = new Map<string, string>();
  for (const id of fromBrief) {
    if (typeof id === "string" && id && !seen.has(id)) seen.set(id, "简报声明");
  }
  if (safeHtml.value) {
    const doc = new DOMParser().parseFromString(safeHtml.value, "text/html");
    for (const node of Array.from(doc.querySelectorAll<HTMLElement>(".ev-link[data-doc]"))) {
      const id = node.dataset.doc ?? "";
      if (!id) continue;
      const label = (node.textContent ?? "").trim().replace(/\s+/g, " ");
      if (!seen.has(id)) seen.set(id, label ? label.slice(0, 18) : "正文引用");
    }
  }
  return Array.from(seen.entries())
    .slice(0, 8)
    .map(([id, label]) => ({ id, label }));
});
const rendered = ref<RenderedBrief | null>(null);
const activeHeadingId = ref("");
const articleRef = ref<HTMLElement | null>(null);
const watchlist = ref<WatchlistItem[]>([]);

/* 历史期次 / 上一期下一期 */
const kindCounts = ref<Record<BriefKind, number>>({ daily: 0, weekly: 0, monthly: 0 });
const issueHistory = ref<BriefSummary[]>([]);
const latestId = ref<string | null>(null);
const latestNeighbors = ref<{ previous_id: string | null; next_id: string | null }>({
  previous_id: null,
  next_id: null,
});
const navLoading = ref<"" | "prev" | "next">("");


const md = new MarkdownIt({ html: false, linkify: true, breaks: false });

/* ---------- 文本 ---------- */

function kindLabel(value: string): string {
  return KIND_LABEL[value] ?? value;
}

function kindFromQuery(value: unknown): BriefKind {
  return value === "weekly" || value === "monthly" ? value : "daily";
}

const pageSub = computed(() =>
  brief.value
    ? `${kindLabel(brief.value.kind)} · ${brief.value.trade_date} ${weekdayLabel.value}`
    : "日报 / 周报 / 月报 · 真实历史期次 · 交易记录",
);

const weekdayLabel = computed(() => {
  const date = brief.value?.trade_date;
  if (!date) return "";
  const parsed = new Date(`${date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return "";
  return WEEKDAYS[parsed.getDay()] ?? "";
});

const updownLabel = computed(() => (prefs.updown === "green" ? "绿涨红跌" : "红涨绿跌"));

const relatedWatch = computed<WatchlistItem[]>(() => watchlist.value.slice(0, 5));

/* ---------- 历史期次导航 ---------- */

/** 当前简报在历史列表中的位置（0 = 本组最新一期，越大越早） */
const issueIndex = computed(() => {
  const id = brief.value?.id;
  if (!id) return -1;
  return issueHistory.value.findIndex((row) => row.id === id);
});

/** 本组总期数：优先用 /briefs/kinds 的分组计数，回退到已加载条数 */
const issueTotal = computed(() => {
  const counted = kindCounts.value[kind.value] ?? 0;
  return counted > issueIndex.value ? counted : issueHistory.value.length;
});

/** 期号（从最早一期开始数），当前简报不在历史窗口内时为 null */
const issueNo = computed(() => {
  if (issueIndex.value < 0 || !issueTotal.value) return null;
  return Math.max(1, issueTotal.value - issueIndex.value);
});

/**
 * 上一期 / 下一期 id：
 * 当前简报正好是最新一期时直接用 /briefs/latest 返回的 neighbors；
 * 翻阅到历史期次后按历史列表相邻位置计算（同组、同排序）。
 */
const prevId = computed<string | null>(() => {
  const current = brief.value?.id;
  if (!current) return null;
  if (latestId.value === current) return latestNeighbors.value.previous_id;
  const index = issueIndex.value;
  return index >= 0 ? issueHistory.value[index + 1]?.id ?? null : null;
});

const nextId = computed<string | null>(() => {
  const current = brief.value?.id;
  if (!current) return null;
  if (latestId.value === current) return latestNeighbors.value.next_id;
  const index = issueIndex.value;
  return index > 0 ? issueHistory.value[index - 1]?.id ?? null : null;
});

const prevTitle = computed(() =>
  prevId.value ? "上一期（更早一期）" : "已是本组最早一期，无更早期次",
);
const nextTitle = computed(() =>
  nextId.value ? "下一期（更新一期）" : "已是最新一期，无更新期次",
);

const emptyText = computed(() => (kind.value === "daily" ? "暂无简报" : `暂无${kindLabel(kind.value)}`));
const emptyHint = computed(() =>
  kind.value === "daily"
    ? "运行 brief_manual 任务，或等待每日 17:30 的定时生成后查看；日报聚合 manual / premarket / postmarket。"
    : `${kindLabel(kind.value)}按周 / 月生成，运行对应简报任务或等待定时生成后查看。`,
);

/* ---------- Markdown 渲染（markdown-it + DOMPurify） ---------- */

function makeEvidenceButton(documentId: string): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ev-link";
  button.dataset.doc = documentId;
  button.title = `查看证据 ${documentId.slice(0, 8)}`;
  button.textContent = "证据";
  return button;
}

/** 从 Markdown 提取一级标题（作为页面正文标题），并从正文中移除该行 */
function extractTitle(source: string): { title: string; body: string } {
  const lines = source.split("\n");
  const headingIndex = lines.findIndex((line) => /^#\s+/.test(line));
  if (headingIndex < 0) return { title: "简报正文", body: source };
  const title = lines[headingIndex]
    .replace(/^#\s+/, "")
    .replace(EVIDENCE_RE, "")
    .replace(/[*`]/g, "")
    .trim();
  const body = [...lines.slice(0, headingIndex), ...lines.slice(headingIndex + 1)].join("\n");
  return { title: title || "简报正文", body };
}

function countChars(source: string): number {
  const text = source
    .replace(EVIDENCE_RE, "")
    .replace(/[#>*`|_~\-]/g, "")
    .replace(/\s+/g, "");
  return text.length;
}

/** 对文本节点做整体替换：证据标记 → 按钮，带符号涨跌幅 → up/down span */
function decorateTextNode(node: Text): void {
  const text = node.nodeValue ?? "";
  if (!text) return;
  const parent = node.parentElement;
  if (parent?.closest("pre, code, .ev-link")) return;
  INLINE_RE.lastIndex = 0;
  const fragment = document.createDocumentFragment();
  let last = 0;
  let changed = false;
  let match: RegExpExecArray | null;
  while ((match = INLINE_RE.exec(text)) !== null) {
    changed = true;
    if (match.index > last) fragment.append(text.slice(last, match.index));
    if (match[1]) {
      fragment.append(makeEvidenceButton(match[1]));
    } else {
      const span = document.createElement("span");
      span.className = match[2].startsWith("+") ? "up" : "down";
      span.textContent = match[2];
      fragment.append(span);
    }
    last = match.index + match[0].length;
  }
  if (!changed) return;
  if (last < text.length) fragment.append(text.slice(last));
  node.replaceWith(fragment);
}

function decorateTextNodes(root: Node): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode as Text);
  for (const node of nodes) decorateTextNode(node);
}

/** 表格：套 .brief-table + 横向滚动容器；数值列右对齐 */
function styleTables(root: ParentNode): void {
  for (const table of Array.from(root.querySelectorAll("table"))) {
    table.classList.add("brief-table");
    const parent = table.parentNode;
    if (parent && !(parent instanceof HTMLDivElement && parent.classList.contains("brief-table-wrap"))) {
      const wrapper = document.createElement("div");
      wrapper.className = "brief-table-wrap";
      parent.insertBefore(wrapper, table);
      wrapper.append(table);
    }
    const htmlTable = table as HTMLTableElement;
    const rows = Array.from(htmlTable.rows);
    if (!rows.length) continue;
    const columnCount = rows[0].cells.length;
    for (let column = 0; column < columnCount; column += 1) {
      let numeric = 0;
      let total = 0;
      for (const row of rows.slice(1)) {
        const cell = row.cells[column];
        if (!cell) continue;
        const text = (cell.textContent ?? "").trim().replace(/\s/g, "");
        if (!text) continue;
        total += 1;
        if (NUMERIC_CELL_RE.test(text)) numeric += 1;
      }
      if (total > 0 && numeric / total >= 0.6) {
        for (const row of rows) row.cells[column]?.classList.add("num");
      }
    }
  }
}

/** 二级标题：生成锚点 id、编号徽标，并收集目录 */
function styleHeadings(root: ParentNode): TocItem[] {
  const headings: TocItem[] = [];
  root.querySelectorAll("h2").forEach((heading, index) => {
    const element = heading as HTMLElement;
    const raw = (element.textContent ?? "").replace(/\s+/g, " ").trim();
    // 去掉原标题自带的手写编号（如「0. 」），改用统一的编号徽标
    const stripped = raw.replace(/^\d+\s*[.、．)）]\s*/, "").trim();
    const label = stripped || raw || `第 ${index + 1} 节`;
    const id = `brief-sec-${index + 1}`;
    element.id = id;
    element.classList.add("a-h2");
    const num = document.createElement("span");
    num.className = "a-num";
    num.textContent = String(index + 1).padStart(2, "0");
    element.textContent = "";
    element.append(num, document.createTextNode(label));
    headings.push({ id, label, num: num.textContent ?? "" });
  });
  root.querySelectorAll("h3").forEach((heading) => heading.classList.add("a-h3"));
  return headings;
}

function renderBrief(source: string): RenderResult {
  const { title, body } = extractTitle(source);
  const template = document.createElement("template");
  template.innerHTML = md.render(body);
  const root = template.content;

  styleTables(root);

  root.querySelectorAll("blockquote").forEach((quote) => {
    quote.classList.add("quote");
    const label = document.createElement("div");
    label.className = "quote-label";
    label.textContent = "主线判断";
    quote.insertBefore(label, quote.firstChild);
  });

  const headings = styleHeadings(root);

  root.querySelectorAll("p").forEach((paragraph) => paragraph.classList.add("a-p"));
  root.querySelectorAll("ul, ol").forEach((list) => list.classList.add("brief-list"));
  root.querySelectorAll("a").forEach((link) => {
    link.setAttribute("target", "_blank");
    link.setAttribute("rel", "noopener noreferrer");
  });

  // 反引号里的 `[D:xxx]` 在 markdown-it 中会渲染为 <code>，先整块替换成证据按钮
  root.querySelectorAll("code").forEach((code) => {
    const match = EVIDENCE_EXACT_RE.exec((code.textContent ?? "").trim());
    if (match) code.replaceWith(makeEvidenceButton(match[1]));
  });

  // 再处理普通文本节点：剩余证据标记 + 涨跌着色（只碰文本节点，不破坏表格结构）
  decorateTextNodes(root);

  const html = DOMPurify.sanitize(template.innerHTML, { ADD_ATTR: ["data-doc"] });
  const evidenceCount = (source.match(EVIDENCE_RE) ?? []).length;
  const chars = countChars(source);
  return {
    html,
    meta: {
      title,
      headings,
      evidenceCount,
      chars,
      minutes: Math.max(1, Math.round(chars / 400)),
    },
  };
}

function applyBrief(): void {
  const source = brief.value?.markdown;
  if (!source) {
    safeHtml.value = "";
    rendered.value = null;
    activeHeadingId.value = "";
    return;
  }
  const result = renderBrief(source);
  safeHtml.value = result.html;
  rendered.value = result.meta;
  activeHeadingId.value = result.meta.headings[0]?.id ?? "";
  void nextTick(() => updateActiveHeading());
}

/* ---------- 目录滚动高亮 ---------- */

function scrollToHeading(id: string): void {
  activeHeadingId.value = id;
  const target = articleRef.value?.querySelector<HTMLElement>(`#${id}`) ?? document.getElementById(id);
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateActiveHeading(): void {
  const container = articleRef.value;
  if (!container) return;
  const headings = Array.from(container.querySelectorAll<HTMLElement>("h2[id]"));
  if (!headings.length) return;
  const topbar = Number.parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--topbar-h"),
  );
  const offset = (Number.isFinite(topbar) ? topbar : 56) + 18;
  let current = headings[0].id;
  for (const heading of headings) {
    if (heading.getBoundingClientRect().top <= offset) current = heading.id;
    else break;
  }
  activeHeadingId.value = current;
}

/* ---------- 取数 ---------- */

function scrollToTop(): void {
  window.scrollTo({ top: 0, behavior: "auto" });
}

/** 同步 URL query（kind / brief），便于刷新与分享后保持当前期次 */
function syncQuery(patch: Record<string, string | null>): void {
  const query: Record<string, string | string[]> = {};
  for (const [key, value] of Object.entries(route.query)) {
    if (typeof value === "string") query[key] = value;
    else if (Array.isArray(value)) query[key] = value.filter((item): item is string => typeof item === "string");
  }
  for (const [key, value] of Object.entries(patch)) {
    if (value === null || value === "") delete query[key];
    else query[key] = value;
  }
  void router.replace({ query });
}

/** 各分组期数（tab 徽标） */
async function loadKindCounts(): Promise<void> {
  try {
    const payload = await getBriefKinds();
    const groups = payload.data?.groups;
    if (groups) {
      kindCounts.value = {
        daily: groups.daily ?? 0,
        weekly: groups.weekly ?? 0,
        monthly: groups.monthly ?? 0,
      };
    }
  } catch {
    /* 徽标失败不影响正文 */
  }
}

/** 本组历史列表（用于期号下拉与历史期次的相邻计算） */
async function loadIssueHistory(requested: BriefKind = kind.value): Promise<void> {
  try {
    const payload = await getBriefList(requested, HISTORY_LIMIT, 0);
    if (requested !== kind.value) return;
    issueHistory.value = payload.data ?? [];
  } catch {
    if (requested !== kind.value) return;
    issueHistory.value = [];
  }
}

/** 载入某分组最新一期：正文 + neighbors（上一期 / 下一期 id） */
async function loadLatest(announce = false): Promise<void> {
  const requested = kind.value;
  loading.value = true;
  error.value = null;
  try {
    const payload = await getLatestBrief(requested);
    if (requested !== kind.value) return;
    latestId.value = payload.data?.id ?? null;
    latestNeighbors.value = payload.neighbors ?? { previous_id: null, next_id: null };
    brief.value = payload.data;
    applyBrief();
    scrollToTop();
    void loadIssueHistory(requested);
    if (announce) {
      toast.info(payload.data ? "已回到本组最新一期" : "本组暂无简报");
    }
  } catch (err) {
    if (requested !== kind.value) return;
    error.value = err instanceof Error ? err : new Error(String(err));
    brief.value = null;
    latestId.value = null;
    latestNeighbors.value = { previous_id: null, next_id: null };
    safeHtml.value = "";
    rendered.value = null;
  } finally {
    if (requested === kind.value) loading.value = false;
  }
}

/** 按 id 打开某一期（上一期 / 下一期 / 期号下拉 / URL 深链） */
async function openBrief(id: string, syncUrl = true): Promise<void> {
  if (!id || id === brief.value?.id) return;
  const requested = kind.value;
  loading.value = true;
  error.value = null;
  try {
    const detail = await getBrief(id);
    if (requested !== kind.value) return;
    brief.value = detail;
    applyBrief();
    scrollToTop();
    if (syncUrl) syncQuery({ brief: detail.id });
  } catch (err) {
    if (requested !== kind.value) return;
    error.value = err instanceof Error ? err : new Error(String(err));
    toast.bad(`该期简报加载失败：${err instanceof Error ? err.message : String(err)}`);
  } finally {
    if (requested === kind.value) loading.value = false;
  }
}

async function loadWatchlist(): Promise<void> {
  try {
    watchlist.value = (await getWatchlist()).data ?? [];
  } catch {
    watchlist.value = [];
  }
}



/* ---------- 交互 ---------- */

function setKind(next: BriefKind, syncUrl = true): void {
  if (kind.value === next) return;
  kind.value = next;
  brief.value = null;
  safeHtml.value = "";
  rendered.value = null;
  activeHeadingId.value = "";
  latestId.value = null;
  latestNeighbors.value = { previous_id: null, next_id: null };
  issueHistory.value = [];
  scrollToTop();
  void loadLatest();
  if (syncUrl) syncQuery({ kind: next === "daily" ? null : next, brief: null });
}

function reload(): void {
  void loadKindCounts();
  void loadLatest();
  void loadIssueHistory();
  toast.info(`已刷新${KIND_TABS.find((option) => option.value === kind.value)?.label ?? "简报"}`);
}

async function goPrev(): Promise<void> {
  const id = prevId.value;
  if (!id || loading.value) return;
  navLoading.value = "prev";
  try {
    await openBrief(id);
  } finally {
    navLoading.value = "";
  }
}

async function goNext(): Promise<void> {
  const id = nextId.value;
  if (!id || loading.value) return;
  navLoading.value = "next";
  try {
    await openBrief(id);
  } finally {
    navLoading.value = "";
  }
}

/** 回到本组最新一期（同时清掉 URL 上的 brief 参数） */
async function goLatest(): Promise<void> {
  if (loading.value) return;
  if (latestId.value && brief.value?.id === latestId.value) {
    syncQuery({ brief: null });
    return;
  }
  await loadLatest(true);
  syncQuery({ brief: null });
}

/** 期号下拉跳转 */
function onSelectIssue(event: Event): void {
  const target = event.target as HTMLSelectElement | null;
  const id = target?.value ?? "";
  if (id) void openBrief(id);
}

function printBrief(): void {
  window.print();
}

async function copyFull(): Promise<void> {
  const text = brief.value?.markdown;
  if (!text) {
    toast.warn("暂无可复制的简报正文");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    toast.ok("简报全文已复制");
  } catch {
    toast.warn("浏览器拒绝剪贴板访问");
  }
}

function openInstrument(item: WatchlistItem): void {
  void historyStore.openHistory("instrument", item.symbol, item.name);
}

function onArticleClick(event: MouseEvent): void {
  const target = event.target as HTMLElement | null;
  const button = target?.closest<HTMLElement>(".ev-link");
  const documentId = button?.dataset.doc;
  if (documentId) void evidence.show(documentId);
}

/* ---------- 生命周期 ---------- */

async function bootstrap(): Promise<void> {
  kind.value = kindFromQuery(route.query.kind);
  void loadKindCounts();
  void loadWatchlist();
  await loadLatest();
  // URL 深链：?brief=<id> 直接打开某一期历史简报
  const wanted = typeof route.query.brief === "string" ? route.query.brief : "";
  if (wanted && wanted !== brief.value?.id) await openBrief(wanted, false);
}

onMounted(() => {
  void bootstrap();
  window.addEventListener("scroll", updateActiveHeading, { passive: true });
  window.addEventListener("resize", updateActiveHeading);
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", updateActiveHeading);
  window.removeEventListener("resize", updateActiveHeading);
});
</script>

<style scoped>
/* ---------- 工具条补充 ---------- */
.brief-toolbar .tool-note { white-space: nowrap; }
.brief-toolbar .seg button .tab-count {
  margin-left: 5px;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.brief-toolbar .seg button.active .tab-count { color: var(--accent); }
.issue-pos {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  white-space: nowrap;
}
.issue-select {
  max-width: 240px;
  min-width: 190px;
  font-size: 10.5px;
}
.toc-item { overflow: hidden; }
.toc-label { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.toc-empty { padding: 6px 7px; font-size: 10px; color: var(--dim); }

/* ---------- 正文（v-html 内容，需 :deep） ---------- */
.md-body {
  padding-top: 4px;
  font-size: 12.5px;
  line-height: 1.85;
  color: color-mix(in srgb, var(--text) 90%, var(--muted));
}
.md-body :deep(h2) { scroll-margin-top: calc(var(--topbar-h) + 12px); }
.md-body :deep(h2:first-child) { margin-top: 10px; }
.md-body :deep(h3) {
  margin: 15px 0 5px;
  font-size: 12.5px;
  font-weight: 650;
  color: var(--text);
}
.md-body :deep(p) { margin: 7px 0; }
.md-body :deep(strong) { color: var(--text); font-weight: 650; }
.md-body :deep(a) { color: var(--accent); text-decoration: none; }
.md-body :deep(a:hover) { text-decoration: underline; }
.md-body :deep(code) {
  font-family: var(--mono);
  font-size: 11px;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--muted);
}
.md-body :deep(hr) {
  border: 0;
  border-top: 1px solid var(--border);
  margin: 14px 0;
}
.md-body :deep(.brief-table-wrap) {
  overflow-x: auto;
  margin: 8px 0 4px;
  border-radius: 7px;
  max-width: 100%;
}
.md-body :deep(.brief-table-wrap) .brief-table { margin: 0; }
.md-body :deep(.quote) { margin: 13px 0 6px; }
.md-body :deep(.quote p) { margin: 0; }
.md-body :deep(.quote-label svg) { width: 11px; height: 11px; }
.md-body :deep(.ev-link) { vertical-align: baseline; }
.md-empty { padding: 20px 0; font-size: 11.5px; color: var(--dim); }

/* ---------- 侧栏补充 ---------- */
.aside-link--btn {
  width: 100%;
  border: 0;
  border-bottom: 1px dashed var(--border);
  background: none;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
}
.aside-link--btn:hover { background: var(--surface-2); }
.aside-link--btn:last-of-type { border-bottom: 0; }
.aside-empty { font-size: 10px; color: var(--dim); padding: 2px 0; }
.aside-print { width: 100%; margin-top: 6px; }
.token-note { margin-top: 7px; font-size: 9px; line-height: 1.6; color: var(--dim); }

/* ---------- 打印：仅输出正文 ---------- */
@media print {
  :global(body) {
    background: #fff !important;
    background-attachment: initial !important;
    color: #111 !important;
  }
  .article { background: #fff !important; border-color: #ddd !important; box-shadow: none !important; }
  .article-eyebrow a { display: none !important; }
  .md-body { font-size: 12px; line-height: 1.75; color: #222; }
  .md-body :deep(.ev-link) { display: none !important; }
  .md-body :deep(.a-p),
  .md-body :deep(.brief-list li),
  .md-body :deep(.quote p),
  .md-body :deep(.quote-label),
  .md-body :deep(h2),
  .md-body :deep(h3),
  .md-body :deep(strong),
  .md-body :deep(.brief-table th),
  .md-body :deep(.brief-table td),
  .md-body :deep(.a-num) {
    color: #222 !important;
  }
  .md-body :deep(.a-num) { border-color: #bbb !important; background: #f2f2f2 !important; }
  .md-body :deep(.brief-table th) { background: #f2f2f2 !important; }
  .md-body :deep(.brief-table td),
  .md-body :deep(.brief-table th) { border-color: #ccc !important; }
  .md-body :deep(.brief-list li::before) { background: #666 !important; }
  .article-meta,
  .article-eyebrow,
  .article-foot { color: #555 !important; }
  .article h1 { color: #111 !important; }
  .md-body :deep(.up),
  .md-body :deep(.down) { color: #333 !important; }
}
</style>
