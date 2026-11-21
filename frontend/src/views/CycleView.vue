<template>
  <div class="view active cyc-root">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 周期定位 · EPIC-C 2.0</div>
        <h1 class="page-h1">
          周期罗盘
          <span class="page-sub">五层周期 · 长债务 / 短债务 / 库存 / 流动性 / 政治窗口 —— 先定位，再判断</span>
        </h1>
      </div>
      <div class="page-actions">
        <RouterLink class="btn btn--sm btn--ghost" to="/analysis#cycle-regime">市场隐含象限</RouterLink>
        <RouterLink class="btn btn--sm btn--ghost" to="/history">世界长河</RouterLink>
        <RouterLink class="btn btn--sm btn--ghost" to="/alerts">周期规则预警</RouterLink>
        <span v-if="payload?.asof" class="badge badge--sm">数据日 {{ fmtDate(payload.asof) }}</span>
        <span v-if="payload?.status" class="badge badge--sm" :class="runTone(payload.status)">
          {{ runText(payload.status) }}
        </span>
        <button class="btn btn--sm" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中…" : "立即重算" }}
        </button>
      </div>
    </div>

    <p v-if="payload?.generated_at" class="cyc-generated">生成于 {{ generatedLabel }}</p>

    <p v-if="recalcError" class="cyc-inline-error">
      <svg class="ic"><use href="#i-alert" /></svg>
      <span>重算失败：{{ recalcError }}</span>
      <button class="btn btn--ghost btn--sm" type="button" :disabled="running" @click="recalc">重试</button>
    </p>

    <p v-if="error && payload" class="cyc-inline-error">
      <svg class="ic"><use href="#i-alert" /></svg>
      <span>自动刷新失败：{{ error.message }}；当前展示上一次成功的数据。</span>
      <button class="btn btn--ghost btn--sm" type="button" @click="refresh()">重试</button>
    </p>

    <SkeletonBlock v-if="!payload && loading" :rows="6" :cells="3" :height="16" />
    <ErrorState v-else-if="!payload && error" :error="error" @retry="refresh" />
    <EmptyState v-else-if="!payload" text="暂无周期状态" hint="请先运行一次周期引擎，再查看周期罗盘。" />

    <template v-else-if="value">
      <CycleHero
        :hero-title="heroTitle"
        :hero-sub="heroSub"
        :hero-tags="heroTags"
        :coverage-text="coverageText"
        :rule-version="ruleVersion"
        :next-calibration="nextCalibration"
      />

      <div class="cyc-row2">
        <CycleCompass
          :growth="compassGrowth"
          :inflation="compassInflation"
          :state="short.state"
          :confidence="longConfidencePct"
        />
        <CycleForces :forces="forces" :stress-count="stressCount" />
      </div>

      <div class="cyc-section-label">
        <span class="cyc-sl-title">关键读数</span>
        <span>
          均为北京时间 {{ readingsAsof || asofLabel }} · z = 相对 5 年 z-score ·
          {{ readingItems.length ? `${readingItems.length - missingReadings} / ${readingItems.length} 项可用` : "读数待加载" }}
        </span>
      </div>
      <CycleReadings
        :readings-unavailable="readingsUnavailable"
        :readings-error-text="readingsErrorText"
        :loading="readingsLoading"
        :kpis="kpis"
        @retry="retryReadings"
      />

      <CycleAlerts :alert-count="alertCount" :generated-label="generatedLabel" :top-alerts="topAlerts" />

      <div class="cyc-section-label">
        <span class="cyc-sl-title">历史类比 Top3</span>
        <span>
          {{
            analogs
              ? `${analogs.n ?? 0} 个样本内近邻 · 剔除最近 ${analogs.min_gap_months ?? 12} 个月`
              : "样本内近邻"
          }}
        </span>
      </div>
      <CycleAnalogCards :analogs="analogs" :analog-slots="analogSlots" />

      <div class="cyc-section-label cyc-section-label--retain">
        <span class="cyc-sl-title">周期定位概览</span>
        <span>原有定位指标 · 与上方设计区块并存的完整口径</span>
      </div>
      <CycleOverviewCards
        :long="long"
        :short="short"
        :sustainability="sustainability"
        :analogs="analogs"
        :top-analogs="topAnalogs"
        :long-tone-class="longToneClass"
        :short-tone-class="shortToneClass"
      />

      <CycleRetainPanels
        :long="long"
        :short="short"
        :liq="liq"
        :inventory="inventory"
        :political="political"
        :indicators-count="indicators.length"
        :rings="rings"
        :axes="axes"
        :polygon="polygon"
        :long-tone-class="longToneClass"
        :short-tone-class="shortToneClass"
        :liquidity-tone-class="liquidityToneClass"
      />

      <CycleStructuralTable
        :structural-rows="structuralRows"
        :degraded-count="structuralDegradedCount"
        :oldest-stale-title="oldestStaleTitle"
        :oldest-stale-text="oldestStaleText"
        :loading="indicatorLoading"
        :error="indicatorError"
        @retry="refreshIndicators"
      />

      <CycleHistoryChart :history="history" :history-months="historyMonths" :history-range="historyRange" />

      <div class="cyc-bottom">
        <CycleScenarioPanel :scenarios="scenarios" :scenario-list="scenarioList" />
        <CycleSustainabilityPanel :sustainability="sustainability" :thresholds="sustainabilityThresholds" />
      </div>

      <div class="cyc-bottom">
        <CycleWorldPanel
          :world="world"
          :stages="stages"
          :power-index="powerIndex"
          :power-components="powerComponents"
          :reserve-currency="reserveCurrency"
        />
        <CycleAnalogTable :analog-list="analogList" :analogs="analogs" />
      </div>

      <div v-if="degradedReasons.length" class="cyc-degraded-box">
        <svg class="ic"><use href="#i-alert" /></svg>
        <div>
          <b>本次运行有 {{ degradedReasons.length }} 项降级</b>
          <div v-for="(reason, index) in degradedReasons.slice(0, 6)" :key="reason.code ?? index" class="cyc-degraded-reason">
            {{ reason.message ?? "未提供降级说明" }}（{{ reason.code ?? "unknown" }}）
          </div>
        </div>
      </div>

      <div class="cyc-foot">
        <span class="mono">run {{ payload?.run_id ?? "—" }}</span>
        <span class="mono">method {{ payload?.state?.method_id ?? "—" }}</span>
        <span class="mono"> asof {{ asofLabel }} · 生成于 {{ generatedLabel }} </span>
        <span class="mono">
          confidence {{ longConfidencePct === null ? "—" : `${longConfidencePct}%` }} ·
          {{ payload?.state?.evidence_grade ?? "—" }}
        </span>
      </div>
    </template>
    <EmptyState
      v-else
      text="周期状态字段缺失"
      hint="接口已返回运行记录，但缺少 state.value（旧版运行结果可能不完整）；请点击上方「立即重算」重新生成。"
    />
  </div>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import CycleCompass from "@/components/cycle/CycleCompass.vue";
