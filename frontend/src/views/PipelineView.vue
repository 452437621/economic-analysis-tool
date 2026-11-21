<template>
  <div class="view active pipe-view">
    <div class="page-head pipe-page-head">
      <div class="pipe-page-title">
        <div class="page-eyebrow">研究分析 · 玻璃盒</div>
        <h1 class="page-h1">
          分析过程 · 数据如何生成结论
          <span class="page-sub">从采集到结论的每一步都可追溯：节点状态、输入特征、规则命中、反证与失效条件</span>
        </h1>
        <span class="gen-at">（生成于 {{ generatedLabel }}）</span>
      </div>
      <div class="page-actions pipe-page-actions">
        <RouterLink class="btn btn--sm btn--ghost" to="/analysis">查看分析结论 →</RouterLink>
        <RouterLink class="btn btn--sm btn--ghost" to="/theses">分析依据 →</RouterLink>
        <span class="badge badge--sm" :class="runBadgeClass(lastRun?.status)">{{ runStatusText(lastRun?.status) }}</span>
        <button class="btn btn--sm" type="button" :disabled="pageLoading" @click="refreshAll">
          <svg class="ic" :class="{ spin: pageLoading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <div v-if="statusError" class="pipe-status-strip">
      <span class="badge badge--warn badge--sm">状态接口异常</span>
      <span class="pipe-status-strip-text">{{ errorText(statusError) }}</span>
      <button class="link-btn" type="button" @click="refreshStatus">重试</button>
    </div>

    <PipelineRunStrip
      :runs="runs"
      :selected-run="selectedRun"
      :selected-run-id="selectedRunId"
      :detail="detail"
      :coverage="coverageData"
      :coverage-error="coverageError"
      :loading="runsLoading"
      :error="runsError"
      @select="selectRun"
      @retry="refreshRuns"
    />

    <div class="kpi-grid pipe-kpi">
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
          <span class="kpi-label">运行</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.runs) : "—" }}</div>
        <div class="kpi-sub">降级 {{ counts ? fmtInt(counts.degraded) : "—" }} · 失败 {{ counts ? fmtInt(counts.failed) : "—" }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-file" /></svg></span>
          <span class="kpi-label">推导</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.derivations) : "—" }}</div>
        <div class="kpi-sub">证据等级 · 置信度 · 失效条件</div>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-db" /></svg></span>
          <span class="kpi-label">观测</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.observations) : "—" }}</div>
        <div class="kpi-sub">原始观测，可回溯 vintage</div>
      </div>
      <div class="kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-cpu" /></svg></span>
          <span class="kpi-label">方法</span>
        </div>
        <div class="kpi-value">{{ counts ? fmtInt(counts.methods) : "—" }}</div>
        <div class="kpi-sub">方法版本登记 · Brier 校准</div>
      </div>
    </div>

    <PipelineDag :nodes="nodes" :selected="selectedNode" :unmapped-count="unmappedStepCount" @select="onNodeSelect" />

    <NodeDetail
      v-if="selectedNodeData"
      :name="selectedNodeData.name"
      :status="selectedNodeData.status"
      :steps="selectedNodeData.steps"
      :duration-ms="selectedNodeData.durationMs"
      :error-count="selectedNodeData.errorCount"
      :degraded-count="selectedNodeData.degradedCount"
      @close="selectedNode = null"
    />

    <div class="pipe-main-grid">
      <PipelineTrace
        :derivation="selectedDerivation"
        :loading="derivationsLoading"
        :error="derivationsError"
        @open="openDerivation"
        @retry="refreshDerivations"
      />
      <ScenarioSandbox :initial="initialComposites" />
    </div>

    <ModelCard
      :methods="methods"
      :methods-loading="methodsLoading"
      :methods-error="methodsError"
      :calibration="calibration"
      :calibration-loading="calibrationLoading"
      :calibration-error="calibrationError"
      :meta="cycleMeta"
      @retry="refreshModel"
    />

    <PipelineStepsCard
      :selected-run="selectedRun"
      :selected-run-id="selectedRunId"
      :detail="detail"
      :loading="detailLoading"
      :error="detailError"
      @refresh="refreshSelected"
      @open="openDerivation"
    />

    <PipelineDerivationsCard
      v-model:code-filter="codeFilter"
      :derivations="derivations"
      :loading="derivationsLoading"
      :error="derivationsError"
      :selected-derivation="selectedDerivation"
      @refresh="refreshDerivations"
      @select="selectDerivation"
      @open="openDerivation"
    />

    <DerivationDrawer :derivation-id="openId" @close="openId = null" />
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
import DerivationDrawer from "@/components/domain/DerivationDrawer.vue";
import PipelineDag from "@/components/pipeline/PipelineDag.vue";
import PipelineDerivationsCard from "@/components/pipeline/PipelineDerivationsCard.vue";
import PipelineRunStrip from "@/components/pipeline/PipelineRunStrip.vue";
import PipelineStepsCard from "@/components/pipeline/PipelineStepsCard.vue";
import PipelineTrace from "@/components/pipeline/PipelineTrace.vue";
import NodeDetail from "@/components/pipeline/NodeDetail.vue";
import ScenarioSandbox from "@/components/pipeline/ScenarioSandbox.vue";
import ModelCard from "@/components/pipeline/ModelCard.vue";
import { usePipelineData } from "@/composables/usePipelineData";
import { fmtInt } from "@/composables/useFormat";
import { errorText, runBadgeClass, runStatusText } from "@/utils/pipelineStatus";

const {
  counts,
  pageLoading,
  generatedLabel,
  statusError,
  refreshStatus,
  runsError,
  runsLoading,
  refreshRuns,
  runs,
  derivationsError,
  derivationsLoading,
  refreshDerivations,
  derivations,
  methodsError,
  methodsLoading,
  methods,
  calibrationError,
  calibrationLoading,
  calibration,
  refreshModel,
  coverageData,
  coverageError,
  cycleMeta,
  selectedRunId,
  detail,
  detailLoading,
  detailError,
  selectedNode,
  selectedNodeData,
  selectedDerivation,
  openId,
  selectedRun,
  lastRun,
  nodes,
  unmappedStepCount,
  initialComposites,
  codeFilter,
  selectRun,
  refreshSelected,
  onNodeSelect,
  selectDerivation,
  openDerivation,
  refreshAll,
} = usePipelineData();
</script>

<style scoped>
.pipe-view {
  min-width: 0;
}
.pipe-page-head {
  flex-wrap: wrap;
  row-gap: 6px;
}
.pipe-page-title {
  min-width: 0;
}
.pipe-page-actions {
  flex-wrap: wrap;
  row-gap: 5px;
}
.pipe-status-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
  padding: 6px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 32%, var(--border));
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 7%, transparent);
}
.pipe-status-strip-text {
  font-size: 9.5px;
  color: var(--muted);
  overflow-wrap: anywhere;
}

.pipe-kpi {
  margin-top: 10px;
}

.pipe-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.06fr) minmax(0, 0.94fr);
  gap: 10px;
  margin-top: 12px;
  align-items: start;
}

@media (max-width: 1240px) {
  .pipe-main-grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 0.95fr);
  }
}
@media (max-width: 1024px) {
  .pipe-main-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
