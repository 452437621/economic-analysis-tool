import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { getAlerts, ackAlert } from "@/api/endpoints";
import type { AlertItem } from "@/api/types";

export const useAlertsStore = defineStore("alerts", () => {
  const items = ref<AlertItem[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const open = ref(false);

  const unread = computed(() => items.value.filter((item) => !item.acknowledged).length);

  async function refresh(): Promise<void> {
    loading.value = true;
    try {
      const payload = await getAlerts(10);
      items.value = payload.data ?? [];
      error.value = null;
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      loading.value = false;
    }
  }

  async function acknowledge(id: string): Promise<void> {
    await ackAlert(id);
    await refresh();
  }

  return { items, loading, error, open, unread, refresh, acknowledge };
});
