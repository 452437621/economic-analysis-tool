<template>
  <div class="topic-tabs" role="tablist" aria-label="专题">
    <button
      v-for="topic in topics"
      :key="topic.id"
      type="button"
      role="tab"
      class="topic-tab"
      :class="{ active: topic.id === activeId }"
      :aria-selected="topic.id === activeId"
      :disabled="loading"
      @click="$emit('select', topic.id)"
    >
      <span class="topic-tab-label">{{ topic.label }}</span>
      <span class="topic-tab-sub">{{ topic.asset }}</span>
    </button>
    <slot />
  </div>
</template>

<script setup lang="ts">
import type { TopicSummary } from "@/api/types";

defineProps<{
  topics: TopicSummary[];
  activeId: string;
  loading?: boolean;
}>();

defineEmits<{ (e: "select", id: string): void }>();
</script>

<style scoped>
.topic-tabs {
  display: flex;
  align-items: stretch;
  gap: 6px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 10px;
  overflow-x: auto;
}
.topic-tab {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-height: 38px;
  padding: 0 12px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  white-space: nowrap;
}
.topic-tab:hover {
  color: var(--text);
}
.topic-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.topic-tab-label {
  font-size: 13px;
  font-weight: 600;
}
.topic-tab-sub {
  font-size: 10px;
  opacity: 0.7;
}
</style>
