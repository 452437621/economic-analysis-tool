<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 专题 · 数据截至 {{ asOfLabel }}</div>
        <h1 class="page-h1">
          {{ meta.name || "专题研判" }}
          <span class="page-sub">{{ meta.subtitle || activeTopic?.subtitle || "" }}</span>
        </h1>
        <span class="gen-at">（生成于 {{ generatedLabel }}）</span>
      </div>
      <div class="page-actions">
        <span v-if="error && overview" class="badge badge--warn badge--sm">刷新失败</span>
        <button class="btn btn--sm" type="button" :disabled="refreshing || !activeId" @click="triggerRefresh">
          <svg class="ic" :class="{ spin: refreshing }"><use href="#i-refresh" /></svg>
          {{ refreshing ? "采集中" : "刷新数据" }}
        </button>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="loading" @click="refresh()">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>重新加载
        </button>
      </div>
    </div>

    <TopicTabs
      v-if="topics.length"
      :topics="topics"
      :active-id="activeId"
      :loading="topicsLoading"
      @select="selectTopic"
    />
    <section v-else-if="topicsError" class="card">
      <ErrorState :error="topicsError" @retry="bootstrap" />
    </section>
    <div v-else-if="topicsLoading" class="card topic-skeleton">
      <SkeletonBlock :rows="2" :cells="4" :height="18" :gap="10" />
    </div>

    <template v-if="!overview && loading">
      <div class="topic-hero-grid topic-skeleton-grid">
        <section class="card"><div class="card-body"><SkeletonBlock :rows="3" :cells="2" :height="28" :gap="12" /></div></section>
        <section class="card"><div class="card-body"><SkeletonBlock :rows="5" :cells="4" :height="14" :gap="10" /></div></section>
      </div>
      <section class="card topic-skeleton"><div class="card-body"><SkeletonBlock :rows="6" :cells="4" :height="14" :gap="9" /></div></section>
    </template>

    <section v-else-if="!overview && error" class="card">
      <ErrorState :error="error" @retry="refresh" />
    </section>

    <template v-else-if="overview">
      <TopicSectionNav :sections="navSections" :active-anchor="activeAnchor" @jump="jumpTo" />
      <section
        v-for="section in sections"
        :id="section.anchor"
        :key="section.id"
        class="topic-section"
      >
        <div class="sec-row">
          <span class="sec-title">{{ section.label }}</span>
        </div>
        <TopicSectionBody
          :section="section"
          :range="chartRange"
          :palette="palette"
          :generated-label="generatedLabel"
          :verdict="overview.verdict ?? null"
          :position="position"
          :position-loading="positionLoading"
          :position-saving="positionSaving"
          :can-edit-manual="activeId === 'gold'"
          :manual-saving="manualSaving"
          @update:range="setChartRange"
          @save-position="savePosition"
          @save-manual="saveManualMetric"
        />
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import TopicTabs from "@/components/topics/TopicTabs.vue";
import TopicSectionNav from "@/components/topics/TopicSectionNav.vue";
import TopicSectionBody from "@/components/topics/TopicSectionBody.vue";
import { useTopicOverview } from "@/composables/useTopicOverview";
import { fmtDateTime } from "@/composables/useFormat";

const route = useRoute();
const router = useRouter();
const routeTopic = typeof route.params.topicId === "string" ? route.params.topicId : "";
const activeId = ref(routeTopic);

const {
  topics,
  topicsLoading,
  topicsError,
  activeTopic,
  overview,
  sections,
  error,
  loading,
  refreshing,
  position,
  positionLoading,
  positionSaving,
  manualSaving,
  chartRange,
  palette,
  bootstrap,
  refresh,
  triggerRefresh,
  savePosition,
  saveManualMetric,
  setChartRange,
} = useTopicOverview(activeId);

const meta = computed(() => overview.value?.meta ?? { as_of: null, generated_at: "", name: "", subtitle: "" });
const generatedLabel = computed(() => (meta.value.generated_at ? fmtDateTime(meta.value.generated_at) : "—"));
const asOfLabel = computed(() => (meta.value.as_of ? String(meta.value.as_of).slice(0, 10) : "—"));
const navSections = computed(() =>
  sections.value.map((item) => ({ id: item.id, label: item.label, anchor: item.anchor })),
);
const activeAnchor = ref("");

function selectTopic(id: string): void {
  if (id === activeId.value) return;
  activeId.value = id;
  activeAnchor.value = "";
  void router.replace({ name: "topics", params: { topicId: id } });
}

function jumpTo(anchor: string): void {
  activeAnchor.value = anchor;
  void router.replace({ name: "topics", params: { topicId: activeId.value }, hash: `#${anchor}` });
  document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

watch(
  () => route.params.topicId,
  (id) => {
    if (typeof id === "string" && id && id !== activeId.value) activeId.value = id;
  },
);

watch(activeId, (id) => {
  if (id && route.params.topicId !== id) {
    void router.replace({ name: "topics", params: { topicId: id } });
  }
});

let observer: IntersectionObserver | null = null;

function setupObserver(): void {
  observer?.disconnect();
  if (typeof IntersectionObserver === "undefined") return;
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible.length) activeAnchor.value = visible[0].target.id;
    },
    { rootMargin: "-90px 0px -65% 0px", threshold: 0 },
  );
  for (const section of sections.value) {
    const element = document.getElementById(section.anchor);
    if (element) observer.observe(element);
  }
}

watch(sections, async () => {
  await nextTick();
  if (!activeAnchor.value && sections.value.length) activeAnchor.value = sections.value[0].anchor;
  setupObserver();
});

onMounted(() => {
  void bootstrap();
});

onBeforeUnmount(() => {
  observer?.disconnect();
});
</script>

<style scoped>
.topic-section {
  scroll-margin-top: calc(var(--topbar-h, 54px) + 52px);
  margin-bottom: 12px;
}
.topic-skeleton {
  margin-top: 10px;
}
.topic-skeleton-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.96fr) minmax(0, 1.04fr);
  gap: 10px;
  margin-top: 10px;
}
@media (max-width: 1360px) {
  .topic-skeleton-grid {
    grid-template-columns: 1fr;
  }
}
</style>
