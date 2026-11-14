import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastKind = "ok" | "warn" | "bad" | "info";

export interface ToastItem {
  id: number;
  message: string;
  kind: ToastKind;
}

let seq = 0;

export const useToastStore = defineStore("toast", () => {
  const items = ref<ToastItem[]>([]);

  function push(message: string, kind: ToastKind = "ok", duration = 2600): void {
    const id = ++seq;
    items.value = [...items.value.slice(-3), { id, message, kind }];
    window.setTimeout(() => dismiss(id), duration);
  }

  function dismiss(id: number): void {
    items.value = items.value.filter((item) => item.id !== id);
  }

  return { items, push, dismiss };
});

export function useToast() {
  const store = useToastStore();
  return {
    ok: (message: string) => store.push(message, "ok"),
    warn: (message: string) => store.push(message, "warn"),
    bad: (message: string) => store.push(message, "bad"),
    info: (message: string) => store.push(message, "info"),
  };
}
