<template>
  <nav class="topic-nav" aria-label="页内分区">
    <div class="topic-nav-inner">
      <button
        v-for="(section, index) in sections"
        :key="section.id"
        type="button"
        class="topic-nav-item"
        :class="{ active: section.anchor === activeAnchor }"
        @click="$emit('jump', section.anchor)"
      >
        <span class="topic-nav-num">{{ String(index + 1).padStart(2, "0") }}</span>
        <span>{{ section.label }}</span>
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import type { TopicSection } from "@/api/types";

defineProps<{
  sections: Array<Pick<TopicSection, "id" | "label" | "anchor">>;
  activeAnchor: string;
}>();

defineEmits<{ (e: "jump", anchor: string): void }>();
</script>

<style scoped>
.topic-nav {
  position: sticky;
  top: var(--topbar-h, 54px);
  z-index: 18;
  margin: 0 0 10px;
  padding: 6px 0;
  background: color-mix(in srgb, var(--bg) 90%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}
.topic-nav-inner {
  display: flex;
  gap: 4px;
  overflow-x: auto;
}
.topic-nav-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  padding: 4px 9px;
  cursor: pointer;
  white-space: nowrap;
}
.topic-nav-item:hover {
  color: var(--text);
  background: var(--surface-2);
}
.topic-nav-item.active {
  color: var(--accent);
  border-color: var(--accent-line);
  background: var(--accent-weak);
}
.topic-nav-num {
  font-size: 9px;
  opacity: 0.75;
}
</style>
