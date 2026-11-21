<template>
  <TopicHeroSection
    v-if="section.kind === 'hero'"
    :data="section.data"
    :generated-label="generatedLabel"
    :verdict="verdict"
  />
  <TopicKpiSection v-else-if="section.kind === 'kpis'" :data="section.data" :label="section.label" />
  <TopicFactorSection v-else-if="section.kind === 'factors'" :data="section.data" />
  <TopicChartGrid
    v-else-if="section.kind === 'charts'"
    :data="section.data"
    :range="range"
    :palette="palette"
    @update:range="$emit('update:range', $event)"
  />
  <TopicTableSection v-else-if="section.kind === 'table'" :tables="tableSpecs(section)" />
  <TopicTableSection v-else-if="section.kind === 'events'" :tables="[eventTable(section.data)]" />
  <TopicValuationSection v-else-if="section.kind === 'valuation'" :data="section.data" :palette="palette" />
  <TopicScenarioSection v-else-if="section.kind === 'scenarios'" :data="section.data" />
  <TopicPositionSection
    v-else-if="section.kind === 'position'"
    :data="section.data"
    :position="position"
    :loading="positionLoading"
    :saving="positionSaving"
    @save="$emit('save-position', $event)"
  />
  <TopicSourcesSection
    v-else-if="section.kind === 'sources'"
    :data="section.data"
    :can-edit="canEditManual"
    :saving="manualSaving"
    @save-manual="$emit('save-manual', $event)"
  />
  <TopicHealthSection v-else-if="section.kind === 'health'" :data="section.data" />
  <TopicMethodologySection v-else-if="section.kind === 'methodology'" :data="section.data" />
  <TopicBulletsSection v-else-if="section.kind === 'bullets'" :data="section.data" :label="section.label" />
  <EmptyState
    v-else
    :text="`未实现的分区类型：${section.kind}`"
    hint="请检查 config/topics.yaml 的 kind 是否在 RENDERERS 中。"
  />
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import type {
  LuoyangVerdict,
  TopicPositionInput,
  TopicPositionResponse,
  TopicSection,
} from "@/api/types";
import type { GoldPalette } from "@/utils/goldCharts";
import type { TopicRange } from "@/utils/topicCharts";
import { eventTable, tableSpecs } from "@/utils/topicNormalize";
import TopicHeroSection from "@/components/topics/TopicHeroSection.vue";
import TopicKpiSection from "@/components/topics/TopicKpiSection.vue";
import TopicFactorSection from "@/components/topics/TopicFactorSection.vue";
import TopicChartGrid from "@/components/topics/TopicChartGrid.vue";
import TopicTableSection from "@/components/topics/TopicTableSection.vue";
import TopicValuationSection from "@/components/topics/TopicValuationSection.vue";
import TopicScenarioSection from "@/components/topics/TopicScenarioSection.vue";
import TopicPositionSection from "@/components/topics/TopicPositionSection.vue";
import TopicSourcesSection from "@/components/topics/TopicSourcesSection.vue";
import TopicHealthSection from "@/components/topics/TopicHealthSection.vue";
import TopicMethodologySection from "@/components/topics/TopicMethodologySection.vue";
import TopicBulletsSection from "@/components/topics/TopicBulletsSection.vue";

defineProps<{
  section: TopicSection;
  range: TopicRange;
  palette: GoldPalette;
  generatedLabel: string;
  verdict?: LuoyangVerdict | null;
  position?: TopicPositionResponse | null;
  positionLoading?: boolean;
  positionSaving?: boolean;
  canEditManual?: boolean;
  manualSaving?: boolean;
}>();

defineEmits<{
  (e: "update:range", range: TopicRange): void;
  (e: "save-position", payload: TopicPositionInput): void;
  (e: "save-manual", payload: { code: string; value: number; as_of?: string; note?: string }): void;
}>();
</script>
