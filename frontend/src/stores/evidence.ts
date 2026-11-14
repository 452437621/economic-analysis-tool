import { defineStore } from "pinia";
import { ref } from "vue";
import { getDocument } from "@/api/endpoints";
import type { DocumentDetail } from "@/api/types";

/** 全局证据抽屉：任意页面点击新闻 / [证据] / 断言链接都会打开这里。 */
export const useEvidenceStore = defineStore("evidence", () => {
  const open = ref(false);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const doc = ref<DocumentDetail | null>(null);
  const history = ref<string[]>([]);

  async function load(id: string): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      doc.value = await getDocument(id);
    } catch (err) {
      doc.value = null;
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      loading.value = false;
    }
  }

  async function show(id: string): Promise<void> {
    open.value = true;
    if (!history.value.includes(id)) history.value = [...history.value.slice(-19), id];
    await load(id);
  }

  function close(): void {
    open.value = false;
  }

  return { open, loading, error, doc, history, show, load, close };
});
