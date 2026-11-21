<template>
  <div class="view active lens-view">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">
          专题 · 多透镜
          <template v-if="state?.asof"> · 数据截至 {{ fmtDate(state.asof) }}</template>
          <template v-if="state?.config_version"> · 配置 v{{ state.config_version }}</template>
        </div>
        <h1 class="page-h1">
          多透镜研判
          <span class="page-sub">
            美联储一脉 · 宋鸿兵 · 宏观 / 微观两层 · 九位思想者 —— 13 套框架加权共振
          </span>
        </h1>
        <span v-if="state?.run" class="gen-at">
          运行 {{ state.run.status }} · 耗时 {{ state.run.duration_ms ?? "—" }} ms ·
          置信度 {{ fmtRatioPct(state.confidence) }} · 证据 {{ state.evidence_grade }}
        </span>
      </div>
      <div class="page-actions">
        <span v-if="state?.run?.degraded" class="badge badge--warn badge--sm">降级运行</span>
        <button class="btn btn--sm btn--primary" type="button" :disabled="running" @click="runNow()">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中" : "重算多透镜" }}
        </button>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="loading" @click="reload()">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <div v-if="state?.disclaimer" class="lens-disclaimer">
      <svg class="ic"><use href="#i-shield-check" /></svg>
      <span>{{ state.disclaimer }}</span>
    </div>

    <template v-if="!state && loading">
      <div class="lens-stats">
        <section v-for="i in 4" :key="i" class="card lens-stat">
          <SkeletonBlock :rows="2" :cells="2" :height="18" />
        </section>
      </div>
      <section class="card"><div class="card-body"><SkeletonBlock :rows="8" :cells="6" :height="14" /></div></section>
    </template>

    <section v-else-if="!state" class="card">
      <ErrorState :error="error" @retry="bootstrap()" />
      <div class="lens-empty-hint">
        首次打开需要先运行一次多透镜；点击「重算多透镜」或上方重试。
      </div>
    </section>

    <template v-else-if="state">
      <!-- 四张总览卡 -->
      <LensSummaryCards :state="state" />

      <LensTabs
        :active-tab="activeTab"
        :fired-count="firedCount"
        :total-rules="totalRules"
        @update:active-tab="activeTab = $event"
      />

      <!-- 合成研判 -->
      <SynthesisTab v-if="activeTab === 'synthesis'" :state="state" />

      <!-- 美联储透镜 -->
      <FedTab v-else-if="activeTab === 'fed'" :state="state" />

      <!-- 宋鸿兵透镜 -->
      <SongTab v-else-if="activeTab === 'song'" :state="state" />

      <!-- 宏观层 / 微观层 -->
      <LayersTab v-else-if="activeTab === 'layers'" :state="state" />

      <!-- 人物透镜 -->
      <PersonasTab v-else-if="activeTab === 'personas'" :state="state" />

      <!-- 规则与证据 -->
      <EvidenceTab v-else :state="state" />

      <!-- 预测登记 -->
      <ForecastPanel
        :state="state"
        :form="form"
        :forecasts="forecasts"
        :submitting="submitting"
        @submit="submitForecast"
      />

      <!-- AI 解读 -->
      <CommentaryPanel
        :ping="ping"
        :commentary="commentary"
        :error="commentError"
        :loading="commentLoading"
        @ask="askAI"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import CommentaryPanel from "@/components/lenses/CommentaryPanel.vue";
import EvidenceTab from "@/components/lenses/EvidenceTab.vue";
import FedTab from "@/components/lenses/FedTab.vue";
import ForecastPanel from "@/components/lenses/ForecastPanel.vue";
import LayersTab from "@/components/lenses/LayersTab.vue";
import LensSummaryCards from "@/components/lenses/LensSummaryCards.vue";
import LensTabs from "@/components/lenses/LensTabs.vue";
import PersonasTab from "@/components/lenses/PersonasTab.vue";
import SongTab from "@/components/lenses/SongTab.vue";
import SynthesisTab from "@/components/lenses/SynthesisTab.vue";
import { useLensState } from "@/composables/useLensState";
import { fmtDate, fmtRatioPct } from "@/composables/useFormat";

const {
  activeTab,
  running,
  submitting,
  commentLoading,
  commentary,
  commentError,
  ping,
  forecasts,
  form,
  state,
  error,
  loading,
  firedCount,
  totalRules,
  bootstrap,
  runNow,
  reload,
  submitForecast,
  askAI,
} = useLensState();
</script>

<style scoped>
.lens-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lens-disclaimer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 11px;
}
.lens-disclaimer .ic {
  width: 13px;
  height: 13px;
  color: var(--accent);
  flex: none;
}
.lens-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.lens-stat {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.card-body { padding: 12px; }
.lens-empty-hint { padding: 0 12px 14px; font-size: 11px; color: var(--dim); }
@media (max-width: 1200px) {
  .lens-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
