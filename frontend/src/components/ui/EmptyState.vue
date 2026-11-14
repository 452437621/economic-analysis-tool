<template>
  <div class="empty-state">
    <svg class="ic empty-icon"><use href="#i-db" /></svg>
    <div class="empty-text">{{ text }}</div>
    <div v-if="hint" class="empty-hint">{{ hint }}</div>
    <slot />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ text?: string; hint?: string }>(), {
  text: "暂无数据",
  hint: "",
});
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 26px 12px;
  color: var(--dim);
  text-align: center;
}
.empty-icon {
  width: 18px;
  height: 18px;
  opacity: 0.7;
}
.empty-text {
  font-size: 11.5px;
  color: var(--muted);
}
.empty-hint {
  font-size: 10px;
  color: var(--dim);
  max-width: 420px;
  line-height: 1.6;
}
</style>
