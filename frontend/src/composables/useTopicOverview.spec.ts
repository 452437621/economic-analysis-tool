import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { ApiError } from "@/api/client";
import * as api from "@/api/endpoints";
import type { TopicOverview, TopicPositionResponse, TopicSummary } from "@/api/types";
import { useTopicOverview } from "./useTopicOverview";

vi.mock("@/api/endpoints", () => ({
  getTopics: vi.fn(),
  getTopicOverview: vi.fn(),
  refreshTopic: vi.fn(),
  getTopicPosition: vi.fn(),
  saveTopicPosition: vi.fn(),
  saveGoldMetric: vi.fn(),
}));

const summary: TopicSummary = {
  id: "gold",
  label: "黄金研判",
  subtitle: "黄金",
  asset: "黄金",
  adapter: "gold",
  order: 10,
  refresh_job: "collect_gold",
  sections: [],
};

const positionSection = {
  id: "position",
  label: "持仓",
  kind: "position" as const,
  anchor: "p",
  order: 10,
  data: { ok: true },
};

function overview(withPosition = false): TopicOverview {
  return {
    meta: {
      topic_id: "gold",
      name: "黄金研判",
      subtitle: "",
      asset: "黄金",
      as_of: null,
      generated_at: "2026-01-01T00:00:00Z",
      config_version: "v1",
      adapter: "gold",
      refresh_job: "collect_gold",
    },
    hero: {
      score: 10,
      label: "中性",
      coverage: 50,
      available_weight: 50,
      total_weight: 100,
      conclusion: "",
      badges: [],
      drivers: [],
    },
    sections: withPosition ? [positionSection] : [],
  };
}

const positionResponse: TopicPositionResponse = {
  topic_id: "gold",
  defaults: { buy_price: 20, buy_date: null, shares_lots: null, dividends: [], add_prices: [], add_ratios: [] },
  overrides: {},
  effective: { buy_price: 20, buy_date: null, shares_lots: null, dividends: [], add_prices: [], add_ratios: [] },
  editable: ["buy_price"],
  updated_at: null,
};

function mountTopic(activeId = "gold") {
  setActivePinia(createPinia());
  const id = ref(activeId);
  let state!: ReturnType<typeof useTopicOverview>;
  const wrapper = mount(
    defineComponent({
      setup() {
        state = useTopicOverview(id);
        return () => null;
      },
    }),
  );
  return { wrapper, id, state: () => state };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getTopics).mockResolvedValue({ data: [summary], config_version: "v1" });
  vi.mocked(api.getTopicOverview).mockResolvedValue(overview());
  vi.mocked(api.getTopicPosition).mockResolvedValue(positionResponse);
  vi.mocked(api.saveTopicPosition).mockResolvedValue(positionResponse);
});

describe("useTopicOverview", () => {
  it("bootstraps topics then loads the overview", async () => {
    const { wrapper, state } = mountTopic();
    await state().bootstrap();
    await flushPromises();
    expect(api.getTopics).toHaveBeenCalledTimes(1);
    expect(api.getTopicOverview).toHaveBeenCalledWith("gold");
    expect(state().overview.value?.meta.topic_id).toBe("gold");
    expect(state().configVersion.value).toBe("v1");
    wrapper.unmount();
  });

  it("falls back to the first enabled topic for an unknown route id", async () => {
    const { wrapper, id, state } = mountTopic("nope");
    await state().bootstrap();
    await flushPromises();
    expect(id.value).toBe("gold");
    expect(api.getTopicOverview).toHaveBeenCalledWith("gold");
    wrapper.unmount();
  });

  it("loads position only when a position section exists and treats 404 as silent", async () => {
    const { wrapper, state } = mountTopic();
    await state().bootstrap();
    await flushPromises();
    expect(api.getTopicPosition).not.toHaveBeenCalled();

    vi.mocked(api.getTopicOverview).mockResolvedValue(overview(true));
    await state().refresh(true);
    await flushPromises();
    expect(api.getTopicPosition).toHaveBeenCalledWith("gold");
    expect(state().position.value?.effective.buy_price).toBe(20);

    vi.mocked(api.getTopicPosition).mockRejectedValue(new ApiError(404, "/api/topics/gold/position"));
    await state().loadPosition();
    expect(state().position.value).toBeNull();
    wrapper.unmount();
  });

  it("sends only whitelisted position fields and refreshes", async () => {
    const { wrapper, state } = mountTopic();
    await state().bootstrap();
    await flushPromises();
    const ok = await state().savePosition({ buy_price: 12.5 });
    expect(ok).toBe(true);
    expect(api.saveTopicPosition).toHaveBeenCalledWith("gold", { buy_price: 12.5 });
    expect(api.getTopicOverview).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
