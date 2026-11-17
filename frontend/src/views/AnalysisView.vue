<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 分析引擎 · 数据截至 {{ asofLabel }}</div>
        <h1 class="page-h1">
          分析引擎
          <span class="page-sub">市场风向 · 周期 · 相关性 · 归因 · 类比 · 日历</span>
        </h1>
      </div>
      <div class="page-actions">
        <span v-if="error && overview" class="badge badge--warn badge--sm">
          <svg class="ic" style="width: 11px; height: 11px"><use href="#i-alert" /></svg>刷新失败
        </span>
        <span class="badge badge--sm"><span class="dot"></span>更新于 {{ updatedLabel }}</span>
        <button class="btn btn--sm" type="button" :disabled="loading" @click="refreshAll()">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <!-- 黄金研判（独立轮询 /api/gold/overview，不阻塞下方分析区块） -->
    <section class="card gold-card">
      <div class="card-head">
        <span class="card-title">黄金研判</span>
        <span v-if="goldError && gold" class="badge badge--warn badge--sm">
          <svg class="ic" style="width: 11px; height: 11px"><use href="#i-alert" /></svg>刷新失败
        </span>
        <div class="card-actions">
          <span v-if="goldScore" class="card-sub">生成于 {{ goldGeneratedLabel }}</span>
        </div>
      </div>

      <div v-if="goldLoading && !gold" class="card-body">
        <SkeletonBlock :rows="2" :cells="4" :height="16" :gap="10" />
      </div>

      <ErrorState v-else-if="goldError && !gold" :error="goldError" @retry="refreshGold" />

      <div v-else-if="goldScore" class="card-body gold-body">
        <div class="gold-main">
          <div class="gold-score-line">
            <span class="gold-score" :class="goldTone">{{ goldScoreText }}</span>
            <span class="gold-scale">/ 100</span>
            <span class="badge badge--sm" :class="goldLabelClass">{{ goldLabel }}</span>
          </div>
          <div class="gold-meta">
            覆盖率 <b>{{ goldCoverageText }}</b>
            <span class="gold-meta-sep">·</span>
            已获取权重 <b>{{ goldAvailableWeight }}</b> / {{ goldTotalWeight }}
          </div>
          <div class="gold-sub">
            {{ goldAvailableCount }}/{{ goldTotalCount }} 因子可用 · 评分区间 −100 ～ +100
          </div>
          <RouterLink class="link-btn gold-link" to="/gold">查看完整黄金研判 →</RouterLink>
        </div>

        <div class="gold-factors">
          <div v-for="factor in goldTopFactors" :key="factor.code" class="gold-factor">
            <div class="gf-top">
              <span class="gf-name" :title="`${factor.name} · ${factor.category_label}`">{{ factor.name }}</span>
              <span class="badge badge--sm" :class="goldSignalClass(factor.signal)">{{ goldSignalText(factor.signal) }}</span>
            </div>
            <div class="gf-value" :title="factor.explain">{{ goldFactorValue(factor) }}</div>
            <div class="gf-foot">
              <span class="gf-contrib" :class="trendClass(factor.contribution)">贡献 {{ fmtSigned(factor.contribution, 2) }}</span>
              <span class="gf-cat">{{ factor.category_label }}</span>
            </div>
          </div>
          <EmptyState v-if="!goldTopFactors.length" text="暂无可评分因子" hint="等待黄金监控任务产出因子数据。" />
        </div>
      </div>

      <div v-else class="card-body">
        <EmptyState text="黄金评分暂不可用" hint="等待黄金监控任务产出评分。" />
      </div>

      <div v-if="goldScore" class="card-foot gold-foot">
        <svg class="ic"><use href="#i-info" /></svg>
        <span class="gold-method" :title="goldMethodology">{{ goldMethodology }}</span>
      </div>
    </section>

    <!-- 首次加载骨架 -->
    <template v-if="!overview && loading">
      <div class="analysis-top">
        <section v-for="index in 3" :key="index" class="card">
          <div class="card-head"><span class="card-title">加载中</span></div>
          <div class="card-body"><SkeletonBlock :rows="5" :cells="2" :height="12" :gap="9" /></div>
        </section>
      </div>
      <section class="card table-card analysis-block">
        <div class="card-head"><span class="card-title">定价归因</span></div>
        <div class="card-body"><SkeletonBlock :rows="6" :cells="7" :height="12" :gap="9" /></div>
      </section>
      <div class="analysis-mid">
        <section class="card table-card">
          <div class="card-head"><span class="card-title">历史类比</span></div>
          <div class="card-body"><SkeletonBlock :rows="5" :cells="5" :height="12" :gap="9" /></div>
        </section>
        <section class="card table-card">
          <div class="card-head"><span class="card-title">异动品种</span></div>
          <div class="card-body"><SkeletonBlock :rows="6" :cells="2" :height="12" :gap="9" /></div>
        </section>
      </div>
    </template>

    <section v-else-if="!overview" class="card">
      <ErrorState :error="error" @retry="refresh()" />
    </section>

    <template v-else>
      <!-- 风向 + 周期 + 相关性 -->
      <div class="analysis-top">
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

        <section class="card regime-card">
          <div class="card-head">
            <span class="card-title">周期状态</span>
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
          <EmptyState v-else text="周期数据缺失" hint="等待分析任务产出周期状态。" />
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
              <EmptyState v-if="!correlation.top_pairs.length" text="暂无相关性样本" />
            </div>
          </div>
          <EmptyState v-else text="相关性数据缺失" hint="等待分析任务产出相关性快照。" />
          <div v-if="correlation" class="card-foot">
            前 {{ correlation.top_pairs.length }} 对 · 窗口 {{ correlation.window }} 日 · 正值涨色 / 负值跌色
          </div>
        </section>
      </div>

      <!-- 定价归因 -->
      <section class="card table-card analysis-block">
        <div class="card-head">
          <span class="card-title">定价归因</span>
          <span class="badge badge--sm">{{ attrWindow ?? "—" }} 日窗口</span>
          <span class="badge badge--sm">近 {{ attrDays ?? "—" }} 日</span>
          <div class="card-actions">
            <span class="card-sub">贡献 = β × 因子变动 · 单位 % · 正值对收益为正贡献</span>
          </div>
        </div>
        <div class="table-wrap table-auto">
          <table class="data-table attr-table">
            <thead>
              <tr>
                <th style="width: 148px">资产</th>
                <th class="num" style="width: 92px">实际</th>
                <th class="num" style="width: 76px">R²</th>
                <th class="num" style="width: 104px">实际利率</th>
                <th class="num" style="width: 104px">盈亏平衡</th>
                <th class="num" style="width: 92px">曲线</th>
                <th class="num" style="width: 92px">美元</th>
                <th class="num" style="width: 96px">残差</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in attributionRows" :key="row.symbol">
                <td>
                  <span class="sym">{{ row.symbol }}</span>
                  <span class="nm attr-name">{{ row.name }}</span>
                </td>
                <td class="num" :class="trendClass(row.actual)">{{ fmtPct(row.actual) }}</td>
                <td class="num attr-r2">{{ fmtNumber(row.r2, 3) }}</td>
                <td class="num" :class="trendClass(row.realYield)">{{ fmtPct(row.realYield) }}</td>
                <td class="num" :class="trendClass(row.breakeven)">{{ fmtPct(row.breakeven) }}</td>
                <td class="num" :class="trendClass(row.curve)">{{ fmtPct(row.curve) }}</td>
                <td class="num" :class="trendClass(row.dxy)">{{ fmtPct(row.dxy) }}</td>
                <td class="num" :class="trendClass(row.residual)">{{ fmtPct(row.residual) }}</td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-if="!attributionRows.length" text="暂无归因数据" hint="等待分析任务产出归因结果。" />
        </div>
        <div v-if="attributionRows.length" class="card-foot">
          <svg class="ic"><use href="#i-info" /></svg>
          <span>
            实际 = 实际利率 + 盈亏平衡 + 曲线 + 美元 + 残差；残差为模型未解释部分。窗口
            {{ attrWindow ?? "—" }} 日，收益区间 {{ attrDays ?? "—" }} 个交易日，R² 偏低说明模型解释力有限。
          </span>
        </div>
      </section>

      <!-- 历史类比 + 异动品种 -->
      <div class="analysis-mid">
        <section class="card table-card">
          <div class="card-head">
            <span class="card-title">历史类比</span>
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
            <EmptyState v-if="!analogs?.matches.length" text="暂无历史类比" hint="等待分析任务产出相似日匹配。" />
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
              @click="openHistory(mover.symbol, mover.name)"
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
      </div>

      <!-- 日历事件后收益 -->
      <section class="card table-card analysis-block">
        <div class="card-head">
          <span class="card-title">日历事件后收益</span>
          <span class="badge badge--sm">{{ calendarStudy?.window ?? "—" }}</span>
          <span class="badge badge--sm">{{ fmtInt(calendarStudy?.events) }} 个事件</span>
          <div class="card-actions">
            <span class="card-sub">{{ calendarStudy ? `${calendarStudy.groups.length} 组样本 · 按样本量降序` : "等待数据" }}</span>
          </div>
        </div>
        <div class="table-wrap table-auto">
          <table class="data-table cal-table">
            <thead>
              <tr>
                <th style="width: 108px">国家 / 地区</th>
                <th style="width: 96px">事件类别</th>
                <th class="num" style="width: 72px">样本</th>
                <th class="num">AU 1日</th>
                <th class="num">AU 3日</th>
                <th class="num">CU 1日</th>
                <th class="num">CU 3日</th>
                <th class="num">沪深300 1日</th>
                <th class="num">沪深300 3日</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in calendarRows" :key="`${row.country}-${row.category}`">
                <td>{{ row.country }}</td>
                <td class="dim">{{ row.category }}</td>
                <td class="num">{{ fmtInt(row.n) }}</td>
                <td class="num" :class="trendClass(row.au1d)">{{ fmtPct(row.au1d) }}</td>
                <td class="num" :class="trendClass(row.au3d)">{{ fmtPct(row.au3d) }}</td>
                <td class="num" :class="trendClass(row.cu1d)">{{ fmtPct(row.cu1d) }}</td>
                <td class="num" :class="trendClass(row.cu3d)">{{ fmtPct(row.cu3d) }}</td>
                <td class="num" :class="trendClass(row.hs3001d)">{{ fmtPct(row.hs3001d) }}</td>
                <td class="num" :class="trendClass(row.hs3003d)">{{ fmtPct(row.hs3003d) }}</td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-if="!calendarRows.length" text="暂无日历研究数据" hint="等待数据采集与事件研究任务产出。" />
        </div>
        <div v-if="calendarStudy" class="card-foot cal-foot">
          <svg class="ic"><use href="#i-info" /></svg>
          <span>{{ calendarStudy.note }}（仅列样本量前 {{ calendarRows.length }} 组，共 {{ calendarStudy.groups.length }} 组。）</span>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtInt, fmtMacro, fmtNumber, fmtPct, fmtSigned, fmtTime, trendClass } from "@/composables/useFormat";
