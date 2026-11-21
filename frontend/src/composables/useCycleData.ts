/** 周期罗盘的取数与归一：状态 / 关键读数 / 指标透明度独立轮询，重算只影响行内提示。 */
import { computed, onMounted, ref } from "vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtNumber, fmtSigned } from "@/composables/useFormat";
import { getJson } from "@/api/client";
import {
  getCycleConfig,
  getCycleReadings,
  getCycleIndicators,
  getCycleState,
  runCycle,
} from "@/api/endpoints";
import type {
  CycleAlert,
  CycleAnalog,
  CycleAnalogs,
  CycleHistory,
  CycleIndicator,
  CycleIndicatorsResponse,
  CycleKey,
  CycleReading,
  CycleReadingCard,
  CycleReadingsResponse,
  CycleScenarioItem,
  CycleStateResponse,
  CycleSustainability,
  CycleWorld,
} from "@/api/types";
import {
  asNumber,
  asText,
  normalizeInventory,
  normalizeLiquidity,
  normalizeLongCycle,
  normalizePolitical,
  normalizePowerComponent,
  normalizeShortCycle,
  normalizeStage,
  type RawOf,
  type SafeLongCycle,
  type SafePowerComponent,
  type SafeShortCycle,
  type SafeStage,
} from "@/utils/cycleNormalize";
import {
  deltaTone,
  directionArrow,
  LIQ_TONE,
  PHASE_TONE,
  SHORT_TONE,
  sparkPolyline,
  toneClass,
  type KpiView,
  type Tone,
} from "@/utils/cycleFormat";

const STRUCTURAL_LAYER = "结构性";
const KPI_ORDER = ["us10y", "us10y_real", "us10y_2y", "gold", "gold_silver", "lme_copper", "dxy", "cn_us_spread"];

