<template>
  <div class="lens-grid lens-grid--3">
    <section class="card lens-card">
      <div class="card-head"><span class="card-title">美元环流</span></div>
      <div class="card-body">
        <div class="lens-big">{{ state.song.state.phase.label }}</div>
        <p class="lens-muted">{{ state.song.state.phase.note }}</p>
        <div class="lens-kv"><span>美元心脏</span><strong>{{ state.song.state.dollar_heart.label }}</strong></div>
        <div class="lens-kv"><span>SOFR−EFFR</span><span class="mono">{{ state.song.state.dollar_heart.level_bp ?? "—" }}bp / 脉冲 {{ state.song.state.dollar_heart.spike_bp ?? "—" }}bp</span></div>
        <p class="lens-muted">{{ state.song.state.dollar_heart.note }}</p>
      </div>
    </section>

    <section class="card lens-card">
      <div class="card-head"><span class="card-title">风险温度</span></div>
      <div class="card-body">
        <div class="lens-risk">
          <div class="lens-kv"><span>收割风险</span><span class="mono">{{ state.song.state.harvest_risk ?? "—" }}/100</span></div>
          <div class="lens-bar lens-bar--risk"><i :style="{ width: `${state.song.state.harvest_risk ?? 0}%` }"></i></div>
        </div>
        <div class="lens-risk">
          <div class="lens-kv"><span>债务货币化风险</span><span class="mono">{{ state.song.state.debt_risk ?? "—" }}/100</span></div>
          <div class="lens-bar lens-bar--risk"><i :style="{ width: `${state.song.state.debt_risk ?? 0}%` }"></i></div>
        </div>
        <div class="lens-kv"><span>黄金状态</span><strong>{{ state.song.state.gold_regime.label }}</strong></div>
        <p class="lens-muted">{{ state.song.state.gold_regime.note }}</p>
      </div>
    </section>

    <section class="card lens-card">
      <div class="card-head"><span class="card-title">资产评分（宋鸿兵透镜）</span></div>
      <div class="card-body">
        <div v-for="[id, score] in songScores" :key="id" class="lens-score-row">
          <div class="lens-score-row-head">
            <span>{{ assetLabel(id) }}</span>
            <span class="mono" :class="scoreClass(score.score)">{{ fmtSigned(score.score) }} {{ score.label }}</span>
          </div>
          <div class="lens-score-bar lens-score-bar--wide">
            <i :class="scoreClass(score.score)" :style="{ width: `${Math.min(50, Math.abs(score.score ?? 0) * 25)}%`, [score.score && score.score < 0 ? 'right' : 'left']: '50%' }"></i>
          </div>
          <div class="lens-muted">{{ score.why }}</div>
        </div>
      </div>
    </section>
  </div>

  <section class="card lens-card">
    <div class="card-head"><span class="card-title">宋鸿兵读数（{{ state.song.coverage.available }}/{{ state.song.coverage.total }}）</span></div>
    <div class="card-body">
      <div class="lens-readings">
        <div v-for="r in state.song.readings" :key="r.id" class="lens-reading" :class="{ 'is-missing': r.value === null }">
          <div class="lens-reading-label">{{ r.label }}</div>
          <div class="lens-reading-value mono">
            {{ r.value === null ? "缺失" : fmtNumber(r.value, r.digits) }}<small>{{ r.value === null ? "" : r.unit }}</small>
          </div>
          <div v-if="r.value !== null" class="lens-reading-meta">
            <span :class="trendClass(r.change)" class="mono">{{ fmtSigned(r.change, r.digits) }} {{ r.change_label }}</span>
            <span class="mono">z {{ fmtSigned(r.z) }}</span>
            <span class="mono">分位 {{ fmtRatioPct(r.percentile) }}</span>
          </div>
          <div v-else class="lens-reading-meta lens-muted">{{ r.missing_reason }}</div>
          <div class="lens-reading-source">
            <span class="badge badge--sm">{{ r.evidence }}</span>
            <span class="lens-muted">{{ r.note || r.source }}</span>
          </div>
        </div>
      </div>
      <p class="lens-narrative">{{ state.song.state.narrative }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { LensScore, LensStateResponse } from "@/api/types";
import { scoreClass } from "@/composables/useLensState";
import { fmtNumber, fmtRatioPct, fmtSigned, trendClass } from "@/composables/useFormat";

const props = defineProps<{ state: LensStateResponse }>();

const songScores = computed(
  () =>
    Object.entries(props.state.song.state.asset_scores ?? {}) as Array<[string, LensScore]>,
);

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
.lens-grid--3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.lens-big {
  font-family: var(--font-mono, monospace); font-size: 30px; line-height: 1.15; color: var(--text);
}
.lens-big small { font-size: 11px; color: var(--muted); margin-left: 4px; font-family: inherit; }
.lens-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--surface-3, rgba(148, 163, 184, 0.18));
  overflow: hidden;
}
.lens-bar i {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), var(--warn));
}
.lens-bar--risk i {
  background: linear-gradient(90deg, var(--warn), var(--down));
}
.lens-kv {
  display: flex; justify-content: space-between; gap: 10px; font-size: 11.5px;
  padding: 4px 0; color: var(--muted);
}
.lens-kv strong { color: var(--text); font-weight: 600; }
.lens-score-bar {
  display: none;
}
.lens-score-bar--wide {
  display: block;
  position: relative;
  height: 4px;
  margin: 4px 0 6px;
  background: var(--surface-3, rgba(148, 163, 184, 0.18));
  border-radius: 2px;
}
.lens-score-bar i {
  position: absolute;
  top: 0;
  height: 100%;
  border-radius: 2px;
  background: var(--muted);
}
.lens-score-bar i.is-up { background: var(--up); }
.lens-score-bar i.is-down { background: var(--down); }
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
.lens-reading-meta { display: flex; gap: 8px; flex-wrap: wrap; font-size: 10px; color: var(--muted); }
.lens-reading-source { display: flex; gap: 6px; align-items: center; font-size: 10px; }
.lens-narrative {
  margin: 12px 0 0; padding-top: 10px; border-top: 1px dashed var(--border);
  font-size: 11.5px; line-height: 1.7; color: var(--muted);
}
.lens-risk { margin-bottom: 8px; }
@media (max-width: 1200px) {
  .lens-grid--3 { grid-template-columns: 1fr; }
}
</style>
