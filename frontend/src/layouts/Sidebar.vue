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
      <div class="sf-version">EPIC v{{ health.health?.version ?? "—" }} · 本地实例</div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useHealthStore } from "@/stores/health";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

/** 全站只有两级菜单：一级分组 + 页面项（不再有第三级分组） */
const NAV_GROUPS: NavGroup[] = [
  {
    label: "今日",
    items: [
      { to: "/", label: "总览", icon: "#i-grid" },
      { to: "/briefs", label: "简报", icon: "#i-file" },
      { to: "/trades", label: "交易", icon: "#i-book" },
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
    label: "专题",
    items: [
      { to: "/gold", label: "黄金研判", icon: "#i-flame" },
      { to: "/signals", label: "交易信号", icon: "#i-activity" },
    ],
  },
  {
    label: "证据",
    items: [
      { to: "/analysis", label: "分析引擎", icon: "#i-cpu" },
      { to: "/pipeline", label: "分析过程", icon: "#i-layers" },
      { to: "/theses", label: "分析依据", icon: "#i-book" },
    ],
  },
  {
    label: "周期",
    items: [
      { to: "/cycle", label: "周期罗盘", icon: "#i-target" },
      { to: "/history", label: "世界长河", icon: "#i-branch" },
      { to: "/principles", label: "原则库", icon: "#i-shield-check" },
    ],
  },
  {
    label: "预警",
    items: [
      { to: "/alerts", label: "预警台", icon: "#i-bell" },
      { to: "/ledger", label: "预测台账", icon: "#i-tasks" },
    ],
  },
  {
    label: "系统",
    items: [{ to: "/system", label: "系统状态", icon: "#i-db" }],
  },
];

const route = useRoute();
const health = useHealthStore();
const counts = computed(() => health.counts);

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
