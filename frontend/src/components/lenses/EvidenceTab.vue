<template>
  <div class="lens-grid lens-grid--2">
    <section class="card lens-card">
      <div class="card-head"><span class="card-title">数据缺口</span><span class="spacer"></span><span class="lens-muted">{{ state.data_gaps.length }} 项</span></div>
      <div class="card-body">
        <ul class="lens-list lens-list--gaps">
          <li v-for="gap in state.data_gaps" :key="gap.id">
            <span class="badge badge--warn badge--sm">{{ gap.id }}</span>
            <div>
              <div class="lens-list-title">{{ gap.label }}</div>
              <div class="lens-muted">{{ gap.reason }} · {{ gap.impact }}</div>
            </div>
          </li>
        </ul>
      </div>
    </section>

    <section class="card lens-card">
      <div class="card-head"><span class="card-title">推导谱系</span></div>
      <div class="card-body">
        <div v-for="row in derivationRows" :key="row.code" class="lens-deriv">
          <div class="lens-kv">
            <span class="mono">{{ row.code }}</span>
            <span class="mono lens-muted">{{ row.method_id }}</span>
          </div>
          <div class="lens-muted">{{ row.claim }}</div>
          <div class="lens-deriv-links">
            <span class="badge badge--sm">{{ row.evidence_grade }}</span>
            <span class="mono">置信 {{ fmtRatioPct(row.confidence) }}</span>
            <RouterLink class="lens-link" :to="`/pipeline?code=${row.code}`">证据抽屉 →</RouterLink>
          </div>
        </div>
      </div>
    </section>
  </div>

  <section class="card lens-card">
    <div class="card-head">
      <span class="card-title">美联储规则 F1–F12</span>
      <span class="spacer"></span>
      <span class="lens-muted">命中 {{ fired.fed }} / {{ state.rules.fed.length }}</span>
    </div>
    <div class="lens-table-wrap">
      <table class="lens-table lens-table--rules">
        <thead><tr><th>规则</th><th>状态</th><th>条件</th><th>失效条件</th></tr></thead>
        <tbody>
          <tr v-for="rule in state.rules.fed" :key="rule.id" :class="`is-${rule.status}`">
            <td><div class="lens-rule-id mono">{{ rule.id }}</div><div class="lens-muted">{{ rule.name }}</div></td>
            <td><span class="lens-status" :class="`lens-status--${rule.status}`">{{ statusText(rule.status) }}</span></td>
            <td>
              <div>{{ rule.message }}</div>
              <div v-if="rule.trace?.length" class="lens-trace mono">
                <div v-for="t in rule.trace" :key="t.condition" :class="{ met: t.met }">{{ t.met ? "✓" : "✗" }} {{ t.condition }}</div>
              </div>
            </td>
            <td class="lens-muted">{{ rule.falsifier || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="card lens-card">
    <div class="card-head">
      <span class="card-title">宋鸿兵规则 S1–S13</span>
      <span class="spacer"></span>
      <span class="lens-muted">命中 {{ fired.song }} / {{ state.rules.song.length }}</span>
    </div>
    <div class="lens-table-wrap">
      <table class="lens-table lens-table--rules">
        <thead><tr><th>规则</th><th>状态</th><th>条件</th><th>失效条件</th></tr></thead>
        <tbody>
          <tr v-for="rule in state.rules.song" :key="rule.id" :class="`is-${rule.status}`">
            <td><div class="lens-rule-id mono">{{ rule.id }}</div><div class="lens-muted">{{ rule.name }}</div></td>
            <td><span class="lens-status" :class="`lens-status--${rule.status}`">{{ statusText(rule.status) }}</span></td>
            <td>
              <div>{{ rule.message }}</div>
              <div v-if="rule.trace?.length" class="lens-trace mono">
                <div v-for="t in rule.trace" :key="t.condition" :class="{ met: t.met }">{{ t.met ? "✓" : "✗" }} {{ t.condition }}</div>
              </div>
            </td>
            <td class="lens-muted">{{ rule.falsifier || "—" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import type { LensDerivation, LensStateResponse } from "@/api/types";
import { statusText } from "@/composables/useLensState";
import { fmtRatioPct } from "@/composables/useFormat";

const props = defineProps<{ state: LensStateResponse }>();

const fired = computed(() => ({
  fed: (props.state.rules.fed ?? []).filter((r) => r.fired).length,
  song: (props.state.rules.song ?? []).filter((r) => r.fired).length,
}));

const derivationRows = computed<LensDerivation[]>(() => {
  const state = props.state;
  const rows = [state.fed.derivation, state.song.derivation];
  if (state.macro?.derivation) rows.push(state.macro.derivation);
  if (state.micro?.derivation) rows.push(state.micro.derivation);
  for (const persona of state.personas) {
    if (persona.derivation) rows.push(persona.derivation);
  }
  rows.push(state.synthesis.derivation);
  return rows;
});
</script>

<style scoped>
.lens-card { overflow: hidden; }
.card-body { padding: 12px; }
.lens-muted { color: var(--muted); font-size: 10.5px; }
.lens-grid { display: grid; gap: 12px; }
.lens-grid--2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.lens-table-wrap { overflow-x: auto; }
.lens-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.lens-list li { display: flex; gap: 8px; align-items: flex-start; line-height: 1.5; }
.lens-list-title { font-size: 11.5px; color: var(--text); }
.lens-list--gaps li { align-items: flex-start; }
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
.lens-table tbody tr.is-fired td { background: color-mix(in srgb, var(--warn) 7%, transparent); }
.lens-kv {
  display: flex; justify-content: space-between; gap: 10px; font-size: 11.5px;
  padding: 4px 0; color: var(--muted);
}
.lens-kv strong { color: var(--text); font-weight: 600; }
.lens-deriv { padding: 8px 0; border-bottom: 1px dashed var(--border); }
.lens-deriv:last-child { border-bottom: none; }
.lens-deriv-links { display: flex; align-items: center; gap: 10px; margin-top: 6px; font-size: 10.5px; color: var(--muted); }
.lens-link { color: var(--accent); text-decoration: none; font-size: 10.5px; }
.lens-link:hover { text-decoration: underline; }
.lens-table--rules td { font-size: 11px; }
.lens-rule-id { font-size: 12px; color: var(--text); }
.lens-status {
  display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10.5px;
  border: 1px solid var(--border); color: var(--muted); white-space: nowrap;
}
.lens-status--fired { color: var(--warn); border-color: var(--warn); }
.lens-status--unknown { color: var(--muted); border-style: dashed; }
.lens-trace { margin-top: 4px; font-size: 10px; color: var(--dim); }
.lens-trace .met { color: var(--warn); }
@media (max-width: 1200px) {
  .lens-grid--2 { grid-template-columns: 1fr; }
}
</style>
