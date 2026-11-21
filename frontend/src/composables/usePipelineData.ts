import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getJson } from "@/api/client";
import {
  getCycleState,
  getLedgerCalibration,
  getV2Derivations,
  getV2Methods,
  getV2Run,
  getV2Runs,
  getV2Status,
} from "@/api/endpoints";
import type {
  CoverageResponse,
  CycleKey,
  CycleStateResponse,
  LedgerCalibration,
  V2Derivation,
  V2Method,
  V2Run,
  V2RunDetail,
} from "@/api/types";
import { usePolling } from "@/composables/usePolling";
import {
  buildNodes,
  stepNode,
  type NodeId,
  type PipeNode,
} from "@/utils/pipelineStatus";
import { fmtDate, fmtDateTime, fmtInt, fmtPct } from "@/composables/useFormat";

const CYCLE_KEYS: CycleKey[] = ["DMI", "ICI", "ECI", "GROWTH", "INFLATION", "LIQUIDITY"];

interface CycleMeta {
  rule_version?: string | null;
  next_calibration?: string | null;
  brier?: number | null;
  calibration_n?: number | null;
  coverage?: { series_covered?: number | null; series_total?: number | null } | null;
}

export function usePipelineData() {
  const route = useRoute();
  const router = useRouter();

  const codeFilter = ref(typeof route.query.code === "string" ? route.query.code : "");

  const statusPoll = usePolling(getV2Status, { interval: 30000, immediate: true });
  const runsPoll = usePolling(() => getV2Runs({ limit: 10 }), { interval: 30000, immediate: true });
  const derivationsPoll = usePolling(
    () => getV2Derivations({ code: codeFilter.value || undefined, limit: 50 }),
    { interval: 30000, immediate: true, watchSource: codeFilter },
  );
  const methodsPoll = usePolling(getV2Methods, { interval: 30000, immediate: true });
  const calibrationPoll = usePolling(getLedgerCalibration, { interval: 30000, immediate: true });
  const coveragePoll = usePolling<CoverageResponse>(() => getJson<CoverageResponse>("/api/system/coverage"), {
    interval: 60000,
    immediate: true,
  });

  const { data: statusData, error: statusError, loading: statusLoading, refresh: refreshStatus } = statusPoll;
  const { data: runsData, error: runsError, loading: runsLoading, refresh: refreshRuns } = runsPoll;
  const {
    data: derivationsData,
    error: derivationsError,
    loading: derivationsLoading,
    refresh: refreshDerivations,
  } = derivationsPoll;
  const { data: methodsData, error: methodsError, loading: methodsLoading, refresh: refreshMethods } = methodsPoll;
  const { data: calibrationData, error: calibrationError, loading: calibrationLoading, refresh: refreshCalibration } =
    calibrationPoll;
  const { data: coverageData, error: coverageError, refresh: refreshCoverage } = coveragePoll;

  const counts = computed(() => statusData.value?.counts ?? null);
  const runs = computed<V2Run[]>(() => runsData.value?.items ?? []);
  const derivations = computed<V2Derivation[]>(() => derivationsData.value?.items ?? []);
  const methods = computed<V2Method[]>(() => methodsData.value?.items ?? []);
  const calibration = computed<LedgerCalibration | null>(() => calibrationData.value?.calibration ?? null);

  const pageLoading = computed(() => statusLoading.value || runsLoading.value || derivationsLoading.value);
  /** 用状态接口的生成时间，而不是浏览器当前时间：避免把「刷新了页面」误读成「数据刚生成」。 */
  const generatedLabel = computed(() =>
    statusData.value?.generated_at ? fmtDateTime(statusData.value.generated_at) : "—",
  );

  const selectedRunId = ref<string | null>(null);
  const detail = ref<V2RunDetail | null>(null);
  const detailLoading = ref(false);
  const detailError = ref<Error | null>(null);
  const selectedNode = ref<NodeId | null>(null);
  const selectedDerivationId = ref<string | null>(null);
  const openId = ref<string | null>(null);

  const cycleState = ref<CycleStateResponse | null>(null);
  const cycleMeta = ref<CycleMeta | null>(null);

  const selectedRun = computed<V2Run | null>(
    () => runs.value.find((run) => run.id === selectedRunId.value) ?? detail.value?.run ?? null,
  );

  const lastRun = computed<V2Run | null>(() => statusData.value?.last_run ?? runs.value[0] ?? null);

  const initialComposites = computed<Record<CycleKey, number | null>>(() => {
    const composites = cycleState.value?.state?.value?.composites;
    const result = {} as Record<CycleKey, number | null>;
    for (const key of CYCLE_KEYS) {
      const value = composites?.[key]?.value;
      result[key] = typeof value === "number" && Number.isFinite(value) ? value : null;
    }
    return result;
  });

  /** 契约外步骤数：这些步骤按 kind 兜底归并，提示里如实说明。 */
  const unmappedStepCount = computed(() => {
    const steps = detail.value?.steps ?? [];
    const runKind = selectedRun.value?.kind;
    return steps.filter((step) => stepNode(step, runKind) === null).length;
  });

  const nodes = computed<PipeNode[]>(() =>
    buildNodes(detail.value?.steps ?? [], selectedRun.value),
  );

  const selectedNodeData = computed<PipeNode | null>(
    () => nodes.value.find((node) => node.id === selectedNode.value) ?? null,
  );

  const selectedDerivation = computed<V2Derivation | null>(() => {
    const list = derivations.value;
    if (selectedDerivationId.value) {
      const hit = list.find((item) => item.id === selectedDerivationId.value);
      if (hit) return hit;
    }
    if (codeFilter.value) {
      return list.find((item) => item.code === codeFilter.value || item.id === codeFilter.value) ?? null;
    }
    const runDerivation = detail.value?.derivations[0];
    if (runDerivation) return runDerivation;
    return list[0] ?? null;
  });

  /** 运行摘要条使用：步骤成功率 = 本运行 ok 步骤 / 全部步骤；未加载到步骤明细时显示 —。 */
  const stepSuccessText = computed(() => {
    const steps = detail.value?.steps ?? [];
    if (!steps.length) return "—";
    const ok = steps.filter((step) => step.status === "ok" && !step.error).length;
    return `${ok}/${steps.length}`;
  });

  const coverageText = computed(() => {
    const coverage = coverageData.value;
    if (!coverage) return "—";
    const covered = fmtInt(coverage.series_covered);
    const total = fmtInt(coverage.series_total);
    const pct = typeof coverage.data_quality_pct === "number" ? ` (${fmtPct(coverage.data_quality_pct, 0)})` : "";
    return `${covered}/${total}${pct}`;
  });

  const coverageTitle = computed(() => {
    const coverage = coverageData.value;
    if (!coverage) return coverageError.value ? "覆盖率接口不可用" : "覆盖率数据尚未返回";
    return [
      `来源：${coverage.method || "/api/system/coverage"}`,
      `序列：${coverage.series_covered}/${coverage.series_total}`,
      `任务：${coverage.jobs_ok ?? "—"}/${coverage.jobs_total ?? "—"}`,
      `最近同步：${coverage.last_sync ? fmtDateTime(coverage.last_sync) : "—"}`,
      `数据日：${coverage.as_of ? fmtDate(coverage.as_of) : "—"}`,
    ].join("\n");
  });

  function onNodeSelect(id: string) {
    selectedNode.value = selectedNode.value === id ? null : (id as NodeId);
  }

  function selectDerivation(id: string) {
    selectedDerivationId.value = id;
  }

  function openDerivation(id: string) {
    openId.value = id;
  }

  async function loadDetail(runId: string) {
    detailLoading.value = true;
    detailError.value = null;
    try {
      const data = await getV2Run(runId);
      if (selectedRunId.value === runId) detail.value = data;
    } catch (error) {
      if (selectedRunId.value === runId) {
        detailError.value = error instanceof Error ? error : new Error(String(error));
      }
    } finally {
      if (selectedRunId.value === runId) detailLoading.value = false;
    }
  }

  function selectRun(runId: string) {
    if (selectedRunId.value === runId && detail.value) return;
    selectedRunId.value = runId;
    selectedDerivationId.value = null;
    detail.value = null;
    void loadDetail(runId);
  }

  function refreshSelected() {
    if (selectedRunId.value) void loadDetail(selectedRunId.value);
  }

  async function loadCycleState() {
    try {
      cycleState.value = await getCycleState();
    } catch {
      cycleState.value = null;
    }
  }

  async function loadCycleMeta() {
    try {
      cycleMeta.value = await getJson<CycleMeta>("/api/v2/cycle/meta");
    } catch {
      cycleMeta.value = null;
    }
  }

  async function refreshModel() {
    await Promise.all([refreshMethods(), refreshCalibration(), loadCycleMeta()]);
  }

  async function refreshAll() {
    await Promise.all([
      refreshStatus(),
      refreshRuns(),
      refreshDerivations(),
      refreshMethods(),
      refreshCalibration(),
      refreshCoverage(),
      loadCycleState(),
      loadCycleMeta(),
    ]);
    refreshSelected();
  }

  watch(
    runs,
    (list) => {
      if (!list.length) {
        selectedRunId.value = null;
        detail.value = null;
        return;
      }
      if (!selectedRunId.value || !list.some((run) => run.id === selectedRunId.value)) {
        selectRun(list[0].id);
        return;
      }
      const persisted = list.find((run) => run.id === selectedRunId.value);
      if (
        persisted &&
        !detailLoading.value &&
        (!detail.value ||
          persisted.status === "running" ||
          detail.value.run.status !== persisted.status ||
          detail.value.run.duration_ms !== persisted.duration_ms)
      ) {
        void loadDetail(persisted.id);
      }
    },
    { immediate: true },
  );

  watch(codeFilter, (value) => {
    selectedDerivationId.value = null;
    const current = typeof route.query.code === "string" ? route.query.code : "";
    if (value === current) return;
    const query = { ...route.query };
    if (value) query.code = value;
    else delete query.code;
    void router.replace({ query });
  });

  watch(
    () => route.query.code,
    (value) => {
      const next = typeof value === "string" ? value : "";
      if (next !== codeFilter.value) codeFilter.value = next;
    },
  );

  // 深链 ?code=：命中同 code 的推导后自动打开溯源抽屉，方便从「世界长河 / 预警台」跳进来直接看证据链。
  let autoOpenCode: string | null = null;
  watch(
    [derivations, codeFilter],
    ([list, code]) => {
      if (!code || !list.length) return;
      if (autoOpenCode === code) return;
      const match = list.find((item) => item.code === code || item.id === code);
      if (!match) return;
      autoOpenCode = code;
      selectedDerivationId.value = match.id;
      openId.value = match.id;
    },
    { immediate: true },
  );

  void loadCycleState();
  void loadCycleMeta();

  return {
    counts,
    pageLoading,
    generatedLabel,
    statusError,
    statusLoading,
    refreshStatus,
    runsError,
    runsLoading,
    refreshRuns,
    runs,
    derivationsError,
    derivationsLoading,
    refreshDerivations,
    derivations,
    methodsError,
    methodsLoading,
    methods,
    refreshMethods,
    calibrationError,
    calibrationLoading,
    calibration,
    refreshModel,
    coverageData,
    coverageError,
    cycleMeta,
    selectedRunId,
    detail,
    detailLoading,
    detailError,
    selectedNode,
    selectedNodeData,
    selectedDerivationId,
    selectedDerivation,
    openId,
    selectedRun,
    lastRun,
    nodes,
    unmappedStepCount,
    initialComposites,
    codeFilter,
    selectRun,
    refreshSelected,
    onNodeSelect,
    selectDerivation,
    openDerivation,
    refreshAll,
    stepSuccessText,
    coverageText,
    coverageTitle,
  };
}
