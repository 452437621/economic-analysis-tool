<template>
  <aside class="card hst-detail">
    <div class="card-head">
      <span class="card-title">事件详情</span>
      <span v-if="event" class="card-sub">{{ event.year }} 年</span>
      <span v-else-if="contextYear !== null" class="card-sub">时间切片</span>
      <div v-if="event || contextYear !== null" class="card-actions">
        <button class="icon-btn" type="button" aria-label="清除选中" @click="emit('close')">
          <svg class="ic"><use href="#i-close" /></svg>
        </button>
      </div>
    </div>

    <div class="card-body hst-detail-body">
      <template v-if="event">
        <div class="hst-detail-kicker">
          {{ event.year }}<template v-if="event.month">-{{ String(event.month).padStart(2, "0") }}</template>
          · {{ event.layer_label }}
        </div>
        <h2 class="hst-detail-title">{{ event.title }}</h2>
        <div class="hst-detail-badges">
          <span class="badge badge--sm">{{ event.category_label }}</span>
          <span v-if="event.power_label" class="badge badge--sm">{{ event.power_label }}</span>
          <span class="badge badge--sm" :class="gradeClass(event.evidence_grade)">证据 {{ event.evidence_grade }}</span>
        </div>

        <div class="hst-detail-desc">
          {{ event.summary || "该事件暂无摘要，请查看来源链接或同期事件。" }}
        </div>

        <section class="hst-detail-block">
          <h3>对今天的影响</h3>
          <p>{{ impactText }}</p>
        </section>

        <dl class="hst-detail-kv">
          <div>
            <dt>类别</dt>
            <dd>{{ event.category_label }}</dd>
          </div>
          <div>
            <dt>层级</dt>
            <dd>{{ event.layer_label }}</dd>
          </div>
          <div>
            <dt>相关势力</dt>
            <dd>{{ event.power_label || "—" }}</dd>
          </div>
          <div>
            <dt>证据级</dt>
            <dd>{{ event.evidence_grade }} 级</dd>
          </div>
        </dl>

        <a v-if="event.source_url" class="hst-src" :href="event.source_url" target="_blank" rel="noreferrer noopener">
          打开原始来源
          <svg class="ic"><use href="#i-external" /></svg>
        </a>
        <p v-else class="hst-detail-muted">该事件为叙事判断，未附单一来源，请结合多份史料交叉核对。</p>

        <section v-if="related.length" class="hst-detail-related">
          <h3>同期关键事件</h3>
          <button v-for="item in related" :key="item.id" type="button" class="hst-related-item" @click="emit('select', item)">
            <span class="mono">{{ item.year }}</span>
            <span>{{ item.title }}</span>
          </button>
        </section>

        <p class="hst-detail-foot">事件编号 {{ event.id }} · 年表为精选，不作为完整性证明。</p>
      </template>

      <template v-else-if="contextYear !== null">
        <div class="hst-detail-kicker">时间切片 · 前后 30 年</div>
        <h2 class="hst-detail-title">{{ contextYear }} 年前后</h2>
        <p class="hst-detail-muted">点击时间轴空白年份得到该切片；点选下面的事件可查看完整影响。</p>
        <div v-if="nearby.length" class="hst-detail-related">
          <h3>该年附近的事件（{{ nearby.length }} 条）</h3>
          <button v-for="item in nearby" :key="item.id" type="button" class="hst-related-item" @click="emit('select', item)">
            <span class="mono">{{ item.year }}</span>
            <span>{{ item.title }}</span>
            <span class="hst-related-layer">{{ item.layer_label }}</span>
          </button>
        </div>
        <p v-else class="hst-detail-muted">该年前后 30 年没有收录事件，试试点击其它年份或时间轴上的事件标记。</p>
      </template>

      <div v-else class="hst-detail-empty">
        <div class="hst-detail-empty-icon"><svg class="ic"><use href="#i-pin" /></svg></div>
        <p>点击时间轴上的<strong>事件标记</strong>，或点击任意<strong>空白年份</strong>查看该时期的影响与来源。</p>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { TimelineEventItem } from "@/api/types";

