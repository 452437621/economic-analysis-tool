<template>
  <section class="card wind-card">
    <div class="card-head">
      <span class="card-title">市场风向</span>
      <span v-if="wind" class="badge badge--sm" :class="windBadgeClass(wind.label)">{{ wind.label }}</span>
      <div class="card-actions"><span class="card-sub">{{ wind?.asof ?? "—" }}</span></div>
    </div>
    <div v-if="wind" class="card-body wind-body">
      <div class="wind-head">
        <span class="wind-score" :class="trendClass(wind.score)">{{ fmtSigned(wind.score, 1) }}</span>
        <span class="wind-unit">/ 100</span>
        <span class="wind-tag" :class="trendClass(wind.score)">{{ wind.label }}</span>
      </div>
      <div class="wind-gauge" :title="`score ${fmtSigned(wind.score, 1)} · −100 避险 / +100 进攻`">
        <span class="wind-zero"></span>
        <i class="wind-needle" :style="{ left: windNeedle }"></i>
      </div>
      <div class="wind-scale"><span>−100 避险</span><span>0</span><span>+100 进攻</span></div>
      <div class="wind-rows">
        <div class="wind-row">
          <span>站上 MA60 广度</span>
          <b>{{ fmtMacro(wind.components.breadth_above_ma60 * 100, "%", 0) }}</b>
        </div>
        <div class="wind-row">
          <span>20 日平均动量</span>
          <b :class="trendClass(wind.components.momentum_20d_avg_pct)">
            {{ fmtPct(wind.components.momentum_20d_avg_pct) }}
          </b>
        </div>
        <div class="wind-row">
          <span>10Y 20 日变动</span>
          <b :class="trendClass(wind.components.us10y_change_20d_pp)">
            {{ fmtMacro(wind.components.us10y_change_20d_pp, "pp", 2) }}
          </b>
        </div>
        <div class="wind-row">
          <span>风险资产池</span>
          <b class="wind-risk">{{ windRisk.length ? windRisk.join(" · ") : "数据不足" }}</b>
        </div>
      </div>
    </div>
    <EmptyState v-else text="风向数据缺失" hint="等待分析任务产出市场风向。" />
    <div v-if="wind" class="card-foot">
      score = 40% 广度 + 35% 动量 + 25% 利率 · {{ wind.asof }}
      <RouterLink
        class="regime-why"
        :to="{ path: '/pipeline', query: { code: 'wind.market' } }"
      >
        为什么是这个读数 → 溯源
      </RouterLink>
    </div>
  </section>

  <section id="cycle-regime" class="card regime-card">
    <div class="card-head">
      <span class="card-title">市场隐含周期象限</span>
      <span class="badge badge--sm badge--accent">市场隐含</span>
      <div class="card-actions"><span class="card-sub">增长 × 通胀象限 · 0–100 分位</span></div>
    </div>
    <div v-if="regimeList.length" class="card-body regime-body">
      <div v-for="regime in regimeList" :key="regime.country" class="regime-block">
        <div class="regime-top">
          <span class="regime-country">{{ countryLabel(regime.country) }}</span>
          <span class="regime-code">{{ regime.country }}</span>
          <span class="badge badge--sm badge--accent">{{ regime.quadrant }}</span>
          <span class="regime-conf">置信 {{ fmtMacro(regime.confidence * 100, "%", 0) }}</span>
        </div>
        <div class="regime-bars">
          <div v-for="item in regimeScores(regime)" :key="item.label" class="regime-bar">
            <span class="rb-label">{{ item.label }}</span>
            <span class="rb-score">{{ fmtNumber(item.score, 1) }}</span>
            <span class="rb-z">z {{ item.z === null ? "—" : fmtSigned(item.z, 2) }}</span>
            <span class="rb-track"><i :style="{ width: scoreWidth(item.score) }"></i></span>
          </div>
        </div>
        <div class="regime-method">{{ regime.method }}</div>
        <RouterLink
          class="regime-why"
          :to="{ path: '/pipeline', query: { code: `regime.${regime.country}` } }"
        >
          为什么是这个象限 → 溯源
        </RouterLink>
      </div>
    </div>
    <EmptyState v-else text="周期数据缺失" hint="等待分析任务产出市场隐含象限。" />
  </section>

  <section class="card corr-card">
    <div class="card-head">
      <span class="card-title">跨资产相关性</span>
      <span class="badge badge--sm">{{ correlation?.window ?? "—" }} 日</span>
      <div class="card-actions"><span class="card-sub">平均 |ρ|</span></div>
    </div>
    <div v-if="correlation" class="card-body corr-body">
      <div class="corr-avg-row">
        <div>
          <div class="corr-avg">{{ fmtNumber(correlation.avg_abs_corr, 3) }}</div>
          <div class="corr-avg-label">平均绝对相关 · 窗口 {{ correlation.window }} 日</div>
        </div>
        <span class="badge badge--sm" :class="corrLevel(correlation.avg_abs_corr).cls">
          {{ corrLevel(correlation.avg_abs_corr).text }}
        </span>
      </div>
      <div class="corr-list">
        <div v-for="pair in correlation.top_pairs" :key="`${pair.a}-${pair.b}`" class="corr-row">
          <span class="corr-pair">{{ pair.a }}<i>/</i>{{ pair.b }}</span>
          <span class="corr-track"><i :class="trendClass(pair.corr)" :style="{ width: corrWidth(pair.corr) }"></i></span>
          <span class="corr-val num" :class="trendClass(pair.corr)">{{ fmtSigned(pair.corr, 3) }}</span>
        </div>
        <EmptyState
          v-if="!correlation.top_pairs.length"
          text="暂无相关性样本"
          hint="本地相关性快照里没有可对比的品种对：确认至少两个标的的日线已入库，再等一次分析作业。"
        />
      </div>
    </div>
    <EmptyState v-else text="相关性数据缺失" hint="等待分析任务产出相关性快照。" />
    <div v-if="correlation" class="card-foot">
      前 {{ correlation.top_pairs.length }} 对 · 窗口 {{ correlation.window }} 日 · 正值涨色 / 负值跌色
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtMacro, fmtNumber, fmtPct, fmtSigned, trendClass } from "@/composables/useFormat";
import type { Correlation, Regime, Wind } from "@/api/types";
import { corrLevel, corrWidth, countryLabel, regimeScores, scoreWidth, windBadgeClass } from "@/utils/analysisFormat";

