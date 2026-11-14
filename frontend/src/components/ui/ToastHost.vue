<template>
  <div class="toast-host">
    <TransitionGroup name="toast">
      <div v-for="item in store.items" :key="item.id" class="toast" :class="item.kind">
        <svg class="ic">
          <use :href="iconFor(item.kind)" />
        </svg>
        <span>{{ item.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useToastStore, type ToastKind } from "@/stores/toast";

const store = useToastStore();

function iconFor(kind: ToastKind): string {
  if (kind === "warn") return "#i-bolt";
  if (kind === "bad") return "#i-close";
  if (kind === "info") return "#i-command";
  return "#i-shield-check";
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