import CycleForces from "@/components/cycle/CycleForces.vue";
import CycleHero from "@/components/cycle/CycleHero.vue";
import CycleReadings from "@/components/cycle/CycleReadings.vue";
import CycleAlerts from "@/components/cycle/CycleAlerts.vue";
import CycleAnalogCards from "@/components/cycle/CycleAnalogCards.vue";
import CycleOverviewCards from "@/components/cycle/CycleOverviewCards.vue";
import CycleRetainPanels from "@/components/cycle/CycleRetainPanels.vue";
import CycleStructuralTable from "@/components/cycle/CycleStructuralTable.vue";
import CycleHistoryChart from "@/components/cycle/CycleHistoryChart.vue";
import CycleScenarioPanel from "@/components/cycle/CycleScenarioPanel.vue";
import CycleSustainabilityPanel from "@/components/cycle/CycleSustainabilityPanel.vue";
import CycleWorldPanel from "@/components/cycle/CycleWorldPanel.vue";
import CycleAnalogTable from "@/components/cycle/CycleAnalogTable.vue";
import { fmtDate } from "@/composables/useFormat";
import { runText, runTone } from "@/utils/cycleFormat";
import { useCycleData } from "@/composables/useCycleData";

const {
  error,
  loading,
  refresh,
  payload,
  value,
  indicators,
  long,
  short,
  liq,
  inventory,
  political,
  sustainability,
  sustainabilityThresholds,
  scenarios,
  scenarioList,
  analogs,
  analogList,
  world,
  powerIndex,
  powerComponents,
  reserveCurrency,
  stages,
  history,
  historyMonths,
  historyRange,
  degradedReasons,
  generatedLabel,
  asofLabel,
  ruleVersion,
  nextCalibration,
  coverageText,
  heroTitle,
  heroSub,
  heroTags,
  compassGrowth,
  compassInflation,
  longConfidencePct,
  readingItems,
  missingReadings,
  readingsUnavailable,
  readingsErrorText,
  readingsAsof,
  readingsLoading,
  retryReadings,
  kpis,
  alertCount,
  topAlerts,
  topAnalogs,
  analogSlots,
  forces,
  stressCount,
  rings,
  axes,
  polygon,
  longToneClass,
  shortToneClass,
  liquidityToneClass,
  structuralRows,
  structuralDegradedCount,
  oldestStaleText,
  oldestStaleTitle,
  indicatorLoading,
  indicatorError,
  refreshIndicators,
  running,
  recalcError,
  recalc,
} = useCycleData();
</script>

