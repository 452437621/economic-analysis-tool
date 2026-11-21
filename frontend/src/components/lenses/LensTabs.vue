<template>
  <div class="lens-tabs">
    <button
      v-for="tab in TABS"
      :key="tab.id"
      class="lens-tab"
      :class="{ active: activeTab === tab.id }"
      type="button"
      @click="emit('update:activeTab', tab.id)"
    >
      {{ tab.label }}
      <span v-if="tab.id === 'evidence'" class="lens-tab-count">
        {{ firedCount }}/{{ totalRules }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { LensTab } from "@/api/types";

defineProps<{
  activeTab: LensTab;
  firedCount: number;
  totalRules: number;
}>();

const emit = defineEmits<{
  (event: "update:activeTab", value: LensTab): void;
}>();

const TABS: Array<{ id: LensTab; label: string }> = [
  { id: "synthesis", label: "合成研判" },
  { id: "fed", label: "美联储透镜" },
  { id: "song", label: "宋鸿兵透镜" },
  { id: "layers", label: "宏观 / 微观" },
  { id: "personas", label: "人物透镜" },
  { id: "evidence", label: "规则与证据" },
];
</script>

<style scoped>
.lens-tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--border);
}
.lens-tab {
  appearance: none;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 7px 12px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}
.lens-tab:hover { color: var(--text); }
.lens-tab.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}
.lens-tab-count {
  margin-left: 5px;
  font-family: var(--font-mono, monospace);
  font-size: 10px;
  color: var(--dim);
}
</style>
