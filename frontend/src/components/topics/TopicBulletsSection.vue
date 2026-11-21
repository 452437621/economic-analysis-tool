<template>
  <section class="card">
    <div class="card-head"><span class="card-title">{{ payload.title || "要点" }}</span></div>
    <div class="card-body">
      <ul v-if="payload.items.length" class="topic-bullets">
        <li v-for="(item, index) in payload.items" :key="index">{{ item }}</li>
      </ul>
      <EmptyState v-else text="暂无要点" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicBulletsData } from "@/api/types";

const props = defineProps<{ data: unknown; label?: string }>();
const payload = computed<TopicBulletsData>(() => {
  const value = (props.data ?? {}) as Partial<TopicBulletsData>;
  return { title: value.title ?? props.label ?? "要点", items: value.items ?? [] };
});
</script>

<style scoped>
.topic-bullets {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 11.5px;
  line-height: 1.6;
}
</style>
