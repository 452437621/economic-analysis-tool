<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 原则库 · 26 条经过时间检验的判断规则</div>
        <h1 class="page-h1">
          原则库
          <span class="page-sub">每条原则都写清「依据什么、看什么指标、何时失效」—— 不是格言，而是可核对的规则</span>
        </h1>
        <span class="gen-at">（生成于 {{ generatedLabel }}）</span>
      </div>
      <div class="page-actions">
        <span v-if="payload?.asof" class="badge badge--sm" title="本轮原则核对使用的数据日">核对日 {{ fmtDate(payload.asof) }}</span>
        <RouterLink class="btn btn--sm" to="/ledger">去预测台账 →</RouterLink>
      </div>
    </div>

    <SkeletonBlock v-if="!payload && loading" :rows="8" :cells="3" :height="16" />
    <ErrorState v-else-if="!payload && error" :error="error" @retry="refresh" />

    <template v-else-if="payload">
      <div class="prg-counts">
        <div v-for="row in statusRows" :key="row.id" class="prg-count" :class="`prg-count--${row.id}`">
          <span class="prg-count-num">{{ row.count }}</span>
          <span class="prg-count-label">{{ row.label }}</span>
        </div>
      </div>

      <div class="prg-filters">
        <div class="prg-group" role="group" aria-label="按类别筛选">
          <button
            v-for="tab in categoryTabs"
            :key="tab.id"
            class="prg-chip"
            :class="{ on: category === tab.id }"
            type="button"
            @click="category = tab.id"
          >
            {{ tab.label }} <span>{{ tab.count }}</span>
          </button>
        </div>
        <div class="prg-group" role="group" aria-label="按状态筛选">
          <button
            v-for="tab in statusTabs"
            :key="tab.id"
            class="prg-chip"
            :class="{ on: status === tab.id }"
            type="button"
            @click="status = tab.id"
          >
            {{ tab.label }} <span>{{ tab.count }}</span>
          </button>
        </div>
        <input v-model="query" class="prg-search" type="search" placeholder="搜索原则名 / 表述 / 指标" />
      </div>

      <EmptyState v-if="!visible.length" text="没有符合筛选条件的原则" hint="换一个类别或清空搜索；原则总数 26 条" />

      <template v-else>
        <section v-for="group in groups" :key="group.id" class="prg-section">
          <header class="prg-section-head">
            <h2 class="prg-section-title">{{ group.label }}</h2>
            <span class="prg-section-sub">{{ group.items.length }} 条 · {{ group.summary }}</span>
          </header>
          <div class="prg-grid">
            <article
              v-for="item in group.items"
              :key="item.id"
              class="prg-card"
              :class="`prg-card--${item.status}`"
              tabindex="0"
              role="button"
              :aria-label="`查看 ${item.id} ${item.name} 的核对方式`"
              @click="openDetail(item.id)"
              @keydown.enter.prevent="openDetail(item.id)"
              @keydown.space.prevent="openDetail(item.id)"
            >
              <header class="prg-head">
                <span class="prg-id mono">{{ item.id }}</span>
                <span class="prg-category">{{ item.category_label }}</span>
                <span class="badge badge--sm" :class="statusTone(item.status)">{{ statusText(item.status) }}</span>
              </header>
              <h3 class="prg-name">{{ item.name }}</h3>
              <p class="prg-statement">{{ item.statement }}</p>

              <dl class="prg-meta">
                <div>
                  <dt>依据</dt>
                  <dd>
                    <span class="badge badge--sm" :class="evidenceTone(item.evidence)">{{ item.evidence_label }}</span>
                    <span class="mono dim">证据级 {{ item.grade }}</span>
                  </dd>
                </div>
                <div>
                  <dt>可观测</dt>
                  <dd>{{ item.observable }}</dd>
                </div>
                <div>
                  <dt>信号</dt>
                  <dd>{{ item.signal }}</dd>
                </div>
                <div>
                  <dt>失效条件</dt>
                  <dd class="prg-falsifier">{{ item.falsifier }}</dd>
                </div>
              </dl>

              <footer class="prg-check">
                <template v-if="item.metric">
                  <span class="mono">{{ item.metric }}</span>
                  <span class="mono dim">{{ item.op }} {{ item.threshold }}</span>
                  <span v-if="item.value != null" class="mono">当前 {{ fmtNumber(item.value, 2) }}</span>
                  <span v-else class="dim">当前值 —（指标本轮缺失）</span>
                </template>
                <span v-else class="dim">定性原则 · 留待复盘时人工核对</span>
                <span class="prg-note">{{ item.note }}</span>
                <span class="prg-more">查看如何核对 →</span>
              </footer>
            </article>
          </div>
        </section>
      </template>

      <div class="card-foot">
        <span class="mono">run {{ payload.run_id.slice(0, 8) }} · {{ payload.counts.total }} 条</span>
        <span>阈值维护在 backend/app/ledger/principles.py；定性原则保持「缺数据」，不强行量化</span>
      </div>
    </template>

    <Drawer
      :open="detailItem !== null"
      :title="detailItem ? `${detailItem.id} · ${detailItem.name}` : '原则详情'"
      :sub="detailItem ? `${detailItem.category_label} · ${statusText(detailItem.status)} · 证据级 ${detailItem.grade}` : ''"
      @close="detailId = null"
    >
      <template v-if="detailItem">
        <p class="prg-detail-statement">{{ detailItem.statement }}</p>

        <div class="prg-detail-kv">
          <div>
            <span>依据</span>
            <b>
              <span class="badge badge--sm" :class="evidenceTone(detailItem.evidence)">{{ detailItem.evidence_label }}</span>
              证据级 {{ detailItem.grade }}
            </b>
          </div>
          <div>
            <span>本轮判定</span>
            <b><span class="badge badge--sm" :class="statusTone(detailItem.status)">{{ statusText(detailItem.status) }}</span></b>
          </div>
          <div>
            <span>核对时间</span>
            <b class="mono">{{ detailItem.checked_at ? fmtDateTime(detailItem.checked_at) : "—" }}</b>
          </div>
        </div>

        <section class="prg-detail-block">
          <h4>如何核对</h4>
          <ol class="prg-steps">
            <li>
              <b>取可观测指标</b>
              <span>{{ detailItem.observable }}</span>
            </li>
            <li>
              <b>读信号</b>
              <span>{{ detailItem.signal }}</span>
            </li>
            <li v-if="detailItem.metric">
              <b>与阈值比较</b>
              <span>
                指标 <code>{{ detailItem.metric }}</code> {{ detailItem.op }} {{ detailItem.threshold }}；
                接近区间 ±{{ detailItem.near }} 记为「接近」；
                本轮当前值
                <span class="mono">{{ detailItem.value == null ? "—（缺失，判定为缺数据）" : fmtNumber(detailItem.value, 2) }}</span>，
                判定「{{ statusText(detailItem.status) }}」。
              </span>
            </li>
            <li v-else>
              <b>人工核对</b>
              <span>该原则没有量化阈值，需要在复盘时对照原文与当下事实逐条判断，系统不代填结论。</span>
            </li>
            <li>
              <b>检查失效条件</b>
              <span class="prg-detail-falsifier">{{ detailItem.falsifier }}</span>
            </li>
          </ol>
        </section>

        <section class="prg-detail-block">
          <h4>系统给出的说明</h4>
          <p>{{ detailItem.note || "本轮没有额外说明。缺数据表示所需指标在数据源中暂不可得，不等于原则未成立。" }}</p>
        </section>

        <section class="prg-detail-block">
          <h4>依据来源</h4>
          <p>
            <span class="badge badge--sm" :class="evidenceTone(detailItem.evidence)">{{ detailItem.evidence_label }}</span>
            {{ evidenceHint(detailItem.evidence) }}（证据级 {{ detailItem.grade }}：A 原文/一手，B 访谈/研究稿，C 推断待核）
          </p>
        </section>

        <p class="prg-detail-foot">
          原则清单与阈值维护在 backend/app/ledger/principles.py；改动后到预测台账点「立即核对」重新判定。
        </p>
      </template>
    </Drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import Drawer from "@/components/ui/Drawer.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtNumber } from "@/composables/useFormat";
