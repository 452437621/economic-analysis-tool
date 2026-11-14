<template>
  <Drawer :open="open" title="自选管理" sub="拖拽排序 · 增删 · 分组 / 优先级" @close="close">
    <template #icon>
      <svg class="ic" style="color: var(--accent)"><use href="#i-grid" /></svg>
    </template>

    <div class="wm-toolbar">
      <span class="wm-hint">拖动卡片调整顺序，或使用 ↑/↓ 微调；「保存顺序」写入服务端。</span>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--ghost" type="button" :disabled="!dirty || saving" @click="saveOrder">
        <svg class="ic"><use href="#i-shield-check" /></svg>保存顺序
      </button>
    </div>

    <ErrorState v-if="error" :error="error" @retry="reload" />
    <SkeletonBlock v-else-if="loading && !items.length" :rows="6" />
    <EmptyState v-else-if="!items.length" text="暂无自选标的" hint="在下方选择标的添加。" />
    <div v-else ref="listRef" class="wm-list">
      <div
        v-for="item in items"
        :key="item.symbol"
        class="wm-item"
        :data-symbol="item.symbol"
      >
        <span class="wm-drag" title="拖拽排序">⋮⋮</span>
        <div class="wm-main">
          <div class="wm-name">
            {{ item.name }}
            <span class="wm-code">{{ item.symbol }}</span>
            <span v-if="item.group" class="badge badge--sm">{{ item.group }}</span>
            <span class="badge badge--sm">P{{ item.priority }}</span>
          </div>
          <div class="wm-sub">
            <span>最新 <b>{{ fmtPrice(item.price, item.asset_class) }}</b></span>
            <span :class="trendClass(item.change_pct)">{{ fmtPct(item.change_pct) }}</span>
            <span v-if="item.note" class="dim">{{ item.note }}</span>
          </div>
        </div>
        <div class="wm-actions">
          <button class="icon-btn" type="button" title="上移" @click="move(item.symbol, 'up')">↑</button>
          <button class="icon-btn" type="button" title="下移" @click="move(item.symbol, 'down')">↓</button>
          <button class="icon-btn" type="button" title="移出自选" @click="remove(item.symbol)">×</button>
        </div>
      </div>
    </div>

    <div class="wm-add">
      <div class="set-title">添加自选</div>
      <div class="wm-add-row">
        <select v-model="form.symbol" class="wm-input wm-select">
          <option value="" disabled>选择标的…</option>
          <option v-for="candidate in candidates" :key="candidate.symbol" :value="candidate.symbol">
            {{ candidate.symbol }} · {{ candidate.name }}
          </option>
        </select>
        <input v-model="form.group" class="wm-input" placeholder="分组（可选）" />
        <select v-model.number="form.priority" class="wm-input wm-priority">
          <option v-for="level in [1, 2, 3, 4, 5]" :key="level" :value="level">P{{ level }}</option>
        </select>
        <button class="btn btn--sm btn--primary" type="button" :disabled="!form.symbol || adding" @click="add">
          添加
        </button>
      </div>
      <div class="set-note">数据来自 /api/watchlist/candidates；已加入自选的标的不会重复出现。</div>
    </div>

    <template #footer>
      <span class="wm-status">{{ statusText }}</span>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--primary" type="button" @click="close">完成</button>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import Sortable from "sortablejs";
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import {
  addWatch,
  getWatchCandidates,
  getWatchlist,
  moveWatch,
  removeWatch,
  reorderWatch,
} from "@/api/endpoints";
import type { WatchCandidate, WatchlistItem } from "@/api/types";
import { fmtPct, fmtPrice, trendClass } from "@/composables/useFormat";
import { useToast } from "@/stores/toast";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();

const toast = useToast();
const items = ref<WatchlistItem[]>([]);
const candidates = ref<WatchCandidate[]>([]);
const loading = ref(false);
const saving = ref(false);
const adding = ref(false);
const error = ref<unknown>(null);
const dirty = ref(false);
const listRef = ref<HTMLElement | null>(null);
const form = ref({ symbol: "", group: "", priority: 3 });
let sortable: Sortable | null = null;

