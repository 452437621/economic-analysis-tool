<template>
  <section class="card lens-card">
    <div class="card-head">
      <span class="card-title">AI 解读（可选）</span>
      <span class="spacer"></span>
      <span class="badge badge--sm" :class="ping?.available ? 'badge--up' : 'badge--warn'">
        {{ ping?.available ? `LLM 可用 · ${ping.model}` : "LLM 未配置" }}
      </span>
    </div>
    <div class="card-body">
      <div class="lens-form">
        <label class="lens-form-wide">问题
          <input v-model="question" type="text" maxlength="200" placeholder="不填则让模型给当前状态做 300 字解读" />
        </label>
        <button class="btn btn--sm" type="button" :disabled="loading || !ping?.available" @click="emit('ask', question)">
          {{ loading ? "生成中" : "生成解读" }}
        </button>
      </div>
      <p v-if="error" class="lens-comment-error">{{ error }}</p>
      <p v-if="commentary" class="lens-commentary">{{ commentary }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";
import type { LensPing } from "@/api/types";

defineProps<{
  ping: LensPing | null;
  commentary: string;
  error: string;
  loading: boolean;
}>();

const emit = defineEmits<{ ask: [question: string] }>();

const question = ref("");
</script>

<style scoped>
.lens-card { overflow: hidden; }
.card-body { padding: 12px; }
.lens-form {
  display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end;
}
.lens-form label {
  display: flex; flex-direction: column; gap: 4px; font-size: 10.5px; color: var(--dim);
}
.lens-form input, .lens-form select {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 5px;
  color: var(--text); font-size: 12px; padding: 6px 8px; min-width: 110px;
}
.lens-form-wide { flex: 1 1 240px; }
.lens-form-wide input { width: 100%; }
.lens-commentary { margin: 12px 0 0; font-size: 12px; line-height: 1.75; color: var(--text); white-space: pre-wrap; }
.lens-comment-error { margin: 10px 0 0; font-size: 11.5px; color: var(--down); }
</style>
