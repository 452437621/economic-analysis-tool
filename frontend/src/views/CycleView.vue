<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 周期定位 · EPIC-C 2.0</div>
        <h1 class="page-h1">
          周期罗盘
          <span class="page-sub">五层周期 · 长债务 / 短债务 / 库存 / 流动性 / 政治窗口 —— 先定位，再判断</span>
        </h1>
      </div>
      <div class="page-actions">
        <span v-if="payload?.asof" class="badge badge--sm">数据日 {{ fmtDate(payload.asof) }}</span>
        <span v-if="payload?.status" class="badge badge--sm" :class="runTone(payload.status)">
          {{ runText(payload.status) }}
        </span>
        <span class="badge badge--sm"><span class="dot"></span>更新于 {{ updatedLabel }}</span>
        <button class="btn btn--sm" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中…" : "立即重算" }}
        </button>
      </div>
    </div>

    <SkeletonBlock v-if="!payload && loading" :rows="6" :cells="3" :height="16" />
    <ErrorState v-else-if="!payload && error" :error="error" @retry="refresh" />

    <template v-else-if="value">
      <div class="kpi-grid">
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-target" /></svg></span>
            <span class="kpi-label">长债务周期</span>
            <span class="kpi-flag badge badge--sm" :class="toneClass(longTone)">{{ long.phase }}</span>
          </div>
          <div class="kpi-value">{{ fmtNumber(long.score, 1) }}<small>DMI</small></div>
          <div class="kpi-sub">
            区间 {{ long.band[0] }}–{{ long.band[1] }} · 位置上沿 {{ Math.round(long.position * 100) }}% · 置信
            {{ fmtNumber(long.confidence, 2) }}
          </div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
            <span class="kpi-label">短债务周期</span>
            <span class="kpi-flag badge badge--sm" :class="toneClass(shortTone)">{{ short.state }}</span>
          </div>
          <div class="kpi-value">
            增长 {{ fmtNumber(short.variables.growth, 0) }}<small>通胀 {{ fmtNumber(short.variables.inflation, 0) }}</small>
          </div>
          <div class="kpi-sub">
            流动性 {{ fmtNumber(short.variables.liq, 0) }} · 12 月增长变化
            {{ fmtSigned(short.variables.d12, 1) }}<template v-if="short.hysteresis_held"> · 滞回保持</template>
          </div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-rates" /></svg></span>
            <span class="kpi-label">债务可持续性</span>
            <span class="kpi-flag badge badge--sm badge--warn">{{ sustainability?.mode ?? "—" }}</span>
          </div>
          <div class="kpi-value">{{ fmtNumber(sustainability?.interest_to_revenue, 1) }}<small>利息 / 收入 %</small></div>
          <div class="kpi-sub">
            r−g {{ fmtSigned(sustainability?.r_minus_g, 1) }}pp · 赤字
            {{ fmtNumber(sustainability?.deficit_to_gdp, 1) }}% GDP
          </div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-layers" /></svg></span>
            <span class="kpi-label">历史类比（样本内）</span>
            <span class="kpi-flag badge badge--sm">{{ analogs?.n ?? 0 }} 个</span>
          </div>
          <div class="kpi-value">
            {{ analogs?.analogs?.[0] ? Math.round(analogs.analogs[0].similarity * 100) : "—" }}<small>% 最相似</small>
          </div>
          <div class="kpi-sub">
            {{ analogs?.analogs?.[0]?.month ?? "—" }} · 相似≠相同，需人工核对时代背景
          </div>
        </article>
      </div>

      <div class="cycle-main">
        <section class="card">
          <div class="card-head">
            <span class="card-title">六分量罗盘</span>
            <span class="card-sub">0–100 归一：越高代表压力/强度越大</span>
            <div class="card-actions">
              <span class="card-sub">{{ fmtInt(indicators.length) }} 个指标参与</span>
            </div>
          </div>
          <div class="card-body compass-body">
            <svg class="compass" viewBox="0 0 260 260" role="img" aria-label="六分量罗盘">
              <circle v-for="ring in rings" :key="ring" cx="130" cy="130" :r="ring" class="ring" />
              <line
                v-for="axis in axes"
                :key="axis.key"
                x1="130"
                y1="130"
                :x2="axis.tipX"
                :y2="axis.tipY"
                class="axis-line"
              />
              <polygon :points="polygon" class="compass-shape" />
              <circle
                v-for="axis in axes"
                :key="`dot-${axis.key}`"
                :cx="axis.pointX"
                :cy="axis.pointY"
                r="2.6"
                class="compass-dot"
              />
              <text
                v-for="axis in axes"
                :key="`label-${axis.key}`"
                :x="axis.labelX"
                :y="axis.labelY"
                :text-anchor="axis.anchor"
                class="compass-label"
              >
                {{ axis.label }}
              </text>
              <text x="130" y="126" text-anchor="middle" class="compass-center">
                {{ long.phase }}
              </text>
              <text x="130" y="142" text-anchor="middle" class="compass-center-sub">
                DMI {{ fmtNumber(long.score, 1) }}
              </text>
            </svg>
            <ul class="compass-legend">
              <li v-for="axis in axes" :key="`legend-${axis.key}`" class="legend-row">
                <span class="legend-name">{{ axis.label }}</span>
                <span class="legend-bar">
                  <i :style="{ width: `${Math.max(2, Math.min(100, axis.value))}%` }"></i>
                </span>
                <b class="mono">{{ fmtNumber(axis.value, 1) }}</b>
                <em class="mono">{{ fmtNumber(axis.confidence, 2) }}</em>
              </li>
            </ul>
          </div>
          <div class="card-foot">
            <span>压力类：DMI / ICI / ECI 越高，债务、内部秩序、外部秩序越紧张。</span>
            <span class="mono">DMI {{ fmtNumber(long.score, 1) }} · 滞回 {{ long.hysteresis_held ? "保持" : "无" }}</span>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <span class="card-title">五层周期</span>
            <span class="card-sub">嵌套定位 · 每层给出当前状态与含义</span>
          </div>
          <div class="card-body layer-list">
            <div class="layer-row">
              <div class="layer-head">
                <span class="layer-name">长债务周期</span>
                <span class="badge badge--sm" :class="toneClass(longTone)">{{ long.phase }}</span>
                <span class="layer-val mono">{{ fmtNumber(long.score, 1) }}</span>
              </div>
              <div class="position-bar"><i :style="{ width: `${Math.round(long.position * 100)}%` }"></i></div>
              <p class="layer-meaning">{{ long.meaning }}</p>
              <p class="layer-meta">下一阶段：{{ long.next_phase ?? "—" }} · {{ long.exit_condition }}</p>
            </div>
            <div class="layer-row">
              <div class="layer-head">
                <span class="layer-name">短债务周期</span>
                <span class="badge badge--sm" :class="toneClass(shortTone)">{{ short.state }}</span>
                <span v-if="short.hysteresis_held" class="badge badge--sm badge--warn">二次确认中</span>
                <span class="layer-val mono">{{ fmtNumber(short.confidence, 2) }}</span>
              </div>
              <p class="layer-meaning">{{ short.meaning }}</p>
              <p class="layer-meta">原始命中：{{ short.raw_state }} · 增长 {{ fmtNumber(short.variables.growth, 1) }} / 通胀 {{ fmtNumber(short.variables.inflation, 1) }}</p>
            </div>
            <div class="layer-row">
              <div class="layer-head">
                <span class="layer-name">库存周期</span>
                <span class="badge badge--sm">{{ inventory.state }}</span>
                <span v-if="inventory.degraded" class="badge badge--sm badge--warn">代理口径</span>
                <span class="layer-val mono">{{ fmtNumber(inventory.confidence, 2) }}</span>
              </div>
              <p class="layer-meaning">{{ inventory.meaning ?? "—" }}</p>
              <p class="layer-meta">{{ inventory.degrade_reason ?? "使用库存与价格动量的合成口径。" }}</p>
            </div>
            <div class="layer-row">
              <div class="layer-head">
                <span class="layer-name">信用 / 流动性</span>
                <span class="badge badge--sm" :class="toneClass(liquidityTone)">{{ liq.state }}</span>
                <span class="layer-val mono">{{ fmtNumber(liq.score, 1) }}</span>
              </div>
              <p class="layer-meaning">{{ liq.meaning }}</p>
              <p class="layer-meta">证据 {{ liq.evidence }} · 置信 {{ fmtNumber(liq.confidence, 2) }}</p>
            </div>
            <div class="layer-row">
              <div class="layer-head">
                <span class="layer-name">政治 / 事件窗口</span>
                <span class="badge badge--sm" :class="political.window === '高不确定性窗口' ? 'badge--warn' : ''">
                  {{ political.window }}
                </span>
                <span class="layer-val mono">{{ political.days_to_nearest ?? "—" }}<small>天</small></span>
              </div>
              <p class="layer-meaning">{{ political.nearest?.name ?? "无临近事件" }}</p>
              <p class="layer-meta">
                {{ political.nearest ? `${political.nearest.date} · ${political.nearest.note}` : "政治日历为空，请检查 config/cycle.yaml。" }}
              </p>
            </div>
          </div>
        </section>
      </div>

      <section class="card history-card">
        <div class="card-head">
          <span class="card-title">分量历史轨迹</span>
          <span class="card-sub">{{ history?.months.length ?? 0 }} 个月 · 月度末值 · 覆盖不足的分量留空</span>
          <div class="card-actions"><span class="card-sub mono">{{ historyRange }}</span></div>
        </div>
        <EChart v-if="chartHasData" :option="chartOption" :height="240" />
        <EmptyState v-else text="暂无历史轨迹" hint="至少有 24 个月数据后才会生成月度序列。" />
        <div class="card-foot">
          <span>历史轨迹用于判断「现在与过去哪里相似」，不作为拐点预测。</span>
          <span class="mono">样本从 {{ history?.months[0] ?? "—" }} 起</span>
        </div>
      </section>

      <div class="cycle-bottom">
        <section class="card">
          <div class="card-head">
            <span class="card-title">未来情景</span>
            <span class="card-sub">{{ scenarios?.horizon ?? "未来 6–36 个月" }} · 概率为规则化先验，未经校准</span>
            <div class="card-actions"><span class="card-sub mono">Σ {{ fmtNumber(scenarios?.sum, 2) }}</span></div>
          </div>
          <div class="card-body scenario-list">
            <div v-for="item in scenarios?.scenarios ?? []" :key="item.id" class="scenario-row">
              <div class="scenario-head">
                <span class="scenario-id mono">{{ item.id }}</span>
                <span class="scenario-name">{{ item.name }}</span>
                <b class="scenario-prob mono">{{ Math.round(item.probability * 100) }}%</b>
              </div>
              <div class="position-bar"><i :style="{ width: `${Math.round(item.probability * 100)}%` }"></i></div>
              <p class="scenario-desc">{{ item.desc }}</p>
              <p class="scenario-assets">资产含义：{{ item.assets }}</p>
            </div>
          </div>
          <div class="card-foot">
            <span>{{ scenarios?.formula ?? "" }}</span>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <span class="card-title">历史类比</span>
            <span class="card-sub">20 维状态向量近邻 · 剔除最近 12 个月</span>
            <div class="card-actions">
              <RouterLink class="card-sub link" :to="{ path: '/pipeline', query: { code: 'cycle.analogs' } }">
                为什么 →
              </RouterLink>
            </div>
          </div>
          <div class="card-body">
            <SkeletonBlock v-if="!analogs" :rows="3" />
            <template v-else>
              <ul class="analog-list">
                <li v-for="item in analogs.analogs.slice(0, 4)" :key="item.month" class="analog-row">
                  <span class="analog-month mono">{{ item.month }}</span>
                  <span class="analog-sim">
                    <i :style="{ width: `${Math.max(4, Math.round(item.similarity * 100))}%` }"></i>
                  </span>
                  <b class="mono">{{ Math.round(item.similarity * 100) }}%</b>
                  <span class="analog-state mono">
                    增长 {{ fmtNumber(item.state.growth, 0) }} · 通胀 {{ fmtNumber(item.state.inflation, 0) }}
                  </span>
                </li>
              </ul>
              <p class="layer-meta">{{ analogs.caveats[0] ?? "" }}</p>
            </template>
          </div>
          <div class="card-foot">
            <span>类比是「样本内比较」，相似不保证同路径。</span>
          </div>
        </section>
      </div>

      <div class="cycle-bottom">
        <section class="card">
          <div class="card-head">
            <span class="card-title">债务可持续性</span>
            <span class="card-sub">r−g / 利息负担 / 赤字三模式判别 · 证据 {{ sustainability?.evidence ?? "—" }}</span>
          </div>
          <div class="card-body">
            <div class="sustain-head">
              <span class="badge badge--sm badge--warn">{{ sustainability?.mode ?? "—" }}</span>
              <span class="mono sustain-risk">{{ sustainability?.risk ?? "" }}</span>
            </div>
            <p class="layer-meaning">{{ sustainability?.explanation ?? "" }}</p>
            <div class="metric-grid">
              <div class="metric">
                <span class="metric-label">r−g</span>
                <b class="mono">{{ fmtSigned(sustainability?.r_minus_g, 1) }}<small>pp</small></b>
              </div>
              <div class="metric">
                <span class="metric-label">利息 / 财政收入</span>
                <b class="mono">{{ fmtNumber(sustainability?.interest_to_revenue, 1) }}<small>%</small></b>
              </div>
              <div class="metric">
                <span class="metric-label">赤字 / GDP</span>
                <b class="mono">{{ fmtNumber(sustainability?.deficit_to_gdp, 1) }}<small>%</small></b>
              </div>
              <div class="metric">
                <span class="metric-label">债务 / GDP</span>
                <b class="mono">{{ fmtNumber(sustainability?.debt_to_gdp, 0) }}<small>%</small></b>
              </div>
            </div>
            <p class="layer-meta">
              关注阈值：利息/收入 ≥{{ sustainability?.thresholds.interest_watch }}%（警戒）、≥{{
                sustainability?.thresholds.interest_alarm
              }}%（警报）；赤字/GDP ≥{{ sustainability?.thresholds.deficit_watch }}%。
            </p>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <span class="card-title">世界秩序位置</span>
            <span class="card-sub">内部秩序与国际秩序分开判定 · E4 叙事级</span>
          </div>
          <div class="card-body">
            <div v-for="stage in stages" :key="stage.id" class="stage-row">
              <div class="stage-head">
                <span class="stage-name">{{ stage.name }}</span>
                <span class="badge badge--sm badge--warn">第 {{ stage.stage }} 阶段 · {{ stage.stage_name }}</span>
                <span class="mono stage-conf">置信 {{ fmtNumber(stage.confidence, 2) }}</span>
              </div>
              <p class="layer-meaning">{{ stage.reason }}</p>
              <p class="layer-meta">失效条件：{{ stage.falsifier }}</p>
            </div>
            <div class="power-block">
              <div class="power-head">
                <span class="layer-name">八项实力指数</span>
                <b class="mono">{{ fmtNumber(world?.power_index.value, 1) }}</b>
                <span class="badge badge--sm" :class="world?.power_index.degraded ? 'badge--warn' : ''">
                  {{ world?.power_index.degraded ? "部分口径降级" : "口径完整" }}
                </span>
              </div>
              <div v-for="item in world?.power_index.components ?? []" :key="item.id" class="power-row">
                <span class="power-name">{{ item.name }}</span>
                <span class="power-bar"><i :style="{ width: `${Math.max(2, Math.min(100, item.value))}%` }"></i></span>
                <b class="mono">{{ fmtNumber(item.value, 0) }}</b>
                <em class="mono">{{ fmtNumber(item.weight * 100, 0) }}%</em>
              </div>
              <p class="layer-meta">
                储备货币：{{ world?.reserve_currency.code }} 份额 {{ fmtNumber(world?.reserve_currency.share, 1) }}%（{{
                  world?.reserve_currency.asof
                }}，{{ world?.reserve_currency.source }}）
              </p>
            </div>
          </div>
        </section>
      </div>

      <div v-if="payload?.degraded_reasons.length" class="degraded-box">
        <svg class="ic"><use href="#i-alert" /></svg>
        <div>
          <b>本次运行有 {{ payload.degraded_reasons.length }} 项降级</b>
          <div v-for="reason in payload.degraded_reasons.slice(0, 6)" :key="reason.code" class="degraded-reason">
            {{ reason.message }}（{{ reason.code }}）
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { EChartsOption } from "echarts";
import EChart from "@/components/charts/EChart.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtInt, fmtNumber, fmtSigned } from "@/composables/useFormat";
import { getCycleState, runCycle } from "@/api/endpoints";
import type { CycleKey, CycleReading, CycleStateResponse } from "@/api/types";

