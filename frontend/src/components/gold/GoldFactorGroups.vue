<template>
  <!-- 因子分组 -->
  <div class="sec-row">
    <span class="sec-title">因子分组</span>
    <span class="sec-count">{{ groups.length }} 组</span>
    <span class="sec-meta">{{ factorsCount }} 项因子 · {{ availableFactorCount }} 项已采集 · 按类别聚合</span>
    <div class="sec-actions">
      <span class="badge badge--sm" :class="pendingCount ? 'badge--warn' : 'badge--live'">
        {{ pendingCount ? `${pendingCount} 项待采集` : "全部已采集" }}
      </span>
    </div>
  </div>
  <div class="group-grid">
    <section v-for="group in groups" :key="group.key" class="card group-card">
      <div class="card-head">
        <svg class="ic group-ic"><use :href="group.icon" /></svg>
        <span class="card-title">{{ group.label }}</span>
        <span class="badge badge--sm">{{ group.factors.length }} 项</span>
        <div class="card-actions">
          <span class="card-sub">
            可用 {{ group.available }}/{{ group.factors.length }} ·
            组贡献
            <b class="group-contrib" :class="trendClass(group.contribution)">{{ fmtSigned(group.contribution, 2) }}</b>
          </span>
        </div>
      </div>
      <div class="group-body">
        <div
          v-for="factor in group.factors"
          :key="factor.code"
          class="frow"
          :class="{ 'frow--off': !factor.available }"
        >
          <div class="frow-top">
            <span class="frow-name" :title="`${factor.name}（${factor.code}）`">{{ factor.name }}</span>
            <span v-if="factor.manual" class="badge badge--sm badge--accent">手动录入</span>
            <span v-else-if="!factor.available" class="badge badge--sm">待接入</span>
            <span v-if="factor.available" class="badge badge--sm" :class="signalClass(factor.signal)">
              {{ signalLabel(factor.signal) }}
            </span>
            <button v-if="factor.manual" class="link-btn entry-link" type="button" @click="$emit('entry', factor)">
              <svg class="ic"><use href="#i-plus" /></svg>录入
            </button>
          </div>
          <div class="frow-mid">
            <span class="frow-val">{{ factorValueText(factor) }}</span>
            <span v-if="factor.available" class="frow-chg" :class="trendClass(factor.change)">{{ fmtPct(factor.change) }}</span>
            <span v-else class="frow-chg dim">—</span>
            <span
              class="frow-asof"
              :class="{ 'frow-asof--stale': isFactorStale(factor) }"
              :title="factor.as_of ? `该因子最新观测日 ${fmtDate(factor.as_of)}（${factor.freq || '—'} 频）` : '尚未采集到观测值'"
            >
              {{ factorAsOfText(factor) }}
            </span>
            <span class="frow-weight">权重 {{ factor.weight }}</span>
            <span class="frow-contrib">
              贡献
              <b :class="factor.available ? trendClass(factor.contribution) : 'dim'">
                {{ factor.available ? fmtSigned(factor.contribution, 2) : "—" }}
              </b>
            </span>
          </div>
          <div class="frow-desc" :title="factor.available ? factor.explain || factor.note : factor.note">
            {{ factor.available ? factor.explain || factor.note : factor.note }}
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { fmtDate, fmtPct, fmtSigned, trendClass } from "@/composables/useFormat";
import type { GoldFactor } from "@/api/types";
import { factorAsOfText, factorValueText, isFactorStale, signalClass, signalLabel } from "@/utils/goldFormat";

interface GroupView {
  key: string;
  label: string;
  icon: string;
  factors: GoldFactor[];
  contribution: number;
  available: number;
}

defineProps<{
  groups: GroupView[];
  factorsCount: number;
  availableFactorCount: number;
  pendingCount: number;
}>();

defineEmits<{ (e: "entry", factor: GoldFactor): void }>();
</script>

<style scoped>
/* ---------- 因子分组 ---------- */
.group-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}
.group-card {
  overflow: hidden;
}
.group-ic {
  width: 13px;
  height: 13px;
  color: var(--accent);
}
.group-contrib {
  font-family: var(--mono);
  font-weight: 650;
}
.group-body {
  padding: 2px 13px 4px;
}
.frow {
  padding: 6px 0 5px;
  border-bottom: 1px dashed var(--border);
}
.frow:last-child {
  border-bottom: 0;
}
.frow-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.frow-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  font-size: 11.5px;
  font-weight: 560;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.frow-top .badge {
  flex: none;
}
.frow-mid {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-top: 2px;
}
.frow-val {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 650;
  color: var(--text);
}
.frow-chg {
  font-family: var(--mono);
  font-size: 10px;
}
.frow-chg.dim {
  color: var(--dim);
  font-family: var(--mono);
}
.frow-weight {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.frow-asof {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.frow-asof--stale {
  color: var(--warn-color, #d08700);
}
.frow-contrib {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--dim);
}
.frow-contrib b {
  font-size: 10.5px;
  font-weight: 650;
}
.frow-desc {
  display: -webkit-box;
  margin-top: 2px;
  overflow: hidden;
  font-size: 9.5px;
  line-height: 1.5;
  color: var(--dim);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.frow--off .frow-name {
  color: var(--muted);
}
.frow--off .frow-val {
  color: var(--dim);
}
.entry-link {
  flex: none;
  padding: 0 2px;
}
.entry-link .ic {
  width: 10px;
  height: 10px;
}
.frow-top .entry-link {
  margin-left: 1px;
}
@media (max-width: 1360px) {
  .group-grid {
    grid-template-columns: 1fr;
  }
}
</style>
