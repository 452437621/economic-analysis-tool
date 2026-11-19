<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">系统 · 状态</div>
        <h1 class="page-h1">
          系统状态
          <span class="page-sub">服务 · 任务 · 数据源 · 质检 · 验收</span>
        </h1>
      </div>
      <div class="page-actions">
        <button class="btn btn--sm" type="button" @click="refreshAll">
          <svg class="ic"><use href="#i-refresh" /></svg>刷新
        </button>
        <a class="btn btn--sm btn--ghost" href="/docs" target="_blank" rel="noopener">
          <svg class="ic"><use href="#i-command" /></svg>API 文档
        </a>
      </div>
    </div>

    <div class="kpi-grid">
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-cpu" /></svg></span>
          <span class="kpi-label">服务状态</span>
          <span class="kpi-flag">
            <span class="badge badge--sm" :class="health.healthy ? 'badge--live' : 'badge--warn'">
              {{ health.healthy ? "运行中" : "降级" }}
            </span>
          </span>
        </div>
        <div class="kpi-value">{{ health.health?.status ?? "—" }}<small>{{ health.health?.env ?? "—" }}</small></div>
        <div class="kpi-sub">v{{ health.health?.version ?? "—" }} · {{ health.health?.timezone ?? "—" }}</div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-db" /></svg></span>
          <span class="kpi-label">数据库</span>
          <span class="kpi-flag">
            <span class="badge badge--sm" :class="health.health?.database.ok ? 'badge--live' : 'badge--warn'">
              {{ health.health?.database.ok ? "正常" : "异常" }}
            </span>
          </span>
        </div>
        <div class="kpi-value">{{ health.health?.database.engine ?? "—" }}<small>SQLite</small></div>
        <div class="kpi-sub">{{ health.health?.database.error ?? "连接正常" }}</div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-tasks" /></svg></span>
          <span class="kpi-label">调度器</span>
          <span class="kpi-flag">
            <span class="badge badge--sm" :class="health.schedulerRunning ? 'badge--live' : 'badge--warn'">
              {{ health.schedulerRunning ? "运行中" : "已停止" }}
            </span>
          </span>
        </div>
        <div class="kpi-value">{{ jobs.length }}<small>个任务</small></div>
        <div class="kpi-sub">
          {{ failedJobs ? `${failedJobs} 个失败` : "全部正常" }} · LLM
          {{ health.health?.llm_enabled ? "已配置" : "未配置（规则模式）" }}
        </div>
      </article>
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-icon"><svg class="ic"><use href="#i-shield-check" /></svg></span>
          <span class="kpi-label">验收自检</span>
          <span class="kpi-flag">
            <span class="badge badge--sm" :class="acceptance?.passed ? 'badge--live' : 'badge--warn'">
              {{ acceptance?.passed ? "通过" : "有失败项" }}
            </span>
          </span>
        </div>
        <div class="kpi-value">{{ acceptancePassed }}<small>/ {{ acceptance?.checks.length ?? "—" }} 项</small></div>
        <div class="kpi-sub">数据质检 {{ quality?.summary.passed ?? "—" }} / {{ quality?.summary.total ?? "—" }}</div>
      </article>
    </div>


    <section class="card" style="margin-top: 12px">
      <div class="card-head">
        <span class="card-title">数据健康 · 序列覆盖</span>
        <span class="card-sub">数据时点 · 整体健康度 · 各域序列覆盖（缺失的序列在研判中会显式降级）</span>
        <div class="card-actions">
          <span class="badge badge--sm" :class="coveragePct >= 90 ? 'badge--live' : coveragePct >= 70 ? 'badge--warn' : 'badge--down'">
            健康 {{ coverage ? coveragePct.toFixed(1) + "%" : "—" }}
          </span>
        </div>
      </div>
      <div class="card-body coverage-body">
        <div class="cov-stats">
          <div class="cov-stat">
            <span class="cov-stat-label">序列覆盖</span>
            <b class="cov-stat-value mono">
              {{ coverage?.series_covered ?? "—" }}<small>/ {{ coverage?.series_total ?? "—" }}</small>
            </b>
            <span class="cov-stat-sub">最新观测仍在发布窗口内的宏观序列</span>
          </div>
          <div class="cov-stat">
            <span class="cov-stat-label">作业健康</span>
            <b class="cov-stat-value mono">
              {{ coverage?.jobs_ok ?? "—" }}<small>/ {{ coverage?.jobs_total ?? "—" }}</small>
            </b>
            <span class="cov-stat-sub">最近一次运行状态为成功的调度任务</span>
          </div>
          <div class="cov-stat">
            <span class="cov-stat-label">最近同步</span>
            <b class="cov-stat-value">{{ coverage?.last_sync ? fmtDateTime(coverage.last_sync) : "—" }}</b>
            <span class="cov-stat-sub">行情 / 宏观 / 日线三表的最新写入时间</span>
          </div>
          <div class="cov-stat">
            <span class="cov-stat-label">数据时点</span>
            <b class="cov-stat-value">{{ coverage?.as_of ? fmtDateTime(coverage.as_of) : "—" }}</b>
            <span class="cov-stat-sub">本次健康度的计算时间</span>
          </div>
        </div>

        <div class="cov-meter">
          <div class="cov-meter-head">
            <span>整体健康度</span>
            <b class="mono">{{ coverage ? coveragePct.toFixed(1) + "%" : "—" }}</b>
          </div>
          <div class="cov-bar"><i :style="{ width: coveragePct + '%' }"></i></div>
          <div class="cov-meter-legend">
            <span>0%</span>
            <span>60% × 序列覆盖 + 40% × 作业健康</span>
            <span>100%</span>
          </div>
        </div>

        <div v-if="methodLines.length" class="cov-method">
          <div class="cov-method-title">计算口径</div>
          <ul class="cov-method-list">
            <li v-for="(line, index) in methodLines" :key="index">{{ line }}</li>
          </ul>
        </div>

        <EmptyState
          v-if="!coverage"
          text="覆盖率接口未就绪"
          hint="覆盖率由后台按「序列覆盖率 + 作业健康率」统计后写入 /api/system/coverage；接口没返回时先看「服务」卡是否正常，再点右上角「刷新」。"
        />
      </div>
    </section>

    <section class="card" style="margin-top: 12px">
      <div class="card-head">
        <span class="card-title">任务调度</span>
        <span class="card-sub">任务目的 · cron 定义 · 最近运行 · 点击「调度次数」查看执行历史；超过 24h 未跑标黄，超过 72h 标红</span>
        <div class="card-actions">
          <span class="badge badge--sm" :class="neverRanJobs ? 'badge--warn' : 'badge--live'">
            {{ neverRanJobs }} 个未运行
          </span>
          <span class="badge badge--sm" :class="staleJobs ? 'badge--warn' : 'badge--live'">
            {{ staleJobs }} 个超 24h
          </span>
          <span class="card-sub">{{ jobs.length }} 项</span>
        </div>
      </div>
      <div class="table-wrap sys-wrap">
        <SkeletonBlock v-if="!jobs.length && jobsLoading" :rows="5" />
        <ErrorState v-else-if="jobsError" :error="jobsError" @retry="loadJobs" />
        <table v-else class="data-table sys-jobs">
          <thead>
            <tr>
              <th class="col-job">任务</th>
              <th class="col-desc">任务描述</th>
              <th class="col-cron">计划</th>
              <th class="col-on">启用</th>
              <th class="col-status">最近状态</th>
              <th class="col-run">最近运行 / 时效</th>
              <th class="col-count">调度次数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.name">
              <td class="mono col-job">{{ job.name }}</td>
              <td class="job-desc col-desc">{{ job.description ?? "—" }}</td>
              <td class="mono col-cron">{{ job.cron }}</td>
              <td class="col-on">{{ job.enabled ? "是" : "否" }}</td>
              <td class="col-status">
                <span
                  class="badge badge--sm"
                  :class="job.last_status === 'error' ? 'badge--warn' : 'badge--live'"
                  :title="job.last_error ?? statusLabel(job.last_status)"
                >
                  {{ statusLabel(job.last_status) }}
                </span>
              </td>
              <td class="col-run">
                <span class="run-cell">
                  <span class="muted">{{ fmtDateTime(job.last_run_at) }}</span>
                  <span
                    v-if="jobStale(job).cls"
                    class="badge badge--sm"
                    :class="jobStale(job).cls"
                    :title="jobStale(job).title"
                  >
                    {{ jobStale(job).text }}
                  </span>
                  <span v-else class="dim sys-age" :title="jobStale(job).title">{{ jobStale(job).text }}</span>
                </span>
              </td>
              <td class="col-count">
                <button class="link-count" type="button" :title="`查看 ${job.name} 的执行历史`" @click="openHistory(job)">
                  <b class="mono">{{ job.run_count }}</b>
                  <span class="link-count-more">次 · 历史</span>
                </button>
              </td>
            </tr>
            <tr v-if="!jobs.length">
              <td colspan="7">
                <EmptyState
                  text="暂无调度任务"
                  hint="后端 /api/system/jobs 没有返回任务：先确认「服务」卡里调度器正常，再看 backend 的 jobs 表是否为空（可用 scripts 里的种子脚本补齐）。"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="sys-grid">
      <section class="card">
        <div class="card-head">
          <span class="card-title">数据源健康</span>
          <span class="card-sub">官方优先 · 失败重试 · 最近检查</span>
          <div class="card-actions"><span class="card-sub">{{ sources.length }} 个来源</span></div>
        </div>
        <div class="table-wrap sys-wrap">
          <SkeletonBlock v-if="!sources.length && sourcesLoading" :rows="5" />
          <ErrorState v-else-if="sourcesError" :error="sourcesError" @retry="loadSources" />
          <table v-else class="data-table">
            <thead>
              <tr>
                <th>来源</th>
                <th>类型</th>
                <th>等级</th>
                <th class="num">条目</th>
                <th>状态</th>
                <th>最近检查</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="source in sources" :key="source.id">
                <td>{{ source.name }}</td>
                <td class="muted">{{ source.kind }}</td>
                <td><span class="badge badge--sm">{{ source.tier ?? "—" }}</span></td>
                <td class="num">{{ fmtInt(source.documents) }}</td>
                <td>
                  <span
                    class="badge badge--sm"
                    :class="source.last_ok === false ? 'badge--warn' : 'badge--live'"
                    :title="source.last_error || (source.base_url ?? '')"
                  >
                    {{ source.last_ok === true ? "正常" : source.last_ok === false ? "失败" : "未检查" }}
                  </span>
                </td>
                <td class="muted">{{ fmtDateTime(source.last_check) }}</td>
              </tr>
              <tr v-if="!sources.length">
                <td colspan="6">
                  <EmptyState
                    text="暂无数据源记录"
                    hint="数据源在 backend 的 sources 表里登记；空表说明采集器还没跑过，先运行一次采集任务再刷新。"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <span class="card-title">数据质检</span>
          <span class="card-sub">官方对账 · 新鲜度</span>
          <div class="card-actions">
            <span class="badge badge--sm" :class="quality?.summary.failed ? 'badge--warn' : 'badge--live'">
              {{ quality?.summary.passed ?? "—" }} / {{ quality?.summary.total ?? "—" }}
            </span>
          </div>
        </div>
        <div class="table-wrap sys-wrap">
          <SkeletonBlock v-if="!quality && qualityLoading" :rows="5" />
          <ErrorState v-else-if="qualityError" :error="qualityError" @retry="loadQuality" />
          <table v-else class="data-table sys-quality">
            <colgroup>
              <col class="q-dataset-col" />
              <col class="q-kind-col" />
              <col class="q-status-col" />
              <col />
            </colgroup>
            <thead>
              <tr>
                <th>数据集</th>
                <th>类型</th>
                <th>状态</th>
                <th>明细</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in quality?.data ?? []" :key="`${row.dataset}-${index}`">
                <td class="q-dataset" :title="row.dataset">{{ row.dataset }}</td>
                <td class="muted q-kind">{{ row.kind }}</td>
                <td>
                  <span class="badge badge--sm" :class="row.passed ? 'badge--live' : 'badge--warn'">
                    {{ row.passed ? "通过" : "失败" }}
                  </span>
                </td>
                <td class="muted q-detail">{{ row.detail ?? "—" }}</td>
              </tr>
              <tr v-if="!(quality?.data ?? []).length">
                <td colspan="4">
                  <EmptyState
                    text="暂无质检结果"
                    hint="质检数据由定时作业把新鲜度 / 覆盖率 / 连续性 / 对账结果写入 data_quality；作业跑过之后这里才有行。"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <section class="card" style="margin-top: 12px">
      <div class="card-head">
        <span class="card-title">验收自检（DoD）</span>
        <span class="card-sub">scripts/check_acceptance.ps1 · {{ acceptance?.checks.length ?? "—" }} 项</span>
        <div class="card-actions">
          <span class="badge badge--sm" :class="acceptance?.passed ? 'badge--live' : 'badge--warn'">
            {{ acceptance?.passed ? "全部通过" : "存在失败项" }}
          </span>
        </div>
      </div>
      <div class="table-wrap sys-wrap">
        <SkeletonBlock v-if="!acceptance && acceptanceLoading" :rows="5" />
        <ErrorState v-else-if="acceptanceError" :error="acceptanceError" @retry="loadAcceptance" />
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>检查项</th>
              <th>状态</th>
              <th>明细</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(check, index) in acceptance?.checks ?? []" :key="index">
              <td>{{ check.name }}</td>
              <td>
                <span class="badge badge--sm" :class="check.passed ? 'badge--live' : 'badge--warn'">
                  {{ check.passed ? "通过" : "失败" }}
                </span>
              </td>
              <td class="muted">{{ String(check.detail ?? "—") }}</td>
            </tr>
            <tr v-if="!(acceptance?.checks ?? []).length">
              <td colspan="3">
                <EmptyState
                  text="尚未运行验收自检"
                  hint="验收检查由 scripts/check_acceptance.ps1 产出并落库；跑到「服务」卡确认后端就绪后，在项目根执行该脚本再点刷新。"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="acceptance?.counts" class="card-foot">
        <span v-for="(value, key) in acceptance.counts" :key="key" class="count-chip">
          {{ countLabel(String(key)) }} <b>{{ fmtInt(Number(value)) }}</b>
        </span>
      </div>
    </section>

    <Drawer
      :open="Boolean(historyJob)"
      :title="historyJob ? `执行历史 · ${historyJob}` : '执行历史'"
      :sub="historySub"
      @close="closeHistory"
    >
      <SkeletonBlock v-if="historyLoading" :rows="6" />
      <ErrorState v-else-if="historyError" :error="historyError" @retry="loadHistory" />
      <EmptyState
        v-else-if="!historyRuns.length"
        text="暂无执行记录"
        hint="任务第一次被调度（或手动触发）后，这里会按时间倒序显示每次运行的开始时间、状态、耗时和摘要。"
      />
      <div v-else class="table-wrap hist-wrap">
        <table class="data-table hist-table">
          <thead>
            <tr>
              <th>开始时间</th>
              <th>状态</th>
              <th class="num">耗时</th>
              <th>摘要 / 错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in historyRuns" :key="run.id">
              <td class="muted mono hist-time">{{ fmtDateTime(run.started_at) }}</td>
              <td>
                <span class="badge badge--sm" :class="runStatusClass(run.status)">
                  {{ statusLabel(run.status) }}
                </span>
              </td>
              <td class="num mono">{{ fmtDuration(run.duration_ms) }}</td>
              <td class="muted hist-detail" :title="run.detail ?? ''">{{ summarizeRun(run) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <template #footer>
        <span class="card-sub">共 {{ historyRuns.length }} 条 · 仅保留每个任务最近 200 次执行</span>
        <button class="btn btn--sm btn--ghost" type="button" @click="loadHistory">刷新</button>
      </template>
    </Drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDateTime, fmtInt } from "@/composables/useFormat";
import {
  getAcceptance,
  getJobRuns,
  getJobs,
  getQuality,
  getSources,
  getSystemCoverage,
} from "@/api/endpoints";
import type { CoverageResponse, JobRow, JobRunRow } from "@/api/types";
import { getJson } from "@/api/client";
import { useHealthStore } from "@/stores/health";

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
const quality = computed(() => qualityData.value ?? null);
const acceptance = computed(() => acceptanceData.value ?? null);
const acceptancePassed = computed(
  () => acceptance.value?.checks.filter((check) => check.passed).length ?? 0,
);

function statusLabel(status: string | null): string {
  if (!status) return "未运行";
  const labels: Record<string, string> = { ok: "成功", error: "失败", running: "运行中", skipped: "跳过", interrupted: "中断" };
  return labels[status] ?? status;
}

/** 超过 24h 未跑标黄，超过 72h 标红（用户要求的作业时效约束） */
const STALE_WARN_HOURS = 24;
const STALE_DOWN_HOURS = 72;

function runAgeHours(iso: string | null): number | null {
  if (!iso) return null;
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return null;
  return (Date.now() - ts) / 3_600_000;
}

interface StaleMark {
  text: string;
  cls: string;
  title: string;
}

function jobStale(job: JobRow): StaleMark {
  const hours = runAgeHours(job.last_run_at);
  if (hours === null) {
    return {
      text: "从未运行",
      cls: "badge--warn",
      title: "没有最近运行记录：确认任务已启用（启用列为「是」），或手动触发一次对应作业。",
    };
  }
  const since = `最近一次运行 ${fmtDateTime(job.last_run_at)}`;
  if (hours >= STALE_DOWN_HOURS) {
    return {
      text: `停滞 ${Math.floor(hours / 24)} 天`,
      cls: "badge--down",
      title: `${since}，已 ${Math.floor(hours / 24)} 天未运行（阈值 72 小时）：检查调度器是否在跑、任务是否被禁用。`,
    };
  }
  if (hours >= STALE_WARN_HOURS) {
    return {
      text: `${Math.round(hours)} 小时未跑`,
      cls: "badge--warn",
      title: `${since}，已 ${Math.round(hours)} 小时未运行（阈值 24 小时）：可能是调度间隔较长或上次运行失败。`,
    };
  }
  return {
    text: `${hours < 1 ? "刚刚" : `${hours.toFixed(1)}h 前`}`,
    cls: "",
    title: `${since}（${hours.toFixed(1)} 小时前）`,
  };
}

const staleJobs = computed(
  () => jobs.value.filter((job) => (runAgeHours(job.last_run_at) ?? Infinity) >= STALE_WARN_HOURS).length,
);
const neverRanJobs = computed(() => jobs.value.filter((job) => !job.last_run_at).length);

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

function countLabel(key: string): string {
  const labels: Record<string, string> = {
    instruments: "标的",
    market_bars: "日线",
    quotes: "快照",
    macro: "宏观",
    calendar: "日历",
    documents: "新闻",
    bodies: "原文",
    claims: "断言",
    briefs: "简报",
    analytics: "分析",
    signals: "信号",
    plans: "计划",
    theses: "论点",
    alerts: "告警",
  };
  return labels[key] ?? key;
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
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
/* 系统状态页的表格全部展开：作业、数据源、验收清单都要能直接看到，
   不套全站 table-wrap 的 411px 内部滚动（否则最后一行会被裁掉半行）。 */
.sys-wrap {
  max-height: none;
}
.sys-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 12px;
}

/* ---------- 数据健康 · 序列覆盖：指标卡 + 进度条 + 逐条口径说明 ---------- */
.coverage-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cov-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.cov-stat {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.cov-stat-label {
  font-size: 10px;
  letter-spacing: 0.4px;
  color: var(--dim);
}
.cov-stat-value {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.25;
  color: var(--text);
}
.cov-stat-value small {
  margin-left: 3px;
  font-size: 10px;
  font-weight: 500;
  color: var(--muted);
}
.cov-stat-sub {
  font-size: 10px;
  line-height: 1.45;
  color: var(--muted);
}
.cov-meter {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cov-meter-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 10.5px;
  color: var(--muted);
}
.cov-meter-head b {
  font-size: 13px;
  color: var(--text);
}
.cov-bar {
  height: 6px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.cov-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
  transition: width 0.3s ease;
}
.cov-meter-legend {
  display: flex;
  justify-content: space-between;
  font-size: 9.5px;
  color: var(--dim);
}
.cov-method {
  padding: 9px 11px;
  border: 1px dashed var(--border);
  border-radius: 8px;
}
.cov-method-title {
  margin-bottom: 5px;
  font-size: 9.5px;
  letter-spacing: 0.5px;
  color: var(--dim);
}
.cov-method-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding-left: 16px;
}
.cov-method-list li {
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--muted);
}