const { data, error, loading, lastUpdated, refresh } = usePolling<CycleStateResponse>(getCycleState, {
  interval: 60_000,
});

const running = ref(false);
const payload = computed(() => data.value);
const value = computed(() => payload.value?.state.value ?? null);
const indicators = computed<CycleReading[]>(() => payload.value?.indicators ?? []);
const long = computed(() => value.value!.long_cycle);
const short = computed(() => value.value!.short_cycle);
const liq = computed(() => value.value!.liquidity);
const inventory = computed(() => value.value!.inventory);
const political = computed(() => value.value!.political);
const sustainability = computed(() => payload.value?.sustainability?.value);
const scenarios = computed(() => payload.value?.scenarios?.value);
const analogs = computed(() => payload.value?.analogs?.value);
const world = computed(() => payload.value?.world?.value);
const history = computed(() => payload.value?.history?.value);
const stages = computed(() => (world.value ? [world.value.us_internal, world.value.global_order] : []));

const updatedLabel = computed(() => (lastUpdated.value ? fmtDateTime(lastUpdated.value.toISOString()).slice(5) : "—"));

const COMPASS: Array<{ key: CycleKey; label: string }> = [
  { key: "DMI", label: "债务货币" },
  { key: "ICI", label: "内部秩序" },
  { key: "ECI", label: "外部秩序" },
  { key: "GROWTH", label: "增长" },
  { key: "INFLATION", label: "通胀" },
  { key: "LIQUIDITY", label: "流动性" },
];

