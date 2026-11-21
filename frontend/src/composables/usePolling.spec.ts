import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { usePolling, type PollingOptions, type PollingState } from "./usePolling";

function mountPolling<T>(fetcher: () => Promise<T>, options: PollingOptions = {}) {
  let state!: PollingState<T>;
  const wrapper = mount(
    defineComponent({
      setup() {
        state = usePolling(fetcher, options);
        return () => null;
      },
    }),
  );
  return { wrapper, getState: () => state };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("usePolling", () => {
  it("fetches immediately and tracks data / loading / lastUpdated", async () => {
    const fetcher = vi.fn().mockResolvedValue({ n: 1 });
    const { wrapper, getState } = mountPolling(fetcher, {
      interval: 5000,
      pauseWhenHidden: false,
    });

    await vi.advanceTimersByTimeAsync(0);

    const state = getState();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(state.data.value).toEqual({ n: 1 });
    expect(state.error.value).toBeNull();
    expect(state.loading.value).toBe(false);
    expect(state.lastUpdated.value).toBeInstanceOf(Date);

    wrapper.unmount();
  });

  it("polls on the configured interval", async () => {
    const fetcher = vi.fn().mockResolvedValue(1);
    const { wrapper } = mountPolling(fetcher, {
      interval: 5000,
      pauseWhenHidden: false,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(fetcher).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5000);
    expect(fetcher).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(10000);
    expect(fetcher).toHaveBeenCalledTimes(4);

    wrapper.unmount();
  });

  it("keeps previous data when a refresh fails", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ok: true })
      .mockRejectedValueOnce(new Error("boom"));
    const { wrapper, getState } = mountPolling(fetcher, {
      interval: 5000,
      pauseWhenHidden: false,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(getState().data.value).toEqual({ ok: true });

    await getState().refresh();

    expect(getState().error.value?.message).toBe("boom");
    expect(getState().data.value).toEqual({ ok: true });
    expect(getState().loading.value).toBe(false);

    wrapper.unmount();
  });

  it("stops polling and ignores refreshes after unmount", async () => {
    const fetcher = vi.fn().mockResolvedValue(1);
    const { wrapper, getState } = mountPolling(fetcher, {
      interval: 5000,
      pauseWhenHidden: false,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(fetcher).toHaveBeenCalledTimes(1);

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(30000);
    expect(fetcher).toHaveBeenCalledTimes(1);

    await getState().refresh();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("does not schedule a timer when unmounted during the initial fetch", async () => {
    let resolve!: (value: number) => void;
    const fetcher = vi.fn(
      () =>
        new Promise<number>((done) => {
          resolve = done;
        }),
    );
    const { wrapper } = mountPolling(fetcher, {
      interval: 5000,
      pauseWhenHidden: false,
    });

    wrapper.unmount();
    resolve(1);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(30000);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("does not start overlapping refreshes", async () => {
    let resolve!: (value: number) => void;
    const fetcher = vi.fn(
      () =>
        new Promise<number>((done) => {
          resolve = done;
        }),
    );
    const { wrapper, getState } = mountPolling(fetcher, {
      interval: 5000,
      pauseWhenHidden: false,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(fetcher).toHaveBeenCalledTimes(1);

    void getState().refresh();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetcher).toHaveBeenCalledTimes(1);

    resolve(1);
    await vi.advanceTimersByTimeAsync(0);
    expect(getState().data.value).toBe(1);

    wrapper.unmount();
  });
});
