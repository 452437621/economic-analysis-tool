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

    <SystemKpis
      :health="health"
      :jobs-count="jobs.length"
      :failed-jobs="failedJobs"
      :acceptance="acceptance"
      :acceptance-passed="acceptancePassed"
      :quality="quality"
    />

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

    <ScheduleCheckCard
      :schedule="schedule"
      :schedule-check="scheduleCheck"
      :quality-gate="qualityGate"
      :overdue-jobs="overdueJobs"
      :schedule-loading="scheduleLoading"
      :schedule-busy="scheduleBusy"
      @trigger="triggerScheduleCheck"
    />

    <JobsCard
      :jobs="jobs"
      :jobs-loading="jobsLoading"
      :jobs-error="jobsError"
      @retry="loadJobs"
      @open="openHistory"
    />

    <div class="sys-grid">
      <SourcesCard
        :sources="sources"
        :chains="chains"
        :sources-loading="sourcesLoading"
        :sources-error="sourcesError"
        @retry="loadSources"
      />

      <QualityCard
        :quality="quality"
        :quality-loading="qualityLoading"
        :quality-error="qualityError"
        @retry="loadQuality"
        @repair="triggerRepair"
        @job="triggerJob"
      />
    </div>

    <AcceptanceCard
      :acceptance="acceptance"
      :acceptance-loading="acceptanceLoading"
      :acceptance-error="acceptanceError"
      @retry="loadAcceptance"
      @job="triggerJob"
    />

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
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import AcceptanceCard from "@/components/system/AcceptanceCard.vue";
import JobsCard from "@/components/system/JobsCard.vue";
import QualityCard from "@/components/system/QualityCard.vue";
import ScheduleCheckCard from "@/components/system/ScheduleCheckCard.vue";
import SourcesCard from "@/components/system/SourcesCard.vue";
import SystemKpis from "@/components/system/SystemKpis.vue";
import { fmtDateTime } from "@/composables/useFormat";
import { statusLabel, useSystemData } from "@/composables/useSystemData";

const {
  health,
  jobs,
  jobsError,
  jobsLoading,
  loadJobs,
  sources,
  chains,
  sourcesError,
  sourcesLoading,
  loadSources,
  quality,
  qualityError,
  qualityLoading,
  loadQuality,
  acceptance,
  acceptanceError,
  acceptanceLoading,
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
} = useSystemData();
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.sys-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
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

@media (max-width: 1240px) {
  .cov-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