import { getAnalytics, getGoldOverview } from "@/api/endpoints";
import type { CalendarStudyGroup, GoldFactor, Regime } from "@/api/types";
import { useHistoryStore } from "@/stores/history";

const historyStore = useHistoryStore();

const { data: overview, error, loading, lastUpdated, refresh } = usePolling(getAnalytics, {
  interval: 120000,
});

/** 黄金研判：独立轮询，失败/加载都不影响下方分析区块 */
const { data: gold, error: goldError, loading: goldLoading, refresh: refreshGold } = usePolling(
  getGoldOverview,
  { interval: 60000 },
);

const goldScore = computed(() => gold.value?.score ?? null);
const goldLabel = computed(() => goldScore.value?.label ?? "—");
const goldScoreText = computed(() => (goldScore.value ? fmtSigned(goldScore.value.score, 1) : "—"));
/** 正分涨色 / 负分跌色 / 中性或 0 用 muted（与后端 ±18 分档一致） */
const goldTone = computed(() => {
  const score = goldScore.value;
  if (!score) return "flat";
  if (score.label === "中性") return "flat";
  if (score.score > 0) return "up";
  if (score.score < 0) return "down";
  return "flat";
});
const goldLabelClass = computed(() => {
  if (goldLabel.value === "强多" || goldLabel.value === "偏多") return "badge--up";
  if (goldLabel.value === "强空" || goldLabel.value === "偏空") return "badge--down";
  return "";
});
const goldCoverageText = computed(() =>
  goldScore.value ? fmtMacro(goldScore.value.coverage, "%", 0) : "—",
);
const goldAvailableCount = computed(
  () => (goldScore.value?.factors ?? []).filter((factor) => factor.available).length,
);
const goldTotalCount = computed(() => goldScore.value?.factors.length ?? 0);
const goldAvailableWeight = computed(() => goldScore.value?.available_weight ?? 0);
const goldTotalWeight = computed(() => goldScore.value?.total_weight ?? 0);
const goldGeneratedLabel = computed(() => (goldScore.value ? fmtTime(goldScore.value.generated_at, true) : "—"));
const goldMethodology = computed(() => goldScore.value?.methodology ?? "");

