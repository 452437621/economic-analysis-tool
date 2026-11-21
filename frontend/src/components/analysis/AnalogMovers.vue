<template>
  <section class="card table-card analog-card">
    <div class="card-head">
      <span class="card-title">相似交易日</span>
      <span class="badge badge--sm">{{ analogs?.matches.length ?? 0 }} 个相似日</span>
      <div class="card-actions">
        <span class="card-sub">当前 {{ analogs?.current_date ?? "—" }} · 20 日远期收益</span>
      </div>
    </div>
    <div v-if="analogs" class="analog-meta">
      <div class="analog-meta-row">
        <span class="am-label">当前基准日</span>
        <b class="mono">{{ analogs.current_date }}</b>
        <span class="am-sep">·</span>
        <span class="am-label">匹配特征</span>
        <span class="analog-features">{{ analogs.features.join(" · ") }}</span>
      </div>
      <div class="analog-note">{{ analogs.note }}</div>
    </div>
    <div class="table-wrap table-auto">
      <table class="data-table analog-table">
        <thead>
          <tr>
            <th style="width: 124px">历史日期</th>
            <th class="num" style="width: 88px">距离</th>
            <th class="num">AU 20日</th>
            <th class="num">CU 20日</th>
            <th class="num">SC 20日</th>
            <th class="num">沪深300 20日</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="match in analogs?.matches ?? []" :key="match.date">
            <td class="mono">{{ match.date }}</td>
            <td class="num">{{ fmtNumber(match.distance, 3) }}</td>
            <td class="num" :class="trendClass(match.forward.AU_20d)">{{ fmtPct(match.forward.AU_20d) }}</td>
            <td class="num" :class="trendClass(match.forward.CU_20d)">{{ fmtPct(match.forward.CU_20d) }}</td>
            <td class="num" :class="trendClass(match.forward.SC_20d)">{{ fmtPct(match.forward.SC_20d) }}</td>
            <td class="num" :class="trendClass(match.forward['000300_20d'])">
              {{ fmtPct(match.forward["000300_20d"]) }}
            </td>
          </tr>
        </tbody>
      </table>
      <EmptyState v-if="!analogs?.matches.length" text="暂无相似交易日" hint="等待分析任务产出相似日匹配。" />
    </div>
    <div class="card-foot analog-foot">
      <svg class="ic"><use href="#i-info" /></svg>
      <span>距离越小表示宏观与价格特征越接近；远期收益为相似日之后的 20 个交易日表现，仅作参照。</span>
    </div>
  </section>

  <section class="card movers-card">
    <div class="card-head">
      <span class="card-title">异动品种</span>
      <span class="badge badge--sm">{{ movers.length }} 个</span>
      <div class="card-actions"><span class="card-sub">20 日涨跌 · 波动率 · 252 日分位</span></div>
    </div>
    <div class="movers-body">
      <button
        v-for="mover in movers"
        :key="mover.symbol"
        class="mover-row"
        type="button"
        :title="`${mover.name} ${mover.symbol} · 点击查看历史走势`"
        @click="$emit('open-history', mover.symbol, mover.name)"
      >
        <span class="mover-main">
          <span class="mover-sym">{{ mover.symbol }}</span>
          <span class="mover-name">{{ mover.name }}</span>
          <span class="badge badge--sm" :class="trendBadgeClass(mover.trend)">{{ trendLabel(mover.trend) }}</span>
        </span>
        <span class="mover-chg" :class="trendClass(mover.change_20d)">{{ fmtPct(mover.change_20d) }}</span>
        <span class="mover-stat">
          <span>分位 {{ fmtMacro(mover.percentile_252, "%", 1) }}</span>
          <span>波动 {{ fmtMacro(mover.vol20, "%", 1) }}</span>
        </span>
      </button>
      <EmptyState v-if="!movers.length" text="暂无异动品种" hint="等待分析任务产出波动监测结果。" />
    </div>
    <div class="card-foot">分位 = 252 日涨跌幅分位；波动 = 20 日年化波动率；点击行查看历史。</div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtMacro, fmtNumber, fmtPct, trendClass } from "@/composables/useFormat";
import type { Analogs, Mover } from "@/api/types";
import { trendBadgeClass, trendLabel } from "@/utils/analysisFormat";

defineProps<{
  analogs: Analogs | null;
  movers: Mover[];
}>();

defineEmits<{ (e: "open-history", symbol: string, name: string): void }>();
</script>

<style scoped>
.analog-card,
.movers-card {
  display: flex;
  flex-direction: column;
}
.analog-card > .card-body,
.movers-card > .movers-body {
  flex: 1 1 auto;
}
.analog-card > .card-foot {
  margin-top: auto;
}
.table-auto {
  max-height: none;
}
.analog-meta {
  padding: 8px 13px 7px;
  border-bottom: 1px solid var(--border);
}
.analog-meta-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  font-size: 9.5px;
  color: var(--dim);
}
.analog-meta-row .am-label {
  flex: none;
}
.analog-meta-row b {
  flex: none;
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
}
.analog-features {
  min-width: 0;
  overflow: hidden;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.analog-note {
  margin-top: 4px;
  font-size: 9.5px;
  line-height: 1.55;
  color: var(--dim);
}
.analog-table td {
  font-size: 11.5px;
}
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
.analog-foot {
  line-height: 1.6;
}

/* ---------- 异动 ---------- */
.movers-body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  padding: 4px 13px 5px;
}
.mover-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 60px 92px;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 34px;
  padding: 0;
  border: 0;
  border-bottom: 1px dashed var(--border);
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.mover-row:last-of-type {
  border-bottom: 0;
}
.mover-row:hover .mover-name {
  color: var(--accent);
}
.mover-main {
  display: flex;
  align-items: baseline;
  gap: 5px;
  min-width: 0;
}
.mover-sym {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.2px;
}
.mover-name {
  min-width: 0;
  overflow: hidden;
  font-size: 10.5px;
  color: var(--muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mover-main .badge {
  flex: none;
  margin-left: auto;
}
.mover-chg {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 650;
  text-align: right;
}
.mover-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}
</style>