interface Props {
  event: TimelineEventItem | null;
  contextYear: number | null;
  nearby: TimelineEventItem[];
  related: TimelineEventItem[];
}

const props = withDefaults(defineProps<Props>(), {
  event: null,
  contextYear: null,
  nearby: () => [],
  related: () => [],
});

const emit = defineEmits<{
  (event: "close"): void;
  (event: "select", item: TimelineEventItem): void;
}>();

const impactText = computed(() => {
  const paragraphs = (props.event?.summary ?? "")
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);
  return paragraphs.length > 1 ? paragraphs.slice(1).join("\n\n") : "该事件的当代映射见历史类比。";
});

const gradeClass = (grade: string | null | undefined) => {
  if (grade === "A") return "badge--accent";
  if (grade === "B") return "badge--live";
  if (grade === "C" || grade === "D") return "badge--warn";
  return "";
};
</script>

<style scoped>
.hst-detail {
  position: sticky;
  top: calc(var(--topbar-h) + 10px);
  min-width: 0;
}
.hst-detail-body {
  padding: 12px 13px;
}
.hst-detail-kicker {
  font-size: 9.5px;
  letter-spacing: 0.3px;
  color: var(--dim);
  font-family: var(--mono);
}
.hst-detail-title {
  margin-top: 3px;
  font-size: 13.5px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--text);
}
.hst-detail-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 7px;
}
.hst-detail-desc {
  margin-top: 9px;
  max-height: 220px;
  overflow-y: auto;
  font-size: 11px;
  line-height: 1.65;
  color: var(--muted);
  white-space: pre-wrap;
}
.hst-detail-block {
  margin-top: 11px;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.hst-detail-block h3 {
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.3px;
  color: var(--accent);
}
.hst-detail-block p {
  margin-top: 4px;
  font-size: 10.5px;
  line-height: 1.65;
  color: var(--muted);
  white-space: pre-wrap;
}
.hst-detail-kv {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px 10px;
  margin-top: 11px;
}
.hst-detail-kv dt {
  font-size: 9px;
  color: var(--dim);
}
.hst-detail-kv dd {
  margin-top: 1px;
  font-size: 10.5px;
  color: var(--text);
}
.hst-src {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 11px;
  font-size: 10px;
  color: var(--accent);
  text-decoration: none;
}
.hst-src:hover {
  text-decoration: underline;
}
.hst-src .ic {
  width: 11px;
  height: 11px;
}
.hst-detail-muted {
  margin-top: 9px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--dim);
}
.hst-detail-related {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}
.hst-detail-related h3 {
  font-size: 10px;
  font-weight: 650;
  color: var(--muted);
  margin-bottom: 5px;
}
.hst-related-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  width: 100%;
  padding: 4px 5px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 10px;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
}
.hst-related-item:hover {
  background: var(--surface-2);
}
.hst-related-item .mono {
  flex: none;
  font-size: 9.5px;
  color: var(--accent);
}
.hst-related-layer {
  flex: none;
  margin-left: auto;
  font-size: 8.5px;
  color: var(--dim);
}
.hst-detail-foot {
  margin-top: 11px;
  font-size: 9px;
  color: var(--dim);
}
.hst-detail-empty {
  padding: 16px 4px 8px;
  text-align: center;
  color: var(--muted);
}
.hst-detail-empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: 50%;
  color: var(--dim);
  background: var(--surface-2);
}
.hst-detail-empty-icon .ic {
  width: 14px;
  height: 14px;
}
.hst-detail-empty p {
  margin-top: 9px;
  font-size: 10.5px;
  line-height: 1.65;
}
.hst-detail-empty strong {
  color: var(--text);
  font-weight: 600;
}
</style>