/** 取 |贡献| 最大的前 4 个可用因子 */
const goldTopFactors = computed<GoldFactor[]>(() => {
  const factors = goldScore.value?.factors ?? [];
  return factors
    .filter((factor) => factor.available && factor.value !== null && factor.value !== undefined)
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 4);
});

function goldFactorValue(factor: GoldFactor): string {
  if (factor.value === null || factor.value === undefined) return "—";
  const digits = factor.unit === "%" ? 2 : Math.abs(factor.value) >= 1000 ? 0 : 2;
  const text = fmtNumber(factor.value, digits);
  if (factor.unit === "%") return `${text}%`;
  return factor.unit ? `${text} ${factor.unit}` : text;
}

function goldSignalText(signal: string): string {
  if (signal === "bullish") return "利多";
  if (signal === "bearish") return "利空";
  if (signal === "neutral") return "中性";
  return "—";
}

function goldSignalClass(signal: string): string {
  if (signal === "bullish") return "badge--up";
  if (signal === "bearish") return "badge--down";
  return "";
}

/** 刷新按钮同时刷新分析引擎与黄金研判 */
function refreshAll(): void {
  void Promise.all([refresh(), refreshGold()]);
}

/** 归因资产展示名（后端只返回 symbol） */
const SYMBOL_NAMES: Record<string, string> = {
  AU: "沪金",
  CU: "沪铜",
  SC: "原油",
  AG: "沪银",
  "603993": "洛阳钼业",
  "000300": "沪深300",
  GC: "COMEX黄金",
  SI: "COMEX白银",
  XAUUSD: "伦敦金现",
  BZ: "Brent原油",
  CL: "WTI原油",
  HG: "LME铜",
  I: "铁矿石",
  AL: "沪铝",
  ZN: "沪锌",
  NI: "沪镍",
  AL_LME: "伦铝",
  ZN_LME: "伦锌",
  NI_LME: "伦镍",
  M: "豆粕",
  P: "棕榈油",
  SR: "白糖",
  CF: "棉花",
  SPX: "标普500",
  NDX: "纳斯达克100",
  DJIA: "道琼斯",
  HSI: "恒生指数",
  DXY: "美元指数",
  USDCNH: "离岸人民币",
  EURUSD: "欧元美元",
  GBPUSD: "英镑美元",
  USDJPY: "美元日元",
  USDSEK: "美元瑞典克朗",
  USDCHF: "美元瑞郎",
  USDCAD: "美元加元",
};

