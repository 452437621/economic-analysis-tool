<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">方法与声明</span>
      <span class="badge badge--sm">口径说明</span>
    </div>
    <div class="card-body">
      <p class="topic-method-text">{{ payload.text || "暂无方法说明。" }}</p>
      <ul v-if="payload.caveats.length" class="topic-caveats">
        <li v-for="(item, index) in payload.caveats" :key="index">{{ item }}</li>
      </ul>
      <p class="topic-disclaimer">{{ payload.disclaimer || "本页仅为研究辅助，不构成投资建议。" }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { TopicMethodologyData } from "@/api/types";

const props = defineProps<{ data: unknown }>();
const payload = computed<TopicMethodologyData>(() => {
  const value = (props.data ?? {}) as Partial<TopicMethodologyData>;
  return {
    text: value.text ?? "暂无方法说明。",
    caveats: value.caveats ?? [],
    disclaimer: value.disclaimer ?? "本页仅为研究辅助，不构成投资建议。",
  };
});
</script>

<style scoped>
.topic-method-text {
  margin: 0 0 8px;
  font-size: 11.5px;
  line-height: 1.7;
}
.topic-caveats {
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 11px;
  color: var(--muted);
  line-height: 1.6;
}
.topic-disclaimer {
  margin: 0;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  font-size: 10.5px;
  color: var(--muted);
}
</style>
