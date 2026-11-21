<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 预测台账 · 先登记，后对账</div>
        <h1 class="page-h1">
          预测台账
          <span class="page-sub">把「当时怎么判断」写下来，到期自动结算</span>
        </h1>
        <span class="gen-at">（生成于 {{ generatedLabel }}）</span>
      </div>
      <div class="page-actions">
        <span v-if="payload?.asof" class="badge badge--sm">数据日 {{ fmtDate(payload.asof) }}</span>
        <span v-if="payload?.status" class="badge badge--sm" :class="payload.status === 'ok' ? 'badge--live' : 'badge--warn'">
          {{ payload.status === "ok" ? "运行正常" : "降级运行" }}
        </span>
        <RouterLink class="ldg-link" to="/alerts">去预警台复核 →</RouterLink>
        <button class="btn btn--sm" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "核对中…" : "立即核对" }}
        </button>
      </div>
    </div>

    <SkeletonBlock v-if="!payload && loading" :rows="6" :cells="3" :height="16" />
    <ErrorState v-else-if="!payload && error" :error="error" @retry="refresh" />

    <template v-else-if="payload">
      <div class="kpi-grid">
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-target" /></svg></span>
            <span class="kpi-label">已结预测命中率</span>
            <span class="kpi-flag badge badge--sm" :class="hitRateTone">{{ rateText }}</span>
          </div>
          <div class="kpi-value">{{ calibration.hit_rate == null ? "—" : Math.round(calibration.hit_rate * 100) }}<small>%</small></div>
          <div class="kpi-sub">样本 {{ calibration.n }} 条 · 概率口径为登记时的主观概率</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
            <span class="kpi-label">Brier 分数</span>
            <span class="kpi-flag badge badge--sm" :class="brierTone">{{ brierText }}</span>
          </div>
          <div class="kpi-value">{{ calibration.brier == null ? "—" : fmtNumber(calibration.brier, 3) }}</div>
          <div class="kpi-sub">越低越好：&lt;0.25 优于随机，&lt;0.15 说明概率有信息量</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-layers" /></svg></span>
            <span class="kpi-label">未结 / 已结</span>
            <span class="kpi-flag badge badge--sm">已结 {{ payload.forecasts.resolved }} 条</span>
          </div>
          <div class="kpi-value">{{ payload.forecasts.open }}<small>/ {{ payload.forecasts.resolved }}</small></div>
          <div class="kpi-sub">最近到期 {{ nextDueText }}</div>
        </article>
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-icon"><svg class="ic"><use href="#i-grid" /></svg></span>
            <span class="kpi-label">原则命中</span>
            <span class="kpi-flag badge badge--sm badge--accent">{{ payload.counts.hit }} / {{ payload.counts.total }}</span>
          </div>
          <div class="kpi-value">{{ payload.counts.hit }}<small>条成立</small></div>
          <div class="kpi-sub">
            接近 {{ payload.counts.near }} · 不成立 {{ payload.counts.miss }} · 缺数据 {{ payload.counts.unknown }}
          </div>
        </article>
      </div>

      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">登记一条新预测</div>
            <div class="card-sub">记录基线、方向、期限与主观概率；到期由「立即核对」自动结算</div>
          </div>
          <span class="badge badge--sm">可登记 {{ payload.forecast_codes.length }} 类对象</span>
        </div>
        <div class="card-body">
          <form class="ldg-form" @submit.prevent="submit">
            <label class="ldg-field">
              <span>预测对象</span>
              <select v-model="form.code">
                <option v-for="item in payload.forecast_codes" :key="item.code" :value="item.code">
                  {{ item.label }}
                </option>
              </select>
            </label>
            <label class="ldg-field ldg-field--sm">
              <span>方向</span>
              <select v-model="form.direction">
                <option value="up">上行</option>
                <option value="down">下行</option>
                <option value="flat">持平（±2%）</option>
              </select>
            </label>
            <label class="ldg-field ldg-field--sm">
              <span>期限（天）</span>
              <input v-model.number="form.horizon" type="number" min="1" max="365" placeholder="30" />
            </label>
            <label class="ldg-field ldg-field--sm">
              <span>主观概率</span>
              <input v-model.number="form.probability" type="number" min="0" max="1" step="0.05" placeholder="0.6" />
            </label>
            <label class="ldg-field ldg-field--sm">
              <span>基线值</span>
              <input v-model.number="form.baseline" type="number" step="any" placeholder="可选" />
            </label>
            <label class="ldg-field ldg-field--wide">
              <span>备注（为什么这样判断）</span>
              <input v-model="form.notes" type="text" maxlength="200" placeholder="例：长端利率在 5.75% 上方遇阻，财政供给压力短期缓和" />
            </label>
            <button class="btn btn--sm" type="submit" :disabled="submitting">
              {{ submitting ? "登记中…" : "登记预测" }}
            </button>
          </form>
          <p v-if="message" class="ldg-message" :class="{ 'ldg-message--err': messageError }">{{ message }}</p>
        </div>
      </div>

      <div class="card table-card">
        <div class="card-head">
          <div>
            <div class="card-title">预测清单</div>
            <div class="card-sub">
              按到期日排序 · 共 {{ rows.length }} 条（未结 {{ openRows.length }} / 已结 {{ resolvedRows.length }}）
            </div>
          </div>
          <div class="card-actions">
            <span class="badge badge--sm">未结 {{ openRows.length }} 条</span>
            <span class="badge badge--sm">已结 {{ resolvedRows.length }} 条</span>
          </div>
        </div>

        <div class="table-wrap ldg-wrap">
          <EmptyState
            v-if="!rows.length"
            text="暂无预测记录"
            hint="「立即核对」会按 60 日斜率自动登记 30 / 90 日预测；也可以在上方手动登记一条。"
          />
          <table v-else class="data-table ldg-table">
            <colgroup>
              <col style="width: 132px" />
              <col style="width: 104px" />
              <col style="width: 132px" />
              <col style="width: 62px" />
              <col style="width: 72px" />
              <col style="width: 158px" />
              <col style="width: 136px" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">代码</th>
                <th scope="col">方向 · 期限</th>
                <th scope="col" class="num" title="基线值 → 按 60 日斜率外推的目标值">基准 → 目标</th>
                <th scope="col" class="num">概率</th>
                <th scope="col">状态</th>
                <th scope="col">到期日</th>
                <th scope="col" class="num" title="已结：结算值 · Brier（越低越好）">结算 / Brier</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.id"
                :class="{ 'is-overdue': overdueDays(row) !== null }"
                :title="rowTitle(row)"
              >
                <td class="nowrap">
                  <span class="mono ldg-code">{{ row.code }}</span>
                  <span class="dim ldg-code-label">{{ row.code_label }}</span>
                </td>
                <td class="nowrap">{{ directionText(row.direction) }} · {{ row.horizon_days }}天</td>
                <td class="num">{{ baseToTarget(row) }}</td>
                <td class="num">{{ row.probability == null ? "—" : fmtNumber(row.probability, 2) }}</td>
                <td>
                  <span class="badge badge--sm" :class="statusTone(row)">{{ statusLabel(row) }}</span>
                </td>
                <td class="nowrap">
                  <span class="mono">{{ row.target_date }}</span>
                  <span v-if="overdueDays(row) !== null" class="badge badge--sm badge--warn ldg-overdue">
                    逾期 {{ overdueDays(row) }} 天
                  </span>
                </td>
                <td class="num">{{ settleText(row) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <details class="ldg-spec">
          <summary>口径说明</summary>
          <ul>
            <li>自动登记：每次核对按 60 日斜率登记 30 / 90 日预测（序列至少 5 个历史点，不足记持平），到期结算写入 forecast_outcomes。</li>
            <li>基线值 = 登记当天读数；目标值 = 按 60 日斜率外推的点预测；结算值 = 到期日实际读数。</li>
            <li>命中 = 实际相对基线的方向与预测方向一致；Brier = (概率 − 命中)²，0 最好、0.25 ≈ 随机 50%。</li>
            <li>只有事前写下方向与概率的记录才进入校准样本，事后叙述不计入；样本低于 10 条时分桶只作方向参考。</li>
            <li>规则与原则阈值维护在 backend/app/ledger/principles.py；修改后点「立即核对」。</li>
          </ul>
        </details>
      </div>

      <div class="ldg-grid">
        <div class="card">
          <div class="card-head">
            <div class="card-title">校准分桶</div>
            <div class="card-sub">按期限分桶 · 已结 {{ calibration.n }} 条</div>
          </div>
          <div class="card-body">
            <EmptyState
              v-if="calibration.n === 0"
              text="样本不足（n=0）"
              hint="登记并等待到期结算后，这里会画按期限分桶的 Brier。"
            />
            <EmptyState
              v-else-if="!calibration.by_horizon.length"
              :text="calibrationShortText"
              hint="同一期限至少 2 条已结预测才会成桶。"
            />
            <template v-else>
              <EChart :option="calibrationOption" :height="200" />
              <p v-if="calibration.n < 10" class="ldg-cal-warn">
                当前只有 {{ calibration.n }} 条已结样本（低于 10 条），分桶 Brier 波动很大，只作方向参考。
              </p>
            </template>
            <p class="ldg-cal-note">参考：Brier 0.25 ≈ 随机猜测（恒定 50% 概率）；低于 0.15 说明概率已带信息量。</p>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div class="card-title">原则核对现状</div>
            <div class="card-actions">
              <RouterLink class="ldg-link" to="/principles">打开原则库 →</RouterLink>
            </div>
          </div>
          <div class="card-body">
            <div class="ldg-status-grid">
              <div v-for="row in statusRows" :key="row.id" class="ldg-status" :class="`ldg-status--${row.id}`">
                <span class="ldg-status-count">{{ row.count }}</span>
                <span class="ldg-status-label">{{ row.label }}</span>
              </div>
            </div>
            <p class="ldg-status-note">逐条依据与缺失原因见原则库；缺数据记为未知，不默认不成立。</p>
          </div>
        </div>
      </div>

      <div v-if="payload.degraded_reasons.length" class="ldg-degraded">
        <strong>降级说明</strong>
        <span v-for="reason in payload.degraded_reasons.slice(0, 6)" :key="reason.code">{{ reason.message }}</span>
      </div>

      <div class="card-foot">
        <span class="mono">run {{ payload.run_id.slice(0, 8) }} · method {{ payload.method_id }}</span>
        <RouterLink class="ldg-link" to="/pipeline">在分析过程查看本次运行的每一步 →</RouterLink>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import type { EChartsOption } from "echarts";
import EChart from "@/components/charts/EChart.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import { fmtDate, fmtDateTime, fmtNumber } from "@/composables/useFormat";
import { createLedgerForecast, getLedgerOverview, runLedger } from "@/api/endpoints";
import type { LedgerForecast } from "@/api/types";
import { useToast } from "@/stores/toast";

const toast = useToast();

const { data: payload, error, loading, refresh } = usePolling(getLedgerOverview, {
  interval: 60_000,
});

const running = ref(false);
const submitting = ref(false);
const message = ref("");
const messageError = ref(false);

const form = reactive({
  code: "",
  direction: "up" as "up" | "down" | "flat",
  horizon: 30,
  probability: 0.6,
  baseline: null as number | null,
  notes: "",
});

watch(payload, (value) => {
  if (value && !form.code) {
    form.code = value.forecast_codes[0]?.code ?? "";
  }
});

/** 台账接口生成时间（generated_at），不是浏览器当前时间。 */
const generatedLabel = computed(() => {
  const iso = payload.value?.generated_at;
  return iso ? fmtDateTime(iso) : "—";
});

/** 最近到期的预测：给出日期与剩余天数；没有未结预测时说明原因。 */
const nextDueText = computed(() => {
  const next = payload.value?.forecasts.next_due;
  if (!next) return "暂无未结预测（登记后按期限自动到期）";
  const target = new Date(next);
  if (Number.isNaN(target.getTime())) return next;
  const days = Math.ceil((target.getTime() - Date.now()) / 86_400_000);
  if (days < 0) return `${next}（已过期 ${Math.abs(days)} 天，下次核对时结算）`;
  if (days === 0) return `${next}（今天到期）`;
  return `${next}（${days} 天后）`;
});

const calibration = computed(
  () => payload.value?.calibration ?? { n: 0, brier: null, hit_rate: null, by_horizon: [] },
);

/** 校准分桶图：横轴期限桶、纵轴 Brier，虚线为 0.25（随机猜测）参考线。 */
const calibrationOption = computed<EChartsOption>(() => {
  const rows = calibration.value.by_horizon;
  return {
    grid: { left: 40, right: 16, top: 26, bottom: 26 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.bucket),
      axisLine: { lineStyle: { color: "rgba(148,163,184,.25)" } },
      axisTick: { show: false },
      axisLabel: { color: "#93A4B8", fontSize: 10 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 0.5,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "rgba(148,163,184,.10)" } },
      axisLabel: { color: "#93A4B8", fontSize: 10 },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 30,
        data: rows.map((row) => row.brier),
        itemStyle: { color: "#5B9CFF", borderRadius: [3, 3, 0, 0] },
        label: {
          show: true,
          position: "top",
          color: "#93A4B8",
          fontSize: 10,
          formatter: (params: { dataIndex: number }) => {
            const row = rows[params.dataIndex];
            return row ? `${fmtNumber(row.brier, 3)} (n=${row.n})` : "";
          },
        },
        markLine: {
          silent: true,
          symbol: "none",
          label: { formatter: "随机 0.25", color: "#93A4B8", fontSize: 9, position: "insideEndTop" },
          lineStyle: { color: "#F5A623", type: "dashed" },
          data: [{ yAxis: 0.25 }],
        },
      },
    ],
  };
});

