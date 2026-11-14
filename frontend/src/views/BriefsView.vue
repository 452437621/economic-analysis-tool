<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">
          内容 · 简报 · {{ brief ? `生成于 ${fmtDateTime(brief.created_at)}` : "等待生成" }}
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

    <!-- 工具条：日报 / 周报 / 月报 + 期次 -->
    <section class="card brief-toolbar">
      <div class="seg">
        <button
          v-for="option in KIND_TABS"
          :key="option.value"
          type="button"
          :class="{ active: kind === option.value }"
          @click="setKind(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
      <div class="brief-date-nav">
        <button class="btn btn--icon btn--sm" type="button" title="上一期" @click="notifyNoHistory">
          <svg class="ic"><use href="#i-chevron-left" /></svg>
        </button>
        <span class="date-chip">{{ brief?.trade_date ?? "—" }} <span>{{ weekdayLabel }}</span></span>
        <button class="btn btn--icon btn--sm" type="button" title="下一期" @click="notifyNoHistory">
          <svg class="ic"><use href="#i-chevron-right" /></svg>
        </button>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="loading" @click="reload">
          <svg class="ic"><use href="#i-refresh" /></svg>最新
        </button>
      </div>
      <div class="tool-right">
        <span class="tool-note"><span class="dot dot--live"></span>页面内三栏阅读 · 旧版弹框阅读已并入本页</span>
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
      <EmptyState text="暂无简报" hint="运行 brief_manual 任务，或等待每日 17:30 的定时生成后查看。">
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

    <!-- 交易日志 -->
    <section class="card journal-card">
      <div class="card-head">
        <span class="card-title">交易日志</span>
        <span class="card-sub">记录判断、执行与偏差 · 最近 5 条</span>
        <div class="card-actions"><span class="badge badge--sm">{{ journal.length }} 条</span></div>
      </div>
      <div class="journal-body">
        <div class="journal-form">
          <textarea
            v-model="journalDraft"
            class="journal-input"
            rows="4"
            maxlength="2000"
            placeholder="记录今天的判断、执行偏差与复盘要点…"
            @keydown.ctrl.enter.prevent="saveEntry"
          ></textarea>
          <div class="journal-actions">
            <span class="journal-hint">{{ journalDraft.length }} / 2000 · Ctrl + Enter 保存</span>
            <button
              class="btn btn--sm btn--primary"
              type="button"
              :disabled="journalSaving || !journalDraft.trim()"
              @click="saveEntry"
            >
              <svg class="ic"><use href="#i-check" /></svg>{{ journalSaving ? "保存中…" : "保存日志" }}
            </button>
          </div>
        </div>
        <div class="journal-list">
          <div v-if="journalLoading" class="journal-skeleton">
            <SkeletonBlock :rows="3" :cells="2" :height="10" />
          </div>
          <ErrorState v-else-if="journalError && !journal.length" :error="journalError" @retry="loadJournal" />
          <EmptyState
            v-else-if="!journal.length"
            text="暂无交易日志"
            hint="保存第一条日志，记录当日判断与执行偏差，周报会自动汇总。"
          />
          <div v-else class="journal-entries">
            <div v-for="entry in journal" :key="entry.id ?? `${entry.entry_date}-${entry.content.slice(0, 12)}`" class="journal-entry">
              <div class="je-head">
                <span class="je-date mono">{{ entry.entry_date }}</span>
                <span v-if="entry.created_at" class="je-time mono">{{ fmtTime(entry.created_at, true) }}</span>
              </div>
              <div class="je-content">{{ entry.content }}</div>
            </div>
          </div>
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
  getJournal,
  getLatestBrief,
  getWatchlist,
  saveJournal,
} from "@/api/endpoints";
import type { Brief, JournalEntry, WatchlistItem } from "@/api/types";
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
const rendered = ref<RenderedBrief | null>(null);
const activeHeadingId = ref("");
const articleRef = ref<HTMLElement | null>(null);
const watchlist = ref<WatchlistItem[]>([]);