import { getLedgerOverview, getLedgerPrinciples } from "@/api/endpoints";
import type { LedgerPrincipleItem, LedgerOverview, LedgerStatus } from "@/api/types";

const { data: payload, error, loading, refresh } = usePolling(getLedgerPrinciples, {
  interval: 60_000,
});

/** 原则接口只返回 asof / run_id；生成时间取自台账总览接口，缺失时显示「—」而不猜测。 */
const { data: overview } = usePolling<LedgerOverview>(getLedgerOverview, { interval: 120_000 });

const category = ref<"all" | "A" | "B" | "C" | "D">("all");
const status = ref<"all" | LedgerStatus>("all");
const query = ref("");
const detailId = ref<string | null>(null);

const generatedLabel = computed(() => {
  const iso = overview.value?.generated_at;
  return iso ? fmtDateTime(iso) : "—";
});

const items = computed(() => payload.value?.items ?? []);

const detailItem = computed<LedgerPrincipleItem | null>(
  () => items.value.find((item) => item.id === detailId.value) ?? null,
);

const statusRows = computed(() => {
  const counts = payload.value?.counts;
  return [
    { id: "hit", label: "成立", count: counts?.hit ?? 0 },
    { id: "near", label: "接近", count: counts?.near ?? 0 },
    { id: "miss", label: "不成立", count: counts?.miss ?? 0 },
    { id: "unknown", label: "缺数据", count: counts?.unknown ?? 0 },
  ];
});