const items = computed<LedgerForecast[]>(() => payload.value?.forecasts.items ?? []);

/** 未结 / 已结合并成一张表，统一按到期日升序，状态用 chip 区分。 */
const rows = computed<LedgerForecast[]>(() =>
  [...items.value].sort((a, b) => a.target_date.localeCompare(b.target_date)),
);
const openRows = computed<LedgerForecast[]>(() => items.value.filter((row) => row.status === "open"));
const resolvedRows = computed<LedgerForecast[]>(() =>
  items.value.filter((row) => row.status !== "open"),
);

const calibrationShortText = computed(
  () => `已结 ${calibration.value.n} 条，但没有可用的分桶数据`,
);

const rateText = computed(() => {
  const rate = calibration.value.hit_rate;
  if (rate == null) return "样本不足";
  if (rate >= 0.6) return "高于抛硬币";
  if (rate >= 0.45) return "接近随机";
  return "低于随机";
});

const hitRateTone = computed(() => {
  const rate = calibration.value.hit_rate;
  if (rate == null) return "";
  if (rate >= 0.6) return "badge--down";
  if (rate >= 0.45) return "";
  return "badge--up";
});

const brierText = computed(() => {
  const score = calibration.value.brier;
  if (score == null) return "样本不足";
  if (score < 0.15) return "有信息量";
  if (score < 0.25) return "优于随机";
  return "需改进";
});