const rings = [23, 46, 69, 92];

const axes = computed(() =>
  COMPASS.map((item, index) => {
    const composite = value.value?.composites?.[item.key];
    const raw = composite?.value ?? 0;
    const score = raw === null || raw === undefined || !Number.isFinite(raw) ? 0 : Math.max(0, Math.min(100, raw));
    const angle = ((-90 + index * 60) * Math.PI) / 180;
    const radius = 92 * (score / 100);
    return {
      ...item,
      value: score,
      confidence: composite?.confidence ?? 0,
      tipX: 130 + Math.cos(angle) * 92,
      tipY: 130 + Math.sin(angle) * 92,
      pointX: 130 + Math.cos(angle) * radius,
      pointY: 130 + Math.sin(angle) * radius,
      labelX: 130 + Math.cos(angle) * 112,
      labelY: 130 + Math.sin(angle) * 112 + (Math.abs(Math.sin(angle)) < 0.1 ? 3 : 0),
      anchor: Math.abs(Math.cos(angle)) < 0.1 ? "middle" : Math.cos(angle) > 0 ? "start" : "end",
    };
  }),
);

const polygon = computed(() =>
  axes.value.map((axis) => `${axis.pointX.toFixed(1)},${axis.pointY.toFixed(1)}`).join(" "),
);

