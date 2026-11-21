<template>
  <div v-if="analogSlots.some((item) => item)" class="cyc-analogy-row">
    <template v-for="(item, index) in analogSlots" :key="item?.month ?? `empty-${index}`">
      <RouterLink
        v-if="item"
        class="cyc-analogy"
        :to="{ path: '/pipeline', query: { code: 'cycle.analogs' } }"
      >
        <div>
          <div class="cyc-analogy-name">{{ item.month }}</div>
          <div class="cyc-analogy-sub">
            增长 {{ fmtNumber(item.state?.growth, 0) }} · 通胀 {{ fmtNumber(item.state?.inflation, 0) }}
          </div>
        </div>
        <div class="cyc-analogy-sim">
          <b>{{ ratioText(item.similarity) }}</b>
          <span>相似度</span>
        </div>
      </RouterLink>
      <div v-else class="cyc-analogy cyc-analogy--empty">
        <div>
          <div class="cyc-analogy-name">暂无更多类比</div>
          <div class="cyc-analogy-sub">样本内近邻不足 3 条</div>
        </div>
        <div class="cyc-analogy-sim"><b>—</b><span>相似度</span></div>
      </div>
    </template>
  </div>
  <EmptyState v-else text="暂无历史类比" hint="样本不足 24 个月时不会生成类比。" />
  <p v-if="Array.isArray(analogs?.caveats) && analogs.caveats.length" class="cyc-caveat">
    {{ analogs.caveats[0] }}
  </p>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtNumber } from "@/composables/useFormat";
import type { CycleAnalog, CycleAnalogs } from "@/api/types";
import type { RawOf } from "@/utils/cycleNormalize";
import { ratioText } from "@/utils/cycleFormat";

defineProps<{
  analogs: RawOf<CycleAnalogs>;
  analogSlots: Array<CycleAnalog | null>;
}>();
</script>

<style scoped>
/* ── E. 历史类比 ────────────────────────────────────── */
.cyc-analogy-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.cyc-analogy {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  height: 62px;
  padding: 8px 12px;
  text-align: left;
  text-decoration: none;
  color: inherit;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow);
  transition: border-color 0.12s, background 0.12s, transform 0.12s;
}
.cyc-analogy:hover {
  border-color: var(--accent-line);
  background: color-mix(in srgb, var(--accent) 4%, var(--surface));
  transform: translateY(-1px);
}
.cyc-analogy--empty {
  cursor: default;
  border-style: dashed;
  opacity: 0.72;
}
.cyc-analogy--empty:hover {
  border-color: var(--border);
  background: var(--surface);
  transform: none;
}
.cyc-analogy-name {
  font-size: 11.5px;
  font-weight: 600;
}
.cyc-analogy-sub {
  font-size: 9.5px;
  color: var(--dim);
  margin-top: 2px;
}
.cyc-analogy-sim {
  text-align: right;
  flex: none;
}
.cyc-analogy-sim b {
  display: block;
  font-family: var(--mono);
  font-size: 17px;
  font-weight: 600;
  color: var(--accent);
  line-height: 1.1;
}
.cyc-analogy-sim span {
  font-size: 8.5px;
  color: var(--dim);
}
.cyc-caveat {
  margin: 6px 2px 0;
  font-size: 9.5px;
  color: var(--dim);
  line-height: 1.5;
}
@media (max-width: 759px) {
  .cyc-analogy-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
