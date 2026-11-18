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
        <div class="cov-head">
          <div class="cov-main">
            <span class="cov-label">覆盖序列</span>
            <span class="cov-value mono">{{ coverage?.series_covered ?? "—" }} / {{ coverage?.series_total ?? "—" }}</span>
          </div>
          <div class="cov-meta">
            <span>序列覆盖 <b class="mono">{{ coverage?.series_covered ?? "—" }}/{{ coverage?.series_total ?? "—" }}</b></span>
            <span>作业健康 <b class="mono">{{ coverage?.jobs_ok ?? "—" }}/{{ coverage?.jobs_total ?? "—" }}</b></span>
            <span>最近同步 <b class="mono">{{ coverage?.last_sync ? fmtDateTime(coverage.last_sync) : "—" }}</b></span>
            <span>计算时间 <b class="mono">{{ coverage?.as_of ? fmtDateTime(coverage.as_of) : "—" }}</b></span>
          </div>
        </div>
        <div class="cov-bar"><i :style="{ width: coveragePct + '%' }"></i></div>
        <div class="cov-note">{{ coverage?.method ?? "健康度 = 60% × 序列覆盖率 + 40% × 作业健康率（最新观测 45 天内视为覆盖）" }}</div>
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
        <span class="card-sub">cron 定义 · 最近运行状态 · 超过 24h 未跑标黄，超过 72h 标红</span>
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
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>任务</th>
              <th>计划</th>
              <th>启用</th>
              <th>最近状态</th>
              <th>最近运行</th>
              <th>时效</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.name">
              <td class="mono">{{ job.name }}</td>
              <td class="mono">{{ job.cron }}</td>
              <td>{{ job.enabled ? "是" : "否" }}</td>
              <td>
                <span class="badge badge--sm" :class="job.last_status === 'error' ? 'badge--warn' : 'badge--live'">
                  {{ statusLabel(job.last_status) }}
                </span>
              </td>
              <td class="muted">{{ fmtDateTime(job.last_run_at) }}</td>
              <td>
                <span
                  v-if="jobStale(job).cls"
                  class="badge badge--sm"
                  :class="jobStale(job).cls"
                  :title="jobStale(job).title"
                >
                  {{ jobStale(job).text }}
                </span>
                <span v-else class="dim sys-age" :title="jobStale(job).title">{{ jobStale(job).text }}</span>
              </td>
              <td class="muted err-cell">{{ job.last_error ?? "—" }}</td>
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
          <table v-else class="data-table">
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
                <td>{{ row.dataset }}</td>
                <td class="muted">{{ row.kind }}</td>
                <td>
                  <span class="badge badge--sm" :class="row.passed ? 'badge--live' : 'badge--warn'">
                    {{ row.passed ? "通过" : "失败" }}
                  </span>
                </td>
                <td class="muted">{{ row.detail ?? "—" }}</td>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDateTime, fmtInt } from "@/composables/useFormat";
import {
  getAcceptance,
  getJobs,
  getQuality,
  getSources,
  getSystemCoverage,
} from "@/api/endpoints";
import type { CoverageResponse, JobRow } from "@/api/types";
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
/* 系统状态页的表格全部展开：作业 28 条、数据源 18 条、验收 14 项都要能直接看到，
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
.err-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
}
</style>
