import { computed, onMounted, reactive, ref } from "vue";
import { ApiError } from "@/api/client";
import {
  createLensForecast,
  getLensForecasts,
  getLensPing,
  getLensState,
  postLensCommentary,
  runLenses,
} from "@/api/endpoints";
import type {
  LensDerivation,
  LensForecast,
  LensPing,
  LensScore,
  LensStateResponse,
  LensTab,
} from "@/api/types";
import { usePolling } from "@/composables/usePolling";
import { useToast } from "@/stores/toast";

export interface LensForecastForm {
  asset: string;
  direction: "up" | "down" | "flat";
  horizon_days: number;
  probability: number;
  notes: string;
}

/** 总览卡与各透镜共用的评分分级。 */
export function scoreClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "is-flat";
  return value >= 0.25 ? "is-up" : value <= -0.25 ? "is-down" : "is-flat";
}

export function agreementClass(value: string): string {
  if (value.includes("空")) return "badge--down";
  if (value.includes("多")) return "badge--up";
  if (value.includes("分歧")) return "badge--warn";
  return "badge--accent";
}

export function statusText(status: string): string {
  return status === "fired" ? "命中" : status === "unknown" ? "缺数据" : "未命中";
}

export function dirText(direction: string): string {
  return direction === "up" ? "看涨" : direction === "down" ? "看跌" : "震荡";
}

export function errText(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.message) as { detail?: string };
      return parsed.detail ?? err.message;
    } catch {
      return err.message;
    }
  }
  return err instanceof Error ? err.message : String(err);
}

export function toScoreEntries(
  scores: Record<string, LensScore> | undefined,
): Array<[string, LensScore]> {
  return Object.entries(scores ?? {});
}

export function useLensState() {
  const toast = useToast();
  const activeTab = ref<LensTab>("synthesis");
  const override = ref<LensStateResponse | null>(null);
  const running = ref(false);
  const submitting = ref(false);
  const commentLoading = ref(false);
  const commentary = ref("");
  const commentError = ref("");
  const ping = ref<LensPing | null>(null);
  const forecasts = ref<LensForecast[]>([]);
  const form = reactive<LensForecastForm>({
    asset: "gold",
    direction: "up" as "up" | "down" | "flat",
    horizon_days: 63,
    probability: 0.6,
    notes: "",
  });

  const { data, error, loading, refresh } = usePolling(getLensState, {
    interval: 120000,
    immediate: false,
  });
  const state = computed(() => override.value ?? data.value);
  const cycle = computed(() => state.value?.synthesis.cycle_context ?? null);
  const fired = computed(() => ({
    fed: (state.value?.rules.fed ?? []).filter((r) => r.fired).length,
    song: (state.value?.rules.song ?? []).filter((r) => r.fired).length,
  }));
  const totalRules = computed(() => {
    if (!state.value) return 0;
    const rules = state.value.rules;
    let total = (rules.fed?.length ?? 0) + (rules.song?.length ?? 0);
    total += (rules.macro?.length ?? 0) + (rules.micro?.length ?? 0);
    for (const list of Object.values(rules.personas ?? {})) total += list.length;
    return total;
  });
  const firedCount = computed(() => {
    if (!state.value) return 0;
    const rules = state.value.rules;
    let total = fired.value.fed + fired.value.song;
    total += (rules.macro ?? []).filter((r) => r.fired).length;
    total += (rules.micro ?? []).filter((r) => r.fired).length;
    for (const list of Object.values(rules.personas ?? {})) total += list.filter((r) => r.fired).length;
    return total;
  });

  const derivationRows = computed<LensDerivation[]>(() => {
    if (!state.value) return [];
    const rows = [state.value.fed.derivation, state.value.song.derivation];
    if (state.value.macro?.derivation) rows.push(state.value.macro.derivation);
    if (state.value.micro?.derivation) rows.push(state.value.micro.derivation);
    for (const persona of state.value.personas) {
      if (persona.derivation) rows.push(persona.derivation);
    }
    rows.push(state.value.synthesis.derivation);
    return rows;
  });

  async function bootstrap(): Promise<void> {
    override.value = null;
    await refresh();
    if (!data.value) {
      try {
        override.value = await runLenses();
        toast.ok("多透镜已首次运行");
      } catch (err) {
        toast.bad(`运行失败：${errText(err)}`);
      }
    }
    void loadPing();
    void loadForecasts();
  }

  async function runNow(): Promise<void> {
    running.value = true;
    try {
      override.value = await runLenses();
      toast.ok("多透镜已重算");
      void loadForecasts();
    } catch (err) {
      toast.bad(`重算失败：${errText(err)}`);
    } finally {
      running.value = false;
    }
  }

  async function reload(): Promise<void> {
    override.value = null;
    await refresh();
  }

  async function loadPing(): Promise<void> {
    try {
      ping.value = await getLensPing();
    } catch {
      ping.value = null;
    }
  }

  async function loadForecasts(): Promise<void> {
    try {
      const payload = await getLensForecasts();
      forecasts.value = payload.items.slice(0, 8);
    } catch {
      forecasts.value = [];
    }
  }

  async function submitForecast(): Promise<void> {
    const asset = state.value?.synthesis.assets.find((a) => a.id === form.asset);
    submitting.value = true;
    try {
      await createLensForecast({
        asset: form.asset,
        direction: form.direction,
        horizon_days: form.horizon_days,
        probability: form.probability,
        baseline_value: asset?.last ?? null,
        notes: form.notes || null,
      });
      form.notes = "";
      toast.ok("预测已登记");
      void loadForecasts();
    } catch (err) {
      toast.bad(`登记失败：${errText(err)}`);
    } finally {
      submitting.value = false;
    }
  }

  async function askAI(question?: string): Promise<void> {
    commentLoading.value = true;
    commentError.value = "";
    try {
      const result = await postLensCommentary(question || undefined);
      commentary.value = result.text;
    } catch (err) {
      commentError.value = errText(err);
    } finally {
      commentLoading.value = false;
    }
  }

  onMounted(() => {
    void bootstrap();
  });

  return {
    activeTab,
    running,
    submitting,
    commentLoading,
    commentary,
    commentError,
    ping,
    forecasts,
    form,
    state,
    error,
    loading,
    cycle,
    fired,
    totalRules,
    firedCount,
    derivationRows,
    bootstrap,
    runNow,
    reload,
    submitForecast,
    askAI,
  };
}
