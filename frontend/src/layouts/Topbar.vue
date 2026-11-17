<template>
  <header class="topbar">
    <div class="crumb">
      <span class="crumb-root">EPIC V2</span>
      <span class="crumb-sep">/</span>
      <span class="crumb-group">{{ group }}</span>
      <span class="crumb-sep">/</span>
      <span class="crumb-page">{{ title }}</span>
    </div>
    <button class="search-trigger" type="button" @click="emit('openPalette')">
      <svg class="ic"><use href="#i-search" /></svg>
      <span>搜索标的、页面或执行命令</span>
      <span class="kbd">Ctrl K</span>
    </button>
    <div class="top-actions">
      <div class="data-status">
        <button
          type="button"
          class="pill pill-data"
          :class="{ 'is-open': dataOpen }"
          :title="health.error ?? '点击查看数据健康详情'"
          :aria-expanded="dataOpen"
          @click.stop="toggleData"
        >
          <span class="dot" :class="health.healthy ? 'dot--live' : 'dot--warn'"></span>
          <span class="pill-label">数据采集</span>
          <b>{{ asOfLabel }}</b>
          <template v-if="coverage">
            <span class="pill-sep">·</span>
            <span class="pill-label">健康</span>
            <b>{{ coverage.data_quality_pct.toFixed(1) }}%</b>
          </template>
          <svg class="ic caret"><use href="#i-chevron-down" /></svg>
        </button>
        <div v-if="dataOpen" class="data-pop" @click.stop>
          <div class="dp-head">
            <span class="dot" :class="health.healthy ? 'dot--live' : 'dot--warn'"></span>
            <span>{{ health.healthy ? "系统正常" : health.error ? "后端未连接" : "连接中…" }}</span>
            <span class="dp-version">v{{ health.health?.version ?? "—" }}</span>
          </div>
          <div class="dp-health" v-if="coverage">
            <div class="dp-health-top"><span>数据健康</span><b class="mono">{{ coverage.data_quality_pct.toFixed(1) }}%</b></div>
            <div class="dp-bar"><i :style="{ width: Math.min(100, Math.max(0, coverage.data_quality_pct)) + '%' }"></i></div>
          </div>
          <div class="dp-rows">
            <div class="dp-row">
              <span>数据采集时间</span><b>{{ asOfLabel }}</b>
            </div>
            <div class="dp-row" v-if="coverage">
              <span>序列覆盖</span><b>{{ coverage.series_covered }}/{{ coverage.series_total }}</b>
            </div>
            <div class="dp-row" v-if="coverage">
              <span>最近同步</span><b>{{ syncLabel }}</b>
            </div>
            <div class="dp-row"><span>后端 API</span><b>{{ apiHost }}</b></div>
            <div class="dp-row"><span>行情标的</span><b>{{ counts?.instruments ?? "—" }} 个</b></div>
            <div class="dp-row"><span>调度器</span><b>{{ health.schedulerRunning ? "运行中" : "已停止" }}</b></div>
          </div>
          <div class="dp-foot">数据不出本机 · 本地实例</div>
        </div>
      </div>
      <span class="pill pill-clock" title="本机系统当前时间">
        <b>{{ nowFullLabel }}</b>
      </span>
      <button
        class="icon-btn"
        type="button"
        :title="alerts.unread ? `告警中心（${alerts.unread} 条未确认）` : '告警中心'"
        @click="emit('openAlerts')"
      >
        <svg class="ic"><use href="#i-bell" /></svg>
        <span v-if="alerts.unread" class="notif-dot"></span>
      </button>
      <button class="icon-btn" type="button" title="切换深色 / 浅色主题" @click="toggleTheme">
        <svg class="ic icon-moon"><use href="#i-moon" /></svg>
        <svg class="ic icon-sun"><use href="#i-sun" /></svg>
      </button>
      <button class="icon-btn" type="button" title="设置（外观 / 数据 / 偏好）" @click="emit('openSettings')">
        <svg class="ic"><use href="#i-settings" /></svg>
      </button>
      <span class="top-divider"></span>
      <span class="avatar" title="本地账户 · 数据不出本机">EP</span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useHealthStore } from "@/stores/health";
