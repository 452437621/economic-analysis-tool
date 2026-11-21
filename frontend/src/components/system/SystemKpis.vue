<template>
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
      <div class="kpi-value">{{ jobsCount }}<small>个任务</small></div>
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
</template>

<script setup lang="ts">
import type { Acceptance, QualityResponse } from "@/api/types";
import type { useHealthStore } from "@/stores/health";

defineProps<{
  health: ReturnType<typeof useHealthStore>;
  jobsCount: number;
  failedJobs: number;
  acceptance: Acceptance | null;
  acceptancePassed: number;
  quality: QualityResponse | null;
}>();
</script>