<style scoped>
/* ── 页面骨架 ───────────────────────────────────────── */
.cyc-root {
  min-width: 0;
}
/* 数据自身生成时点：小字跟随标题，不展示系统当前时间 */
.cyc-generated {
  margin: -6px 2px 10px;
  font-size: 9.5px;
  color: var(--dim);
  font-family: var(--mono);
  letter-spacing: 0.2px;
}
/* 重算失败行内提示（不阻塞页面其余内容） */
.cyc-inline-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 2px 10px;
  padding: 6px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 8%, transparent);
  font-size: 10.5px;
  color: var(--warn);
}
.cyc-inline-error .ic {
  width: 13px;
  height: 13px;
  flex: none;
}
.cyc-inline-error span {
  flex: 1;
  min-width: 0;
}
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}

/* ── B. row-2 ───────────────────────────────────────── */
.cyc-row2 {
  display: grid;
  grid-template-columns: minmax(0, 560px) minmax(0, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}

/* ── C. 关键读数 ────────────────────────────────────── */
.cyc-section-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 10px 2px 6px;
  font-size: 10px;
  color: var(--dim);
}
.cyc-section-label--retain {
  margin-top: 16px;
}
.cyc-sl-title {
  font-size: 10.5px;
  color: var(--muted);
  font-weight: 600;
  letter-spacing: 0.3px;
}

.cyc-bottom {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
}
.cyc-degraded-box {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  margin-top: 10px;
  padding: 9px 12px;
  border: 1px solid color-mix(in srgb, var(--warn) 38%, transparent);
  border-radius: var(--radius-card);
  background: color-mix(in srgb, var(--warn) 8%, var(--surface));
  font-size: 10px;
  color: var(--muted);
}
.cyc-degraded-box .ic {
  color: var(--warn);
  flex: none;
}
.cyc-degraded-box b {
  color: var(--text);
  font-size: 10.5px;
}
.cyc-degraded-reason {
  margin-top: 3px;
  font-size: 9.5px;
  color: var(--dim);
}
.cyc-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 12px;
  padding: 8px 2px 4px;
  border-top: 1px dashed var(--border);
  font-size: 8.5px;
  color: var(--dim);
}
.spin {
  animation: cyc-spin 1s linear infinite;
}
@keyframes cyc-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── 响应式 ─────────────────────────────────────────── */
@media (max-width: 1279px) {
  .cyc-row2 {
    grid-template-columns: minmax(0, 1fr);
  }
  .cyc-bottom {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