const ATTR_ORDER: readonly string[] = ["AU", "CU", "SC", "AG", "603993", "000300"];

const wind = computed(() => overview.value?.wind ?? null);
const windRisk = computed(() => wind.value?.components.risk_assets ?? []);
const regimeList = computed<Regime[]>(() => {
  const map = overview.value?.regimes;
  if (!map) return [];
  const order = ["US", "CN"];
  const keys = [
    ...order.filter((key) => Boolean(map[key])),
    ...Object.keys(map).filter((key) => !order.includes(key)),
  ];
  return keys.map((key) => map[key]);
});
const correlation = computed(() => overview.value?.correlation ?? null);
const analogs = computed(() => overview.value?.analogs ?? null);
const calendarStudy = computed(() => overview.value?.calendar_study ?? null);
const movers = computed(() => overview.value?.movers ?? []);

const updatedLabel = computed(() =>
  lastUpdated.value ? fmtTime(lastUpdated.value.toISOString()) : "—",
);
const asofLabel = computed(() => {
  if (wind.value?.asof) return wind.value.asof;
  return overview.value?.asof ? fmtDate(overview.value.asof) : "—";
});
const windNeedle = computed(() => {
  const score = Math.max(-100, Math.min(100, wind.value?.score ?? 0));
  return `${((score + 100) / 2).toFixed(1)}%`;
});

