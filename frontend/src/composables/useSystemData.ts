import { computed, onMounted, ref } from "vue";
import {
  getAcceptance,
  getJobRuns,
  getJobs,
  getQuality,
  getQualityGate,
  getSchedule,
  getScheduleCheck,
  getSources,
  getSystemCoverage,
  repairQuality,
  runJob,
  runScheduleCheck,
} from "@/api/endpoints";
import type {
  CoverageResponse,
  JobRow,
  JobRunRow,
  QualityGate,
  ScheduleCheckRow,
  ScheduleResponse,
} from "@/api/types";
import { fmtDateTime } from "@/composables/useFormat";
import { usePolling } from "@/composables/usePolling";
import { useHealthStore } from "@/stores/health";

export function statusLabel(status: string | null): string {
  if (!status) return "未运行";
  const labels: Record<string, string> = { ok: "成功", error: "失败", running: "运行中", skipped: "跳过", interrupted: "中断" };
  return labels[status] ?? status;
}

export function useSystemData() {
  const health = useHealthStore();

  const {
    data: jobsData,
    error: jobsError,
    loading: jobsLoading,
    refresh: refreshJobs,
  } = usePolling(getJobs, { interval: 60000 });
  const {
    data: sourcesData,
    error: sourcesError,
    loading: sourcesLoading,
    refresh: refreshSources,
  } = usePolling(getSources, { interval: 120000 });
  const {
    data: qualityData,
    error: qualityError,
    loading: qualityLoading,
    refresh: refreshQuality,
  } = usePolling(getQuality, { interval: 120000 });
  const {
    data: acceptanceData,
    error: acceptanceError,
    loading: acceptanceLoading,
    refresh: refreshAcceptance,
  } = usePolling(getAcceptance, { interval: 60000 });

  const {
    data: coverage,
  } = usePolling<CoverageResponse>(() => getSystemCoverage(), { interval: 60000 });
  const {
    data: scheduleData,
    loading: scheduleLoading,
    refresh: refreshSchedule,
  } = usePolling<ScheduleResponse>(() => getSchedule(), { interval: 60000 });
  const {
    data: scheduleCheckData,
    refresh: refreshScheduleCheck,
  } = usePolling<{ data: ScheduleCheckRow[]; schedule: ScheduleResponse }>(
    () => getScheduleCheck(1),
    { interval: 60000 },
  );
  const { data: gateData } = usePolling<QualityGate>(() => getQualityGate(), { interval: 60000 });
  const schedule = computed(() => scheduleData.value ?? null);
  const scheduleCheck = computed(() => scheduleCheckData.value?.data?.[0] ?? null);
  const qualityGate = computed(() => gateData.value ?? null);
  const overdueJobs = computed(
    () => (schedule.value?.jobs ?? []).filter((job) => job.overdue).slice(0, 8),
  );
  const scheduleBusy = ref(false);

  async function triggerScheduleCheck(): Promise<void> {
    scheduleBusy.value = true;
    try {
      await runScheduleCheck({ wait: false, run_data: true, run_downstream: true });
      await refreshScheduleCheck();
      await refreshSchedule();
    } finally {
      scheduleBusy.value = false;
    }
  }

  async function triggerJob(name: string | null | undefined): Promise<void> {
    if (!name) return;
    if (name === "schedule_check") {
      await triggerScheduleCheck();
      return;
    }
    await runJob(name);
  }

  async function triggerRepair(): Promise<void> {
    await repairQuality({ recheck: true });
    await refreshQuality();
    await refreshAcceptance();
  }

  const coveragePct = computed(() => coverage.value?.data_quality_pct ?? 0);
  /** 后端把口径写成一段长文本：按分号拆成逐条说明，避免堆成一坨。 */
  const methodLines = computed(() => {
    const method = coverage.value?.method ?? "健康度 = 60% × 序列覆盖率 + 40% × 作业健康率（最新观测 45 天内视为覆盖）";
    return method
      .split(/[；;\n]/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
  });

  const jobs = computed(() => jobsData.value?.data ?? []);
  const failedJobs = computed(() => jobs.value.filter((job) => job.last_status === "error").length);
  const sources = computed(() => sourcesData.value?.data ?? []);
  const chains = computed(() => sourcesData.value?.chains ?? []);
  const quality = computed(() => qualityData.value ?? null);
  const acceptance = computed(() => acceptanceData.value ?? null);
  const acceptancePassed = computed(
    () => acceptance.value?.checks.filter((check) => check.passed).length ?? 0,
  );

  /* ---------- 执行历史抽屉（点击「调度次数」打开） ---------- */
  const historyJob = ref<string | null>(null);
  const historyRuns = ref<JobRunRow[]>([]);
  const historyLoading = ref(false);
  const historyError = ref<Error | null>(null);

  const historySub = computed(() => {
    if (!historyJob.value) return "";
    const job = jobs.value.find((row) => row.name === historyJob.value);
    if (!job) return "";
    const cron = job.cron ? `计划 ${job.cron}` : "无计划";
    return `${cron} · 累计 ${job.run_count} 次 · 最近 ${fmtDateTime(job.last_run_at)}`;
  });

  function openHistory(job: JobRow): void {
    historyJob.value = job.name;
    void loadHistory();
  }

  function closeHistory(): void {
    historyJob.value = null;
    historyRuns.value = [];
    historyError.value = null;
  }

  async function loadHistory(): Promise<void> {
    const name = historyJob.value;
    if (!name) return;
    historyLoading.value = true;
    historyError.value = null;
    try {
      const payload = await getJobRuns(name, 50);
      historyRuns.value = payload.data ?? [];
    } catch (err) {
      historyError.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      historyLoading.value = false;
    }
  }

  function runStatusClass(status: string): string {
    if (status === "error" || status === "interrupted") return "badge--warn";
    if (status === "running") return "badge--live";
    return "badge--live";
  }

  function fmtDuration(ms: number | null): string {
    if (ms === null || Number.isNaN(ms)) return "—";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
    const minutes = Math.floor(ms / 60_000);
    const seconds = Math.round((ms % 60_000) / 1000);
    return `${minutes}m${seconds}s`;
  }

  /** JobRun.detail 是 JSON 摘要；压成一行可读文本，完整内容挂在 title 上。 */
  function summarizeRun(run: JobRunRow): string {
    if (!run.detail) return "—";
    let parsed: unknown;
    try {
      parsed = JSON.parse(run.detail);
    } catch {
      return String(run.detail).slice(0, 160);
    }
    if (!parsed || typeof parsed !== "object") return String(parsed).slice(0, 160);
    const record = parsed as Record<string, unknown>;
    if (record.error) return `错误：${String(record.error)}`;
    const pairs = Object.entries(record)
      .filter(([, value]) => value !== null && value !== undefined && value !== "")
      .map(([key, value]) => `${key}=${typeof value === "number" ? value : String(value)}`);
    const text = pairs.join(" · ");
    return text ? text.slice(0, 160) : "—";
  }

  function loadJobs(): void {
    void refreshJobs();
  }
  function loadSources(): void {
    void refreshSources();
  }
  function loadQuality(): void {
    void refreshQuality();
  }
  function loadAcceptance(): void {
    void refreshAcceptance();
  }

  function refreshAll(): void {
    void health.refresh();
    void refreshJobs();
    void refreshSources();
    void refreshQuality();
    void refreshAcceptance();
  }

  onMounted(() => {
    void health.refresh();
  });

  return {
    health,
    jobs,
    jobsError,
    jobsLoading,
    refreshJobs,
    loadJobs,
    sources,
    chains,
    sourcesError,
    sourcesLoading,
    refreshSources,
    loadSources,
    quality,
    qualityError,
    qualityLoading,
    refreshQuality,
    loadQuality,
    acceptance,
    acceptanceError,
    acceptanceLoading,
    refreshAcceptance,
    loadAcceptance,
    coverage,
    schedule,
    scheduleLoading,
    scheduleCheck,
    qualityGate,
    overdueJobs,
    scheduleBusy,
    coveragePct,
    methodLines,
    failedJobs,
    acceptancePassed,
    triggerScheduleCheck,
    triggerJob,
    triggerRepair,
    historyJob,
    historyRuns,
    historyLoading,
    historyError,
    historySub,
    openHistory,
    closeHistory,
    loadHistory,
    runStatusClass,
    fmtDuration,
    summarizeRun,
    refreshAll,
  };
}
