<template>
  <section class="card pipe-deriv-card">
    <header class="card-head">
      <span class="card-title">
        推导清单
        <span class="card-sub">{{ derivations.length }} 条 · 点击行在溯源树查看</span>
      </span>
      <div class="card-actions pipe-deriv-actions">
        <label class="field pipe-filter-field">
          <svg class="ic"><use href="#i-filter" /></svg>
          <input v-model="codeFilter" class="mono" type="text" placeholder="按 code 过滤，如 cycle.state.world" />
        </label>
        <button class="btn btn--ghost btn--sm" type="button" @click="emit('refresh')">
          <svg class="ic"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </header>
    <div class="card-body pipe-deriv-body">
      <SkeletonBlock v-if="loading && !derivations.length" :rows="4" />
      <ErrorState v-else-if="error && !derivations.length" :error="error" @retry="emit('refresh')" />
      <EmptyState
        v-else-if="!derivations.length"
        :text="codeFilter ? '没有匹配该 code 的推导' : '暂无推导数据'"
        :hint="codeFilter ? '试试清空过滤条件。' : '运行分析任务后会生成带证据链的推导。'"
      />
      <div v-else class="table-wrap pipe-table-wrap">
        <table class="data-table pipe-deriv-table">
          <thead>
            <tr>
              <th>结论</th>
              <th>code</th>
              <th>证据</th>
              <th class="num">置信度</th>
              <th>措辞</th>
              <th>观测日</th>
              <th class="num">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in derivations"
              :key="item.id"
              class="pipe-deriv-row"
              :class="{ 'pipe-deriv-row--active': item.id === selectedDerivation?.id }"
              @click="emit('select', item.id)"
            >
              <td class="pipe-claim-cell">{{ item.claim }}</td>
              <td class="mono pipe-code-cell">{{ item.code }}</td>
              <td><span class="badge badge--sm" :class="gradeClass(item.evidence_grade)">{{ item.evidence_grade }}</span></td>
              <td class="num mono">{{ confidencePct(item.confidence) }}</td>
              <td class="muted">{{ confidenceLabel(item.confidence) }}</td>
              <td class="mono dim">{{ fmtDate(item.asof) }}</td>
              <td class="num pipe-deriv-ops">
                <button class="link-btn" type="button" @click.stop="emit('select', item.id)">溯源</button>
                <button class="link-btn" type="button" @click.stop="emit('open', item.id)">为什么 →</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { V2Derivation } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDate } from "@/composables/useFormat";
import { confidenceLabel, confidencePct, gradeClass } from "@/utils/pipelineStatus";

defineProps<{
  derivations: V2Derivation[];
  loading: boolean;
  error: Error | null;
  selectedDerivation: V2Derivation | null;
}>();

const codeFilter = defineModel<string>("codeFilter", { required: true });

const emit = defineEmits<{
  refresh: [];
  select: [id: string];
  open: [id: string];
}>();
</script>

<style scoped>
.pipe-deriv-card {
  margin-top: 12px;
}
.pipe-deriv-actions {
  flex-wrap: wrap;
  row-gap: 4px;
}
.pipe-filter-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: 240px;
  max-width: 100%;
  height: 26px;
  padding: 0 7px;
}
.pipe-filter-field svg {
  width: 11px;
  height: 11px;
  flex: none;
  color: var(--dim);
}
.pipe-filter-field input {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--text);
  font-size: 9.5px;
  outline: none;
}
.pipe-deriv-body {
  min-width: 0;
}
.pipe-table-wrap {
  max-height: none;
}
.pipe-deriv-table {
  width: 100%;
}
.pipe-deriv-table th,
.pipe-deriv-table td {
  white-space: nowrap;
}
.pipe-deriv-table td.pipe-claim-cell,
.pipe-deriv-table td.pipe-code-cell {
  white-space: normal;
}
.pipe-claim-cell {
  min-width: 0;
  max-width: none;
  padding: 5px 10px !important;
  line-height: 1.45;
}
.pipe-code-cell {
  max-width: none;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pipe-deriv-row {
  cursor: pointer;
}
.pipe-deriv-row:hover td {
  background: var(--surface-2);
}
.pipe-deriv-row--active td {
  background: var(--accent-weak);
}
.pipe-deriv-ops {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  align-items: center;
}
@media (max-width: 1024px) {
  .pipe-filter-field {
    width: 210px;
  }
}
</style>
