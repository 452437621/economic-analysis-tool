<template>
  <Drawer
    :open="open"
    title="告警中心"
    :sub="alerts.unread ? `${alerts.unread} 条未确认` : '无未确认告警'"
    @close="close"
  >
    <template #icon>
      <svg class="ic" style="color: var(--warn)"><use href="#i-bell" /></svg>
    </template>

    <ErrorState v-if="alerts.error" :error="alerts.error" @retry="alerts.refresh()" />
    <EmptyState v-else-if="!alerts.items.length && !alerts.loading" text="暂无告警" hint="价格 / 利差 / 事件 / 持仓 等规则触发后会出现在这里。" />
    <div v-else class="alerts-list">
      <div v-for="alert in alerts.items" :key="alert.id" class="alert-row">
        <span class="sev" :class="severityClass(alert.level)"></span>
        <div>
          <div class="alert-text"><ZhText :text="alert.title" /></div>
          <div class="alert-meta">
            <span>{{ kindLabel(alert.kind) }}</span>
            <span v-if="alert.message"><ZhText :text="alert.message" inline /></span>
          </div>
        </div>
        <div class="alert-actions">
          <span class="alert-time">{{ fmtTime(alert.created_at, true) }}</span>
          <button
            v-if="!alert.acknowledged"
            class="btn btn--sm btn--ghost"
            type="button"
            @click="ack(alert.id)"
          >
            确认
          </button>
          <span v-else class="badge badge--sm">已确认</span>
        </div>
      </div>
    </div>

    <template #footer>
      <button class="btn btn--sm btn--ghost" type="button" @click="alerts.refresh()">
        <svg class="ic"><use href="#i-refresh" /></svg>刷新
      </button>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--primary" type="button" @click="close">关闭</button>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import ZhText from "@/components/ui/ZhText.vue";
import { useAlertsStore } from "@/stores/alerts";
import { useToast } from "@/stores/toast";
import { fmtTime } from "@/composables/useFormat";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();
const alerts = useAlertsStore();
const toast = useToast();

function close(): void {
  emit("update:open", false);
}

function severityClass(level: string): string {
  if (level === "critical") return "sev--critical";
  if (level === "warn") return "sev--warn";
  return "sev--info";
}

function kindLabel(kind: string): string {
  const labels: Record<string, string> = {
    price: "价格告警",
    rate: "利差告警",
    event: "事件告警",
    position: "持仓告警",
    data: "数据源告警",
  };
  return labels[kind] ?? kind;
}

async function ack(id: string): Promise<void> {
  try {
    await alerts.acknowledge(id);
    toast.ok("告警已确认");
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : String(err));
  }
}
</script>

<style scoped>
.alerts-list {
  display: flex;
  flex-direction: column;
}
.alert-row {
  align-items: start;
}
.alert-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
</style>