const journal = ref<JournalEntry[]>([]);
const journalDraft = ref("");
const journalLoading = ref(false);
const journalError = ref<Error | null>(null);
const journalSaving = ref(false);

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
    : "日报 / 周报 / 月报 · 交易日志",
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

async function loadBrief(): Promise<void> {
  const requested = kind.value;
  loading.value = true;
  error.value = null;
  try {
    const payload = await getLatestBrief(requested);
    if (requested !== kind.value) return;
    brief.value = payload.data;
    applyBrief();
  } catch (err) {
    if (requested !== kind.value) return;
    error.value = err instanceof Error ? err : new Error(String(err));
    brief.value = null;
    safeHtml.value = "";
    rendered.value = null;
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

async function loadJournal(): Promise<void> {
  journalLoading.value = true;
  journalError.value = null;
  try {
    journal.value = (await getJournal(5)).data ?? [];
  } catch (err) {
    journalError.value = err instanceof Error ? err : new Error(String(err));
  } finally {
    journalLoading.value = false;
  }
}

async function saveEntry(): Promise<void> {
  const content = journalDraft.value.trim();
  if (!content || journalSaving.value) return;
  journalSaving.value = true;
  try {
    await saveJournal(content);
    journalDraft.value = "";
    toast.ok("交易日志已保存");
    await loadJournal();
  } catch (err) {
    toast.bad(`保存失败：${err instanceof Error ? err.message : String(err)}`);
  } finally {
    journalSaving.value = false;
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
  void loadBrief();
  if (syncUrl) {
    const query = { ...route.query };
    if (next === "daily") delete query.kind;
    else query.kind = next;
    void router.replace({ query });
  }
}

function reload(): void {
  void loadBrief();
  void loadJournal();
  toast.info(`已刷新${KIND_TABS.find((option) => option.value === kind.value)?.label ?? "简报"}`);
}

function notifyNoHistory(): void {
  toast.info("暂无历史期次缓存：当前仅展示每类最新一期，可用「日报 / 周报 / 月报」切换。");
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

onMounted(() => {
  kind.value = kindFromQuery(route.query.kind);
  void loadBrief();
  void loadWatchlist();
  void loadJournal();
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

/* ---------- 交易日志 ---------- */
.journal-card { margin-top: 10px; }
.journal-body {
  display: grid;
  grid-template-columns: 348px minmax(0, 1fr);
  gap: 0;
}
.journal-form {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 11px 13px;
  border-right: 1px solid var(--border);
}
.journal-input {
  width: 100%;
  min-height: 84px;
  resize: vertical;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 11.5px;
  line-height: 1.65;
}
.journal-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}
.journal-input::placeholder { color: var(--dim); }
.journal-actions { display: flex; align-items: center; gap: 8px; }
.journal-hint { font-size: 9px; color: var(--dim); }
.journal-actions .btn { margin-left: auto; }
.journal-list { min-width: 0; padding: 6px 13px 8px; }
.journal-skeleton { padding: 6px 0; }
.journal-entries { display: flex; flex-direction: column; }
.journal-entry { padding: 5px 0; border-bottom: 1px dashed var(--border); }
.journal-entry:last-child { border-bottom: 0; }
.je-head { display: flex; align-items: center; gap: 8px; }
.je-date { font-size: 9.5px; color: var(--accent); }
.je-time { font-size: 9px; color: var(--dim); }
.je-content {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.6;
  color: color-mix(in srgb, var(--text) 88%, var(--muted));
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---------- 打印：仅输出正文 ---------- */
@media print {
  :global(body) {
    background: #fff !important;
    background-attachment: initial !important;
    color: #111 !important;
  }
  .article { background: #fff !important; border-color: #ddd !important; box-shadow: none !important; }
  .article-eyebrow a { display: none !important; }
  .journal-card { display: none !important; }
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

/* ---------- 窄屏兜底 ---------- */
@media (max-width: 1180px) {
  .journal-body { grid-template-columns: 1fr; }
  .journal-form { border-right: 0; border-bottom: 1px solid var(--border); }
}
</style>