const brierTone = computed(() => {
  const score = calibration.value.brier;
  if (score == null) return "";
  if (score < 0.15) return "badge--down";
  if (score < 0.25) return "badge--accent";
  return "badge--up";
});

const statusRows = computed(() => {
  const counts = payload.value?.counts;
  if (!counts) return [];
  return [
    { id: "hit", label: "成立", count: counts.hit },
    { id: "near", label: "接近", count: counts.near },
    { id: "miss", label: "不成立", count: counts.miss },
    { id: "unknown", label: "缺数据", count: counts.unknown },
  ];
});

function directionText(direction: string): string {
  return direction === "up" ? "上行" : direction === "down" ? "下行" : "持平";
}

function statusLabel(row: LedgerForecast): string {
  if (row.status === "open") return "未结";
  return row.hit ? "命中" : "未中";
}

function statusTone(row: LedgerForecast): string {
  if (row.status === "open") return "badge--accent";
  return row.hit ? "badge--live" : "badge--down";
}

/** 基准 → 目标合并为一列；两端都缺时只显示一个「—」。 */
function baseToTarget(row: LedgerForecast): string {
  if (row.baseline_value == null && row.point == null) return "—";
  return `${fmtNumber(row.baseline_value, 2)} → ${fmtNumber(row.point, 2)}`;
}

