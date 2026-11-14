<template>
  <div class="skeleton-rows" :style="{ gap: `${gap}px` }">
    <div v-for="index in rows" :key="index" class="skeleton-row" :style="{ height: `${height}px` }">
      <i v-for="cell in cells" :key="cell" :style="{ flex: cellFlex(cell) }"></i>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    rows?: number;
    cells?: number;
    height?: number;
    gap?: number;
  }>(),
  { rows: 4, cells: 4, height: 14, gap: 8 },
);

function cellFlex(index: number): number {
  return index === 0 ? 1.4 : 1;
}
</script>

<style scoped>
.skeleton-rows {
  display: flex;
  flex-direction: column;
}
.skeleton-row {
  display: flex;
  gap: 12px;
  align-items: center;
}
.skeleton-row i {
  display: block;
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    color-mix(in srgb, var(--surface-3) 70%, var(--surface-2)) 37%,
    var(--surface-2) 63%
  );
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
}
@keyframes shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .skeleton-row i {
    animation: none;
  }
}
</style>
