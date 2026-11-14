import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { getHealth } from "@/api/endpoints";
import type { Health } from "@/api/types";

export const useHealthStore = defineStore("health", () => {
  const health = ref<Health | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastUpdated = ref<Date | null>(null);

  const status = computed(() => health.value?.status ?? "unknown");
  const healthy = computed(() => status.value === "ok");
  const schedulerRunning = computed(() => health.value?.scheduler?.running ?? false);
  const counts = computed(() => health.value?.counts);
  const nextJob = computed(() => health.value?.scheduler?.jobs?.[0] ?? null);

  async function refresh(): Promise<void> {
    loading.value = true;
    try {
      health.value = await getHealth();
      error.value = null;
      lastUpdated.value = new Date();
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      loading.value = false;
    }
  }

  return { health, loading, error, lastUpdated, status, healthy, schedulerRunning, counts, nextJob, refresh };
});
