import { onBeforeUnmount, onMounted, ref } from "vue";
import { usePrefsStore } from "@/stores/prefs";

/** 本地时钟（秒级），设置里可关闭秒级刷新。 */
export function useClock() {
  const prefs = usePrefsStore();
  const now = ref(new Date());
  let timer: number | null = null;

  function tick(): void {
    now.value = new Date();
  }

  onMounted(() => {
    tick();
    timer = window.setInterval(tick, prefs.secondsClock ? 1000 : 30000);
  });

  onBeforeUnmount(() => {
    if (timer !== null) window.clearInterval(timer);
  });

  return { now };
}

/** 格式化本地时钟 */
export function useClockText() {
  const { now } = useClock();
  const text = computedText(now);
  return { now, text };
}

import { computed, type Ref } from "vue";

function computedText(now: Ref<Date>) {
  return computed(() =>
    now.value
      .toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
      .replace(/\//g, "-"),
  );
}