export function useCycleData() {
  const { data, error, loading, refresh } = usePolling<CycleStateResponse>(getCycleState, {
    interval: 60_000,
  });

  /** 关键读数走独立接口：失败时只降级 C 段，不影响其余区块。 */
  const readingsPoll = usePolling<CycleReadingsResponse>(getCycleReadings, { interval: 60_000 });

  /** 指标全量（32 条，含 evidence / source / stale_days / degraded）：独立轮询，只用于透明度卡。 */
  const indicatorPoll = usePolling<CycleIndicatorsResponse>(getCycleIndicators, { interval: 120_000 });
  const refreshIndicators = (): void => {
    void indicatorPoll.refresh();
  };

  const structuralRows = computed<CycleIndicator[]>(() =>
    (indicatorPoll.data.value?.items ?? []).filter((row) => (row.layer ?? "").includes(STRUCTURAL_LAYER)),
  );
  const structuralDegradedCount = computed(() => structuralRows.value.filter((row) => row.degraded).length);
  const oldestStaleDays = computed<number | null>(() => {
    const days = structuralRows.value
      .map((row) => row.stale_days)
      .filter((value): value is number => typeof value === "number");
    return days.length ? Math.max(...days) : null;
  });
  const oldestStaleText = computed(() =>
    oldestStaleDays.value === null ? "—" : `${oldestStaleDays.value} 天`,
  );
  const oldestStaleTitle = computed(() => {
    if (oldestStaleDays.value === null) return "后端未给出 stale_days，无法判断观测时效";
    const oldest = structuralRows.value
      .filter((row) => row.stale_days === oldestStaleDays.value)
      .map((row) => `${row.name}（观测日 ${fmtDate(row.asof)}）`);
    return `最旧的人工观测：${oldest.join("、")}`;
  });

  const running = ref(false);
  const recalcError = ref<string | null>(null);
  const payload = computed(() => data.value);
  const value = computed(() => payload.value?.state?.value ?? null);
  const indicators = computed<CycleReading[]>(() => {
    const list = payload.value?.indicators;
    if (!Array.isArray(list)) return [];
    return list.filter((item): item is CycleReading => !!item && typeof item === "object");
  });

  // ── 防御式归一 ───────────────────────────────────────────
  const long = computed<SafeLongCycle>(() => normalizeLongCycle(value.value?.long_cycle));

  const short = computed<SafeShortCycle>(() => normalizeShortCycle(value.value?.short_cycle));

  const liq = computed(() => normalizeLiquidity(value.value?.liquidity));

  const inventory = computed(() => normalizeInventory(value.value?.inventory));

  const political = computed(() => normalizePolitical(value.value?.political));

  const sustainability = computed(() => payload.value?.sustainability?.value ?? null);
  /** thresholds 可能整段缺失，单独归一，模板不再直接点属性 */
  const sustainabilityThresholds = computed<Partial<CycleSustainability["thresholds"]>>(
    () => (sustainability.value?.thresholds ?? {}) as Partial<CycleSustainability["thresholds"]>,
  );

  const scenarios = computed(() => payload.value?.scenarios?.value ?? null);
  /** 情景条目逐项归一：probability/name/desc/assets 任一缺失都不影响渲染 */
  const scenarioList = computed<CycleScenarioItem[]>(() => {
    const list = scenarios.value?.scenarios;
    if (!Array.isArray(list)) return [];
    return list
      .filter((item): item is CycleScenarioItem => !!item && typeof item === "object")
      .map((item) => ({
        id: asText(item.id, "—"),
        name: asText(item.name, "未命名情景"),
        probability: asNumber(item.probability) ?? 0,
        base: asNumber(item.base) ?? 0,
        adjustment: asNumber(item.adjustment) ?? 0,
        desc: asText(item.desc, "—"),
        assets: asText(item.assets, "—"),
        triggers: Array.isArray(item.triggers) ? item.triggers : [],
      }));
  });
  const analogs = computed<RawOf<CycleAnalogs>>(
    () => (payload.value?.analogs?.value as RawOf<CycleAnalogs>) ?? null,
  );
  const analogList = computed<CycleAnalog[]>(() => {
    const list = analogs.value?.analogs;
    if (!Array.isArray(list)) return [];
    return list
      .filter((item): item is CycleAnalog => !!item && typeof item === "object")
      .map((item) => {
        const state = (item.state ?? {}) as Partial<CycleAnalog["state"]>;
        return {
          month: asText(item.month, "—"),
          similarity: asNumber(item.similarity) ?? 0,
          distance: asNumber(item.distance) ?? 0,
          state: { growth: asNumber(state.growth), inflation: asNumber(state.inflation) },
        };
      });
  });

  /** 世界秩序是顶层推导 payload（payload.world.value）；缺失时兼容旧形态 local state.value.world。 */
  const world = computed<RawOf<CycleWorld>>(() => {
    const response = payload.value;
    if (!response) return null;
    const top = response.world?.value as RawOf<CycleWorld>;
    if (top) return top;
    // 兼容旧后端把 world 挂在 state.value 下的形态
    const legacy = (response.state?.value as unknown as { world?: CycleWorld | null } | undefined)?.world;
    return (legacy as RawOf<CycleWorld>) ?? null;
  });

  const powerIndex = computed<RawOf<CycleWorld["power_index"]>>(() => world.value?.power_index ?? null);
  /** 八项实力逐项归一：value 归一到 0–100 保证进度条可用，weight 转百分比 */
  const powerComponents = computed<SafePowerComponent[]>(() => {
    const list = powerIndex.value?.components;
    if (!Array.isArray(list)) return [];
    return list.map((item) => normalizePowerComponent(item));
  });
  const reserveCurrency = computed<RawOf<CycleWorld["reserve_currency"]>>(
    () => world.value?.reserve_currency ?? null,
  );

  const stages = computed<SafeStage[]>(() => {
    const list = [world.value?.us_internal, world.value?.global_order];
    return list
      .filter((stage): stage is NonNullable<typeof stage> => !!stage)
      .map((stage) => normalizeStage(stage));
  });

  const history = computed<RawOf<CycleHistory>>(
    () => (payload.value?.history?.value as RawOf<CycleHistory>) ?? null,
  );
  const historyMonths = computed<string[]>(() => {
    const months = history.value?.months;
    return Array.isArray(months) ? months : [];
  });

  const degradedReasons = computed<Array<{ code?: string; message?: string }>>(() => {
    const list = payload.value?.degraded_reasons;
    return Array.isArray(list) ? list : [];
  });

  // ── 时间标签：只展示数据自身时点，不展示系统当前时间 ────────
  const generatedLabel = computed<string>(() => {
    const raw = payload.value?.generated_at;
    return raw ? fmtDateTime(raw) : "—";
  });
  const asofLabel = computed<string>(() => fmtDate(payload.value?.asof));

  /** 后端 /api/v2/cycle/meta 为新增端点：返回失败时静默回退到 config.version。 */
  interface CycleMeta {
    rule_version?: string | null;
    next_calibration?: string | null;
    brier?: number | null;
    calibration_n?: number | null;
    coverage?: { series_covered?: number | null; series_total?: number | null } | null;
  }

  const meta = ref<CycleMeta | null>(null);
  const configVersion = ref<string | null>(null);

  async function loadMeta(): Promise<void> {
    try {
      meta.value = await getJson<CycleMeta>("/api/v2/cycle/meta");
    } catch {
      meta.value = null;
    }
  }

  async function loadConfigVersion(): Promise<void> {
    try {
      const config = await getCycleConfig();
      configVersion.value = config.version ?? null;
    } catch {
      configVersion.value = null;
    }
  }

  onMounted(() => {
    void loadMeta();
    void loadConfigVersion();
  });

  const ruleVersion = computed<string>(() => meta.value?.rule_version || configVersion.value || "—");
  const nextCalibration = computed<string>(() => meta.value?.next_calibration || "—");

  const coverageText = computed<string>(() => {
    const coverage = meta.value?.coverage;
    const covered = coverage?.series_covered ?? null;
    const total = coverage?.series_total ?? null;
    if (covered !== null && total !== null && total > 0) return `${covered}/${total}`;
    const list = indicators.value;
    if (!list.length) return "—";
    return `${list.filter((reading) => reading.value !== null).length}/${list.length}`;
  });

  // ── 通用读数查找 ─────────────────────────────────────────
  function findReading(ids: string[]): CycleReading | null {
    const list = indicators.value;
    for (const wanted of ids) {
      const hit = list.find((reading) => reading.id.toLowerCase() === wanted.toLowerCase());
      if (hit && hit.value !== null) return hit;
    }
    for (const wanted of ids) {
      const hit = list.find((reading) => reading.id.toLowerCase().includes(wanted.toLowerCase()));
      if (hit && hit.value !== null) return hit;
    }
    return null;
  }

  function compositeValue(key: CycleKey): number | null {
    const raw = value.value?.composites?.[key]?.value;
    if (raw === null || raw === undefined || !Number.isFinite(raw)) return null;
    return Math.max(0, Math.min(100, raw));
  }

  function readingsForScore(key: CycleKey): number {
    return indicators.value.filter((reading) => {
      const raw = (reading as unknown as { score?: string | number | null }).score;
      return raw === key && reading.score_value !== null;
    }).length;
  }

  // ── A. Hero ──────────────────────────────────────────────
  const heroTitle = computed<string>(() => {
    const meaning = (long.value.meaning ?? "").replace(/\s+/g, " ").trim();
    const shortMeaning = meaning ? meaning.slice(0, 18) : "阶段定位";
    return `美国 · 长债务周期${long.value.phase}：${shortMeaning}`;
  });

  const compassGrowth = computed<number | null>(
    () => compositeValue("GROWTH") ?? short.value.variables.growth ?? null,
  );
  const compassInflation = computed<number | null>(
    () => compositeValue("INFLATION") ?? short.value.variables.inflation ?? null,
  );

  const growthArrow = computed(() => directionArrow(compositeValue("GROWTH")));
  const inflationArrow = computed(() => directionArrow(compositeValue("INFLATION")));

  /** 综合置信度（百分比；兼容 0–1 与 0–100 两种存量口径） */
  const longConfidencePct = computed<number | null>(() => {
    const raw = long.value.confidence;
    if (raw === null || !Number.isFinite(raw)) return null;
    const scaled = raw <= 1 ? raw * 100 : raw;
    return Math.max(0, Math.min(100, Math.round(scaled)));
  });

  const heroSub = computed<string>(() => {
    const confidence = longConfidencePct.value;
    const confText = confidence === null ? "—" : `${confidence}%`;
    return `短周期：${short.value.state} · 综合置信度 ${confText} · 增长${growthArrow.value} 通胀${inflationArrow.value}`;
  });

  interface HeroTag {
    key: string;
    label: string;
    value: string;
    z: number | null;
  }

  const alertsPayload = computed(() => payload.value?.alerts?.value ?? null);
  const alertList = computed<CycleAlert[]>(() => {
    const list = alertsPayload.value?.alerts;
    if (!Array.isArray(list)) return [];
    return list.filter((alert): alert is CycleAlert => !!alert && typeof alert === "object");
  });
  const spreadAlert = computed(
    () =>
      alertList.value.find(
        (alert) => alert.metric === "cn_us_spread" || (alert.metric_name ?? "").includes("中美"),
      ) ?? null,
  );

  const heroTags = computed<HeroTag[]>(() => {
    const tags: Array<HeroTag | null> = [];
    const real = findReading(["us_real10y", "US10Y_REAL"]);
    if (real && real.value !== null) {
      tags.push({
        key: "real10y",
        label: "10Y 实际利率",
        value: `${fmtNumber(real.value, 2)}${real.unit ? ` ${real.unit}` : ""}`,
        z: real.z,
      });
    }
    const curve = findReading(["us_curve_slope"]);
    if (curve && curve.value !== null) {
      tags.push({ key: "curve", label: "10Y–2Y 利差", value: `${fmtSigned(curve.value * 100, 0)} bp`, z: curve.z });
    }
    if (spreadAlert.value && spreadAlert.value.value !== null) {
      tags.push({
        key: "cnus",
        label: "中美 10Y 利差",
        value: `${fmtSigned(spreadAlert.value.value, 0)} ${spreadAlert.value.unit ?? "bp"}`,
        z: null,
      });
    }
    const us10y = findReading(["us_10y"]);
    if (us10y && us10y.value !== null) {
      tags.push({
        key: "us10y",
        label: "美债 10Y",
        value: `${fmtNumber(us10y.value, 2)}${us10y.unit ? ` ${us10y.unit}` : ""}`,
        z: us10y.z,
      });
    }
    const breakeven = findReading(["us_breakeven"]);
    if (breakeven && breakeven.value !== null) {
      tags.push({
        key: "breakeven",
        label: "10Y 盈亏平衡",
        value: `${fmtNumber(breakeven.value, 2)}${breakeven.unit ? ` ${breakeven.unit}` : ""}`,
        z: breakeven.z,
      });
    }
    return tags.filter((tag): tag is HeroTag => tag !== null).slice(0, 3);
  });

  // ── C. 关键读数（直连 /api/v2/cycle/readings，缺失只显示原因） ─────────
  const readingItems = computed<CycleReadingCard[]>(() => {
    const list = readingsPoll.data.value?.items;
    if (!Array.isArray(list)) return [];
    return list.filter((item): item is CycleReadingCard => !!item && typeof item === "object");
  });
  const missingReadings = computed<number>(() => readingItems.value.filter((item) => item.missing).length);
  /** 设计稿固定的 8 张卡顺序：接口返回顺序不同也按此排，其余读数追加在后。 */
  const orderedReadings = computed<CycleReadingCard[]>(() => {
    const rank = (id: string): number => {
      const index = KPI_ORDER.indexOf(id);
      return index === -1 ? KPI_ORDER.length : index;
    };
    return readingItems.value.slice().sort((a, b) => rank(a.id) - rank(b.id));
  });
  const readingsUnavailable = computed<boolean>(
    () => !!readingsPoll.error.value && readingItems.value.length === 0,
  );
  const readingsErrorText = computed<string>(() => readingsPoll.error.value?.message ?? "请求失败");

  /** 卡片右上角日期：取全部读数里最新的 asof。 */
  const readingsAsof = computed<string>(() => {
    const dates = readingItems.value
      .map((item) => item.asof)
      .filter((value): value is string => !!value);
    if (!dates.length) return "";
    return fmtDate(dates.reduce((a, b) => (a > b ? a : b)));
  });

  const kpis = computed<KpiView[]>(() =>
    orderedReadings.value.map((item) => {
      const digits = item.digits ?? 2;
      const unit = item.unit ?? "";
      const raw = item.value;
      const usable = !item.missing && raw !== null && raw !== undefined && Number.isFinite(raw);
      const delta = item.delta_1d === undefined || item.delta_1d === null ? null : item.delta_1d;
      const z = item.z ?? null;
      return {
        id: item.id,
        label: item.label ?? "未命名读数",
        value: usable ? fmtNumber(raw, digits) : "—",
        unit,
        z,
        zClass: z === null ? "" : z > 0 ? "cyc-kpi-z--pos" : z < 0 ? "cyc-kpi-z--neg" : "",
        missing: !usable,
        reason: item.reason ?? null,
        source: item.source ?? null,
        evidence: item.evidence ?? "E2",
        deltaText: usable && delta !== null ? `${fmtSigned(delta, digits)}${unit}` : "",
        deltaClass: deltaTone(delta),
        spark: usable ? sparkPolyline(item.spark) : "",
        sparkColor: z !== null && z > 0 ? "var(--up)" : z !== null && z < 0 ? "var(--down)" : "var(--accent)",
        tooltip: [item.source ?? "", item.asof ? `asof ${item.asof}` : "", item.reason ?? ""]
          .filter(Boolean)
          .join(" · "),
      };
    }),
  );

  // ── D. 今日预警 ──────────────────────────────────────────
  const triggeredAlerts = computed(() =>
    alertList.value.filter((alert) => alert.triggered === true || alert.status === "triggered"),
  );
  const alertCount = computed<number>(() => alertsPayload.value?.triggered ?? triggeredAlerts.value.length);
  const topAlerts = computed<CycleAlert[]>(() => triggeredAlerts.value.slice(0, 3));

  // ── E. 历史类比 Top3 ─────────────────────────────────────
  const topAnalogs = computed<CycleAnalog[]>(() => analogList.value.slice(0, 3));
  const analogSlots = computed<Array<CycleAnalog | null>>(() => {
    const slots: Array<CycleAnalog | null> = topAnalogs.value.slice(0, 3);
    while (slots.length < 3) slots.push(null);
    return slots;
  });

  // ── B. 五力仪表 ──────────────────────────────────────────
  interface ForceRow {
    key: string;
    name: string;
    score: number | null;
    basis: number;
    proxy: string | null;
    missing: boolean;
  }

  const oilReading = computed<CycleReading | null>(() => {
    const direct = findReading(["oil_mom"]);
    if (direct) return direct;
    return (
      indicators.value.find(
        (reading) => reading.value !== null && (/oil/i.test(reading.id) || /原油|油价/.test(reading.name)),
      ) ?? null
    );
  });

  /** cycle.yaml 的 pct 类读数以小数存放（0.0085 = 0.85%），展示与换算时统一放大。 */
  function pctReading(reading: CycleReading | null): number | null {
    if (!reading || reading.value === null || !Number.isFinite(reading.value)) return null;
    const unit = (reading.unit ?? "").toLowerCase();
    if (unit === "pct" && Math.abs(reading.value) <= 1) return reading.value * 100;
    return reading.value;
  }

  const naturalShock = computed<{ score: number | null; basis: number; proxy: string | null }>(() => {
    const oil = oilReading.value;
    const pct = pctReading(oil);
    if (pct === null) {
      return { score: null, basis: 0, proxy: "代理口径 E1 · 原油价格读数缺失" };
    }
    const momentum = Math.max(-25, Math.min(25, pct));
    const score = Math.round(Math.max(0, Math.min(100, 50 + momentum * 2)));
    return { score, basis: 1, proxy: "代理口径 E1 · 50+2×原油60日动量（当前 " + `${fmtSigned(momentum, 1)}%）` };
  });

  const techRevolution = computed<{ score: number | null; basis: number; proxy: string | null }>(() => {
    const ndx = indicators.value.find(
      (reading) => reading.value !== null && /ndx|nasdaq|纳斯达克/i.test(`${reading.id} ${reading.name}`),
    );
    if (!ndx || ndx.value === null) {
      return { score: null, basis: 0, proxy: "代理口径 E1 · NDX/SPX 相对动量读数缺失" };
    }
    return { score: null, basis: 1, proxy: "代理口径 E1 · NDX 相对 SPX 60 日动量" };
  });

  const forces = computed<ForceRow[]>(() => {
    const dmi = compositeValue("DMI");
    const ici = compositeValue("ICI");
    const eci = compositeValue("ECI");
    return [
      { key: "DMI", name: "债务 / 货币", score: dmi, basis: readingsForScore("DMI"), proxy: null, missing: dmi === null },
      { key: "ICI", name: "内部冲突", score: ici, basis: readingsForScore("ICI"), proxy: null, missing: ici === null },
      { key: "ECI", name: "外部冲突", score: eci, basis: readingsForScore("ECI"), proxy: null, missing: eci === null },
      {
        key: "NAT",
        name: "自然冲击",
        score: naturalShock.value.score,
        basis: naturalShock.value.basis,
        proxy: naturalShock.value.proxy,
        missing: naturalShock.value.score === null,
      },
      {
        key: "TECH",
        name: "技术革命",
        score: techRevolution.value.score,
        basis: techRevolution.value.basis,
        proxy: techRevolution.value.proxy,
        missing: true,
      },
    ];
  });

  const stressCount = computed<number>(
    () => forces.value.filter((force) => force.score !== null && force.score >= 75).length,
  );

  // ── F. 保留：六分量罗盘（原功能）──────────────────────────
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

  const longTone = computed<Tone>(() => PHASE_TONE[long.value.phase_id] ?? "accent");
  const shortTone = computed<Tone>(() => SHORT_TONE[short.value.state] ?? "accent");
  const liquidityTone = computed<Tone>(() => LIQ_TONE[liq.value.state] ?? "plain");
  const longToneClass = computed(() => toneClass(longTone.value));
  const shortToneClass = computed(() => toneClass(shortTone.value));
  const liquidityToneClass = computed(() => toneClass(liquidityTone.value));

  const historyRange = computed(() => {
    const months = historyMonths.value;
    if (!months.length) return "—";
    return `${months[0]} ~ ${months[months.length - 1]}`;
  });

  async function recalc(): Promise<void> {
    if (running.value) return;
    running.value = true;
    recalcError.value = null;
    try {
      await runCycle();
      await refresh();
      void readingsPoll.refresh();
      void loadMeta();
    } catch (err) {
      // 重算失败只在行内提示，绝不整页消失
      recalcError.value = err instanceof Error ? err.message : String(err);
    } finally {
      running.value = false;
    }
  }

  return {
    // 原始轮询
    data,
    error,
    loading,
    refresh,
    readingsPoll,
    indicatorPoll,
    refreshIndicators,
    // 重算
    running,
    recalcError,
    recalc,
    // 归一数据
    payload,
    value,
    indicators,
    long,
    short,
    liq,
    inventory,
    political,
    sustainability,
    sustainabilityThresholds,
    scenarios,
    scenarioList,
    analogs,
    analogList,
    world,
    powerIndex,
    powerComponents,
    reserveCurrency,
    stages,
    history,
    historyMonths,
    historyRange,
    degradedReasons,
    // 标签 / meta
    generatedLabel,
    asofLabel,
    ruleVersion,
    nextCalibration,
    coverageText,
    // Hero
    heroTitle,
    heroSub,
    heroTags,
    compassGrowth,
    compassInflation,
    longConfidencePct,
    // 读数
    readingItems,
    missingReadings,
    readingsUnavailable,
    readingsErrorText,
    readingsAsof,
    readingsLoading: computed(() => readingsPoll.loading.value),
    retryReadings: () => readingsPoll.refresh(),
    indicatorLoading: computed(() => indicatorPoll.loading.value),
    indicatorError: computed(() => indicatorPoll.error.value),
    kpis,
    // 预警
    alertsPayload,
    alertList,
    triggeredAlerts,
    alertCount,
    topAlerts,
    // 类比
    topAnalogs,
    analogSlots,
    // 五力
    forces,
    stressCount,
    // 六分量
    rings,
    axes,
    polygon,
    // 色调
    longTone,
    shortTone,
    liquidityTone,
    longToneClass,
    shortToneClass,
    liquidityToneClass,
    // 透明度表
    structuralRows,
    structuralDegradedCount,
    oldestStaleText,
    oldestStaleTitle,
  };
}