const categoryTabs = computed(() => {
  const base = [{ id: "all" as const, label: "全部", count: items.value.length }];
  const labels: Record<string, string> = payload.value?.categories ?? {};
  return [
    ...base,
    ...Object.entries(labels).map(([id, label]) => ({
      id: id as "A" | "B" | "C" | "D",
      label,
      count: items.value.filter((row) => row.category === id).length,
    })),
  ];
});

const statusTabs = computed(() => [
  { id: "all" as const, label: "全部状态", count: items.value.length },
  ...statusRows.value.map((row) => ({ id: row.id as LedgerStatus, label: row.label, count: row.count })),
]);

const visible = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  return items.value.filter((item) => {
    if (category.value !== "all" && item.category !== category.value) return false;
    if (status.value !== "all" && item.status !== status.value) return false;
    if (!keyword) return true;
    return [item.id, item.name, item.statement, item.observable, item.metric ?? ""]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });
});

/** 按 A/B/C/D 类别分组（沿用接口 categories 顺序）；只有筛选到单一类别时该组即全部结果。 */
const groups = computed(() => {
  const labels: Record<string, string> = payload.value?.categories ?? {};
  const order = Object.keys(labels);
  const buckets = new Map<string, LedgerPrincipleItem[]>();
  for (const item of visible.value) {
    const list = buckets.get(item.category) ?? [];
    list.push(item);
    buckets.set(item.category, list);
  }
  const ids = order.length ? order.filter((id) => buckets.has(id)) : [...buckets.keys()];
  return ids.map((id) => {
    const list = buckets.get(id) ?? [];
    const tally = [
      ["hit", "成立"],
      ["near", "接近"],
      ["miss", "不成立"],
      ["unknown", "缺数据"],
    ] as const;
    const summary = tally
      .map(([key, label]) => `${label} ${list.filter((row) => row.status === key).length}`)
      .join(" · ");
    return { id, label: labels[id] ?? id, items: list, summary };
  });
});

function statusText(value: LedgerStatus | undefined): string {
  if (!value) return "—";
  return { hit: "成立", near: "接近", miss: "不成立", unknown: "缺数据" }[value];
}

function statusTone(value: LedgerStatus): string {
  return { hit: "badge--down", near: "badge--warn", miss: "badge--up", unknown: "" }[value];
}

function evidenceTone(evidence: string): string {
  if (evidence === "原文") return "badge--accent";
  if (evidence === "推断") return "badge--warn";
  return "";
}

function evidenceHint(evidence: string): string {
  if (evidence === "原文") return "来自书/访谈原文，可直接引用";
  if (evidence === "访谈") return "来自访谈记录，口径以原文为准";
  if (evidence === "推断") return "由多重事实归纳，需持续检验";
  if (evidence === "争议") return "存在相反证据，正反两侧都需记录";
  return "未核实或未标注";
}

function openDetail(id: string): void {
  detailId.value = id;
}
</script>

<style scoped>
.prg-counts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.prg-count {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
}

