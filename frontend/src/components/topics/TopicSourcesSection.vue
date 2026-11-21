<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">数据源与手动指标</span>
      <span class="badge badge--sm" :class="okCount === providers.length ? 'badge--live' : 'badge--warn'">
        {{ okCount }}/{{ providers.length }} 正常
      </span>
      <div class="card-actions">
        <button v-if="canEdit" type="button" class="btn btn--sm" @click="openEntry()">
          <svg class="ic"><use href="#i-plus" /></svg>录入指标
        </button>
      </div>
    </div>
    <div v-if="providers.length" class="card-body table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>数据集</th><th>来源</th><th>状态</th><th>记录</th><th>最近检查</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in providers" :key="`${item.dataset || item.provider}`">
            <td>{{ item.dataset || "—" }}</td>
            <td>{{ providerLabel(item.provider) }}</td>
            <td>
              <span class="badge badge--sm" :class="providerState(item).tone">{{ providerState(item).label }}</span>
              <span v-if="item.error" class="topic-provider-error" :title="item.error">{{ item.error }}</span>
            </td>
            <td class="num">{{ item.records }}</td>
            <td class="muted">{{ providerTime(item.checked_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <EmptyState v-else text="暂无数据源运行记录" hint="等待采集任务首次运行。" />

    <div v-if="manual.length" class="card-body table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>手动指标</th><th>数值</th><th>单位</th><th>日期</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="item in manual" :key="item.code">
            <td>{{ item.name }}</td>
            <td class="num">{{ item.value ?? "—" }}</td>
            <td>{{ item.unit || "—" }}</td>
            <td>{{ item.as_of || "—" }}</td>
            <td>
              <button v-if="canEdit" type="button" class="link-btn" @click="openEntry(item)">录入</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Drawer :open="open" title="录入手动指标" :sub="form.code" @close="open = false">
      <template #icon>
        <svg class="ic" style="color: var(--accent)"><use href="#i-plus" /></svg>
      </template>
      <label class="topic-field-label" for="topic-manual-code">指标</label>
      <select id="topic-manual-code" v-model="form.code" class="topic-field">
        <option v-for="item in manual" :key="item.code" :value="item.code">
          {{ item.name }}（{{ item.unit || "—" }}）
        </option>
      </select>
      <label class="topic-field-label" for="topic-manual-value">数值</label>
      <input id="topic-manual-value" v-model="form.value" class="topic-field" type="number" step="any" />
      <label class="topic-field-label" for="topic-manual-date">数据日期</label>
      <input id="topic-manual-date" v-model="form.as_of" class="topic-field" type="date" />
      <label class="topic-field-label" for="topic-manual-note">备注（可选）</label>
      <textarea id="topic-manual-note" v-model="form.note" class="topic-field" rows="2"></textarea>
      <template #footer>
        <button type="button" class="btn btn--ghost" @click="open = false">取消</button>
        <button type="button" class="btn btn--primary" :disabled="saving || !valid" @click="submit">
          {{ saving ? "保存中" : "保存" }}
        </button>
      </template>
    </Drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicProvider, TopicSourcesData } from "@/api/types";
import { providerLabel, providerState, providerTime } from "@/utils/topicFormat";

const props = defineProps<{
  data: unknown;
  canEdit?: boolean;
  saving?: boolean;
}>();

const emit = defineEmits<{
  (e: "save-manual", payload: { code: string; value: number; as_of?: string; note?: string }): void;
}>();

const payload = computed(() => {
  const value = (props.data ?? {}) as Partial<TopicSourcesData>;
  return {
    providers: (value.providers ?? []) as TopicProvider[],
    manual: value.manual ?? [],
    manualEditable: Boolean(value.manualEditable),
  };
});
const providers = computed(() => payload.value.providers);
const manual = computed(() => payload.value.manual);
const canEdit = computed(() => Boolean(props.canEdit ?? payload.value.manualEditable));
const okCount = computed(() => providers.value.filter((item) => item.ok).length);

const open = ref(false);
const form = reactive({ code: "", value: "", as_of: "", note: "" });
const valid = computed(() => Boolean(form.code) && form.value !== "" && Number.isFinite(Number(form.value)));

function openEntry(item?: { code: string }) {
  const first = item?.code || manual.value[0]?.code || "";
  form.code = first;
  form.value = "";
  form.as_of = "";
  form.note = "";
  open.value = true;
}

function submit() {
  if (!valid.value) return;
  emit("save-manual", {
    code: form.code,
    value: Number(form.value),
    as_of: form.as_of || undefined,
    note: form.note || undefined,
  });
  open.value = false;
}
</script>

<style scoped>
.topic-provider-error {
  margin-left: 6px;
  font-size: 10px;
  color: var(--warn);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
  display: inline-block;
  vertical-align: bottom;
}
.topic-field-label {
  display: block;
  margin: 10px 0 4px;
  font-size: 10.5px;
  color: var(--muted);
}
.topic-field {
  width: 100%;
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface-2);
  color: var(--text);
  font-size: 11.5px;
}
</style>
