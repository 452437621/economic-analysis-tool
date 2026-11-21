<template>
  <Teleport to="body">
    <div class="palette-wrap" :class="{ open }" @click.self="close">
      <div class="palette" role="dialog" aria-modal="true" aria-label="命令面板">
        <div class="palette-input">
          <svg class="ic"><use href="#i-command" /></svg>
          <input
            ref="inputRef"
            v-model="query"
            type="text"
            placeholder="搜索页面、标的或执行命令…"
            autocomplete="off"
            spellcheck="false"
            @keydown.down.prevent="move(1)"
            @keydown.up.prevent="move(-1)"
            @keydown.enter.prevent="execute(activeIndex)"
            @keydown.esc.prevent="close"
          />
          <span class="kbd">ESC</span>
        </div>
        <div class="palette-list">
          <template v-for="group in filteredGroups" :key="group.label">
            <div class="palette-group">{{ group.label }}</div>
            <div
              v-for="item in group.items"
              :key="item.id"
              class="palette-item"
              :class="{ active: flatItems[activeIndex]?.id === item.id }"
              @mouseenter="setActive(item.id)"
              @click="run(item)"
            >
              <svg class="ic"><use :href="item.icon" /></svg>
              <span>{{ item.label }}</span>
              <span class="pi-hint">{{ item.hint }}</span>
            </div>
          </template>
          <div v-if="!flatItems.length" class="palette-empty">没有匹配的页面、标的或命令</div>
        </div>
        <div class="palette-foot">
          <span><span class="kbd">↑</span> <span class="kbd">↓</span> 选择</span>
          <span><span class="kbd">Enter</span> 执行</span>
          <span><span class="kbd">Esc</span> 关闭</span>
          <span class="spacer"></span>
          <span>{{ flatItems.length }} 项</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { usePrefsStore } from "@/stores/prefs";
import { useToast } from "@/stores/toast";
import { getWatchCandidates } from "@/api/endpoints";
import type { WatchCandidate } from "@/api/types";

interface PaletteItem {
  id: string;
  label: string;
  hint: string;
  icon: string;
  kind: "page" | "action" | "symbol";
  run: () => void | Promise<void>;
}

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();

const router = useRouter();
const prefs = usePrefsStore();
const toast = useToast();

const inputRef = ref<HTMLInputElement | null>(null);
const query = ref("");
const activeIndex = ref(0);
const candidates = ref<WatchCandidate[]>([]);

const PAGES: PaletteItem[] = [
  { id: "page-overview", label: "总览", hint: "工作台", icon: "#i-grid", kind: "page", run: () => { void router.push("/"); } },
  { id: "page-market", label: "市场行情", hint: "工作台", icon: "#i-chart", kind: "page", run: () => { void router.push("/market"); } },
  { id: "page-rates", label: "利率与流动性", hint: "研究分析", icon: "#i-rates", kind: "page", run: () => { void router.push("/rates"); } },
  { id: "page-topics", label: "专题研判", hint: "研究分析", icon: "#i-flame", kind: "page", run: () => { void router.push("/topics"); } },
  { id: "page-gold", label: "黄金研判", hint: "专题", icon: "#i-flame", kind: "page", run: () => { void router.push("/topics/gold"); } },
  { id: "page-luoyang", label: "洛阳钼业研判", hint: "专题", icon: "#i-target", kind: "page", run: () => { void router.push("/topics/luoyang"); } },
  { id: "page-analysis", label: "分析引擎", hint: "研究分析", icon: "#i-cpu", kind: "page", run: () => { void router.push("/analysis"); } },
  { id: "page-signals", label: "交易信号", hint: "研究分析", icon: "#i-activity", kind: "page", run: () => { void router.push("/signals"); } },
  { id: "page-theses", label: "分析依据", hint: "研究分析", icon: "#i-branch", kind: "page", run: () => { void router.push("/theses"); } },
  { id: "page-briefs", label: "简报与日志", hint: "内容", icon: "#i-file", kind: "page", run: () => { void router.push("/briefs"); } },
  { id: "page-system", label: "系统状态", hint: "系统", icon: "#i-db", kind: "page", run: () => { void router.push("/system"); } },
];

const actions = computed<PaletteItem[]>(() => [
  {
    id: "action-theme",
    label: prefs.resolvedTheme === "dark" ? "切换到浅色主题" : "切换到深色主题",
    hint: "外观",
    icon: "#i-palette",
    kind: "action",
    run: () => prefs.setThemeMode(prefs.resolvedTheme === "dark" ? "light" : "dark"),
  },
  {
    id: "action-settings",
    label: "打开设置",
    hint: "外观 / 数据 / 偏好",
    icon: "#i-settings",
    kind: "action",
    run: () => {
      prefs.settingsOpen = true;
    },
  },
  {
    id: "action-refresh",
    label: "刷新页面数据",
    hint: "重新加载",
    icon: "#i-refresh",
    kind: "action",
    run: () => {
      location.reload();
    },
  },
]);

const symbolItems = computed<PaletteItem[]>(() =>
  candidates.value.slice(0, 30).map((item) => ({
    id: `symbol-${item.symbol}`,
    label: `${item.symbol} · ${item.name}`,
    hint: item.watched ? "已在自选 · 打开历史走势" : "打开历史走势",
    icon: "#i-chart",
    kind: "symbol" as const,
    run: () => {
      void router.push({ path: "/market", query: { symbol: item.symbol } });
    },
  })),
);

const flatItems = computed<PaletteItem[]>(() => {
  const keyword = query.value.trim().toLowerCase();
  const match = (item: PaletteItem) =>
    !keyword ||
    item.label.toLowerCase().includes(keyword) ||
    item.hint.toLowerCase().includes(keyword) ||
    item.id.includes(keyword);
  return [...PAGES, ...actions.value, ...symbolItems.value].filter(match);
});

const filteredGroups = computed(() => {
  const items = flatItems.value;
  const list = [
    { label: "页面", items: items.filter((item) => item.kind === "page") },
    { label: "命令", items: items.filter((item) => item.kind === "action") },
    { label: "标的", items: items.filter((item) => item.kind === "symbol") },
  ];
  return list.filter((group) => group.items.length > 0);
});

let lastId = "";

function move(step: number): void {
  const total = flatItems.value.length;
  if (!total) return;
  activeIndex.value = (activeIndex.value + step + total) % total;
  lastId = flatItems.value[activeIndex.value]?.id ?? "";
}

function setActive(id: string): void {
  const index = flatItems.value.findIndex((item) => item.id === id);
  if (index >= 0) activeIndex.value = index;
}

function execute(index: number): void {
  const item = flatItems.value[index];
  if (item) void run(item);
}

async function run(item: PaletteItem): Promise<void> {
  close();
  try {
    await item.run();
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : String(err));
  }
}

function close(): void {
  emit("update:open", false);
}

watch(
  () => props.open,
  async (open) => {
    if (!open) return;
    query.value = "";
    activeIndex.value = 0;
    candidates.value = candidates.value.length ? candidates.value : ((await getWatchCandidates()).data ?? []);
    await nextTick();
    inputRef.value?.focus();
  },
);

watch(query, () => {
  activeIndex.value = 0;
});
</script>
