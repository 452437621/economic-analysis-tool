<template>
  <div class="topic-scenarios">
    <div class="kpi-grid topic-scenario-cards">
      <article v-for="card in cards" :key="card.key" class="card topic-scenario-card" :class="`scenario--${card.key}`">
        <div class="topic-scenario-head">
          <span>{{ card.label }}</span>
          <span class="badge badge--sm">{{ probText(card.scenario?.prob) }}</span>
        </div>
        <template v-if="card.scenario">
          <div class="topic-scenario-target">{{ fmtSigned(card.scenario.target_mid, 2) }} 元</div>
          <div class="topic-scenario-upside" :class="trendClass(card.scenario.upside_pct)">
            {{ fmtSigned(card.scenario.upside_pct, 1) }}%
          </div>
          <dl class="topic-scenario-meta">
            <div><dt>铜价</dt><dd>{{ fmtNumber(card.scenario.copper_price_yuan_t, 0) }}</dd></div>
            <div><dt>净利</dt><dd>{{ fmtNumber(card.scenario.np_2027e_yi, 1) }} 亿</dd></div>
            <div><dt>EPS</dt><dd>{{ fmtNumber(card.scenario.eps_2027e, 3) }}</dd></div>
            <div><dt>区间</dt><dd>{{ rangeText(card.scenario.target_range) }}</dd></div>
          </dl>
        </template>
        <EmptyState v-else text="情景数据不足" />
      </article>
    </div>

    <section v-if="payload.ok" class="card">
      <div class="card-head">
        <span class="card-title">概率加权与四法权重</span>
        <span v-if="payload.eps_source" class="card-sub">盈利口径：{{ payload.eps_source }}</span>
      </div>
      <div class="card-body topic-weighted">
        <div class="topic-weighted-main">
          <div><span>期望价格</span><b>{{ fmtNumber(weighted.expected_price, 2) }} 元</b></div>
          <div><span>期望收益</span><b :class="trendClass(weighted.expected_return_pct)">{{ fmtSigned(weighted.expected_return_pct, 1) }}%</b></div>
          <div><span>赔率</span><b>{{ fmtNumber(weighted.reward_risk_ratio, 2) }}</b></div>
          <div><span>沪铜 5 年分位</span><b>{{ payload.cu_pct_5y != null ? `${payload.cu_pct_5y.toFixed(0)}%` : "—" }}</b></div>
        </div>
        <div class="topic-methods">
          <span v-for="method in methods" :key="method.name" class="topic-method-chip">
            {{ method.name }} <b>{{ method.weight != null ? `${(method.weight * 100).toFixed(0)}%` : "—" }}</b>
          </span>
        </div>
      </div>
      <div class="card-foot">
        情景为公开数据推演；铜价敏感性
        {{ payload.copper_sensitivity?.sens_yi_per_1000 ?? "—" }} 亿净利 / 每千元铜价。
      </div>
    </section>

    <section v-if="copperGrid.length" class="card table-card">
      <div class="card-head"><span class="card-title">铜价敏感性</span></div>
      <div class="card-body table-wrap">
        <table class="data-table">
          <thead><tr><th>沪铜(元/吨)</th><th>归母净利(亿)</th><th>EPS</th><th>PE 9.5x</th><th>PE 11.5x</th></tr></thead>
          <tbody>
            <tr v-for="row in copperGrid" :key="String(row.copper)">
              <td class="num">{{ row.copper }}</td>
              <td class="num">{{ row.np_yi ?? "—" }}</td>
              <td class="num">{{ row.eps ?? "—" }}</td>
              <td class="num">{{ row.pe_9_5x ?? "—" }}</td>
              <td class="num">{{ row.pe_11_5x ?? "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <EmptyState v-if="!payload.ok" :text="payload.reason || '情景数据不足'" hint="需要沪铜序列与估值/财务数据。" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicScenariosData } from "@/api/types";
import { fmtNumber, fmtSigned, trendClass } from "@/composables/useFormat";
import { scenarioCards } from "@/utils/topicNormalize";

const props = defineProps<{ data: unknown }>();

const payload = computed<TopicScenariosData>(() => (props.data ?? {}) as TopicScenariosData);
const cards = computed(() => scenarioCards(props.data));
const weighted = computed(() => payload.value.weighted ?? {});
const methods = computed(() => payload.value.methods ?? []);
const copperGrid = computed(() => payload.value.copper_grid ?? []);

function probText(prob?: number): string {
  return prob != null ? `概率 ${(prob * 100).toFixed(0)}%` : "概率 —";
}

function rangeText(range?: Array<number | null>): string {
  if (!range?.length) return "—";
  return range.map((item) => (item == null ? "—" : item.toFixed(2))).join(" ~ ");
}
</script>

<style scoped>
.topic-scenarios {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.topic-scenario-cards {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.topic-scenario-card {
  padding: 10px 12px;
  border-top: 2px solid var(--border);
}
.topic-scenario-card.scenario--bear {
  border-top-color: var(--down-color);
}
.topic-scenario-card.scenario--base {
  border-top-color: var(--accent);
}
.topic-scenario-card.scenario--bull {
  border-top-color: var(--up-color);
}
.topic-scenario-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--muted);
}
.topic-scenario-target {
  margin-top: 6px;
  font-size: 20px;
  font-weight: 680;
  font-variant-numeric: tabular-nums;
}
.topic-scenario-upside {
  font-size: 11px;
  font-weight: 600;
}
.topic-scenario-upside.up {
  color: var(--up-color);
}
.topic-scenario-upside.down {
  color: var(--down-color);
}
.topic-scenario-meta {
  margin: 8px 0 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 8px;
  font-size: 10px;
}
.topic-scenario-meta div {
  display: flex;
  justify-content: space-between;
  gap: 6px;
}
.topic-scenario-meta dt {
  color: var(--muted);
}
.topic-scenario-meta dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}
.topic-weighted-main {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px;
  font-size: 10.5px;
}
.topic-weighted-main div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--muted);
}
.topic-weighted-main b {
  color: var(--text);
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}
.topic-methods {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.topic-method-chip {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 10px;
  color: var(--muted);
}
@media (max-width: 900px) {
  .topic-scenario-cards {
    grid-template-columns: 1fr;
  }
}
</style>
