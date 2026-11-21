import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "overview",
    component: () => import("@/views/OverviewView.vue"),
    meta: { title: "总览", group: "今日" },
  },
  {
    path: "/market",
    name: "market",
    component: () => import("@/views/MarketView.vue"),
    meta: { title: "市场行情", group: "市场" },
  },
  {
    path: "/rates",
    name: "rates",
    component: () => import("@/views/RatesView.vue"),
    meta: { title: "利率与流动性", group: "市场" },
  },
  {
    path: "/analysis",
    name: "analysis",
    component: () => import("@/views/AnalysisView.vue"),
    meta: { title: "分析引擎", group: "证据" },
  },
  {
    path: "/pipeline",
    name: "pipeline",
    component: () => import("@/views/PipelineView.vue"),
    meta: { title: "分析过程", group: "证据" },
  },
  {
    path: "/cycle",
    name: "cycle",
    component: () => import("@/views/CycleView.vue"),
    meta: { title: "周期罗盘", group: "周期" },
  },
  {
    path: "/alerts",
    name: "alerts",
    component: () => import("@/views/AlertsView.vue"),
    meta: { title: "预警台", group: "预警" },
  },
  {
    path: "/history",
    name: "history",
    component: () => import("@/views/HistoryView.vue"),
    meta: { title: "世界长河", group: "周期" },
  },
  {
    path: "/ledger",
    name: "ledger",
    component: () => import("@/views/LedgerView.vue"),
    meta: { title: "预测台账", group: "预警" },
  },
  {
    path: "/principles",
    name: "principles",
    component: () => import("@/views/PrinciplesView.vue"),
    meta: { title: "原则库", group: "周期" },
  },
  {
    path: "/signals",
    name: "signals",
    component: () => import("@/views/SignalsView.vue"),
    meta: { title: "交易信号", group: "专题" },
  },
  {
    path: "/topics/:topicId?",
    name: "topics",
    component: () => import("@/views/TopicsView.vue"),
    meta: { title: "专题研判", group: "专题" },
  },
  {
    path: "/gold",
    redirect: (to) => ({ path: "/topics/gold", hash: to.hash, query: to.query }),
  },
  {
    path: "/lenses",
    name: "lenses",
    component: () => import("@/views/LensesView.vue"),
    meta: { title: "多透镜研判", group: "专题" },
  },
  {
    path: "/theses",
    name: "theses",
    component: () => import("@/views/ThesesView.vue"),
    meta: { title: "分析依据", group: "证据" },
  },
  {
    path: "/briefs",
    name: "briefs",
    component: () => import("@/views/BriefsView.vue"),
    meta: { title: "简报", group: "今日" },
  },
  {
    path: "/trades",
    name: "trades",
    component: () => import("@/views/TradesView.vue"),
    meta: { title: "交易", group: "今日" },
  },
  {
    path: "/journal",
    redirect: "/trades",
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
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition;
    if (to.hash) return { el: to.hash, top: 64, behavior: "smooth" };
    return { top: 0 };
  },
});

export default router;
