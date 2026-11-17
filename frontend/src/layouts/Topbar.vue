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
      <span
        class="pill pill-data"
        :title="health.error ?? `后端 ${apiHost} · 版本 ${health.health?.version ?? '—'} · 数据采集时间为最近一次成功采集，刷新于 ${syncTime}`"
      >
        <span class="dot" :class="health.healthy ? 'dot--live' : 'dot--warn'"></span>
        <span class="pill-label">数据采集</span>
        <b>{{ asOfLabel }}</b>
        <template v-if="coverage">
          <span class="pill-sep">·</span>
          <span class="pill-label">健康</span>
          <b>{{ coverage.data_quality_pct.toFixed(1) }}%</b>
        </template>
      </span>
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
let timer: number | undefined;

async function loadCoverage(): Promise<void> {
  try {
    const payload = await getSystemCoverage();
    coverage.value = payload;
  } catch {
    coverage.value = null;
  }
}

onMounted(() => {
  void loadCoverage();
  timer = window.setInterval(() => void loadCoverage(), 60000);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
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
.pill-data { gap: 5px; }
.pill-label { font-size: 10px; color: var(--dim); }
.pill-clock { padding: 0 11px; }
.pill-clock b {
  letter-spacing: -.2px;
  font-variant-numeric: tabular-nums;
}
</style>
