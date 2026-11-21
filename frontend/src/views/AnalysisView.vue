<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 分析引擎 · 数据截至 {{ asofLabel }}</div>
        <h1 class="page-h1">
          分析引擎
          <span class="page-sub">市场风向 · 周期 · 相关性 · 归因 · 类比 · 异动 · 日历</span>
        </h1>
        <span class="gen-at">（生成于 {{ updatedLabel }}）</span>
      </div>
      <div class="page-actions">
        <span v-if="error && overview" class="badge badge--warn badge--sm">
          <svg class="ic" style="width: 11px; height: 11px"><use href="#i-alert" /></svg>刷新失败
        </span>
                <button class="btn btn--sm" type="button" :disabled="loading" @click="refreshAll()">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <GoldBriefCard
      :gold="gold"
      :gold-error="goldError"
      :gold-loading="goldLoading"
      :gold-score="goldScore"
      :gold-generated-label="goldGeneratedLabel"
      :gold-score-text="goldScoreText"
      :gold-tone="goldTone"
      :gold-label-class="goldLabelClass"
      :gold-label="goldLabel"
      :gold-coverage-text="goldCoverageText"
      :gold-available-weight="goldAvailableWeight"
      :gold-total-weight="goldTotalWeight"
      :gold-available-count="goldAvailableCount"
      :gold-total-count="goldTotalCount"
      :gold-top-factors="goldTopFactors"
      :gold-methodology="goldMethodology"
      @retry="refreshGold"
    />

    <EngineTransparency
      :methods="methods"
      :methods-error="methodsError"
      :methods-loading="methodsLoading"
      :method-total="methodTotal"
      :method-rows="methodRows"
      :method-kind-summary="methodKindSummary"
      :method-sha-title="methodShaTitle"
      :method-sha-summary="methodShaSummary"
      :runs="runs"
      :runs-loading="runsLoading"
      :runs-error="runsError"
      :derivations="derivations"
      :derivations-loading="derivationsLoading"
      :derivations-error="derivationsError"
      :deriv-total="derivTotal"
      :grade-rows="gradeRows"
      :quality="quality"
      :quality-loading="qualityLoading"
      :quality-error="qualityError"
      :quality-summary-text="qualitySummaryText"
      :quality-failed-text="qualityFailedText"
      :quality-passed-class="qualityPassedClass"
      :quality-date-label="qualityDateLabel"
      @retry-methods="refreshMethods"
      @retry-runs="refreshRuns"
      @retry-derivations="refreshDerivations"
      @retry-quality="refreshQuality"
    />

    <!-- 首次加载骨架 -->
    <template v-if="!overview && loading">
      <div class="analysis-top">
        <section v-for="index in 3" :key="index" class="card">
          <div class="card-head"><span class="card-title">加载中</span></div>
          <div class="card-body"><SkeletonBlock :rows="5" :cells="2" :height="12" :gap="9" /></div>
        </section>
      </div>
      <section class="card table-card analysis-block">
        <div class="card-head"><span class="card-title">定价归因</span></div>
        <div class="card-body"><SkeletonBlock :rows="6" :cells="7" :height="12" :gap="9" /></div>
      </section>
      <div class="analysis-mid">
        <section class="card table-card">
          <div class="card-head"><span class="card-title">相似交易日</span></div>
          <div class="card-body"><SkeletonBlock :rows="5" :cells="5" :height="12" :gap="9" /></div>
        </section>
        <section class="card table-card">
          <div class="card-head"><span class="card-title">异动品种</span></div>
          <div class="card-body"><SkeletonBlock :rows="6" :cells="2" :height="12" :gap="9" /></div>
        </section>
      </div>
    </template>

    <section v-else-if="!overview" class="card">
      <ErrorState :error="error" @retry="refresh()" />
    </section>

    <template v-else>
      <!-- 风向 + 周期 + 相关性 -->
      <div class="analysis-top">
        <MarketWindRegime
          :wind="wind"
          :wind-risk="windRisk"
          :wind-needle="windNeedle"
          :regime-list="regimeList"
          :correlation="correlation"
        />
      </div>

      <AttributionTable :attribution-rows="attributionRows" :attr-window="attrWindow" :attr-days="attrDays" />

      <!-- 相似交易日 + 异动品种 -->
      <div class="analysis-mid">
        <AnalogMovers :analogs="analogs" :movers="movers" @open-history="openHistory" />
      </div>

      <!-- 日历事件后收益 -->
      <section class="card table-card analysis-block">
        <div class="card-head">
          <span class="card-title">日历事件后收益</span>
          <span class="badge badge--sm">{{ calendarStudy?.window ?? "—" }}</span>
          <span class="badge badge--sm">{{ fmtInt(calendarStudy?.events) }} 个事件</span>
          <div class="card-actions">
            <span class="card-sub">{{ calendarStudy ? `${calendarStudy.groups.length} 组样本 · 按样本量降序` : "等待数据" }}</span>
          </div>
        </div>
        <div class="table-wrap table-auto">
          <table class="data-table cal-table">
            <thead>
              <tr>
                <th style="width: 108px">国家 / 地区</th>
                <th style="width: 96px">事件类别</th>
                <th class="num" style="width: 72px">样本</th>
                <th class="num">AU 1日</th>
                <th class="num">AU 3日</th>
                <th class="num">CU 1日</th>
                <th class="num">CU 3日</th>
                <th class="num">沪深300 1日</th>
                <th class="num">沪深300 3日</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in calendarRows" :key="`${row.country}-${row.category}`">
                <td>{{ row.country }}</td>
                <td class="dim">{{ row.category }}</td>
                <td class="num">{{ fmtInt(row.n) }}</td>
                <td class="num" :class="trendClass(row.au1d)">{{ fmtPct(row.au1d) }}</td>
                <td class="num" :class="trendClass(row.au3d)">{{ fmtPct(row.au3d) }}</td>
                <td class="num" :class="trendClass(row.cu1d)">{{ fmtPct(row.cu1d) }}</td>
                <td class="num" :class="trendClass(row.cu3d)">{{ fmtPct(row.cu3d) }}</td>
                <td class="num" :class="trendClass(row.hs3001d)">{{ fmtPct(row.hs3001d) }}</td>
                <td class="num" :class="trendClass(row.hs3003d)">{{ fmtPct(row.hs3003d) }}</td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-if="!calendarRows.length" text="暂无日历研究数据" hint="等待数据采集与事件研究任务产出。" />
        </div>
        <div v-if="calendarStudy" class="card-foot cal-foot">
          <svg class="ic"><use href="#i-info" /></svg>
          <span>{{ calendarStudy.note }}（仅列样本量前 {{ calendarRows.length }} 组，共 {{ calendarStudy.groups.length }} 组。）</span>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import GoldBriefCard from "@/components/analysis/GoldBriefCard.vue";
