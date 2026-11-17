<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 原则库 · 26 条经过时间检验的判断规则</div>
        <h1 class="page-h1">
          原则库
          <span class="page-sub">每条原则都写清「依据什么、看什么指标、何时失效」—— 不是格言，而是可核对的规则</span>
        </h1>
      </div>
      <div class="page-actions">
        <span v-if="payload?.asof" class="badge badge--sm">核对日 {{ fmtDate(payload.asof) }}</span>
        <span class="badge badge--sm"><span class="dot"></span>更新于 {{ updatedLabel }}</span>
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
        <div class="prg-group">
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
        <div class="prg-group">
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

      <EmptyState v-if="!visible.length" text="没有符合筛选条件的原则" hint="换一个类别或清空搜索" />

      <div v-else class="prg-grid">
        <article v-for="item in visible" :key="item.id" class="prg-card" :class="`prg-card--${item.status}`">
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
            </template>
            <span v-else class="dim">定性原则 · 留待复盘时人工核对</span>
            <span class="prg-note">{{ item.note }}</span>
          </footer>
        </article>
      </div>

      <div class="card-foot">
        <span class="mono">run {{ payload.run_id.slice(0, 8) }} · {{ payload.counts.total }} 条</span>
        <span>阈值维护在 backend/app/ledger/principles.py；七条定性原则保持「缺数据」，不强行量化</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtNumber } from "@/composables/useFormat";
import { getLedgerPrinciples } from "@/api/endpoints";
import type { LedgerStatus } from "@/api/types";

const { data: payload, error, loading, lastUpdated, refresh } = usePolling(getLedgerPrinciples, {
  interval: 60_000,
});

const category = ref<"all" | "A" | "B" | "C" | "D">("all");
const status = ref<"all" | LedgerStatus>("all");
const query = ref("");

const updatedLabel = computed(() => (lastUpdated.value ? fmtDateTime(lastUpdated.value.toISOString()) : "—"));

const items = computed(() => payload.value?.items ?? []);

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

function statusText(value: LedgerStatus): string {
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

.prg-search:focus,
.prg-chip:focus-visible {
  outline: 1px solid var(--accent);
  outline-offset: 1px;
}

@media (max-width: 900px) {
  .prg-counts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .prg-search {
    margin-left: 0;
    width: 100%;
  }
}
</style>
