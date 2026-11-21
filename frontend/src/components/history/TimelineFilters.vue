<template>
  <!-- 时间窗 / 图层筛选条（原型 index.html:2728-2745） -->
  <div class="card filterbar">
    <span class="filter-label">时间窗</span>
    <div class="seg" role="group" aria-label="时间窗">
      <button
        v-for="item in WINDOWS"
        :key="item"
        type="button"
        :class="{ active: windowStart === item }"
        :aria-pressed="windowStart === item"
        @click="emit('setWindow', item)"
      >
        {{ item }}–2100
      </button>
    </div>
    <span class="divider-v"></span>
    <span class="filter-label">图层</span>
    <div class="chip-group">
      <button
        v-for="layer in LAYER_CHIPS"
        :key="layer.key"
        type="button"
        class="chip-toggle"
        :class="{ on: layerState[layer.key] }"
        :aria-pressed="layerState[layer.key]"
        @click="emit('toggleLayer', layer.key)"
      >
        <span class="ct-dot" :style="{ background: layer.color }"></span>{{ layer.label }}
      </button>
    </div>
    <span class="filter-hint">事件标注为关键节点，非完整年表</span>
  </div>
</template>

<script setup lang="ts">
import { LAYER_CHIPS } from "@/components/history/timeline/data";
import { WINDOWS } from "@/components/history/timeline/geometry";
import type { LayerKey } from "@/components/history/timeline/types";

defineProps<{
  windowStart: number;
  layerState: Record<LayerKey, boolean>;
}>();

const emit = defineEmits<{
  setWindow: [year: number];
  toggleLayer: [key: LayerKey];
}>();
</script>

<style scoped>
/* 筛选条（原型 index.html:477-480） */
.filterbar {
  display: flex;
  align-items: center;
  gap: 11px;
  flex-wrap: wrap;
  padding: 7px 12px;
  margin-top: 10px;
}
.filter-label {
  font-size: 9.5px;
  color: var(--dim);
  letter-spacing: 0.5px;
  white-space: nowrap;
}
.filter-hint {
  margin-left: auto;
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.divider-v {
  width: 1px;
  height: 18px;
  background: var(--border);
  flex: none;
}
.chip-group {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}
.chip-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--dim);
  font-size: 10.5px;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.12s, border-color 0.12s, background 0.12s;
}
.chip-toggle:hover {
  color: var(--muted);
  border-color: var(--border-strong);
}
.chip-toggle .ct-dot {
  width: 6px;
  height: 6px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.7;
}
.chip-toggle.on {
  color: var(--accent);
  border-color: var(--accent-line);
  background: var(--accent-weak);
}
.chip-toggle.on .ct-dot {
  opacity: 1;
}
</style>
