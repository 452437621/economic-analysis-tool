<template>
  <div class="lens-stats">
    <section class="card lens-stat">
      <div class="lens-stat-label">美联储立场</div>
      <div class="lens-stat-value">
        {{ state.fed.state.stance ?? "—" }}<small>/100</small>
      </div>
      <div class="lens-stat-meta">
        <span class="badge badge--sm" :class="stanceBadge">{{ state.fed.state.stance_label }}</span>
        <span class="mono">{{ state.fed.state.regime.label }}</span>
      </div>
      <div class="lens-bar"><i :style="{ width: `${state.fed.state.stance ?? 0}%` }"></i></div>
    </section>

    <section class="card lens-stat">
      <div class="lens-stat-label">美元环流</div>
      <div class="lens-stat-value lens-stat-value--text">{{ state.song.state.phase.label }}</div>
      <div class="lens-stat-meta">
        <span class="badge badge--sm" :class="heartBadge">{{ state.song.state.dollar_heart.label }}</span>
        <span class="mono">{{ state.song.state.dollar_heart.level_bp ?? "—" }}bp</span>
      </div>
      <div class="lens-stat-note">{{ state.song.state.phase.note }}</div>
    </section>

    <section class="card lens-stat">
      <div class="lens-stat-label">黄金状态</div>
      <div class="lens-stat-value lens-stat-value--text" :class="goldClass">
        {{ state.song.state.gold_regime.label }}
      </div>
      <div class="lens-stat-meta">
        <span class="mono">收割 {{ state.song.state.harvest_risk ?? "—" }}</span>
        <span class="mono">债务 {{ state.song.state.debt_risk ?? "—" }}</span>
      </div>
      <div class="lens-stat-note">{{ state.song.state.gold_regime.note }}</div>
    </section>

    <section class="card lens-stat">
      <div class="lens-stat-label">多镜合成</div>
      <div class="lens-stat-value">
        {{ state.synthesis.consensus_count }}<small>项共振</small>
      </div>
      <div class="lens-stat-meta">
        <span class="badge badge--sm">{{ state.synthesis.divergences.length }} 项分歧</span>
        <span class="mono">参与 {{ state.synthesis.lens_count ?? 13 }} 套</span>
        <span class="mono">{{ state.synthesis.outlook.horizon_days }} 天</span>
      </div>
      <div class="lens-stat-note">{{ state.synthesis.narrative }}</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { LensStateResponse } from "@/api/types";

const props = defineProps<{ state: LensStateResponse }>();

const stanceBadge = computed(() => {
  const value = props.state.fed.state.stance ?? 50;
  return value >= 70 ? "badge--warn" : value <= 30 ? "badge--up" : "badge--accent";
});
const heartBadge = computed(() => {
  const id = props.state.song.state.dollar_heart.id;
  return id === "infarction" ? "badge--down" : id === "angina" ? "badge--warn" : "badge--accent";
});
const goldClass = computed(() => {
  const id = props.state.song.state.gold_regime.id;
  return id === "strategic" || id === "accumulate" ? "is-up" : id === "avoid" ? "is-down" : "";
});
</script>

<style scoped>
.lens-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.lens-stat {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.lens-stat-label {
  font-size: 10.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--dim);
}
.lens-stat-value {
  font-family: var(--font-mono, monospace);
  font-size: 26px;
  line-height: 1.1;
  color: var(--text);
}
.lens-stat-value small {
  font-size: 11px;
  color: var(--muted);
  margin-left: 2px;
}
.lens-stat-value--text {
  font-size: 20px;
  font-family: inherit;
  font-weight: 600;
}
.lens-stat-value--text.is-up { color: var(--up); }
.lens-stat-value--text.is-down { color: var(--down); }
.lens-stat-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--muted);
}
.lens-stat-note {
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--dim);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
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
@media (max-width: 1200px) {
  .lens-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
