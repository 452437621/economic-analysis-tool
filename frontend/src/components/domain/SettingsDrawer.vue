<template>
  <Drawer
    :open="prefs.settingsOpen"
    title="设置"
    sub="外观与偏好"
    width="settings"
    @close="prefs.settingsOpen = false"
  >
    <template #icon>
      <svg class="ic" style="color: var(--accent)"><use href="#i-settings" /></svg>
    </template>

    <div class="set-section">
      <div class="set-title">主题</div>
      <div class="set-desc">默认深色（金融终端）；浅色用于白天，护眼为暖色，跟随系统自动切换。</div>
      <div class="opt-row">
        <button
          v-for="option in THEME_OPTIONS"
          :key="option.value"
          class="opt"
          :class="{ active: prefs.themeMode === option.value }"
          type="button"
          @click="prefs.setThemeMode(option.value)"
        >
          <span class="opt-head">{{ option.label }} <span v-if="option.value === 'dark'" class="badge badge--sm">默认</span></span>
          <span class="opt-preview">
            <i v-for="color in option.colors" :key="color" :style="{ background: color }"></i>
          </span>
        </button>
      </div>
    </div>

    <div class="set-section">
      <div class="set-title">涨跌配色</div>
      <div class="set-desc">国内习惯红涨绿跌；如更习惯国际配色可切换为绿涨红跌。</div>
      <div class="opt-row">
        <button class="opt" :class="{ active: prefs.updown === 'red' }" type="button" @click="prefs.setUpdown('red')">
          <span class="opt-head"><span class="up">红</span>涨 <span class="down">绿</span>跌</span>
          <span class="opt-preview"><i style="background: #f0544f"></i><i style="background: #2fbf71"></i></span>
        </button>
        <button class="opt" :class="{ active: prefs.updown === 'green' }" type="button" @click="prefs.setUpdown('green')">
          <span class="opt-head"><span class="down">绿</span>涨 <span class="up">红</span>跌</span>
          <span class="opt-preview"><i style="background: #2fbf71"></i><i style="background: #f0544f"></i></span>
        </button>
      </div>
    </div>

    <div class="set-section">
      <div class="set-title">界面密度</div>
      <div class="set-desc">紧凑模式压缩表格行高与卡片间距，适合小屏或信息密集场景。</div>
      <div class="seg">
        <button type="button" :class="{ active: prefs.density === 'standard' }" @click="prefs.density = 'standard'">标准</button>
        <button type="button" :class="{ active: prefs.density === 'compact' }" @click="prefs.density = 'compact'">紧凑</button>
      </div>
    </div>

    <div class="set-section">
      <div class="set-title">行情刷新</div>
      <div class="seg">
        <button
          v-for="option in REFRESH_OPTIONS"
          :key="option"
          type="button"
          :class="{ active: prefs.refreshInterval === option }"
          @click="prefs.refreshInterval = option"
        >
          {{ option }} 秒
        </button>
      </div>
      <div class="set-note">影响行情快照、自选与系统状态轮询；分析/简报等低频数据仍按服务端节奏刷新。</div>
    </div>

    <div class="set-section">
      <div class="set-title">显示</div>
      <div class="set-row">
        <span>秒级市场时钟</span>
        <label class="switch">
          <input v-model="prefs.secondsClock" type="checkbox" /><i></i>
        </label>
      </div>
      <div class="set-row">
        <span>行悬停高亮</span>
        <label class="switch">
          <input v-model="prefs.hoverHighlight" type="checkbox" /><i></i>
        </label>
      </div>
    </div>

    <div class="set-section">
      <div class="set-title">关于</div>
      <div class="set-note">
        EPIC · 本地宏观—市场—交易分析工作台<br />
        Vue 3 + TypeScript + Vite 前端 · v{{ appVersion }}<br />
        主题与配色偏好保存在本机 localStorage。
      </div>
    </div>

    <template #footer>
      <button class="btn btn--sm btn--ghost" type="button" @click="prefs.reset()">重置外观</button>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--primary" type="button" @click="prefs.settingsOpen = false">完成</button>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import Drawer from "@/components/ui/Drawer.vue";
import { usePrefsStore, type ThemeMode } from "@/stores/prefs";
import { useHealthStore } from "@/stores/health";
import { computed } from "vue";

const prefs = usePrefsStore();
const health = useHealthStore();
const appVersion = computed(() => health.health?.version ?? "1.1.0");

const THEME_OPTIONS: Array<{ value: ThemeMode; label: string; colors: string[] }> = [
  { value: "dark", label: "深色", colors: ["#0A0E13", "#111721", "#4CC2FF"] },
  { value: "light", label: "浅色", colors: ["#F4F7FA", "#FFFFFF", "#0B6FB3"] },
  { value: "sepia", label: "护眼", colors: ["#F4ECDC", "#FFFBF0", "#9A5B00"] },
  { value: "auto", label: "跟随系统", colors: ["#0A0E13", "#F4F7FA", "#4CC2FF"] },
];

const REFRESH_OPTIONS = [10, 15, 30, 60];
</script>

<style scoped>
.switch {
  position: relative;
  display: inline-flex;
  width: 34px;
  height: 18px;
  flex: none;
}
.switch input {
  position: absolute;
  opacity: 0;
  inset: 0;
  margin: 0;
  cursor: pointer;
}
.switch i {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: var(--surface-3);
  border: 1px solid var(--border);
  transition: background 0.15s;
}
.switch i::after {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--muted);
  transition: transform 0.15s, background 0.15s;
}
.switch input:checked + i {
  background: color-mix(in srgb, var(--accent) 24%, transparent);
  border-color: var(--accent-line);
}
.switch input:checked + i::after {
  transform: translateX(16px);
  background: var(--accent);
}
</style>