type Tone = "ok" | "warn" | "up" | "down" | "accent" | "plain";
const PHASE_TONE: Record<string, Tone> = {
  normal: "ok",
  bubble_early: "ok",
  bubble_late: "warn",
  top: "warn",
  deflationary: "up",
  printing: "warn",
  debasement: "up",
};
const longTone = computed<Tone>(() => PHASE_TONE[long.value.phase_id] ?? "accent");
const SHORT_TONE: Record<string, Tone> = {
  复苏: "ok",
  过热: "warn",
  放缓: "plain",
  衰退: "up",
  萧条: "up",
};
const shortTone = computed<Tone>(() => SHORT_TONE[short.value.state] ?? "accent");
const LIQ_TONE: Record<string, Tone> = { 宽松: "ok", 中性: "plain", 收紧: "warn" };
const liquidityTone = computed<Tone>(() => LIQ_TONE[liq.value.state] ?? "plain");

function toneClass(tone: Tone): string {
  if (tone === "ok") return "badge--live";
  if (tone === "warn") return "badge--warn";
  if (tone === "up") return "badge--up";
  if (tone === "down") return "badge--down";
  if (tone === "accent") return "badge--accent";
  return "";
}

function runTone(status: string): string {
  return status === "ok" ? "badge--live" : status === "failed" ? "badge--up" : "badge--warn";
}

