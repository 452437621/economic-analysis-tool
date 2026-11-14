<template>
  <Teleport to="body">
    <div class="scrim" :class="{ show: open }" @click="emit('close')"></div>
    <aside
      class="drawer"
      :class="[{ open }, width === 'settings' ? 'drawer--settings' : '']"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
    >
      <div class="drawer-head">
        <slot name="icon" />
        <span class="drawer-title">{{ title }}</span>
        <span v-if="sub" class="drawer-sub">{{ sub }}</span>
        <button class="icon-btn icon-close" type="button" aria-label="关闭" @click="emit('close')">
          <svg class="ic"><use href="#i-close" /></svg>
        </button>
      </div>
      <div class="drawer-body">
        <slot />
      </div>
      <div v-if="$slots.footer" class="drawer-foot">
        <slot name="footer" />
      </div>
    </aside>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    sub?: string;
    width?: "default" | "settings";
  }>(),
  { sub: "", width: "default" },
);

const emit = defineEmits<{ close: [] }>();

// 打开时锁定页面滚动 + Esc 关闭
function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.body.style.overflow = "hidden";
      document.addEventListener("keydown", onKeydown);
    } else {
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKeydown);
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  document.body.style.overflow = "";
  document.removeEventListener("keydown", onKeydown);
});
</script>
