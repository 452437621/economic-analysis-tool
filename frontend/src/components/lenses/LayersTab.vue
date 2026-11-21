<template>
  <div v-if="!state.macro && !state.micro" class="card lens-card">
    <EmptyState text="尚无宏观/微观层推导" hint="点击「重算多透镜」生成宏观层与微观层。" />
  </div>
  <div v-else class="lens-grid lens-grid--2">
    <section v-if="state.macro" class="card lens-card">
      <div class="card-head">
        <span class="card-title">宏观层 · 象限与流动性</span>
        <span class="spacer"></span>
        <span class="badge badge--sm">{{ state.macro.coverage.available }}/{{ state.macro.coverage.total }}</span>
      </div>
      <div class="card-body">
        <div class="lens-big">{{ state.macro.state.regime.label }}</div>
        <p class="lens-muted">{{ state.macro.state.regime.note }}</p>
        <div class="lens-kv"><span>净流动性 13 周</span><strong class="mono">{{ state.macro.state.liquidity.value ?? "—" }}% {{ state.macro.state.liquidity.label }}</strong></div>
        <div class="lens-kv"><span>财政脉冲（TTM 赤字/GDP）</span><strong class="mono">{{ state.macro.state.fiscal.value ?? "—" }}% {{ state.macro.state.fiscal.label }}</strong></div>
        <div class="lens-kv"><span>融资紧张度</span><strong class="mono">{{ state.macro.state.funding.value ?? "—" }}bp {{ state.macro.state.funding.label }}</strong></div>
        <div v-if="state.macro.state.flags.length" class="lens-flags">
          <span v-for="flag in state.macro.state.flags" :key="flag" class="badge badge--warn badge--sm">{{ flag }}</span>
        </div>
        <p class="lens-narrative">{{ state.macro.state.narrative }}</p>
        <div class="lens-score-grid">
          <div v-for="[id, score] in macroScores" :key="id" class="lens-score-row">
            <div class="lens-score-row-head">
              <span>{{ assetLabel(id) }}</span>
              <span class="mono" :class="scoreClass(score.score)">{{ fmtSigned(score.score) }} {{ score.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="state.micro" class="card lens-card">
      <div class="card-head">
        <span class="card-title">微观层 · 价格结构与实物紧张</span>
        <span class="spacer"></span>
        <span class="badge badge--sm">{{ state.micro.coverage.available }}/{{ state.micro.coverage.total }}</span>
      </div>
      <div class="card-body">
        <div class="lens-big">{{ state.micro.state.risk_appetite.label }}</div>
        <div class="lens-kv"><span>黄金微观评分</span><strong class="mono" :class="scoreClass(state.micro.state.gold_micro)">{{ fmtSigned(state.micro.state.gold_micro) }}</strong></div>
        <div v-if="state.micro.state.crowding.length" class="lens-flags">
          <span v-for="flag in state.micro.state.crowding" :key="flag" class="badge badge--warn badge--sm">{{ flag }}</span>
        </div>
        <p class="lens-narrative">{{ state.micro.state.narrative }}</p>
        <div class="lens-score-grid">
          <div v-for="[id, score] in microScores" :key="id" class="lens-score-row">
            <div class="lens-score-row-head">
              <span>{{ assetLabel(id) }}</span>
              <span class="mono" :class="scoreClass(score.score)">{{ fmtSigned(score.score) }} {{ score.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>

  <section v-if="macroLayer" class="card lens-card">
    <div class="card-head"><span class="card-title">宏观层读数（{{ macroLayer.coverage.available }}/{{ macroLayer.coverage.total }}）</span></div>
    <div class="card-body">
      <div class="lens-readings">
        <div v-for="r in macroLayer.readings" :key="r.id" class="lens-reading" :class="{ 'is-missing': r.value === null }">
          <div class="lens-reading-label">{{ r.label }}</div>
          <div class="lens-reading-value mono">
            {{ r.value === null ? "缺失" : fmtNumber(r.value, r.digits) }}<small>{{ r.value === null ? "" : r.unit }}</small>
          </div>
          <div class="lens-reading-source"><span class="badge badge--sm">{{ r.evidence }}</span><span class="lens-muted">{{ r.note || r.source }}</span></div>
        </div>
      </div>
    </div>
  </section>

  <section v-if="microLayer" class="card lens-card">
    <div class="card-head"><span class="card-title">微观层读数（{{ microLayer.coverage.available }}/{{ microLayer.coverage.total }}）</span></div>
    <div class="card-body">
      <div class="lens-readings">
        <div v-for="r in microLayer.readings" :key="r.id" class="lens-reading" :class="{ 'is-missing': r.value === null }">
          <div class="lens-reading-label">{{ r.label }}</div>
          <div class="lens-reading-value mono">
            {{ r.value === null ? "缺失" : fmtNumber(r.value, r.digits) }}<small>{{ r.value === null ? "" : r.unit }}</small>
          </div>
          <div class="lens-reading-source"><span class="badge badge--sm">{{ r.evidence }}</span><span class="lens-muted">{{ r.note || r.source }}</span></div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { LensStateResponse } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import { scoreClass, toScoreEntries } from "@/composables/useLensState";
import { fmtNumber, fmtSigned } from "@/composables/useFormat";

const props = defineProps<{ state: LensStateResponse }>();

const macroLayer = computed(() => props.state.macro ?? null);
const microLayer = computed(() => props.state.micro ?? null);
const macroScores = computed(() => toScoreEntries(props.state.macro?.scores));
const microScores = computed(() => toScoreEntries(props.state.micro?.scores));

function assetLabel(id: string): string {
  const found = props.state.synthesis.assets.find((a) => a.id === id);
  return found?.label ?? id;
}
</script>

<style scoped>
.lens-card { overflow: hidden; }
.card-body { padding: 12px; }
.lens-muted { color: var(--muted); font-size: 10.5px; }
.lens-grid { display: grid; gap: 12px; }
.lens-grid--2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.lens-big {
  font-family: var(--font-mono, monospace); font-size: 30px; line-height: 1.15; color: var(--text);
}
.lens-kv {
  display: flex; justify-content: space-between; gap: 10px; font-size: 11.5px;
  padding: 4px 0; color: var(--muted);
}
.lens-kv strong { color: var(--text); font-weight: 600; }
.lens-narrative {
  margin: 12px 0 0; padding-top: 10px; border-top: 1px dashed var(--border);
  font-size: 11.5px; line-height: 1.7; color: var(--muted);
}
.is-up { color: var(--up); }
.is-down { color: var(--down); }
.is-flat { color: var(--muted); }
.lens-readings {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;
}
.lens-reading {
  border: 1px solid var(--border); border-radius: 6px; padding: 8px;
  display: flex; flex-direction: column; gap: 4px; background: var(--surface-2);
}
.lens-reading.is-missing { opacity: 0.65; }
.lens-reading-label { font-size: 11px; color: var(--text); }
.lens-reading-value { font-size: 18px; line-height: 1.2; color: var(--text); }
.lens-reading-value small { font-size: 10px; color: var(--muted); margin-left: 2px; }
.lens-reading-source { display: flex; gap: 6px; align-items: center; font-size: 10px; }
@media (max-width: 1200px) {
  .lens-grid--2 { grid-template-columns: 1fr; }
}
</style>
