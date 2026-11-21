<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 黄金 · 数据截至 {{ earliestFactorAsOf }}</div>
        <h1 class="page-h1">
          黄金研判
          <span class="page-sub">央行购金 · 全球 ETF · 租赁/掉期/存储 · 库存与实物 · 做市商持仓 · 价格与宏观驱动</span>
        </h1>
        <span class="gen-at">（生成于 {{ updatedLabel }}）</span>
      </div>
      <div class="page-actions">
        <span v-if="error && overview" class="badge badge--warn badge--sm">
          <svg class="ic" style="width: 11px; height: 11px"><use href="#i-alert" /></svg>刷新失败
        </span>
                <button class="btn btn--sm" type="button" :disabled="collecting" @click="triggerRefresh()">
          <svg class="ic" :class="{ spin: collecting }"><use href="#i-refresh" /></svg>
          {{ collecting ? "采集中" : "刷新数据" }}
        </button>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="loading" @click="refresh()">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>重新加载
        </button>
      </div>
    </div>

    <!-- 首次加载骨架 -->
    <template v-if="!overview && loading">
      <div class="score-grid">
        <section class="card">
          <div class="card-head"><span class="card-title">综合评分</span></div>
          <div class="card-body"><SkeletonBlock :rows="3" :cells="2" :height="28" :gap="12" /></div>
        </section>
        <section class="card">
          <div class="card-head"><span class="card-title">结论与关键驱动</span></div>
          <div class="card-body"><SkeletonBlock :rows="5" :cells="4" :height="14" :gap="10" /></div>
        </section>
      </div>
      <section class="card table-card skeleton-block">
        <div class="card-head"><span class="card-title">走势图表</span></div>
        <div class="card-body"><SkeletonBlock :rows="4" :cells="2" :height="42" :gap="10" /></div>
      </section>
      <section class="card table-card skeleton-block">
        <div class="card-head"><span class="card-title">因子明细</span></div>
        <div class="card-body"><SkeletonBlock :rows="8" :cells="8" :height="12" :gap="9" /></div>
      </section>
    </template>

    <section v-else-if="!overview" class="card">
      <ErrorState :error="error" @retry="refresh()" />
    </section>

    <template v-else>
      <!-- 评分 + 结论 -->
      <div class="score-grid">
        <GoldScoreCard
          :score-value="scoreValue"
          :score-label="scoreLabel"
          :score-badge-class="scoreBadgeClass"
          :score-trend="scoreTrend"
          :gauge-offset="gaugeOffset"
          :coverage="coverage"
          :coverage-pct="coveragePct"
          :available-weight="availableWeight"
          :total-weight="totalWeight"
          :available-factor-count="availableFactorCount"
          :factors-count="factors.length"
          :generated-label="generatedLabel"
          :methodology-brief="methodologyBrief"
        />
        <GoldDrivers
          :conclusion-text="conclusionText"
          :coverage-note="coverageNote"
          :top-drivers="topDrivers"
          :coverage="coverage"
        />
      </div>

      <GoldFactorGroups
        :groups="groups"
        :factors-count="factors.length"
        :available-factor-count="availableFactorCount"
        :pending-count="pendingCount"
        @entry="openEntry"
      />

      <GoldCharts
        :chart-cards="chartCards"
        :chart-range="chartRange"
        :series-count="seriesCount"
        :price-overlays="priceOverlays"
        @range="setChartRange"
        @toggle-overlay="togglePriceOverlay"
      />

      <GoldFactorTable :sorted-factors="sortedFactors" :available-factor-count="availableFactorCount" @entry="openEntry" />

      <GoldProviders
        :providers="providers"
        :ok-count="okCount"
        :manual="manual"
        :pending-manual-count="pendingManualCount"
        :provider-checked-label="providerCheckedLabel"
        @entry="openEntry"
      />

      <GoldMethodology
        :factors-count="factors.length"
        :total-weight="totalWeight"
        :methodology="methodology"
        :earliest-factor-as-of="earliestFactorAsOf"
        :coverage="coverage"
      />
    </template>

    <GoldEntryDialog :entry="entry" @close="closeEntry" @submit="submitEntry" />
  </div>
</template>

<script setup lang="ts">
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import GoldScoreCard from "@/components/gold/GoldScoreCard.vue";
import GoldDrivers from "@/components/gold/GoldDrivers.vue";
import GoldFactorGroups from "@/components/gold/GoldFactorGroups.vue";
import GoldCharts from "@/components/gold/GoldCharts.vue";
import GoldFactorTable from "@/components/gold/GoldFactorTable.vue";
import GoldProviders from "@/components/gold/GoldProviders.vue";
import GoldMethodology from "@/components/gold/GoldMethodology.vue";
import GoldEntryDialog from "@/components/gold/GoldEntryDialog.vue";
import { useGoldOverview } from "@/composables/useGoldOverview";

const {
  overview,
  error,
  loading,
  refresh,
  factors,
  providers,
  manual,
  scoreValue,
  scoreLabel,
  coverage,
  availableWeight,
  totalWeight,
  generatedLabel,
  methodology,
  earliestFactorAsOf,
  updatedLabel,
  scoreTrend,
  scoreBadgeClass,
  gaugeOffset,
  coveragePct,
  availableFactorCount,
  pendingCount,
  pendingManualCount,
  okCount,
  providerCheckedLabel,
  seriesCount,
  methodologyBrief,
  coverageNote,
  sortedFactors,
  topDrivers,
  groups,
  conclusionText,
  entry,
  openEntry,
  closeEntry,
  submitEntry,
  collecting,
  triggerRefresh,
  chartRange,
  priceOverlays,
  chartCards,
  togglePriceOverlay,
  setChartRange,
} = useGoldOverview();
</script>

<style scoped>
/* ---------- 顶部评分区 ---------- */
.score-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.96fr) minmax(0, 1.04fr);
  gap: 10px;
  align-items: stretch;
  margin-bottom: 10px;
}
.score-grid > .card {
  display: flex;
  flex-direction: column;
}

/* ---------- 骨架 ---------- */
.skeleton-block {
  margin-top: 10px;
}

/* ---------- 响应式 ---------- */
@media (max-width: 1360px) {
  .score-grid {
    grid-template-columns: 1fr;
  }
}
</style>