interface AttributionRow {
  symbol: string;
  name: string;
  actual: number | null;
  r2: number | null;
  realYield: number | null;
  breakeven: number | null;
  curve: number | null;
  dxy: number | null;
  residual: number | null;
  window: number | null;
  days: number | null;
}

function toNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

const attributionRows = computed<AttributionRow[]>(() => {
  const map = overview.value?.attribution;
  if (!map) return [];
  const keys = [
    ...ATTR_ORDER.filter((key) => Boolean(map[key])),
    ...Object.keys(map).filter((key) => !ATTR_ORDER.includes(key)),
  ];
  return keys.map((symbol) => {
    const entry = map[symbol];
    const contributions = entry.contributions_pct ?? {};
    const factor = (key: string): number | null => toNumber(contributions[key]);
    return {
      symbol,
      name: SYMBOL_NAMES[symbol] ?? symbol,
      actual: toNumber(entry.actual_pct),
      r2: toNumber(entry.r2),
      realYield: factor("real_yield_chg"),
      breakeven: factor("breakeven_chg"),
      curve: factor("curve_chg"),
      dxy: factor("dxy_chg"),
      residual: toNumber(entry.residual_pct),
      window: toNumber(entry.window),
      days: toNumber(entry.contrib_days),
    };
  });
});

const attrWindow = computed(() => attributionRows.value[0]?.window ?? null);
const attrDays = computed(() => attributionRows.value[0]?.days ?? null);

function cell(group: CalendarStudyGroup, symbol: string, horizon: string): number | null {
  return toNumber(group.assets?.[symbol]?.[horizon]);
}

const calendarRows = computed(() => {
  const groups = calendarStudy.value?.groups ?? [];
  return [...groups]
    .sort((a, b) => (b.n ?? 0) - (a.n ?? 0))
    .slice(0, 12)
    .map((group) => ({
      country: group.country,
      category: group.category,
      n: group.n,
      au1d: cell(group, "AU", "1d"),
      au3d: cell(group, "AU", "3d"),
      cu1d: cell(group, "CU", "1d"),
      cu3d: cell(group, "CU", "3d"),
      hs3001d: cell(group, "000300", "1d"),
      hs3003d: cell(group, "000300", "3d"),
    }));
});

function countryLabel(country: string): string {
  if (country === "US") return "美国";
  if (country === "CN") return "中国";
  return country;
}

function regimeScores(regime: Regime): Array<{ label: string; score: number; z: number | null }> {
  return [
    { label: "增长", score: regime.growth_score, z: regime.growth_z ?? null },
    { label: "通胀", score: regime.inflation_score, z: regime.inflation_z ?? null },
    { label: "流动", score: regime.liquidity_score, z: null },
  ];
}

function scoreWidth(score: number | null): string {
  const value = Math.max(0, Math.min(100, score ?? 0));
  return `${value}%`;
}

function windBadgeClass(label: string): string {
  if (label === "进攻") return "badge--up";
  if (label === "避险") return "badge--down";
  return "";
}

function corrWidth(corr: number | null): string {
  return `${Math.max(3, Math.min(100, Math.abs(corr ?? 0) * 100))}%`;
}