function runText(status: string): string {
  return status === "ok" ? "运行成功" : status === "failed" ? "运行失败" : "部分降级";
}

const historyRange = computed(() => {
  const months = history.value?.months ?? [];
  if (!months.length) return "—";
  return `${months[0]} ~ ${months[months.length - 1]}`;
});

const chartHasData = computed(() => {
  const series = history.value?.series;
  if (!series) return false;
  return Object.values(series).some((points) => (points ?? []).some((point) => point !== null));
});

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

const CHART_COLORS: Record<string, string> = {
  DMI: "#F5A524",
  GROWTH: "#4CC2FF",
  INFLATION: "#F0544F",
  LIQUIDITY: "#2FBF71",
};

const chartOption = computed<EChartsOption>(() => {
  const months = history.value?.months ?? [];
  const seriesData = history.value?.series ?? {};
  const keys = ["DMI", "GROWTH", "INFLATION", "LIQUIDITY"].filter((key) => (seriesData[key] ?? []).some((v) => v !== null));
  return {
    grid: { left: 42, right: 16, top: 26, bottom: 28 },
    tooltip: { trigger: "axis", backgroundColor: cssVar("--surface-2", "#172030"), borderColor: cssVar("--border-strong", "#223047"), textStyle: { color: cssVar("--text", "#E6EDF5"), fontSize: 11 } },
    legend: { top: 2, left: 8, itemWidth: 10, itemHeight: 2, textStyle: { color: cssVar("--muted", "#93A4B8"), fontSize: 10 } },
    xAxis: { type: "category", data: months, axisLine: { lineStyle: { color: cssVar("--border", "rgba(148,163,184,.2)") } }, axisLabel: { color: cssVar("--dim", "#64748B"), fontSize: 9, interval: Math.max(0, Math.floor(months.length / 6) - 1) } },
    yAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: cssVar("--border", "rgba(148,163,184,.12)") } }, axisLabel: { color: cssVar("--dim", "#64748B"), fontSize: 9 } },
    series: keys.map((key) => ({
      name: key,
      type: "line" as const,
      data: seriesData[key],
      smooth: true,
      connectNulls: false,
      showSymbol: false,
      lineStyle: { width: 1.6, color: CHART_COLORS[key] },
      itemStyle: { color: CHART_COLORS[key] },
    })),
  };
});

