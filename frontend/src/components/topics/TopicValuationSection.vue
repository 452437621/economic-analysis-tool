<template>
  <div class="topic-valuation">
    <div class="kpi-grid topic-valuation-cards">
      <article v-for="card in cards" :key="card.key" class="card topic-valuation-card">
        <div class="topic-valuation-label">{{ card.label }}</div>
        <div class="topic-valuation-value">{{ card.value }}</div>
        <div class="topic-valuation-note">{{ card.note }}</div>
      </article>
    </div>

    <section v-if="fairChart" class="card">
      <div class="card-head">
        <span class="card-title">实际利率模型：公允价 vs 现价</span>
        <span class="badge badge--sm">{{ fairChart.unit }}</span>
      </div>
      <div class="card-body topic-chart-body">
        <EChart :option="buildTopicChartOption(fairChart, palette, 'all')" :height="280" />
      </div>
      <div v-if="valuation.valuation_note" class="card-foot">{{ valuation.valuation_note }}</div>
    </section>
    <div v-else-if="valuation.valuation_note" class="topic-valuation-note-line">{{ valuation.valuation_note }}</div>

    <section v-if="scorecards.length" class="card table-card">
      <div class="card-head"><span class="card-title">估值打分卡</span></div>
      <div class="card-body table-wrap">
        <table class="data-table">
          <thead><tr><th>指标</th><th>数值</th><th>5 年分位</th><th>判断</th><th>说明</th></tr></thead>
          <tbody>
            <tr v-for="item in scorecards" :key="item.metric">
              <td>{{ item.metric }}</td>
              <td class="num">{{ item.value ?? "—" }}{{ item.unit || "" }}</td>
              <td class="num">{{ item.pct_5y != null ? `${item.pct_5y.toFixed(0)}%` : "—" }}</td>
              <td>{{ item.assessment }}</td>
              <td class="muted">{{ item.caveat || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="percentileRows.length" class="card table-card">
      <div class="card-head"><span class="card-title">估值分位</span></div>
      <div class="card-body table-wrap">
        <table class="data-table">
          <thead><tr><th>指标</th><th>1 年</th><th>3 年</th><th>5 年</th><th>全部</th></tr></thead>
          <tbody>
            <tr v-for="row in percentileRows" :key="row.label">
              <td>{{ row.label }}</td>
              <td class="num">{{ pct(row.values?.["1y"]) }}</td>
              <td class="num">{{ pct(row.values?.["3y"]) }}</td>
              <td class="num">{{ pct(row.values?.["5y"]) }}</td>
              <td class="num">{{ pct(row.values?.["all"]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="peers.length" class="card table-card">
      <div class="card-head">
        <span class="card-title">同业估值</span>
        <span class="card-sub">{{ peers.length }} 家</span>
      </div>
      <div class="card-body table-wrap">
        <table class="data-table">
          <thead><tr><th>公司</th><th>价格</th><th>PE</th><th>PB</th><th>市值(亿)</th><th>涨跌</th></tr></thead>
          <tbody>
            <tr v-for="item in peers" :key="item.code">
              <td>{{ item.name }}<span class="topic-code">{{ item.code }}</span></td>
              <td class="num">{{ item.price ?? "—" }}</td>
              <td class="num">{{ item.pe_ttm ?? "—" }}</td>
              <td class="num">{{ item.pb ?? "—" }}</td>
              <td class="num">{{ item.market_cap_yi ?? "—" }}</td>
              <td class="num" :class="trendClass(item.pct_chg)">{{ fmtSigned(item.pct_chg, 2) }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EChart from "@/components/charts/EChart.vue";
import type { TopicChartSpec, TopicPeer, TopicScorecard, TopicValuationData } from "@/api/types";
import { fmtSigned, trendClass } from "@/composables/useFormat";
import type { GoldPalette } from "@/utils/goldCharts";
import { buildTopicChartOption } from "@/utils/topicCharts";
import { valuationCards } from "@/utils/topicNormalize";

const props = defineProps<{ data: unknown; palette: GoldPalette }>();

const valuation = computed<TopicValuationData>(() => (props.data ?? {}) as TopicValuationData);
const cards = computed(() => valuationCards(props.data));
const scorecards = computed<TopicScorecard[]>(() => valuation.value.scorecards ?? valuation.value.scorecard ?? []);
const peers = computed<TopicPeer[]>(() => valuation.value.peers ?? []);

const fairChart = computed<TopicChartSpec | null>(() => {
  const history = valuation.value.history;
  if (!history?.dates?.length) return null;
  return {
    key: "fair_value",
    title: "公允价 vs 现价",
    unit: "美元/盎司",
    kind: "line",
    dates: history.dates,
    series: [
      { name: "现价", values: history.actual ?? [] },
      { name: "模型公允价", values: history.fair ?? [] },
    ],
    hasData: true,
  };
});

const percentileRows = computed(() => {
  const rows: Array<{ label: string; values?: Record<string, { ok?: boolean; pct?: number | null }> }> = [];
  if (valuation.value.pe_percentile) rows.push({ label: "PE(TTM)", values: valuation.value.pe_percentile });
  if (valuation.value.pb_percentile) rows.push({ label: "PB(MRQ)", values: valuation.value.pb_percentile });
  if (valuation.value.ps_percentile) rows.push({ label: "PS(TTM)", values: valuation.value.ps_percentile });
  return rows;
});

function pct(value?: { ok?: boolean; pct?: number | null }): string {
  if (!value?.ok || value.pct == null) return "—";
  return `${value.pct.toFixed(0)}%`;
}
</script>

<style scoped>
.topic-valuation {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.topic-valuation-cards {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}
.topic-valuation-card {
  padding: 10px 12px;
}
.topic-valuation-label {
  font-size: 10.5px;
  color: var(--muted);
}
.topic-valuation-value {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.topic-valuation-note {
  margin-top: 4px;
  font-size: 10px;
  color: var(--muted);
}
.topic-valuation-note-line {
  font-size: 11px;
  color: var(--muted);
}
.topic-chart-body {
  padding: 6px 8px 4px;
}
.topic-code {
  margin-left: 5px;
  font-size: 9px;
  color: var(--muted);
  font-family: var(--mono, monospace);
}
</style>
