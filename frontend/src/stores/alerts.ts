import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { getAlerts, ackAlert } from "@/api/endpoints";
import type { AlertItem } from "@/api/types";

export const useAlertsStore = defineStore("alerts", () => {
  const items = ref<AlertItem[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const open = ref(false);
  const unreadTotal = ref(0);

  // 全库未确认数优先（与总览页口径一致），接口未返回时退回当前列表计数
  const unread = computed(
    () => unreadTotal.value || items.value.filter((item) => !item.acknowledged).length,
  );

  async function refresh(): Promise<void> {
    loading.value = true;
    try {
      const payload = await getAlerts(10);
      items.value = payload.data ?? [];
      unreadTotal.value = payload.meta?.unread ?? 0;
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
