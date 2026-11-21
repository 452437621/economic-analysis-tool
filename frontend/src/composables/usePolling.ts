import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from "vue";

export interface PollingOptions {
  interval?: number | Ref<number> | (() => number);
  immediate?: boolean;
  /** 页面不可见时暂停（默认 true） */
  pauseWhenHidden?: boolean;
  /** 依赖变化时重新拉取 */
  watchSource?: Ref<unknown> | (() => unknown);
}

export interface PollingState<T> {
  data: Ref<T | null>;
  error: Ref<Error | null>;
  loading: Ref<boolean>;
  lastUpdated: Ref<Date | null>;
  refresh: () => Promise<void>;
}

/**
 * 轮询一段异步数据，页面隐藏时自动暂停，错误不清空已有数据。
 * 用法：const { data, loading, error, refresh } = usePolling(() => getSnapshot(), { interval: 15000 })
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  options: PollingOptions = {},
): PollingState<T> {
  const { immediate = true, pauseWhenHidden = true } = options;
  const data = ref<T | null>(null) as Ref<T | null>;
  const error = ref<Error | null>(null);
  const loading = ref(false);
  const lastUpdated = ref<Date | null>(null);
  let timer: number | null = null;
  let inflight = false;
  let disposed = false;

  const intervalMs = computed(() => {
    const source = options.interval;
    const raw =
      typeof source === "function"
        ? source()
        : typeof source === "number"
          ? source
          : source?.value;
    return Math.max(1000, Number(raw ?? 15000));
  });

  async function refresh(): Promise<void> {
    if (inflight || disposed) return;
    inflight = true;
    loading.value = true;
    try {
      const result = await fetcher();
      if (!disposed) {
        data.value = result;
        error.value = null;
        lastUpdated.value = new Date();
      }
    } catch (err) {
      if (!disposed) error.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      inflight = false;
      loading.value = false;
    }
  }

  function schedule(): void {
    if (disposed) return;
    stopTimer();
    timer = window.setTimeout(async () => {
      if (!document.hidden) await refresh();
      if (disposed) return;
      schedule();
    }, intervalMs.value);
  }

  function stopTimer(): void {
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
  }

  function onVisibility(): void {
    if (!document.hidden) void refresh();
  }

  onMounted(async () => {
    if (pauseWhenHidden) document.addEventListener("visibilitychange", onVisibility);
    if (immediate) await refresh();
    if (disposed) return;
    schedule();
  });

  onBeforeUnmount(() => {
    disposed = true;
    stopTimer();
    document.removeEventListener("visibilitychange", onVisibility);
  });

  if (options.watchSource) {
    watch(options.watchSource, () => {
      void refresh();
    });
  }

  return { data, error, loading, lastUpdated, refresh };
}
