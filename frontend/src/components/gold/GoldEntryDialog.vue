<template>
  <!-- 手动指标录入弹层 -->
  <Drawer :open="entry.open" title="录入手动指标" :sub="entry.code" @close="$emit('close')">
    <template #icon>
      <svg class="ic" style="color: var(--accent)"><use href="#i-plus" /></svg>
    </template>
    <div class="entry-intro">
      <b>{{ entry.name }}</b>
      <span>{{ entry.unit }} · {{ freqLabel(entry.freq) }} · 来源 {{ entry.manualSource }}</span>
    </div>
    <label class="entry-label" for="gold-entry-value">数值（{{ entry.unit || "—" }}）</label>
    <input
      id="gold-entry-value"
      v-model="entry.value"
      class="entry-input"
      type="number"
      step="any"
      placeholder="请输入数值，支持小数"
      @keyup.enter="$emit('submit')"
    />
    <label class="entry-label" for="gold-entry-date">数据日期</label>
    <input id="gold-entry-date" v-model="entry.asOf" class="entry-input" type="date" />
    <label class="entry-label" for="gold-entry-note">备注（可选）</label>
    <input
      id="gold-entry-note"
      v-model="entry.note"
      class="entry-input"
      type="text"
      maxlength="200"
      placeholder="数据来源 / 口径说明"
    />
    <div class="entry-tip">
      <svg class="ic"><use href="#i-info" /></svg>
      <span>仅标记为 manual 的指标允许手动写入；保存后自动刷新评分与覆盖率。</span>
    </div>
    <p v-if="entry.noteTip" class="entry-hint">{{ entry.noteTip }}</p>
    <template #footer>
      <button class="btn btn--sm btn--ghost" type="button" @click="$emit('close')">取消</button>
      <span class="spacer"></span>
      <button
        class="btn btn--sm btn--primary"
        type="button"
        :disabled="entry.saving || !entry.value"
        @click="$emit('submit')"
      >
        {{ entry.saving ? "保存中…" : "保存并刷新" }}
      </button>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import Drawer from "@/components/ui/Drawer.vue";
import type { EntryState } from "@/composables/useGoldOverview";
import { freqLabel } from "@/utils/goldFormat";

defineProps<{ entry: EntryState }>();

defineEmits<{ (e: "close"): void; (e: "submit"): void }>();
</script>

<style scoped>
/* ---------- 录入弹层 ---------- */
.entry-intro {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.entry-intro b {
  font-size: 12px;
}
.entry-intro span {
  font-size: 9.5px;
  color: var(--dim);
}
.entry-label {
  display: block;
  margin-bottom: 4px;
  font-size: 9.5px;
  color: var(--dim);
}
.entry-input {
  width: 100%;
  height: 32px;
  margin-bottom: 12px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  outline: none;
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 12px;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.entry-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}
.entry-input::placeholder {
  color: var(--dim);
}
.entry-tip {
  display: flex;
  gap: 6px;
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
.entry-tip .ic {
  width: 11px;
  height: 11px;
  margin-top: 1px;
  flex: none;
}
.entry-hint {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
</style>
