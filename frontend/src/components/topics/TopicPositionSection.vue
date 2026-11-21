<template>
  <div class="topic-position">
    <section class="card">
      <div class="card-head">
        <span class="card-title">持仓与操作</span>
        <span v-if="payload.stance" class="badge badge--sm" :class="stanceClass">{{ payload.stance }}</span>
        <div class="card-actions">
          <button type="button" class="btn btn--sm" :disabled="loading" @click="openEditor">
            <svg class="ic"><use href="#i-settings" /></svg>修改持仓
          </button>
        </div>
      </div>
      <div class="card-body">
        <div class="kpi-grid topic-position-cards">
          <div class="topic-position-card"><span>买入价</span><b>{{ fmtNumber(payload.buy_price, 2) }} 元</b></div>
          <div class="topic-position-card"><span>最新价</span><b>{{ fmtNumber(payload.current_price, 2) }} 元</b></div>
          <div class="topic-position-card">
            <span>浮动盈亏</span>
            <b :class="trendClass(payload.pnl_pct)">{{ fmtSigned(payload.pnl_pct, 2) }}%</b>
          </div>
          <div class="topic-position-card">
            <span>含分红回报</span>
            <b :class="trendClass(payload.total_return_pct_with_div)">{{ fmtSigned(payload.total_return_pct_with_div, 2) }}%</b>
          </div>
          <div class="topic-position-card"><span>含分红回本价</span><b>{{ fmtNumber(payload.breakeven_price_with_div, 3) }}</b></div>
          <div class="topic-position-card">
            <span>回本需涨</span>
            <b :class="payload.rally_needed_with_div_pct && payload.rally_needed_with_div_pct > 0 ? 'up' : 'flat'">
              {{ fmtSigned(payload.rally_needed_with_div_pct, 1) }}%
            </b>
          </div>
          <div class="topic-position-card"><span>持仓评分</span><b>{{ payload.score ?? "—" }}/100</b></div>
          <div class="topic-position-card"><span>2026 累计分红</span><b>{{ fmtNumber(payload.dividend_2026_ps, 4) }} 元/股</b></div>
        </div>
        <ul v-if="payload.score_reasons?.length" class="topic-position-reasons">
          <li v-for="item in payload.score_reasons" :key="item">{{ item }}</li>
        </ul>
        <div v-if="triggers.length" class="topic-triggers">
          <div v-for="item in triggers" :key="item.key"><b>{{ item.key }}</b>{{ item.value }}</div>
        </div>
      </div>
      <div v-if="payload.price_date" class="card-foot">
        价格截至 {{ payload.price_date }}；成本与回本使用不复权价，收益与因子使用前复权价。
      </div>
    </section>

    <section v-if="averagingRows.length" class="card table-card">
      <div class="card-head">
        <span class="card-title">分批补仓测算</span>
        <span class="card-sub">按买入价 + 补仓价 × 比例</span>
      </div>
      <div class="card-body table-wrap">
        <table class="data-table">
          <thead>
            <tr><th v-for="column in averagingCols" :key="column.key" :style="{ textAlign: column.align || 'left' }">{{ column.label }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in averagingRows" :key="index">
              <td v-for="column in averagingCols" :key="column.key" :style="{ textAlign: column.align || 'left' }">
                {{ formatCell(row[column.key], column) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <EmptyState
      v-if="!payload.ok"
      :text="payload.reason || '持仓数据不足'"
      hint="需要不复权日线或手动配置买入价。"
    />

    <Drawer :open="open" title="修改持仓参数" sub="写入本地数据库" @close="open = false">
      <template #icon>
        <svg class="ic" style="color: var(--accent)"><use href="#i-settings" /></svg>
      </template>
      <label class="topic-field-label" for="topic-pos-price">买入价（元）</label>
      <input id="topic-pos-price" v-model="form.buy_price" class="topic-field" type="number" step="0.001" min="0" />
      <label class="topic-field-label" for="topic-pos-date">买入日期（YYYY-MM 或 YYYY-MM-DD）</label>
      <input id="topic-pos-date" v-model="form.buy_date" class="topic-field" type="text" placeholder="2026-02" />
      <label class="topic-field-label" for="topic-pos-shares">持仓手数（可选）</label>
      <input id="topic-pos-shares" v-model="form.shares_lots" class="topic-field" type="number" step="1" min="0" />
      <label class="topic-field-label" for="topic-pos-dividends">分红（每行：日期,每股派现）</label>
      <textarea id="topic-pos-dividends" v-model="form.dividends" class="topic-field" rows="3" placeholder="2026-05-27,0.286"></textarea>
      <label class="topic-field-label" for="topic-pos-add-prices">补仓价（逗号分隔）</label>
      <input id="topic-pos-add-prices" v-model="form.add_prices" class="topic-field" type="text" placeholder="12.5,12.0,11.5" />
      <label class="topic-field-label" for="topic-pos-add-ratios">补仓比例（逗号分隔）</label>
      <input id="topic-pos-add-ratios" v-model="form.add_ratios" class="topic-field" type="text" placeholder="0.25,0.5,0.75" />
      <p v-if="error" class="topic-form-error">{{ error }}</p>
      <template #footer>
        <button type="button" class="btn btn--ghost" @click="open = false">取消</button>
        <button type="button" class="btn btn--primary" :disabled="saving" @click="submit">
          {{ saving ? "保存中" : "保存" }}
        </button>
      </template>
    </Drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicPositionData, TopicPositionInput, TopicPositionResponse } from "@/api/types";
import { fmtNumber, fmtSigned, trendClass } from "@/composables/useFormat";
import { formatCell } from "@/utils/topicFormat";
import { averagingColumns } from "@/utils/topicNormalize";

const props = defineProps<{
  data: unknown;
  position?: TopicPositionResponse | null;
  loading?: boolean;
  saving?: boolean;
}>();

const emit = defineEmits<{
  (e: "save", payload: TopicPositionInput): void;
}>();

const payload = computed<TopicPositionData>(() => (props.data ?? {}) as TopicPositionData);
const averagingRows = computed(() => payload.value.averaging_table ?? []);
const averagingCols = computed(() => averagingColumns(averagingRows.value));
const triggers = computed(() => {
  const value = payload.value.triggers ?? {};
  return [
    { key: "加仓条件", value: String(value.add_condition ?? "—") },
    { key: "减仓条件", value: String(value.reduce_condition ?? "—") },
  ].filter((item) => item.value !== "—" && item.value !== "undefined");
});
const stanceClass = computed(() => {
  const stance = payload.value.stance ?? "";
  if (stance.includes("加仓") || stance.includes("持有")) return "badge--up";
  if (stance.includes("减仓")) return "badge--down";
  return "";
});

const open = ref(false);
const error = ref("");
const form = reactive({
  buy_price: "",
  buy_date: "",
  shares_lots: "",
  dividends: "",
  add_prices: "",
  add_ratios: "",
});

function values() {
  return props.position?.effective ?? payload.value.effective ?? payload.value.defaults ?? null;
}

function openEditor() {
  const effective = values();
  form.buy_price = effective?.buy_price != null ? String(effective.buy_price) : "";
  form.buy_date = effective?.buy_date ?? "";
  form.shares_lots = effective?.shares_lots != null ? String(effective.shares_lots) : "";
  form.dividends = (effective?.dividends ?? [])
    .map((item) => `${item.date},${item.per_share}`)
    .join("\n");
  form.add_prices = (effective?.add_prices ?? []).join(",");
  form.add_ratios = (effective?.add_ratios ?? []).join(",");
  error.value = "";
  open.value = true;
}

function parseDividends(text: string): Array<{ date: string; per_share: number }> {
  const rows: Array<{ date: string; per_share: number }> = [];
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const [date, value] = trimmed.split(/[,，]/).map((item) => item.trim());
    const perShare = Number(value);
    if (!date || !Number.isFinite(perShare) || perShare < 0) {
      throw new Error(`分红格式错误：${trimmed}`);
    }
    rows.push({ date, per_share: perShare });
  }
  return rows;
}

function parseNumbers(text: string): number[] {
  return text
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map(Number);
}

function submit() {
  error.value = "";
  try {
    const buyPrice = form.buy_price === "" ? undefined : Number(form.buy_price);
    if (buyPrice !== undefined && (!Number.isFinite(buyPrice) || buyPrice <= 0)) {
      throw new Error("买入价必须大于 0");
    }
    const shares = form.shares_lots === "" ? undefined : Number(form.shares_lots);
    if (shares !== undefined && (!Number.isFinite(shares) || shares < 0)) {
      throw new Error("持仓手数必须大于等于 0");
    }
    const buyDate = form.buy_date.trim() || undefined;
    if (buyDate && !/^\d{4}-\d{2}(-\d{2})?$/.test(buyDate)) {
      throw new Error("买入日期需为 YYYY-MM 或 YYYY-MM-DD");
    }
    const addPrices = parseNumbers(form.add_prices);
    if (addPrices.some((item) => !Number.isFinite(item) || item <= 0)) {
      throw new Error("补仓价必须全部大于 0");
    }
    const addRatios = parseNumbers(form.add_ratios);
    if (addRatios.some((item) => !Number.isFinite(item) || item < 0)) {
      throw new Error("补仓比例必须全部大于等于 0");
    }
    const patch: TopicPositionInput = {
      buy_price: buyPrice,
      buy_date: buyDate,
      shares_lots: shares,
      dividends: parseDividends(form.dividends),
      add_prices: addPrices,
      add_ratios: addRatios,
    };
    emit("save", patch);
    open.value = false;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  }
}
</script>

<style scoped>
.topic-position {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.topic-position-cards {
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
}
.topic-position-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 7px 9px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 10px;
  color: var(--muted);
}
.topic-position-card b {
  font-size: 14px;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.topic-position-card b.up {
  color: var(--up-color);
}
.topic-position-card b.down {
  color: var(--down-color);
}
.topic-position-reasons {
  margin: 9px 0 0;
  padding-left: 17px;
  font-size: 10.5px;
  color: var(--muted);
  line-height: 1.6;
}
.topic-triggers {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
  font-size: 10.5px;
  color: var(--muted);
}
.topic-triggers b {
  margin-right: 6px;
  color: var(--text);
}
.topic-field-label {
  display: block;
  margin: 10px 0 4px;
  font-size: 10.5px;
  color: var(--muted);
}
.topic-field {
  width: 100%;
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface-2);
  color: var(--text);
  font-size: 11.5px;
}
.topic-form-error {
  margin: 8px 0 0;
  font-size: 10.5px;
  color: var(--warn);
}
</style>