import { useAlertsStore } from "@/stores/alerts";
import { usePrefsStore } from "@/stores/prefs";
import { useClock } from "@/composables/useClock";
import { getSystemCoverage } from "@/api/endpoints";
import type { CoverageResponse } from "@/api/types";

const emit = defineEmits<{
  openPalette: [];
  openAlerts: [];
  openSettings: [];
}>();

const route = useRoute();
const health = useHealthStore();
const alerts = useAlertsStore();
const prefs = usePrefsStore();
const { now } = useClock();

const coverage = ref<CoverageResponse | null>(null);
const counts = computed(() => health.counts);
const dataOpen = ref(false);
let timer: number | undefined;

async function loadCoverage(): Promise<void> {
  try {
    const payload = await getSystemCoverage();
    coverage.value = payload;
  } catch {
    coverage.value = null;
  }
}

function toggleData(): void {
  dataOpen.value = !dataOpen.value;
}

function onDocClick(): void {
  dataOpen.value = false;
}

onMounted(() => {
  void loadCoverage();
  timer = window.setInterval(() => void loadCoverage(), 60000);
  document.addEventListener("click", onDocClick);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
  document.removeEventListener("click", onDocClick);
});

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** 数据采集时间：最近一次成功采集的时点（yyyy-MM-dd HH:mm） */
const asOfLabel = computed(() => {
  const raw = coverage.value?.as_of;
  if (raw) {
    const date = new Date(raw);
    if (!Number.isNaN(date.getTime())) {
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }
    return raw;
  }
  return syncTime.value;
});

/** 最近同步：数据健康面板内的相对时间口径（MM-DD HH:mm） */
const syncLabel = computed(() => {
  const raw = coverage.value?.as_of;
  if (!raw) return "—";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
});

/** 系统当前时间：固定 yyyy-MM-dd HH:mm:ss，独立 pill 显示 */
const nowFullLabel = computed(() => {
  const d = now.value;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
});

const title = computed(() => String(route.meta.title ?? "总览"));
const group = computed(() => String(route.meta.group ?? "今日"));
const apiHost = computed(() => location.host);
const syncTime = computed(() => {
  const date = health.lastUpdated ?? now.value;
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
});

function toggleTheme(): void {
  prefs.setThemeMode(prefs.resolvedTheme === "dark" ? "light" : "dark");
}
</script>

<style scoped>
.pill-data {
  gap: 5px;
  cursor: pointer;
  font: inherit;
}
.pill-data.is-open {
  border-color: var(--border-strong);
  background: var(--surface-2);
}
.pill-data .caret {
  width: 11px;
  height: 11px;
  color: var(--dim);
  transition: transform .16s ease;
}
.pill-data.is-open .caret {
  transform: rotate(180deg);
}
.pill-label { font-size: 10px; color: var(--dim); }
.pill-clock { padding: 0 11px; }
.pill-clock b {
  letter-spacing: -.2px;
  font-variant-numeric: tabular-nums;
}

.data-status {
  position: relative;
}

.data-pop {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 65;
  width: 260px;
  padding: 10px 11px 9px;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: var(--shadow-pop);
  animation: popIn .14s ease both;
}
@keyframes popIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: none; }
}
.dp-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  color: var(--muted);
}
.dp-version {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--dim);
}
.dp-health {
  margin: 8px 0 6px;
}
.dp-health-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 9.5px;
  color: var(--muted);
}
.dp-health-top b {
  color: var(--ok);
  font-size: 10.5px;
}
.dp-bar {
  height: 4px;
  margin-top: 5px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.dp-bar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--ok));
}
.dp-rows {
  display: grid;
  gap: 3px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
}
.dp-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 9.5px;
  color: var(--dim);
}
.dp-row b {
  font-family: var(--mono);
  font-weight: 500;
  color: var(--muted);
  white-space: nowrap;
}
.dp-foot {
  margin-top: 7px;
  padding-top: 6px;
  border-top: 1px solid var(--border);
  font-size: 8.5px;
  color: var(--dim);
}
</style>