async function recalc(): Promise<void> {
  if (running.value) return;
  running.value = true;
  try {
    await runCycle();
    await refresh();
  } finally {
    running.value = false;
  }
}
</script>

<style scoped>
.cycle-main {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1.25fr);
  gap: 10px;
  margin-top: 10px;
}
.compass-body {
  display: grid;
  grid-template-columns: minmax(0, 260px) minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}
.compass {
  width: 100%;
  max-height: 250px;
}
.ring {
  fill: none;
  stroke: color-mix(in srgb, var(--muted) 18%, transparent);
  stroke-dasharray: 2 3;
}
.axis-line {
  stroke: color-mix(in srgb, var(--muted) 16%, transparent);
}
.compass-shape {
  fill: color-mix(in srgb, var(--accent) 16%, transparent);
  stroke: var(--accent);
  stroke-width: 1.4;
}
.compass-dot {
  fill: var(--accent);
}
.compass-label {
  fill: var(--muted);
  font-size: 9.5px;
}
.compass-center {
  fill: var(--text);
  font-size: 13px;
  font-weight: 650;
}
.compass-center-sub {
  fill: var(--dim);
  font-size: 9.5px;
  font-family: var(--mono);
}
.compass-legend {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.legend-row {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) 34px 30px;
  gap: 7px;
  align-items: center;
  font-size: 10.5px;
  color: var(--muted);
}
.legend-name {
  white-space: nowrap;
}
.legend-bar {
  height: 5px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.legend-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 55%, transparent), var(--accent));
}
.legend-row b {
  text-align: right;
  color: var(--text);
  font-size: 11px;
}
.legend-row em {
  text-align: right;
  color: var(--dim);
  font-size: 9px;
  font-style: normal;
}
.layer-list {
  display: grid;
  gap: 10px;
}
.layer-row {
  border-bottom: 1px dashed var(--border);
  padding-bottom: 8px;
}
.layer-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
.layer-head {
  display: flex;
  align-items: center;
  gap: 7px;
}
.layer-name {
  font-size: 11.5px;
  font-weight: 650;
  color: var(--text);
  white-space: nowrap;
}
.layer-val {
  margin-left: auto;
  font-size: 11px;
  color: var(--muted);
}
.layer-val small {
  margin-left: 2px;
  font-size: 9px;
  color: var(--dim);
}
.position-bar {
  height: 4px;
  margin: 5px 0 4px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.position-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--warn) 45%, transparent), var(--warn));
}
.layer-meaning {
  margin: 2px 0 0;
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.5;
}
.layer-meta {
  margin: 2px 0 0;
  font-size: 9.5px;
  color: var(--dim);
  line-height: 1.45;
}
.history-card {
  margin-top: 10px;
}
.cycle-bottom {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}
.scenario-list {
  display: grid;
  gap: 8px;
}
.scenario-row {
  border-bottom: 1px dashed var(--border);
  padding-bottom: 7px;
}
.scenario-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
.scenario-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.scenario-id {
  font-size: 9.5px;
  color: var(--accent);
}
.scenario-name {
  font-size: 11px;
  color: var(--text);
}
.scenario-prob {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--text);
}
.scenario-desc,
.scenario-assets {
  margin: 2px 0 0;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.45;
}
.scenario-assets {
  color: var(--dim);
}
.analog-list {
  display: grid;
  gap: 6px;
  margin: 0 0 6px;
  padding: 0;
  list-style: none;
}
.analog-row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) 36px auto;
  gap: 8px;
  align-items: center;
  font-size: 10.5px;
}
.analog-month {
  color: var(--accent);
  font-size: 10px;
}
.analog-sim {
  height: 5px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.analog-sim i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}