defineProps<{
  wind: Wind | null;
  windRisk: string[];
  windNeedle: string;
  regimeList: Regime[];
  correlation: Correlation | null;
}>();
</script>

<style scoped>
.wind-card,
.regime-card,
.corr-card {
  display: flex;
  flex-direction: column;
}
.wind-body,
.corr-body {
  flex: 1 1 auto;
}
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}

/* ---------- 风向 ---------- */
.wind-body {
  padding-top: 9px;
}
.wind-head {
  display: flex;
  align-items: baseline;
  gap: 5px;
}
.wind-score {
  font-family: var(--mono);
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -1px;
  line-height: 1.02;
}
.wind-unit {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
}
.wind-tag {
  margin-left: auto;
  font-size: 11px;
  font-weight: 650;
}
.wind-gauge {
  position: relative;
  height: 6px;
  margin-top: 9px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--down) 58%, transparent),
    var(--surface-3) 50%,
    color-mix(in srgb, var(--up) 58%, transparent)
  );
}
.wind-zero {
  position: absolute;
  top: -3px;
  bottom: -3px;
  left: 50%;
  width: 1px;
  background: var(--border-strong);
}
.wind-needle {
  position: absolute;
  top: -3px;
  width: 3px;
  height: 12px;
  margin-left: -1.5px;
  border-radius: 2px;
  background: var(--text);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--bg) 72%, transparent);
}
.wind-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 3px;
  font-size: 9px;
  color: var(--dim);
}
.wind-rows {
  display: grid;
  gap: 5px;
  margin-top: 10px;
}
.wind-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 10.5px;
}
.wind-row > span {
  color: var(--muted);
}
.wind-row > b {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
}
.wind-risk {
  max-width: 62%;
  color: var(--muted);
  font-size: 9.5px !important;
  font-weight: 400 !important;
  text-align: right;
}

/* ---------- 周期 ---------- */
.regime-body {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: 1fr 1fr;
  gap: 0 14px;
  padding-top: 9px;
}
.regime-block {
  min-width: 0;
}
.regime-block + .regime-block {
  padding-left: 14px;
  border-left: 1px solid var(--border);
}
.regime-top {
  display: flex;
  align-items: center;
  gap: 5px;
}
.regime-country {
  font-size: 12px;
  font-weight: 650;
}
.regime-code {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.regime-conf {
  margin-left: auto;
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}
.regime-bars {
  display: grid;
  gap: 5px;
  margin-top: 8px;
}
.regime-bar {
  display: grid;
  grid-template-columns: 28px 32px 50px minmax(0, 1fr);
  align-items: center;
  gap: 5px;
}
.rb-label {
  font-size: 9.5px;
  color: var(--muted);
}
.rb-score {
  font-family: var(--mono);
  font-size: 10.5px;
  font-weight: 650;
}
.rb-z {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  text-align: right;
  white-space: nowrap;
}
.rb-track {
  height: 4px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.rb-track i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}
.regime-method {
  min-height: 42px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
  font-size: 9px;
  line-height: 1.5;
  color: var(--dim);
}
.regime-why {
  display: inline-block;
  margin-top: 4px;
  font-size: 9.5px;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
}
.regime-why:hover {
  text-decoration: underline;
}

/* ---------- 相关性 ---------- */
.corr-body {
  padding-top: 9px;
}
.corr-avg-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.corr-avg {
  font-family: var(--mono);
  font-size: 27px;
  font-weight: 700;
  letter-spacing: -0.8px;
  line-height: 1;
}
.corr-avg-label {
  margin-top: 3px;
  font-size: 9px;
  color: var(--dim);
}
.corr-avg-row .badge {
  margin-left: auto;
}
.corr-list {
  display: grid;
  gap: 5px;
  margin-top: 10px;
}
.corr-row {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr) 50px;
  align-items: center;
  gap: 6px;
}
.corr-pair {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.corr-pair i {
  padding: 0 2px;
  font-style: normal;
  color: var(--dim);
}
.corr-track {
  height: 4px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.corr-track i {
  display: block;
  height: 100%;
  border-radius: 999px;
}
.corr-track i.up {
  background: var(--up-color);
}
.corr-track i.down {
  background: var(--down-color);
}
.corr-val {
  font-size: 10px;
  font-weight: 600;
}
</style>
