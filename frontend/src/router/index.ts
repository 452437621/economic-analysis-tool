import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "overview",
    component: () => import("@/views/OverviewView.vue"),
    meta: { title: "总览", group: "工作台" },
  },
  {
    path: "/market",
    name: "market",
    component: () => import("@/views/MarketView.vue"),
    meta: { title: "市场行情", group: "工作台" },
  },
  {
    path: "/rates",
    name: "rates",
    component: () => import("@/views/RatesView.vue"),
    meta: { title: "利率与流动性", group: "研究分析" },
  },
  {
    path: "/analysis",
    name: "analysis",
    component: () => import("@/views/AnalysisView.vue"),
    meta: { title: "分析引擎", group: "研究分析" },
  },
  {
    path: "/pipeline",
    name: "pipeline",
    component: () => import("@/views/PipelineView.vue"),
    meta: { title: "透明管线", group: "研究分析" },
  },
  {
    path: "/cycle",
    name: "cycle",
    component: () => import("@/views/CycleView.vue"),
    meta: { title: "周期罗盘", group: "研究分析" },
  },
  {
    path: "/alerts",
    name: "alerts",
    component: () => import("@/views/AlertsView.vue"),
    meta: { title: "预警台", group: "研究分析" },
  },
  {
    path: "/history",
    name: "history",
    component: () => import("@/views/HistoryView.vue"),
    meta: { title: "世界长河", group: "研究分析" },
  },
  {
    path: "/signals",
    name: "signals",
    component: () => import("@/views/SignalsView.vue"),
    meta: { title: "交易信号", group: "研究分析" },
  },
  {
    path: "/gold",
    name: "gold",
    component: () => import("@/views/GoldView.vue"),
    meta: { title: "黄金研判", group: "研究分析" },
  },
  {
    path: "/theses",
    name: "theses",
    component: () => import("@/views/ThesesView.vue"),
    meta: { title: "论点与证据", group: "研究分析" },
  },
  {
    path: "/briefs",
    name: "briefs",
    component: () => import("@/views/BriefsView.vue"),
    meta: { title: "简报与日志", group: "内容" },
  },
  {
    path: "/system",
    name: "system",
    component: () => import("@/views/SystemView.vue"),
    meta: { title: "系统状态", group: "系统" },
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 };
  },
});

export default router;
