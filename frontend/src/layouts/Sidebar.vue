<template>
  <aside class="sidebar" aria-label="主导航">
    <div class="brand">
      <div class="brand-mark">E2</div>
      <div>
        <div class="brand-name">EPIC V2</div>
        <div class="brand-sub">周期研判 · 宏观工作台</div>
      </div>
    </div>
    <nav class="nav">
      <div v-for="group in NAV_GROUPS" :key="group.label" class="nav-group">
        <div class="nav-label">{{ group.label }}</div>
        <RouterLink
          v-for="item in group.items"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to) }"
        >
          <svg class="ic"><use :href="item.icon" /></svg>
          <span>{{ item.label }}</span>
          <span v-if="badgeFor(item.to)" class="nav-badge">{{ badgeFor(item.to) }}</span>
        </RouterLink>
      </div>
    </nav>
    <div class="sidebar-foot">
      <div class="sf-status">
        <span class="dot" :class="health.healthy ? 'dot--live' : 'dot--warn'"></span>
        <span>{{ health.healthy ? "系统正常" : health.error ? "后端未连接" : "连接中…" }}</span>
      </div>
      <div class="sf-health" v-if="coverage">
        <div class="sf-health-top"><span>数据健康</span><b class="mono">{{ coverage.data_quality_pct.toFixed(1) }}%</b></div>
        <div class="sf-health-bar"><i :style="{ width: Math.min(100, Math.max(0, coverage.data_quality_pct)) + '%' }"></i></div>
        <div class="sf-health-note">序列覆盖 {{ coverage.series_covered }}/{{ coverage.series_total }} · 最近同步 {{ syncLabel }}</div>
      </div>
      <div class="sf-rows">
        <div class="sf-row"><span>后端 API</span><b>{{ apiHost }}</b></div>
        <div class="sf-row"><span>行情标的</span><b>{{ counts?.instruments ?? "—" }} 个</b></div>
        <div class="sf-row"><span>调度器</span><b>{{ health.schedulerRunning ? "运行中" : "已停止" }}</b></div>
      </div>
      <div class="sf-version">
        EPIC v{{ health.health?.version ?? "—" }} · 本地实例<br />
        {{ clockText }}
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useHealthStore } from "@/stores/health";
import { useClockText } from "@/composables/useClock";
import { getSystemCoverage } from "@/api/endpoints";
import type { CoverageResponse } from "@/api/types";
import { usePolling } from "@/composables/usePolling";
import { getJson } from "@/api/client";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_GROUPS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "今日",
    items: [
      { to: "/", label: "总览", icon: "#i-grid" },
      { to: "/briefs", label: "简报与日志", icon: "#i-file" },
    ],
  },
  {
    label: "市场",
    items: [
      { to: "/market", label: "市场行情", icon: "#i-chart" },
      { to: "/rates", label: "利率与流动性", icon: "#i-rates" },
    ],
  },
  {
    label: "研判",
    items: [
      { to: "/cycle", label: "周期罗盘", icon: "#i-target" },
      { to: "/history", label: "世界长河", icon: "#i-book" },
      { to: "/pipeline", label: "透明管线", icon: "#i-layers" },
      { to: "/alerts", label: "预警台", icon: "#i-bell" },
      { to: "/analysis", label: "分析引擎", icon: "#i-cpu" },
      { to: "/ledger", label: "预测台账", icon: "#i-tasks" },
      { to: "/principles", label: "原则库", icon: "#i-shield-check" },
      { to: "/gold", label: "黄金研判", icon: "#i-flame" },
      { to: "/signals", label: "交易信号", icon: "#i-activity" },
      { to: "/theses", label: "论点与证据", icon: "#i-branch" },
    ],
  },
  {
    label: "系统",
    items: [
      { to: "/system", label: "系统状态", icon: "#i-db" },
      { to: "/tokens", label: "设计规范", icon: "#i-palette" },
    ],
  },
];

const route = useRoute();
const health = useHealthStore();
const counts = computed(() => health.counts);
const { text: clockText } = useClockText();
const apiHost = computed(() => location.host);

const { data: coverage } = usePolling<CoverageResponse>(
  () => getSystemCoverage(),
  { interval: 120000 },
);

const syncLabel = computed(() => {
  const raw = coverage.value?.as_of;
  if (!raw) return "—";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
});

function isActive(to: string): boolean {
  if (to === "/") return route.path === "/";
  return route.path === to || route.path.startsWith(`${to}/`);
}

function badgeFor(to: string): string | number {
  if (to === "/market") return counts.value?.instruments ?? "";
  if (to === "/theses") return counts.value?.theses || "";
  return "";
}
</script>

<style scoped>
.nav-item {
  text-decoration: none;
}

.sf-health {
  margin: 2px 0 8px;
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}

.sf-health-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 9.5px;
  color: var(--muted);
}

.sf-health-top b {
  color: var(--ok);
  font-size: 10.5px;
}

.sf-health-bar {
  height: 4px;
  margin: 5px 0 4px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}

.sf-health-bar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--ok));
}

.sf-health-note {
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
