<template>
  <span
    class="zh-text"
    :class="inline ? 'zh-text--inline' : 'zh-text--stack'"
    :title="hint"
  >
    <template v-if="zh">
      <span class="zh-text__main">{{ zh }}</span>
      <span v-if="original" class="zh-text__original is-original">{{ text }}</span>
    </template>
    <template v-else>{{ text }}</template>
  </span>
</template>

<script setup lang="ts">
/**
 * 英文文本的中文对照展示：有译文时中文为主、英文原文以次要小字附在下方（inline 时同一行），
 * 没有译文时原样显示英文并给 title 提示「暂无中文对照」；纯中文文本不重复展示。
 *
 * 翻译由 useZhTranslate 自动批量请求（模块级共享缓存与队列，同一屏只会发一批）。
 */
import { computed } from "vue";
import { useZhTranslate } from "@/composables/useZhTranslate";

const props = withDefaults(
  defineProps<{
    /** 英文原文；纯中文时原样显示 */
    text?: string | null;
    /** 有译文时是否保留英文原文行，默认保留 */
    original?: boolean;
    /** true = 中文与英文同行；false = 中文在上、英文原文本行在下 */
    inline?: boolean;
  }>(),
  { text: "", original: true, inline: false },
);

const { zhFor, statusFor } = useZhTranslate(() => [props.text ?? ""]);

const zh = computed(() => zhFor(props.text));
const hint = computed(() => (statusFor(props.text) === "none" ? "暂无中文对照" : undefined));
</script>

<style scoped>
.zh-text {
  min-width: 0;
}

.zh-text--stack {
  display: inline-flex;
  flex-direction: column;
  vertical-align: top;
}

.zh-text--inline {
  display: inline;
}

.zh-text__main {
  color: inherit;
}

.zh-text__original.is-original {
  color: var(--muted);
  font-size: 0.92em;
  line-height: 1.35;
}

.zh-text--stack .zh-text__original.is-original {
  color: var(--muted);
  font-size: 0.86em;
  margin-top: 1px;
  opacity: 0.9;
  white-space: normal;
}

.zh-text--inline .zh-text__original.is-original {
  margin-left: 6px;
}
</style>
