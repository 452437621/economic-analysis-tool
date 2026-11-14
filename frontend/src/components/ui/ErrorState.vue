<template>
  <div class="error-state">
    <svg class="ic"><use href="#i-bolt" /></svg>
    <span class="err-text">{{ message || "加载失败" }}</span>
    <button class="btn btn--sm btn--ghost" type="button" @click="emit('retry')">
      <svg class="ic"><use href="#i-refresh" /></svg>重试
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ error?: unknown }>();
const emit = defineEmits<{ retry: [] }>();

const message = computed(() => {
  if (!props.error) return "";
  if (props.error instanceof Error) return props.error.message;
  return String(props.error);
});
</script>

<style scoped>
.error-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 12px;
  font-size: 11.5px;
  color: var(--bad, #f0544f);
}
.error-state .ic {
  width: 14px;
  height: 14px;
  color: var(--warn);
}
.err-text {
  color: var(--muted);
}
</style>