/** 已结行：结算值 · Brier；未结行留空。 */
function settleText(row: LedgerForecast): string {
  if (row.status !== "resolved") return "—";
  return `${fmtNumber(row.actual, 2)} · Brier ${fmtNumber(row.brier, 3)}`;
}

/** 未结且已过到期日的行：返回逾期天数，用于高亮与提示。 */
function overdueDays(row: LedgerForecast): number | null {
  if (row.status !== "open") return null;
  const target = new Date(`${row.target_date}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.floor((today.getTime() - target.getTime()) / 86_400_000);
  return diff > 0 ? diff : null;
}

function rowTitle(row: LedgerForecast): string {
  const parts = [`登记 ${row.made_at ? fmtDate(row.made_at) : "—"}`];
  if (row.notes) parts.push(`备注：${row.notes}`);
  if (row.status !== "open" && row.resolved_at) parts.push(`结算 ${fmtDate(row.resolved_at)}`);
  return parts.join(" · ");
}

async function recalc(): Promise<void> {
  if (running.value) return;
  running.value = true;
  try {
    await runLedger();
    await refresh();
    toast.ok("已核对并结算到期预测");
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : "核对失败，请稍后重试");
  } finally {
    running.value = false;
  }
}

async function submit(): Promise<void> {
  if (!form.code) {
    message.value = "请先选择预测对象";
    messageError.value = true;
    return;
  }
  submitting.value = true;
  message.value = "";
  messageError.value = false;
  try {
    const result = await createLedgerForecast({
      code: form.code,
      direction: form.direction,
      horizon_days: Math.max(1, Math.min(365, Number(form.horizon) || 30)),
      probability: form.probability == null ? null : Math.max(0, Math.min(1, Number(form.probability))),
      baseline_value: form.baseline == null || Number.isNaN(Number(form.baseline)) ? null : Number(form.baseline),
      notes: form.notes.trim() || null,
    });
    message.value = `已登记：${result.code} · ${directionText(result.direction)} · 到期 ${result.target_date}`;
    form.notes = "";
    await refresh();
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err);
    messageError.value = true;
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.ldg-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}

.ldg-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 200px;
}

.ldg-field--sm {
  min-width: 110px;
}

.ldg-field--wide {
  flex: 1;
  min-width: 260px;
}

.ldg-field span {
  font-size: 10.5px;
  color: var(--dim);
}

.ldg-field select,
.ldg-field input {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 11.5px;
  padding: 7px 9px;
}

.ldg-field input[type="text"] {
  font-family: inherit;
}

.ldg-message {
  margin: 10px 0 0;
  font-size: 11.5px;
  color: var(--down);
}

.ldg-message--err {
  color: var(--up);
}

/* ── 预测清单：单表 + 状态 chip，内部滚动，避免页面无限长 ── */
.ldg-wrap {
  max-height: 520px;
}

.ldg-table th,
.ldg-table td {
  padding-left: 8px;
  padding-right: 8px;
}

.ldg-table tbody tr.is-overdue td {
  background: color-mix(in srgb, var(--warn) 7%, transparent);
}

.ldg-table tbody tr.is-overdue:hover td {
  background: color-mix(in srgb, var(--warn) 12%, transparent);
}

.ldg-overdue {
  margin-left: 5px;
}

.ldg-code {
  font-weight: 650;
  font-size: 11px;
}

.ldg-code-label {
  margin-left: 5px;
  font-size: 10px;
}

.ldg-spec {
  border-top: 1px solid var(--border);
  padding: 7px 13px 9px;
  font-size: 10px;
  color: var(--dim);
}

.ldg-spec summary {
  cursor: pointer;
  color: var(--muted);
  font-size: 10.5px;
  user-select: none;
}

.ldg-spec summary:hover {
  color: var(--text);
}

.ldg-spec ul {
  margin: 7px 0 0;
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  line-height: 1.6;
}

.ldg-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
  margin-top: 10px;
}

@media (max-width: 1100px) {
  .ldg-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

.ldg-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.ldg-status {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  text-align: center;
}

.ldg-status-count {
  display: block;
  font-family: var(--mono);
  font-size: 18px;
  color: var(--text);
}

.ldg-status-label {
  font-size: 10px;
  color: var(--dim);
}

.ldg-status--hit .ldg-status-count {
  color: var(--up);
}

.ldg-status--near .ldg-status-count {
  color: var(--warn);
}

.ldg-status--miss .ldg-status-count {
  color: var(--down);
}

.ldg-status-note {
  margin: 12px 0 0;
  font-size: 10.5px;
  line-height: 1.6;
  color: var(--dim);
}

.ldg-cal-note {
  margin: 12px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--dim);
}

.ldg-link {
  color: var(--accent);
  font-size: 10.5px;
  text-decoration: none;
}

.ldg-link:hover {
  text-decoration: underline;
}

.ldg-degraded {
  background: color-mix(in srgb, var(--warn) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent);
  border-radius: 10px;
  color: var(--warn);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  margin-top: 14px;
  padding: 10px 12px;
}

.ldg-cal-warn {
  margin: 10px 0 0;
  font-size: 10px;
  line-height: 1.6;
  color: var(--warn);
}

@media (max-width: 1024px) {
  .ldg-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
