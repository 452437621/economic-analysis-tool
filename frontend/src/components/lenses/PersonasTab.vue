<template>
  <div v-if="!state.personas.length" class="card lens-card">
    <EmptyState text="尚无人物透镜" hint="确认 config/personas/*.yaml 存在后重算。" />
  </div>
  <div v-else class="lens-grid lens-grid--3">
    <section v-for="persona in state.personas" :key="persona.id" class="card lens-card">
      <div class="card-head">
        <span class="card-title">{{ persona.name }}</span>
        <span class="spacer"></span>
        <span class="badge badge--sm" :class="persona.state.lean.score >= 0 ? 'badge--up' : 'badge--warn'">
          {{ persona.state.lean.label }} {{ fmtSigned(persona.state.lean.score) }}
        </span>
      </div>
      <div class="card-body">
        <div class="lens-muted">{{ persona.title }}</div>
        <div class="lens-muted">{{ persona.school }}</div>
        <div class="lens-kv"><span>覆盖率</span><span class="mono">{{ persona.state.coverage.available }}/{{ persona.state.coverage.total }}</span></div>
        <div class="lens-kv"><span>命中规则</span><span class="mono">{{ persona.state.fired_rules.length }} 条</span></div>
        <div v-if="persona.state.fired_rules.length" class="lens-flags">
          <span v-for="ruleId in persona.state.fired_rules" :key="ruleId" class="badge badge--warn badge--sm">{{ ruleId }}</span>
        </div>
        <p class="lens-muted">{{ persona.state.narrative }}</p>
      </div>
    </section>
  </div>

  <section class="card lens-card">
    <div class="card-head"><span class="card-title">人物评分矩阵</span><span class="spacer"></span><span class="lens-muted">{{ personaMatrix.length }} 套透镜 × {{ matrixAssets.length }} 类资产</span></div>
    <div class="card-body lens-table-wrap">
      <table class="lens-table">
        <thead>
          <tr>
            <th>透镜</th>
            <th>倾向</th>
            <th v-for="asset in matrixAssets" :key="asset.id">{{ asset.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in personaMatrix" :key="row.id">
            <td>{{ row.name }}</td>
            <td class="mono" :class="scoreClass(row.lean)">{{ fmtSigned(row.lean) }}</td>
            <td v-for="asset in matrixAssets" :key="asset.id" class="mono" :class="scoreClass(row.scores[asset.id] ?? null)">
              {{ row.scores[asset.id] === undefined ? "—" : fmtSigned(row.scores[asset.id] ?? null) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { LensStateResponse } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import { scoreClass } from "@/composables/useLensState";
import { fmtSigned } from "@/composables/useFormat";

const props = defineProps<{ state: LensStateResponse }>();

/** 人物评分矩阵：行=人物透镜，列=七类资产 */
const personaMatrix = computed(() =>
  (props.state.personas ?? []).map((persona) => {
    const scores: Record<string, number | null> = {};
    for (const [assetId, item] of Object.entries(persona.scores ?? {})) {
      scores[assetId] = item?.score ?? null;
    }
    return { id: persona.id, name: persona.name, lean: persona.state.lean.score, scores };
  }),
);
const matrixAssets = computed(() =>
  (props.state.synthesis.assets ?? []).map((asset) => ({ id: asset.id, label: asset.label })),
);
</script>

<style scoped>
.lens-card { overflow: hidden; }
.card-body { padding: 12px; }
.lens-muted { color: var(--muted); font-size: 10.5px; }
.lens-grid { display: grid; gap: 12px; }
.lens-grid--3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.lens-kv {
  display: flex; justify-content: space-between; gap: 10px; font-size: 11.5px;
  padding: 4px 0; color: var(--muted);
}
.lens-kv strong { color: var(--text); font-weight: 600; }
.lens-table-wrap { overflow-x: auto; }
.lens-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}
.lens-table th {
  text-align: left;
  font-weight: 500;
  color: var(--dim);
  font-size: 10.5px;
  padding: 7px 10px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.lens-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.lens-table tbody tr:hover { background: var(--surface-2); }
.is-up { color: var(--up); }
.is-down { color: var(--down); }
.is-flat { color: var(--muted); }
@media (max-width: 1200px) {
  .lens-grid--3 { grid-template-columns: 1fr; }
}
</style>
