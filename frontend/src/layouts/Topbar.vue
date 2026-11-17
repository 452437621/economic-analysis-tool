<template>
  <header class="topbar">
    <div class="crumb">
      <span class="crumb-root">{{ group }}</span>
      <span class="crumb-sep">/</span>
      <span class="crumb-page">{{ title }}</span>
    </div>
    <button class="search-trigger" type="button" @click="emit('openPalette')">
      <svg class="ic"><use href="#i-search" /></svg>
      <span>搜索标的、页面或执行命令</span>
      <span class="kbd">Ctrl K</span>
    </button>
    <div class="top-actions">
      <span class="pill" :title="health.error ?? `后端 ${apiHost} · 版本 ${health.health?.version ?? '—'} · 时间为本页最近一次成功刷新`">
        <span class="dot" :class="health.healthy ? 'dot--live' : 'dot--warn'"></span>
        刷新于 <b>{{ syncTime }}</b>
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
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useHealthStore } from "@/stores/health";
import { useAlertsStore } from "@/stores/alerts";
import { usePrefsStore } from "@/stores/prefs";
import { useClock } from "@/composables/useClock";

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

const title = computed(() => String(route.meta.title ?? "总览"));
const group = computed(() => String(route.meta.group ?? "工作台"));
const apiHost = computed(() => location.host);
const syncTime = computed(() => {
  const date = health.lastUpdated ?? now.value;
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
});

function toggleTheme(): void {
  prefs.setThemeMode(prefs.resolvedTheme === "dark" ? "light" : "dark");
}
</script>
