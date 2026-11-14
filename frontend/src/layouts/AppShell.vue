<template>
  <div class="app-shell">
    <Sidebar />
    <Topbar @open-palette="paletteOpen = true" @open-alerts="alerts.open = true" @open-settings="prefs.settingsOpen = true" />
    <main class="main">
      <RouterView v-slot="{ Component }">
        <Transition name="fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
    <CommandPalette v-model:open="paletteOpen" />
    <SettingsDrawer />
    <AlertsDrawer v-model:open="alerts.open" />
    <EvidenceDrawer />
    <HistoryModal v-if="historyStore.open" />
    <ToastHost />
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import Sidebar from "@/layouts/Sidebar.vue";
import Topbar from "@/layouts/Topbar.vue";
import CommandPalette from "@/components/domain/CommandPalette.vue";
import SettingsDrawer from "@/components/domain/SettingsDrawer.vue";
import AlertsDrawer from "@/components/domain/AlertsDrawer.vue";
import EvidenceDrawer from "@/components/domain/EvidenceDrawer.vue";
import ToastHost from "@/components/ui/ToastHost.vue";
import { usePrefsStore } from "@/stores/prefs";
import { useHealthStore } from "@/stores/health";
import { useAlertsStore } from "@/stores/alerts";
import { useHistoryStore } from "@/stores/history";
import { useEvidenceStore } from "@/stores/evidence";

// 历史走势依赖 ECharts（约 636 KB）：仅在首次打开时加载，避免拖慢首屏。
const HistoryModal = defineAsyncComponent(() => import("@/components/domain/HistoryModal.vue"));

const prefs = usePrefsStore();
const health = useHealthStore();
const alerts = useAlertsStore();
const historyStore = useHistoryStore();
const evidence = useEvidenceStore();
const route = useRoute();
const router = useRouter();

const paletteOpen = ref(false);

let healthTimer: number | null = null;
let alertsTimer: number | null = null;

function onKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null;
  const typing =
    target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    paletteOpen.value = true;
    return;
  }
  if (event.key === "/" && !typing) {
    event.preventDefault();
    paletteOpen.value = true;
    return;
  }
  if (event.key === "Escape") {
    if (paletteOpen.value) paletteOpen.value = false;
    else if (prefs.settingsOpen) prefs.settingsOpen = false;
    else if (alerts.open) alerts.open = false;
  }
}

watch(
  () => route.meta.title,
  (title) => {
    document.title = title ? `${String(title)} · EPIC` : "EPIC · 宏观市场交易工作台";
  },
  { immediate: true },
);

watch(
  () => prefs.density,
  (density) => {
    document.body.classList.toggle("is-compact", density === "compact");
  },
  { immediate: true },
);

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
  void health.refresh();
  void alerts.refresh();
  healthTimer = window.setInterval(() => void health.refresh(), 30000);
  alertsTimer = window.setInterval(() => void alerts.refresh(), 30000);
  applyDeepLinks();
});

/** 兼容旧版深链：?doc= / ?history=kind:key / ?brief= / ?palette=1 / ?settings=1 */
function applyDeepLinks(): void {
  const params = new URLSearchParams(location.search);
  if (params.get("palette") === "1") paletteOpen.value = true;
  if (params.get("settings") === "1") prefs.settingsOpen = true;
  if (params.get("alerts") === "1") alerts.open = true;
  const doc = params.get("doc");
  if (doc) void evidence.show(doc);
  const historyParam = params.get("history");
  if (historyParam) {
    const [kind, key] = historyParam.includes(":")
      ? (historyParam.split(":") as [string, string])
      : (["macro", historyParam] as [string, string]);
    void historyStore.openHistory(kind === "instrument" ? "instrument" : "macro", key, key);
  }
  const briefParam = params.get("brief");
  if (briefParam) void router.push({ path: "/briefs", query: { kind: briefParam } });
}

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  if (healthTimer !== null) window.clearInterval(healthTimer);
  if (alertsTimer !== null) window.clearInterval(alertsTimer);
});
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}
</style>