.analog-row b {
  text-align: right;
  color: var(--text);
  font-size: 11px;
}
.analog-state {
  color: var(--dim);
  font-size: 9.5px;
  white-space: nowrap;
}
.sustain-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.sustain-risk {
  font-size: 10px;
  color: var(--warn);
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 8px 0 6px;
}
.metric {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface-2) 55%, transparent);
}
.metric-label {
  display: block;
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}
.metric b {
  font-size: 14px;
  color: var(--text);
}
.metric b small {
  margin-left: 2px;
  font-size: 9px;
  color: var(--dim);
}
.stage-row {
  border-bottom: 1px dashed var(--border);
  padding-bottom: 7px;
  margin-bottom: 7px;
}
.stage-head {
  display: flex;
  align-items: center;
  gap: 7px;
}
.stage-name {
  font-size: 11px;
  font-weight: 650;
  color: var(--text);
}
.stage-conf {
  margin-left: auto;
  font-size: 9.5px;
  color: var(--dim);
}
.power-block {
  margin-top: 2px;
}
.power-head {
  display: flex;
  align-items: baseline;
  gap: 7px;
  margin-bottom: 5px;
}
.power-head b {
  font-size: 13px;
  color: var(--text);
}
.power-row {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr) 30px 30px;
  gap: 7px;
  align-items: center;
  font-size: 10px;
  color: var(--muted);
  padding: 2px 0;
}
.power-bar {
  height: 4px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.power-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 70%, transparent);
}
.power-row b {
  text-align: right;
  color: var(--text);
  font-size: 10.5px;
}
.power-row em {
  text-align: right;
  font-style: normal;
  font-size: 9px;
  color: var(--dim);
}
.link {
  color: var(--accent);
  text-decoration: none;
}
.degraded-box {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding: 9px 12px;
  border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--warn) 9%, transparent);
  font-size: 10.5px;
  color: var(--muted);
}
.degraded-box .ic {
  width: 14px;
  height: 14px;
  color: var(--warn);
}
.degraded-reason {
  margin-top: 2px;
  color: var(--dim);
  font-size: 10px;
}
.spin {
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1180px) {
  .cycle-main,
  .cycle-bottom {
    grid-template-columns: minmax(0, 1fr);
  }
  .compass-body {
    grid-template-columns: minmax(0, 1fr);
    justify-items: center;
  }
  .compass-legend {
    width: 100%;
  }
}
</style>
