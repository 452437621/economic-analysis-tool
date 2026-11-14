<template>
  <aside class="sidebar" aria-label="主导航">
    <div class="brand">
      <div class="brand-mark">EP</div>
      <div>
        <div class="brand-name">EPIC</div>
        <div class="brand-sub">宏观 · 市场 · 交易工作台</div>
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
      <div class="sf-rows">
        <div class="sf-row"><span>后端 API</span><b>{{ apiHost }}</b></div>
        <div class="sf-row"><span>行情标的</span><b>{{ counts?.instruments ?? "—" }} 个</b></div>
        <div class="sf-row"><span>调度器</span><b>{{ health.schedulerRunning ? "运行中" : "已停止" }}</b></div>
      </div>
      <div class="sf-version">
        EPIC v{{ health.health?.version ?? "—" }} · Vue 前端<br />
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

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_GROUPS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "工作台",
    items: [
      { to: "/", label: "总览", icon: "#i-grid" },
      { to: "/market", label: "市场行情", icon: "#i-chart" },
    ],
  },
  {
    label: "研究分析",
    items: [
      { to: "/rates", label: "利率与流动性", icon: "#i-rates" },
      { to: "/analysis", label: "分析引擎", icon: "#i-cpu" },
      { to: "/signals", label: "交易信号", icon: "#i-activity" },
      { to: "/theses", label: "论点与证据", icon: "#i-branch" },
    ],
  },
  {
    label: "内容",
    items: [{ to: "/briefs", label: "简报与日志", icon: "#i-file" }],
  },
  {
    label: "系统",
    items: [{ to: "/system", label: "系统状态", icon: "#i-db" }],
  },
];

const route = useRoute();
const health = useHealthStore();
const counts = computed(() => health.counts);
const { text: clockText } = useClockText();
const apiHost = computed(() => location.host);

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
</style>