import EngineTransparency from "@/components/analysis/EngineTransparency.vue";
import MarketWindRegime from "@/components/analysis/MarketWindRegime.vue";
import AttributionTable from "@/components/analysis/AttributionTable.vue";
import AnalogMovers from "@/components/analysis/AnalogMovers.vue";
import { fmtInt, fmtPct, trendClass } from "@/composables/useFormat";
import { useAnalysisOverview } from "@/composables/useAnalysisOverview";

const {
  overview,
  error,
  loading,
  refresh,
  gold,
  goldError,
  goldLoading,
  refreshGold,
  methods,
  methodsError,
  methodsLoading,
  refreshMethods,
  runs,
  runsError,
  runsLoading,
  refreshRuns,
  derivations,
  derivationsError,
  derivationsLoading,
  refreshDerivations,
  quality,
  qualityError,
  qualityLoading,
  refreshQuality,
  methodTotal,
  methodRows,
  methodKindSummary,
  methodShaSummary,
  methodShaTitle,
  derivTotal,
  gradeRows,
  qualitySummaryText,
  qualityFailedText,
  qualityPassedClass,
  qualityDateLabel,
  goldScore,
  goldLabel,
  goldScoreText,
  goldTone,
  goldLabelClass,
  goldCoverageText,
  goldAvailableCount,
  goldTotalCount,
  goldAvailableWeight,
  goldTotalWeight,
  goldGeneratedLabel,
  goldMethodology,
  goldTopFactors,
  refreshAll,
  wind,
  windRisk,
  regimeList,
  correlation,
  analogs,
  calendarStudy,
  movers,
  updatedLabel,
  asofLabel,
  windNeedle,
  attributionRows,
  attrWindow,
  attrDays,
  calendarRows,
  openHistory,
} = useAnalysisOverview();
</script>

<style scoped>
.analysis-top {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.32fr) minmax(0, 0.98fr);
  gap: 10px;
  align-items: stretch;
}
.analysis-top > .card,
.analysis-mid > .card {
  display: flex;
  flex-direction: column;
}
.analysis-block {
  margin-top: 10px;
}
.analysis-mid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 352px;
  gap: 10px;
  margin-top: 10px;
  align-items: stretch;
}
.table-auto {
  max-height: none;
}
.cal-table td {
  font-size: 11.5px;
}
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
.cal-foot {
  line-height: 1.6;
}

@media (max-width: 1240px) {
  .analysis-top {
    grid-template-columns: 1fr 1fr;
  }
  .analysis-top .corr-card {
    grid-column: 1 / -1;
  }
  .analysis-mid {
    grid-template-columns: 1fr;
  }
}
</style>
