<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 交易信号</div>
        <h1 class="page-h1">
          交易信号
          <span class="page-sub">信号 · 交易计划 · 回测 · 预测校准</span>
        </h1>
        <span class="gen-at">（生成于 {{ updatedLabel }}）</span>
      </div>
      <div class="page-actions">
        <span v-if="summaryError && decisions" class="badge badge--warn badge--sm">
          <svg class="ic" style="width: 11px; height: 11px"><use href="#i-alert" /></svg>刷新失败
        </span>
                <button class="btn btn--sm" type="button" :disabled="summaryLoading" @click="refreshSummary()">
          <svg class="ic" :class="{ spin: summaryLoading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <!-- 首次加载骨架 -->
    <template v-if="!decisions && summaryLoading">
      <div class="kpi-grid">
        <article v-for="index in 4" :key="index" class="card kpi">
          <div class="kpi-top"><span class="kpi-label">加载中</span></div>
          <div class="card-body" style="padding: 8px 0 2px">
            <SkeletonBlock :rows="2" :cells="2" :height="10" :gap="6" />
          </div>
          <div class="kpi-meter"><i class="track"></i></div>
        </article>
      </div>
      <section class="card sig-block">
        <div class="card-head"><span class="card-title">信号类型统计</span></div>
        <div class="card-body"><SkeletonBlock :rows="2" :cells="3" :height="14" :gap="10" /></div>
      </section>
      <section class="card table-card sig-block">
        <div class="card-head"><span class="card-title">当前信号</span></div>
        <div class="card-body"><SkeletonBlock :rows="7" :cells="5" :height="12" :gap="9" /></div>
      </section>
    </template>

    <section v-else-if="!decisions" class="card">
      <ErrorState :error="summaryError" @retry="refreshSummary()" />
    </section>

    <template v-else>
      <!-- 指标卡 -->
      <div class="kpi-grid">
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
            <span class="kpi-label">当前信号</span>
            <span class="kpi-flag"><span class="badge badge--sm badge--live">已生成</span></span>
          </div>
          <div class="kpi-value">{{ fmtInt(counts.signals) }}<small>条</small></div>
          <div class="kpi-sub">按强度排序 · 表内展示前 {{ visibleSignals.length }} 条</div>
          <div class="kpi-meter"><i class="ok" :style="{ width: meterWidth(counts.signals) }"></i><i class="track"></i></div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-tasks" /></svg></span>
            <span class="kpi-label">交易计划</span>
            <span class="kpi-flag"><span class="badge badge--sm badge--warn">草稿</span></span>
          </div>
          <div class="kpi-value">{{ fmtInt(counts.plans) }}<small>个</small></div>
          <div class="kpi-sub">draft 草稿 · 需人工确认后执行</div>
          <div class="kpi-meter"><i class="warn" :style="{ width: meterWidth(counts.plans) }"></i><i class="track"></i></div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-target" /></svg></span>
            <span class="kpi-label">未结预测</span>
            <span class="kpi-flag"><span class="badge badge--sm">待结算</span></span>
          </div>
          <div class="kpi-value">{{ fmtInt(openPredictions) }}<small>条</small></div>
          <div class="kpi-sub">结算后进入预测校准账本</div>
          <div class="kpi-meter"><i :style="{ width: meterWidth(openPredictions) }"></i><i class="track"></i></div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-shield-check" /></svg></span>
            <span class="kpi-label">突破命中率</span>
            <span class="kpi-flag">
              <span class="badge badge--sm" :class="breakoutHit !== null && breakoutHit >= 0.5 ? 'badge--live' : 'badge--warn'">
                walk-forward
              </span>
            </span>
          </div>
          <div class="kpi-value">{{ breakoutHitLabel }}<small>{{ breakout?.horizon ?? "—" }} 日</small></div>
          <div class="kpi-sub">breakout · 含 {{ fmtMacro(breakout?.cost_pct, "%", 2) }} 交易成本</div>
          <div class="kpi-meter">
            <i :class="breakoutHit !== null && breakoutHit >= 0.5 ? 'ok' : 'warn'" :style="{ width: hitMeterWidth }"></i>
            <i class="track"></i>
          </div>
        </article>
      </div>

      <!-- 信号类型统计 -->
      <section class="card sig-block">
        <div class="card-head">
          <span class="card-title">信号类型统计</span>
          <span class="badge badge--sm">{{ fmtInt(typeTotal) }} 条历史信号</span>
          <div class="card-actions"><span class="card-sub">全部历史信号 · 多空分布与平均强度</span></div>
        </div>
        <div class="card-body sig-type-body">
          <div class="sig-type-grid">
            <div v-for="stat in typeStats" :key="stat.key" class="sig-type">
              <div class="sig-type-head">
                <span class="sig-type-name">{{ stat.label }}</span>
                <span class="sig-type-key">{{ stat.key }}</span>
                <span class="badge badge--sm">{{ fmtInt(stat.count) }} 条</span>
              </div>
              <div class="sig-type-counts">
                <span>多 <b class="up">{{ fmtInt(stat.long) }}</b></span>
                <span>空 <b class="down">{{ fmtInt(stat.short) }}</b></span>
                <span class="st-avg">平均强度 <b>{{ fmtNumber(stat.avgStrength, 2) }}</b></span>
              </div>
              <div class="sig-meter"><i :style="{ width: strengthWidth(stat.avgStrength) }"></i></div>
            </div>
          </div>
          <EmptyState v-if="!typeStats.length" text="暂无信号类型统计" hint="等待信号引擎产出。" />
        </div>
      </section>

      <!-- 当前信号 -->
      <section class="card table-card sig-block">
        <div class="card-head">
          <span class="card-title">当前信号</span>
          <span class="badge badge--sm">{{ visibleSignals.length }} / {{ signals.length }} 条</span>
          <div class="card-actions"><span class="card-sub">按信号强度降序 · 方向：多 = 看涨 / 空 = 看跌</span></div>
        </div>
        <div v-if="visibleSignals.length" class="table-wrap table-auto">
          <table class="data-table sig-table">
            <thead>
              <tr>
                <th style="width: 150px">品种</th>
                <th style="width: 108px">类型</th>
                <th style="width: 68px">方向</th>
                <th class="num" style="width: 118px">强度</th>
                <th>说明</th>
                <th class="num" style="width: 104px">信号日期</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="signal in visibleSignals" :key="signal.id">
                <td>
                  <span class="sym">{{ signal.symbol }}</span>
                  <span class="nm">{{ symbolName(signal.symbol) }}</span>
                </td>
                <td><span class="badge badge--sm">{{ typeLabel(signal.type) }}</span></td>
                <td>
                  <span class="badge badge--sm" :class="directionClass(signal.direction)">
                    {{ directionLabel(signal.direction) }}
                  </span>
                </td>
                <td class="num">
                  <span class="strength-cell">
                    <span class="strength-track"><i :style="{ width: strengthWidth(signal.strength) }"></i></span>
                    <b>{{ fmtNumber(signal.strength, 2) }}</b>
                  </span>
                </td>
                <td class="note-cell" :title="signal.note ?? ''">{{ signal.note ?? "—" }}</td>
                <td class="num tm">{{ fmtDate(signal.ts) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else text="暂无当前信号" hint="等待信号扫描任务产出；信号会按强度排序展示前 10 条。" />
      </section>

      <!-- 交易计划 -->
      <section class="card table-card sig-block">
        <div class="card-head">
          <span class="card-title">交易计划</span>
          <span class="badge badge--sm">{{ plans.length }} 个</span>
          <div class="card-actions"><span class="card-sub">以损定量 · 单笔风险预算 ≤ 0.3% · 风控徽标取 checks 全部通过</span></div>
        </div>
        <div v-if="plans.length" class="table-wrap table-auto">
          <table class="data-table plan-table">
            <thead>
              <tr>
                <th style="width: 132px">品种</th>
                <th style="width: 66px">方向</th>
                <th class="num" style="width: 152px">入场区</th>
                <th class="num" style="width: 92px">止损</th>
                <th class="num" style="width: 92px">T1</th>
                <th class="num" style="width: 96px">标准手</th>
                <th class="num" style="width: 100px">保证金</th>
                <th class="num" style="width: 84px">手续费</th>
                <th style="width: 98px">风控</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="plan in plans" :key="plan.id">
                <tr>
                  <td>
                    <span class="sym">{{ plan.symbol }}</span>
                    <span class="nm">{{ symbolName(plan.symbol) }}</span>
                  </td>
                  <td>
                    <span class="badge badge--sm" :class="sideClass(plan.side)">{{ sideLabel(plan.side) }}</span>
                  </td>
                  <td class="num">
                    <span class="mono">{{ fmtPrice(plan.entry_low) }} – {{ fmtPrice(plan.entry_high) }}</span>
                  </td>
                  <td class="num">{{ fmtPrice(plan.stop) }}</td>
                  <td class="num">{{ fmtPrice(targetValue(plan, "T1")) }}</td>
                  <td class="num">
                    <template v-if="plan.size > 0">{{ fmtInt(plan.size) }}<span class="unit">手</span></template>
                    <template v-else>
                      <b class="zero-lots">{{ fmtNumber(plan.size, 2) }} 手</b><span class="unit">标准</span>
                    </template>
                  </td>
                  <td class="num">{{ fmtInt(plan.detail?.margin) }}<span class="unit">元</span></td>
                  <td class="num">{{ fmtNumber(plan.detail?.fee, 2) }}<span class="unit">元</span></td>
                  <td>
                    <span
                      v-if="planPassed(plan) === true"
                      class="badge badge--sm badge--live"
                      title="风控检查全部通过"
                    >
                      <svg class="ic" style="width: 10px; height: 10px"><use href="#i-shield-check" /></svg>通过
                    </span>
                    <span v-else-if="planPassed(plan) === false" class="badge badge--sm badge--warn" :title="failedText(plan)">
                      <svg class="ic" style="width: 10px; height: 10px"><use href="#i-alert" /></svg>拦截
                    </span>
                    <span v-else class="badge badge--sm" title="该计划没有风控检查记录">无检查</span>
                  </td>
                </tr>
                <tr class="plan-sub-row">
                  <td colspan="9">
                    <div class="plan-sub" :title="planSubtitle(plan)">
                      <span>
                        仓位 <b>{{ fmtNumber(plan.detail?.lots ?? plan.size, 2) }}</b> 标准手（基准权益
                        {{ fmtInt(plan.detail?.base_equity) }} · 止损距离
                        {{ fmtMacro(plan.detail?.stop_distance_pct, "%", 2) }} · 权重
                        {{ fmtMacro(plan.detail?.weight_pct, "%", 1) }} · 杠杆
                        {{ fmtNumber(plan.detail?.leverage, 1) }}×）
                      </span>
                      <span>
                        风险金额 <b>{{ fmtInt(plan.detail?.risk_amount) }}</b> 元 · 盈亏比
                        <b>{{ fmtNumber(plan.detail?.risk_reward, 2) }}</b>
                      </span>
                      <span>时间止损 <b>{{ fmtInt(plan.time_stop_days) }}</b> 日 · 状态 <b>{{ plan.status }}</b></span>
                      <span class="ps-invalid">失效：{{ plan.invalidation ?? "—" }}</span>
                    </div>
                    <div v-if="plan.detail?.sizing_note" class="plan-sub plan-sub--note">
                      <span>{{ plan.detail.sizing_note }}</span>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <EmptyState v-else text="暂无交易计划" hint="信号通过风控后才会生成为草稿计划。" />
        <div class="card-foot plan-foot">
          <svg class="ic"><use href="#i-info" /></svg>
          <span>
            计划均为 <b>draft 草稿</b>，仅为按风险预算测算的建议，需人工确认后执行；手数以「标准权益 10 万」为基准计算（可与整数手并存），
            仓位/止损/权重由波动与共识强度推导，<b>与账户余额无关</b>，按自有权益等比缩放即可。保证金 / 手续费为按合约乘数与保证金率估算。
          </span>
        </div>
      </section>

      <!-- 信号回测 -->
      <section class="card table-card sig-block">
        <div class="card-head">
          <span class="card-title">信号回测</span>
          <span class="badge badge--sm">walk-forward</span>
          <div class="card-actions"><span class="card-sub">三条规则 · 10 日持有 · 含交易成本</span></div>
        </div>
        <div v-if="backtestRows.length" class="table-wrap table-auto">
          <table class="data-table backtest-table">
            <thead>
              <tr>
                <th style="width: 190px">规则</th>
                <th class="num">命中率</th>
                <th class="num">均值</th>
                <th class="num">样本</th>
                <th class="num">训练命中</th>
                <th class="num">测试命中</th>
                <th class="num">盈亏比</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rule in backtestRows" :key="rule.key">
                <td>
                  <span class="bt-rule">{{ rule.label }}</span>
                  <span class="bt-key">{{ rule.key }}</span>
                  <span class="badge badge--sm">{{ fmtInt(rule.horizon) }} 日</span>
                </td>
                <td class="num" :class="trendClass(rule.hit === null ? null : rule.hit - 0.5)">{{ hitLabel(rule.hit) }}</td>
                <td class="num" :class="trendClass(rule.avg)">{{ fmtPct(rule.avg) }}</td>
                <td class="num">{{ fmtInt(rule.count) }}</td>
                <td class="num">{{ hitLabel(rule.train) }}</td>
                <td class="num">{{ hitLabel(rule.test) }}</td>
                <td class="num">{{ fmtNumber(rule.profitFactor, 2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else text="暂无回测结果" hint="运行信号回测任务后展示三条规则的历史表现。" />
        <div v-if="backtestRows.length" class="card-foot">
          <span>成本 <b>{{ fmtMacro(backtestMeta?.cost, "%", 2) }}</b> / 笔 · 持有 <b>{{ fmtInt(backtestMeta?.horizon) }}</b> 交易日</span>
          <span>·</span>
          <span>walk-forward 分界 <b>{{ backtestMeta?.split ?? "—" }}</b>，测试段为样本外</span>
          <span class="spacer"></span>
          <span>均值 = 扣除成本后的单笔平均收益</span>
        </div>
      </section>

      <!-- 预测校准 -->
      <section class="card sig-block">
        <div class="card-head">
          <span class="card-title">预测校准</span>
          <span class="badge badge--sm">{{ reviewData ? `${fmtInt(reviewData.count)} 条已结算` : "加载中" }}</span>
          <div class="card-actions"><span class="card-sub">Brier 越低越好 · 0.25 约等于无信息基线</span></div>
        </div>
        <div v-if="reviewLoading && !reviewData" class="card-body">
          <SkeletonBlock :rows="2" :cells="3" :height="14" :gap="10" />
        </div>
        <ErrorState v-else-if="reviewError" :error="reviewError" @retry="refreshReview()" />
        <div v-else class="card-body calib-body">
          <div class="calib-metrics">
            <div class="calib-metric">
              <span class="cm-label">已结算预测</span>
              <span class="cm-value">{{ fmtInt(reviewData?.count) }}</span>
            </div>
            <div class="calib-metric">
              <span class="cm-label">Brier 分数</span>
              <span class="cm-value">{{ reviewData?.brier != null ? fmtNumber(reviewData.brier, 3) : "—" }}</span>
            </div>
            <div class="calib-metric">
              <span class="cm-label">方向命中率</span>
              <span class="cm-value">{{ reviewData?.hit_rate != null ? fmtMacro(reviewData.hit_rate * 100, "%", 1) : "—" }}</span>
            </div>
          </div>
          <div class="calib-right">
            <table v-if="calibrationRows.length" class="data-table calib-table">
              <thead>
                <tr>
                  <th>概率段</th>
                  <th class="num">预测</th>
                  <th class="num">实际</th>
                  <th class="num">样本</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in calibrationRows" :key="row.bucket">
                  <td class="mono">{{ row.bucket }}</td>
                  <td class="num">{{ percentLabel(row.predicted) }}</td>
                  <td class="num">{{ percentLabel(row.actual) }}</td>
                  <td class="num">{{ fmtInt(row.count) }}</td>
                </tr>
              </tbody>
            </table>
            <EmptyState
              v-else
              text="暂无已结算预测"
              :hint="`${fmtInt(openPredictions)} 条预测仍未结算；结算后自动生成 Brier 分数与校准分段。`"
            />
          </div>
        </div>
        <div class="card-foot">
          <svg class="ic"><use href="#i-info" /></svg>
          <span>预测结算后才计入评分；样本不足时校准曲线仅供参考，不构成交易依据。</span>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtInt, fmtMacro, fmtNumber, fmtPct, fmtPrice, fmtTime, trendClass } from "@/composables/useFormat";
import { getDecisions, getDecisionsReview } from "@/api/endpoints";
import { SIGNAL_TYPE_LABEL } from "@/utils/market";
import type { BacktestRule, RiskCheck, TradePlan } from "@/api/types";

const {
  data: summaryPayload,
  error: summaryError,
  loading: summaryLoading,
  lastUpdated,
  refresh: refreshSummary,
} = usePolling(getDecisions, { interval: 60000 });
const {
  data: reviewPayload,
  error: reviewError,
  loading: reviewLoading,
  refresh: refreshReview,
} = usePolling(getDecisionsReview, { interval: 60000 });

const SYMBOL_NAMES: Record<string, string> = {
  AG: "沪银",
  AU: "沪金",
  CU: "沪铜",
  SC: "原油",
  SR: "白糖",
  M: "豆粕",
  P: "棕榈油",
  ZN: "沪锌",
  AL: "沪铝",
  NI: "沪镍",
  I: "铁矿石",
  CF: "棉花",
  "000300": "沪深300",
  "603993": "洛阳钼业",
  GC: "COMEX黄金",
  SI: "COMEX白银",
  XAUUSD: "伦敦金现",
  BZ: "Brent原油",
  CL: "WTI原油",
  HG: "LME铜",
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
  AL_LME: "伦铝",
  ZN_LME: "伦锌",
  NI_LME: "伦镍",
};

const TYPE_ORDER = ["momentum", "mean_reversion", "breakout"];
const RULE_ORDER = ["momentum", "mean_reversion", "breakout"];

const decisions = computed(() => summaryPayload.value);
const reviewData = computed(() => reviewPayload.value?.data ?? null);
const counts = computed(() => decisions.value?.counts ?? { signals: 0, plans: 0 });
const openPredictions = computed(() => decisions.value?.open_predictions ?? 0);
const breakout = computed(() => decisions.value?.backtest?.breakout ?? null);
const breakoutHit = computed(() => breakout.value?.hit_rate ?? null);
const breakoutHitLabel = computed(() =>
  breakoutHit.value === null ? "—" : fmtMacro(breakoutHit.value * 100, "%", 1),
);
const hitMeterWidth = computed(() =>
  `${Math.max(0, Math.min(100, Math.round((breakoutHit.value ?? 0) * 100)))}%`,
);
const updatedLabel = computed(() =>
  lastUpdated.value ? fmtTime(lastUpdated.value.toISOString()) : "—",
);
const todayLabel = computed(() => {
  const date = new Date();
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
});

const signals = computed(() => decisions.value?.signals ?? []);
const plans = computed(() => decisions.value?.plans ?? []);
const visibleSignals = computed(() =>
  [...signals.value].sort((a, b) => (b.strength ?? 0) - (a.strength ?? 0)).slice(0, 10),
);

function typeLabel(type: string): string {
  return SIGNAL_TYPE_LABEL[type] ?? type;
}

const typeStats = computed(() => {
  const map = decisions.value?.signal_types ?? {};
  const keys = [
    ...TYPE_ORDER.filter((key) => Boolean(map[key])),
    ...Object.keys(map).filter((key) => !TYPE_ORDER.includes(key)),
  ];
  return keys.map((key) => {
    const stat = map[key];
    return {
      key,
      label: typeLabel(key),
      count: stat.count ?? 0,
      long: stat.long ?? 0,
      short: stat.short ?? 0,
      avgStrength: stat.avg_strength ?? 0,
    };
  });
});
const typeTotal = computed(() => typeStats.value.reduce((sum, stat) => sum + stat.count, 0));

interface BacktestRow {
  key: string;
  label: string;
  horizon: number | null;
  cost: number | null;
  count: number | null;
  hit: number | null;
  avg: number | null;
  train: number | null;
  test: number | null;
  profitFactor: number | null;
  split: string | null;
}

function toNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

const backtestRows = computed<BacktestRow[]>(() => {
  const map = decisions.value?.backtest ?? {};
  const keys = [
    ...RULE_ORDER.filter((key) => Boolean(map[key])),
    ...Object.keys(map).filter((key) => !RULE_ORDER.includes(key)),
  ];
  return keys.map((key) => {
    const rule: BacktestRule = map[key];
    return {
      key,
      label: typeLabel(key),
      horizon: toNumber(rule.horizon),
      cost: toNumber(rule.cost_pct),
      count: toNumber(rule.count),
      hit: toNumber(rule.hit_rate),
      avg: toNumber(rule.avg_return_pct),
      train: toNumber(rule.walk_forward?.train?.hit_rate),
      test: toNumber(rule.walk_forward?.test?.hit_rate),
      profitFactor: toNumber(rule.profit_factor),
      split: rule.walk_forward?.split ?? null,
    };
  });
});
const backtestMeta = computed(() => backtestRows.value[0] ?? null);

interface CalibrationRow {
  bucket: string;
  predicted: number | null;
  actual: number | null;
  count: number | null;
}

const calibrationRows = computed<CalibrationRow[]>(() => {
  const rows = reviewData.value?.calibration ?? [];
  return rows.map((row) => {
    const raw = row as unknown as Record<string, unknown>;
    return {
      bucket: typeof raw.bucket === "string" ? raw.bucket : "—",
      predicted: toNumber(raw.predicted ?? raw.avg_probability),
      actual: toNumber(raw.actual ?? raw.hit_rate),
      count: toNumber(raw.count ?? raw.n),
    };
  });
});

function symbolName(symbol: string): string {
  return SYMBOL_NAMES[symbol] ?? "";
}

function directionLabel(direction: "long" | "short"): string {
  return direction === "long" ? "多" : "空";
}

function directionClass(direction: "long" | "short"): string {
  return direction === "long" ? "badge--up" : "badge--down";
}

function sideLabel(side: "long" | "short"): string {
  return side === "long" ? "多" : "空";
}

function sideClass(side: "long" | "short"): string {
  return side === "long" ? "badge--up" : "badge--down";
}

function meterWidth(value: number | null, max = 12): string {
  const ratio = Math.max(0, Math.min(1, (value ?? 0) / max));
  return `${Math.round(ratio * 100)}%`;
}

function strengthWidth(value: number | null): string {
  const ratio = Math.max(0, Math.min(1, value ?? 0));
  return `${Math.round(ratio * 100)}%`;
}

function hitLabel(value: number | null): string {
  return value === null ? "—" : fmtMacro(value * 100, "%", 1);
}

function percentLabel(value: number | null): string {
  return value === null ? "—" : fmtMacro(value * 100, "%", 0);
}

function checksOf(plan: TradePlan): RiskCheck[] {
  return plan.checks ?? [];
}

function planPassed(plan: TradePlan): boolean | null {
  const checks = checksOf(plan);
  if (!checks.length) return null;
  return checks.every((check) => check.passed);
}

function failedChecks(plan: TradePlan): RiskCheck[] {
  return checksOf(plan).filter((check) => !check.passed);
}

function failedText(plan: TradePlan): string {
  const failed = failedChecks(plan);
  if (!failed.length) return "风控检查全部通过";
  return failed.map((check) => `${check.rule}：${check.detail}`).join("；");
}

function targetValue(plan: TradePlan, key: string): number | null {
  return toNumber(plan.targets?.[key]);
}

function marginPctLabel(plan: TradePlan): string {
  const pct = plan.detail?.margin_pct;
  if (pct === undefined || pct === null || !Number.isFinite(pct)) return "—";
  return fmtMacro(pct * 100, "%", 0);
}

function planSubtitle(plan: TradePlan): string {
  const items = [
    `仓位 ${fmtNumber(plan.detail?.lots ?? plan.size, 2)} 标准手（基准权益 ${fmtInt(plan.detail?.base_equity)} · 合约 ×${fmtNumber(
      plan.detail?.contract_size,
      0,
    )} · 保证金率 ${marginPctLabel(plan)}）`,
    `止损 ${fmtMacro(plan.detail?.stop_distance_pct, "%", 2)} · 权重 ${fmtMacro(plan.detail?.weight_pct, "%", 1)} · 杠杆 ${fmtNumber(
      plan.detail?.leverage,
      1,
    )}×`,
    `风险金额 ${fmtInt(plan.detail?.risk_amount)} 元 · 盈亏比 ${fmtNumber(plan.detail?.risk_reward, 2)}`,
    `时间止损 ${fmtInt(plan.time_stop_days)} 日 · 状态 ${plan.status}`,
    `失效：${plan.invalidation ?? "—"}`,
  ];
  if (plan.detail?.sizing_note) items.push(plan.detail.sizing_note);
  return items.join(" · ");
}
</script>

<style scoped>
.sig-block {
  margin-top: 10px;
}
.table-auto {
  max-height: none;
}

/* ---------- 类型统计 ---------- */
.sig-type-body {
  padding-top: 9px;
}
.sig-type-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.sig-type {
  padding: 8px 10px 7px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.sig-type-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.sig-type-name {
  font-size: 11.5px;
  font-weight: 650;
}
.sig-type-key {
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--dim);
}
.sig-type-head .badge {
  margin-left: auto;
}
.sig-type-counts {
  display: flex;
  gap: 14px;
  margin-top: 6px;
  font-size: 9.5px;
  color: var(--dim);
}
.sig-type-counts b {
  font-family: var(--mono);
  font-size: 11.5px;
  font-weight: 650;
}
.sig-type-counts .up {
  color: var(--up-color);
}
.sig-type-counts .down {
  color: var(--down-color);
}
.st-avg {
  margin-left: auto;
}
.sig-meter {
  height: 3px;
  margin-top: 6px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.sig-meter i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}

/* ---------- 当前信号 ---------- */
.sig-table {
  table-layout: fixed;
}
.sig-table .nm,
.plan-table .nm {
  margin-left: 5px;
}
.sig-table .note-cell {
  overflow: hidden;
  color: var(--muted);
  text-overflow: ellipsis;
}
.strength-cell {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.strength-track {
  display: block;
  width: 44px;
  height: 4px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.strength-track i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}

/* ---------- 交易计划 ---------- */
.plan-table {
  table-layout: fixed;
}
.plan-sub-row td {
  height: auto;
  padding: 0 10px 5px;
  background: color-mix(in srgb, var(--surface-2) 34%, transparent);
  border-bottom: 1px solid var(--border);
}
.plan-sub-row + tr td {
  border-top: 0;
}
.plan-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 1px 14px;
  padding: 2px 0 3px;
  font-size: 9.5px;
  line-height: 1.55;
  color: var(--muted);
  white-space: normal;
}
.plan-sub b {
  font-family: var(--mono);
  font-weight: 600;
  color: var(--text);
}
.plan-sub .ps-warn {
  color: var(--warn);
}
.plan-sub .ps-invalid {
  color: var(--dim);
}
.unit {
  margin-left: 2px;
  font-family: var(--sans);
  font-size: 9px;
  font-weight: 400;
  color: var(--dim);
}
.zero-lots {
  color: var(--warn);
  font-weight: 650;
}
.zero-tag {
  margin-left: 4px;
  padding: 0 3px;
  border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
  border-radius: 3px;
  font-size: 8.5px;
  font-weight: 400;
  color: var(--warn);
}
.plan-sub--note {
  margin-top: 3px;
  padding-top: 3px;
  border-top: 1px dashed var(--border);
  color: var(--dim);
}
.plan-foot {
  line-height: 1.6;
  color: var(--muted);
}
.plan-foot b {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--warn);
}

/* ---------- 回测 ---------- */
.backtest-table td {
  font-size: 11.5px;
}
.bt-rule {
  font-size: 11.5px;
  font-weight: 650;
}
.bt-key {
  margin-left: 6px;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.bt-rule + .bt-key + .badge {
  margin-left: 6px;
}

/* ---------- 校准 ---------- */
.calib-body {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}
.calib-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.calib-metric {
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.cm-label {
  display: block;
  font-size: 9px;
  letter-spacing: 0.3px;
  color: var(--dim);
}
.cm-value {
  display: block;
  margin-top: 2px;
  font-family: var(--mono);
  font-size: 19px;
  font-weight: 680;
  letter-spacing: -0.4px;
}
.calib-right {
  min-width: 0;
}
.calib-table td {
  font-size: 11px;
}

.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}

@media (max-width: 1100px) {
  .sig-type-grid {
    grid-template-columns: 1fr;
  }
  .calib-body {
    grid-template-columns: 1fr;
  }
}
</style>