function corrLevel(avg: number | null): { text: string; cls: string } {
  if (avg === null) return { text: "—", cls: "" };
  if (avg >= 0.4) return { text: "联动偏高", cls: "badge--warn" };
  if (avg >= 0.25) return { text: "联动中等", cls: "badge--accent" };
  return { text: "联动偏弱", cls: "" };
}

function trendLabel(trend: string): string {
  if (trend === "up") return "上行";
  if (trend === "down") return "下行";
  if (trend === "mixed") return "震荡";
  return trend || "—";
}

function trendBadgeClass(trend: string): string {
  if (trend === "up") return "badge--up";
  if (trend === "down") return "badge--down";
  return "";
}

function openHistory(symbol: string, name: string): void {
  void historyStore.openHistory("instrument", symbol, name);
}
</script>

<style scoped>
.analysis-top {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.32fr) minmax(0, 0.98fr);
  gap: 10px;
  align-items: stretch;
}
.analysis-top > .card,
.analysis-mid > .card {
  display: flex;
  flex-direction: column;
}
.analysis-top > .card > .card-body,
.analysis-mid > .card > .card-body {
  flex: 1 1 auto;
}
.analysis-block {
  margin-top: 10px;
}
.analysis-mid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 352px;
  gap: 10px;
  margin-top: 10px;
  align-items: stretch;
}
.analysis-mid > .card > .card-foot {
  margin-top: auto;
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
.table-auto {
  max-height: none;
}
.attr-table td.num {
  font-size: 11.5px;
}
.attr-name {
  margin-left: 6px;
  font-family: var(--sans);
  font-size: 11px;
  color: var(--muted);
}
.attr-r2 {
  color: var(--muted);
}
.analog-table td,
.cal-table td {
  font-size: 11.5px;
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

.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
.analog-foot,
.cal-foot {
  line-height: 1.6;
}

@media (max-width: 1240px) {
  .analysis-top {
    grid-template-columns: 1fr 1fr;
  }
  .analysis-top .corr-card {
    grid-column: 1 / -1;
  }
  .analysis-mid {
    grid-template-columns: 1fr;
  }
}

/* ---------- 黄金研判 ---------- */
.gold-card {
  margin-bottom: 10px;
}
.gold-body {
  display: flex;
  align-items: stretch;
  gap: 18px;
  padding: 11px 13px 12px;
}
.gold-main {
  display: flex;
  flex: none;
  flex-direction: column;
  min-width: 208px;
  max-width: 252px;
  padding-right: 18px;
  border-right: 1px solid var(--border);
}
.gold-score-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.gold-score {
  font-family: var(--mono);
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -1px;
  line-height: 1.05;
}
.gold-scale {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
}
.gold-score-line .badge {
  margin-left: auto;
  flex: none;
}
.gold-meta {
  margin-top: 4px;
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.55;
}
.gold-meta b {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 650;
  color: var(--text);
}
.gold-meta-sep {
  padding: 0 3px;
  color: var(--dim);
}
.gold-sub {
  margin-top: 3px;
  font-size: 9px;
  line-height: 1.5;
  color: var(--dim);
}
.gold-link {
  align-self: flex-start;
  margin-top: auto;
  padding-top: 6px;
}
.gold-factors {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  min-width: 0;
}
.gold-factor {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 7px 9px 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.gf-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.gf-name {
  min-width: 0;
  overflow: hidden;
  font-size: 10.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gf-top .badge {
  flex: none;
  margin-left: auto;
}
.gf-value {
  margin-top: 5px;
  overflow: hidden;
  font-family: var(--mono);
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.3px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gf-foot {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  margin-top: 2px;
  font-size: 9px;
  color: var(--dim);
}
.gf-contrib {
  flex: none;
  font-family: var(--mono);
  font-weight: 600;
  white-space: nowrap;
}
.gf-cat {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gold-foot {
  min-width: 0;
}
.gold-method {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

@media (max-width: 1240px) {
  .gold-factors {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .gold-body {
    flex-direction: column;
  }
  .gold-main {
    max-width: none;
    padding-right: 0;
    padding-bottom: 9px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
  .gold-link {
    margin-top: 6px;
  }
}
</style>