const statusText = computed(() => {
  if (dirty.value) return "顺序已修改，尚未保存";
  return `${items.value.length} 个自选 · 拖拽或 ↑↓ 调整`;
});

async function reload(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [watchPayload, candidatePayload] = await Promise.all([getWatchlist(), getWatchCandidates()]);
    items.value = watchPayload.data ?? [];
    candidates.value = (candidatePayload.data ?? []).filter((item) => !item.watched);
    dirty.value = false;
  } catch (err) {
    error.value = err;
  } finally {
    loading.value = false;
  }
}

function initSortable(): void {
  sortable?.destroy();
  sortable = null;
  if (!listRef.value) return;
  sortable = Sortable.create(listRef.value, {
    animation: 140,
    handle: ".wm-drag",
    ghostClass: "wm-ghost",
    onEnd: (event) => {
      if (event.oldIndex === undefined || event.newIndex === undefined) return;
      if (event.oldIndex === event.newIndex) return;
      const list = [...items.value];
      const [moved] = list.splice(event.oldIndex, 1);
      list.splice(event.newIndex, 0, moved);
      items.value = list;
      dirty.value = true;
    },
  });
}

async function saveOrder(): Promise<void> {
  saving.value = true;
  try {
    await reorderWatch(items.value.map((item) => item.symbol));
    dirty.value = false;
    toast.ok("自选顺序已保存");
    await reload();
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : String(err));
  } finally {
    saving.value = false;
  }
}

async function move(symbol: string, direction: "up" | "down"): Promise<void> {
  try {
    await moveWatch(symbol, direction);
    await reload();
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : String(err));
  }
}

async function remove(symbol: string): Promise<void> {
  try {
    await removeWatch(symbol);
    toast.ok(`已移出 ${symbol}`);
    await reload();
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : String(err));
  }
}

async function add(): Promise<void> {
  if (!form.value.symbol) return;
  adding.value = true;
  try {
    await addWatch({
      symbol: form.value.symbol,
      group: form.value.group.trim() || null,
      priority: form.value.priority,
    });
    toast.ok(`已添加 ${form.value.symbol}`);
    form.value = { symbol: "", group: "", priority: 3 };
    await reload();
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : String(err));
  } finally {
    adding.value = false;
  }
}

function close(): void {
  if (dirty.value) {
    toast.warn("顺序未保存，已按服务端顺序关闭");
    reload().catch(() => undefined);
  }
  emit("update:open", false);
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      void reload();
      void nextTick(() => initSortable());
    } else {
      sortable?.destroy();
      sortable = null;
    }
  },
);

watch(items, () => nextTick(() => initSortable()));

onBeforeUnmount(() => {
  sortable?.destroy();
  sortable = null;
});
</script>

<style scoped>
.wm-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.wm-hint {
  font-size: 10px;
  color: var(--dim);
  line-height: 1.5;
}
.wm-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.wm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.wm-ghost {
  opacity: 0.4;
  border-style: dashed;
}
.wm-drag {
  cursor: grab;
  color: var(--dim);
  font-size: 12px;
  letter-spacing: -2px;
  user-select: none;
}
.wm-main {
  min-width: 0;
  flex: 1;
}
.wm-name {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
}
.wm-code {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--dim);
  font-weight: 400;
}
.wm-sub {
  display: flex;
  gap: 8px;
  margin-top: 1px;
  font-size: 9.5px;
  color: var(--muted);
}
.wm-sub b {
  font-family: var(--mono);
  font-weight: 600;
}
.wm-actions {
  display: flex;
  gap: 3px;
}
.wm-actions .icon-btn {
  width: 24px;
  height: 22px;
  font-size: 11px;
}
.wm-add {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.wm-add-row {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.wm-input {
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 11px;
}
.wm-input:focus {
  outline: none;
  border-color: var(--accent-line);
}
.wm-select {
  flex: 1 1 200px;
  min-width: 0;
}
.wm-priority {
  width: 64px;
}
.wm-status {
  font-size: 10px;
  color: var(--dim);
}
.dim {
  color: var(--dim);
}
</style>