.prg-count-num {
  display: block;
  font-family: var(--mono);
  font-size: 22px;
  color: var(--text);
}

.prg-count-label {
  font-size: 10.5px;
  color: var(--dim);
}

.prg-count--hit .prg-count-num {
  color: var(--up);
}

.prg-count--near .prg-count-num {
  color: var(--warn);
}

.prg-count--miss .prg-count-num {
  color: var(--down);
}

.prg-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 14px 0;
}

.prg-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.prg-chip {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  cursor: pointer;
  font-size: 10.5px;
  padding: 5px 11px;
}

.prg-chip span {
  color: var(--dim);
  margin-left: 4px;
}

.prg-chip.on {
  border-color: var(--accent);
  color: var(--accent);
}

.prg-search {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 11.5px;
  margin-left: auto;
  min-width: 240px;
  padding: 7px 10px;
}

.prg-section {
  margin-bottom: 18px;
}

.prg-section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

.prg-section-title {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--text);
  margin: 0;
}

.prg-section-sub {
  font-size: 10px;
  color: var(--dim);
  font-family: var(--mono);
}

.prg-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 14px;
}

.prg-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border-strong);
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.prg-card:hover {
  border-color: var(--border-strong);
  background: color-mix(in srgb, var(--accent) 3%, var(--surface));
}

.prg-card:focus-visible {
  outline: 1px solid var(--accent);
  outline-offset: 1px;
}

.prg-card--hit {
  border-left-color: var(--up);
}

.prg-card--near {
  border-left-color: var(--warn);
}

.prg-card--miss {
  border-left-color: var(--down);
}

.prg-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prg-id {
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
}

.prg-category {
  color: var(--dim);
  font-size: 10.5px;
  margin-right: auto;
}

.prg-name {
  font-size: 14px;
  margin: 8px 0 6px;
}

.prg-statement {
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.7;
  margin: 0 0 10px;
}

.prg-meta {
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding-top: 10px;
}

.prg-meta > div {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 8px;
}

.prg-meta dt {
  color: var(--dim);
  font-size: 10px;
  padding-top: 2px;
}

.prg-meta dd {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
  margin: 0;
}

.prg-meta dd .badge {
  margin-right: 6px;
}

.prg-falsifier {
  color: var(--warn);
}

.prg-check {
  border-top: 1px dashed var(--border);
  color: var(--muted);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 10.5px;
  margin-top: 10px;
  padding-top: 9px;
}

.prg-note {
  color: var(--dim);
  flex-basis: 100%;
}

.prg-more {
  color: var(--accent);
  font-size: 10px;
  margin-left: auto;
}

.prg-search:focus,
.prg-chip:focus-visible {
  outline: 1px solid var(--accent);
  outline-offset: 1px;
}

/* 详情抽屉 */
.prg-detail-statement {
  margin: 0 0 12px;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--text);
}

.prg-detail-kv {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.prg-detail-kv > div {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.prg-detail-kv span {
  font-size: 9.5px;
  color: var(--dim);
}

.prg-detail-kv b {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text);
}

.prg-detail-block {
  margin-bottom: 14px;
}

.prg-detail-block h4 {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 650;
  color: var(--muted);
  letter-spacing: 0.3px;
}

.prg-detail-block p {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--muted);
}

.prg-steps {
  list-style: none;
  counter-reset: prg-step;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prg-steps li {
  counter-increment: prg-step;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  gap: 8px;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--muted);
}

.prg-steps li::before {
  content: counter(prg-step);
  align-self: start;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--surface-3);
  color: var(--dim);
  font-family: var(--mono);
  font-size: 9.5px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.prg-steps li b {
  display: block;
  color: var(--text);
  font-weight: 600;
  font-size: 11px;
}

.prg-steps code {
  font-family: var(--mono);
  font-size: 10.5px;
  background: var(--surface-3);
  border-radius: 4px;
  padding: 1px 4px;
}

.prg-detail-falsifier {
  color: var(--warn);
}

.prg-detail-foot {
  margin: 0;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  font-size: 10px;
  line-height: 1.6;
  color: var(--dim);
}

@media (max-width: 900px) {
  .prg-counts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .prg-search {
    margin-left: 0;
    width: 100%;
  }

  .prg-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
