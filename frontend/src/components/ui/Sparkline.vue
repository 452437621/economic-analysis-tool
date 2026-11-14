<template>
  <svg
    class="spark"
    :class="trendClass"
    :viewBox="`0 0 ${width} ${height}`"
    preserveAspectRatio="none"
    role="img"
    :aria-label="`迷你走势，${clean.length} 个点`"
  >
    <path v-if="areaPath" :d="areaPath" class="spark-area" />
    <path v-if="linePath" :d="linePath" class="spark-line" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    values: Array<number | null | undefined>;
    width?: number;
    height?: number;
    positive?: boolean | null;
  }>(),
  { width: 120, height: 28, positive: null },
);

const clean = computed(() => props.values.filter((v): v is number => typeof v === "number" && Number.isFinite(v)));
const trendClass = computed(() => {
  if (props.positive === true) return "is-up";
  if (props.positive === false) return "is-down";
  if (clean.value.length < 2) return "is-flat";
  const first = clean.value[0];
  const last = clean.value[clean.value.length - 1];
  return last > first ? "is-up" : last < first ? "is-down" : "is-flat";
});

const geometry = computed(() => {
  const list = clean.value;
  if (list.length < 2) return null;
  const w = props.width;
  const h = props.height;
  const pad = 2;
  let min = Math.min(...list);
  let max = Math.max(...list);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const x = (index: number) => pad + ((w - pad * 2) * index) / (list.length - 1);
  const y = (value: number) => pad + (h - pad * 2) * (1 - (value - min) / (max - min));
  const line = list.map((value, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const area = `${line} L${x(list.length - 1).toFixed(1)},${h - pad} L${pad},${h - pad} Z`;
  return { line, area };
});

const linePath = computed(() => geometry.value?.line ?? "");
const areaPath = computed(() => geometry.value?.area ?? "");
</script>

<style scoped>
.spark {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.spark-line {
  fill: none;
  stroke: var(--up-color);
  stroke-width: 1.5;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.spark-area {
  fill: var(--up-color);
  opacity: 0.1;
}
.spark.is-down .spark-line {
  stroke: var(--down-color);
}
.spark.is-down .spark-area {
  fill: var(--down-color);
}
.spark.is-flat .spark-line {
  stroke: var(--dim);
}
.spark.is-flat .spark-area {
  fill: var(--dim);
}
</style>