/* ---------- 任务调度：固定列宽，避免新增描述/次数列把表格撑出横向滚动 ---------- */
.sys-jobs {
  table-layout: fixed;
}
.sys-jobs .col-job {
  width: 150px;
}
.sys-jobs .col-cron {
  width: 118px;
}
.sys-jobs .col-on {
  width: 44px;
  text-align: center;
}
.sys-jobs .col-status {
  width: 84px;
}
.sys-jobs .col-run {
  width: 190px;
}
.sys-jobs .col-count {
  width: 96px;
  text-align: right;
}
.sys-jobs td.col-job {
  overflow: hidden;
  text-overflow: ellipsis;
}
.sys-jobs .job-desc {
  font-size: 10.5px;
  line-height: 1.45;
  color: var(--muted);
  white-space: normal;
  overflow-wrap: anywhere;
}
/* ---------- 数据质检：数据集列加宽且不换行，明细列收窄自动换行 ---------- */
.sys-quality {
  table-layout: fixed;
}
.sys-quality .q-dataset-col {
  width: 132px;
}
.sys-quality .q-kind-col {
  width: 84px;
}
.sys-quality .q-status-col {
  width: 72px;
}
.sys-quality .q-dataset {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sys-quality .q-kind,
.sys-quality .q-detail {
  font-size: 10.5px;
  line-height: 1.45;
}
.sys-quality .q-kind {
  white-space: nowrap;
}
.sys-quality .q-detail {
  white-space: normal;
  overflow-wrap: anywhere;
}

.run-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.link-count {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 10px;
  cursor: pointer;
}
.link-count:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.link-count b {
  font-size: 11px;
  color: var(--text);
}
.link-count-more {
  font-size: 9.5px;
  color: var(--dim);
}

/* ---------- 执行历史抽屉 ---------- */
.hist-wrap {
  max-height: none;
}
.hist-table {
  table-layout: fixed;
}
.hist-table th:nth-child(1) {
  width: 112px;
}
.hist-table th:nth-child(2) {
  width: 64px;
}
.hist-table th:nth-child(3) {
  width: 62px;
}
.hist-table .hist-time {
  font-size: 10px;
  white-space: nowrap;
}
.hist-table .hist-detail {
  font-size: 10px;
  line-height: 1.4;
  white-space: normal;
  overflow-wrap: anywhere;
}

.count-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 10px;
  color: var(--dim);
}
.count-chip b {
  font-family: var(--mono);
  color: var(--muted);
  font-weight: 600;
}
.sys-age {
  font-family: var(--mono);
  font-size: 10px;
  white-space: nowrap;
}
@media (max-width: 1240px) {
  .sys-grid {
    grid-template-columns: 1fr;
  }
  .cov-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
