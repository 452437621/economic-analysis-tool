<template>
  <Drawer :open="open" :title="title" :sub="sub" @close="emit('close')">
    <div class="tf-form" @keydown.ctrl.enter.prevent="submit">
      <!-- 基本信息 -->
      <section class="tf-group">
        <div class="tf-group-title">基本信息</div>
        <div class="tf-grid">
          <label class="tf-field">
            <span class="tf-label">交易日<em>*</em></span>
            <input v-model="draft.trade_date" type="date" />
            <span v-if="errors.trade_date" class="tf-err">{{ errors.trade_date }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">品种代码<em>*</em></span>
            <input
              v-model="draft.symbol"
              type="text"
              list="trade-symbols"
              maxlength="32"
              placeholder="如 AU / RB / 600519"
              autocomplete="off"
              @input="onSymbolInput"
              @blur="onSymbolInput"
            />
            <datalist id="trade-symbols">
              <option v-for="hint in SYMBOLS" :key="hint.symbol" :value="hint.symbol">
                {{ hint.name }}
              </option>
            </datalist>
            <span v-if="errors.symbol" class="tf-err">{{ errors.symbol }}</span>
            <span v-else class="tf-hint">输入代码或从候选中选择，自动带出名称与类型</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">品种名称</span>
            <input
              v-model="draft.name"
              type="text"
              maxlength="64"
              placeholder="如 沪金主连"
              autocomplete="off"
            />
            <span v-if="errors.name" class="tf-err">{{ errors.name }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">品种类型<em>*</em></span>
            <select v-model="draft.asset_class">
              <option v-for="item in ASSET_CLASSES" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <span v-if="errors.asset_class" class="tf-err">{{ errors.asset_class }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">方向<em>*</em></span>
            <select v-model="draft.direction">
              <option value="long">做多</option>
              <option value="short">做空</option>
            </select>
            <span v-if="errors.direction" class="tf-err">{{ errors.direction }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">状态</span>
            <select v-model="draft.status">
              <option v-for="item in STATUSES" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>
          <label class="tf-field tf-field--full">
            <span class="tf-label">策略</span>
            <input
              v-model="draft.strategy"
              type="text"
              maxlength="200"
              placeholder="如 趋势跟随 / 突破回踩 / 套利"
              autocomplete="off"
            />
            <span v-if="errors.strategy" class="tf-err">{{ errors.strategy }}</span>
          </label>
        </div>
      </section>

      <!-- 价格与仓位 -->
      <section class="tf-group">
        <div class="tf-group-title">价格与仓位</div>
        <div class="tf-grid">
          <label class="tf-field">
            <span class="tf-label">计划数量</span>
            <input v-model="draft.planned_qty" type="number" step="any" inputmode="decimal" placeholder="0" />
            <span v-if="errors.planned_qty" class="tf-err">{{ errors.planned_qty }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">实际数量</span>
            <input v-model="draft.filled_qty" type="number" step="any" inputmode="decimal" placeholder="0" />
            <span v-if="errors.filled_qty" class="tf-err">{{ errors.filled_qty }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">开仓价</span>
            <input v-model="draft.entry_price" type="number" step="any" inputmode="decimal" placeholder="0.00" />
            <span v-if="errors.entry_price" class="tf-err">{{ errors.entry_price }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">平仓价</span>
            <input v-model="draft.exit_price" type="number" step="any" inputmode="decimal" placeholder="0.00" />
            <span v-if="errors.exit_price" class="tf-err">{{ errors.exit_price }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">止损价</span>
            <input v-model="draft.stop_price" type="number" step="any" inputmode="decimal" placeholder="0.00" />
            <span v-if="errors.stop_price" class="tf-err">{{ errors.stop_price }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">止盈价</span>
            <input v-model="draft.target_price" type="number" step="any" inputmode="decimal" placeholder="0.00" />
            <span v-if="errors.target_price" class="tf-err">{{ errors.target_price }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">保证金</span>
            <input v-model="draft.margin" type="number" step="any" inputmode="decimal" placeholder="0.00" />
            <span v-if="errors.margin" class="tf-err">{{ errors.margin }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">杠杆倍数</span>
            <input v-model="draft.leverage" type="number" step="any" inputmode="decimal" placeholder="1" />
            <span v-if="errors.leverage" class="tf-err">{{ errors.leverage }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">手续费</span>
            <input v-model="draft.fee" type="number" step="any" inputmode="decimal" placeholder="0.00" />
            <span v-if="errors.fee" class="tf-err">{{ errors.fee }}</span>
          </label>
        </div>

        <!-- 前端预览：只做展示，不覆盖用户手填 -->
        <div class="tf-preview">
          <div class="tf-preview-item">
            <span>预估盈亏</span>
            <b :class="previewPnl === null ? 'flat' : previewPnlClass">{{ previewPnlText }}</b>
          </div>
          <div class="tf-preview-item">
            <span>预估收益率</span>
            <b :class="previewReturn === null ? 'flat' : previewReturnClass">{{ previewReturnText }}</b>
          </div>
          <div class="tf-preview-item">
            <span>盈亏比</span>
            <b>{{ previewRrText }}</b>
          </div>
        </div>
        <div class="tf-hint">
          预估盈亏 = (平仓价 − 开仓价) × 数量 × 方向 − 手续费（数量优先用实际数量）；收益率 = 预估盈亏 / 保证金。
        </div>
      </section>

      <!-- 风险与复盘 -->
      <section class="tf-group">
        <div class="tf-group-title">风险与复盘</div>
        <div class="tf-grid">
          <label class="tf-field">
            <span class="tf-label">止损金额</span>
            <input v-model="draft.risk_amount" type="number" step="any" inputmode="decimal" placeholder="0.00" />
            <span v-if="errors.risk_amount" class="tf-err">{{ errors.risk_amount }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">盈亏比</span>
            <input v-model="draft.rr" type="number" step="any" inputmode="decimal" placeholder="留空自动计算" />
            <span v-if="errors.rr" class="tf-err">{{ errors.rr }}</span>
          </label>
          <label class="tf-field">
            <span class="tf-label">预计胜率（%）</span>
            <input
              v-model="draft.planned_win_rate"
              type="number"
              step="any"
              inputmode="decimal"
              placeholder="如 55"
            />
            <span v-if="errors.planned_win_rate" class="tf-err">{{ errors.planned_win_rate }}</span>
          </label>
          <label class="tf-field tf-field--full">
            <span class="tf-label">盈亏归因</span>
            <textarea v-model="draft.attribution" rows="2" maxlength="400" placeholder="如 趋势判断正确 / 追高被套 / 止损过紧"></textarea>
            <span v-if="errors.attribution" class="tf-err">{{ errors.attribution }}</span>
          </label>
          <label class="tf-field tf-field--full">
            <span class="tf-label">计划说明</span>
            <textarea
              v-model="draft.plan_note"
              rows="3"
              maxlength="2000"
              placeholder="入场逻辑、触发条件、风控与退出计划。"
            ></textarea>
            <span v-if="errors.plan_note" class="tf-err">{{ errors.plan_note }}</span>
          </label>
          <label class="tf-field tf-field--full">
            <span class="tf-label">复盘结论</span>
            <textarea
              v-model="draft.review_note"
              rows="3"
              maxlength="2000"
              placeholder="执行偏差、结果归因、下次怎么改进。"
            ></textarea>
            <span v-if="errors.review_note" class="tf-err">{{ errors.review_note }}</span>
          </label>
          <label class="tf-field tf-field--full">
            <span class="tf-label">标签（逗号分隔，最多 8 个）</span>
            <input v-model="draft.tags" type="text" maxlength="160" placeholder="趋势, 止损, 复盘" />
            <span v-if="errors.tags" class="tf-err">{{ errors.tags }}</span>
            <span v-else class="tf-hint">已填 {{ tagCount }} / 8 个</span>
          </label>
        </div>
      </section>
    </div>

    <template #footer>
      <span v-if="submitError" class="tf-submit-error" :title="submitError">{{ submitError }}</span>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--ghost" type="button" :disabled="saving" @click="emit('close')">
        取消
      </button>
      <button class="btn btn--sm btn--primary" type="button" :disabled="saving" @click="submit">
        <svg class="ic"><use href="#i-check" /></svg>{{ saving ? "保存中…" : isEdit ? "保存修改" : "保存交易" }}
      </button>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import Drawer from "@/components/ui/Drawer.vue";
import { createTrade, updateTrade } from "@/api/endpoints";
import type {
  TradeAssetClass,
  TradeDirection,
  TradeInput,
  TradeItem,
  TradeStatus,
} from "@/api/types";
import { fmtNumber, fmtPct, fmtSigned } from "@/composables/useFormat";
import { useToast } from "@/stores/toast";

const props = defineProps<{ open: boolean; trade: TradeItem | null }>();
const emit = defineEmits<{ close: []; saved: [item: TradeItem] }>();

const toast = useToast();

const ASSET_CLASSES: { value: TradeAssetClass; label: string }[] = [
  { value: "futures", label: "期货" },
  { value: "stock", label: "股票" },
  { value: "option", label: "期权" },
  { value: "forex", label: "外汇" },
  { value: "crypto", label: "加密" },
  { value: "other", label: "其他" },
];

const STATUSES: { value: TradeStatus; label: string }[] = [
  { value: "planned", label: "计划" },
  { value: "open", label: "持仓中" },
  { value: "closed", label: "已平仓" },
  { value: "cancelled", label: "已取消" },
];

/** 品种快捷项：选中后自动带出中文名与品种类型 */
const SYMBOLS: { symbol: string; name: string; asset_class: TradeAssetClass }[] = [
  { symbol: "AU", name: "沪金", asset_class: "futures" },
  { symbol: "AG", name: "沪银", asset_class: "futures" },
  { symbol: "RB", name: "螺纹钢", asset_class: "futures" },
  { symbol: "MA", name: "甲醇", asset_class: "futures" },
  { symbol: "SH", name: "烧碱", asset_class: "futures" },
  { symbol: "SA", name: "纯碱", asset_class: "futures" },
  { symbol: "M", name: "豆粕", asset_class: "futures" },
  { symbol: "Y", name: "豆油", asset_class: "futures" },
  { symbol: "P", name: "棕榈油", asset_class: "futures" },
  { symbol: "CU", name: "沪铜", asset_class: "futures" },
  { symbol: "SC", name: "原油", asset_class: "futures" },
  { symbol: "IF", name: "沪深300", asset_class: "futures" },
  { symbol: "NQ", name: "纳斯达克100", asset_class: "futures" },
];

const NUMERIC_FIELDS = [
  "planned_qty",
  "filled_qty",
  "entry_price",
  "exit_price",
  "stop_price",
  "target_price",
  "margin",
  "leverage",
  "fee",
  "risk_amount",
  "rr",
  "planned_win_rate",
] as const;

type NumericKey = (typeof NUMERIC_FIELDS)[number];

interface Draft {
  trade_date: string;
  symbol: string;
  name: string;
  asset_class: TradeAssetClass;
  direction: TradeDirection;
  status: TradeStatus;
  strategy: string;
  planned_qty: string;
  filled_qty: string;
  entry_price: string;
  exit_price: string;
  stop_price: string;
  target_price: string;
  margin: string;
  leverage: string;
  fee: string;
  risk_amount: string;
  rr: string;
  planned_win_rate: string;
  attribution: string;
  plan_note: string;
  review_note: string;
  tags: string;
}

function today(): string {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

function blankDraft(): Draft {
  return {
    trade_date: today(),
    symbol: "",
    name: "",
    asset_class: "futures",
    direction: "long",
    status: "closed",
    strategy: "",
    planned_qty: "",
    filled_qty: "",
    entry_price: "",
    exit_price: "",
    stop_price: "",
    target_price: "",
    margin: "",
    leverage: "",
    fee: "",
    risk_amount: "",
    rr: "",
    planned_win_rate: "",
    attribution: "",
    plan_note: "",
    review_note: "",
    tags: "",
  };
}

const draft = reactive<Draft>(blankDraft());
const errors = reactive<Record<string, string>>({});
const saving = ref(false);
const submitError = ref("");

const isEdit = computed(() => Boolean(props.trade));
const title = computed(() => (isEdit.value ? "编辑交易" : "新建交易"));
const sub = computed(() =>
  props.trade ? `${props.trade.symbol} · ${props.trade.trade_date}` : "股票 / 期货 / 期权 / 外汇 / 加密 均可记录",
);

function clearErrors(): void {
  for (const key of Object.keys(errors)) delete errors[key];
}

function numText(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

function seed(): void {
  const row = props.trade;
  const base = blankDraft();
  if (row) {
    Object.assign(base, {
      trade_date: row.trade_date,
      symbol: row.symbol,
      name: row.name ?? "",
      asset_class: row.asset_class,
      direction: row.direction,
      status: row.status,
      strategy: row.strategy ?? "",
      planned_qty: numText(row.planned_qty),
      filled_qty: numText(row.filled_qty),
      entry_price: numText(row.entry_price),
      exit_price: numText(row.exit_price),
      stop_price: numText(row.stop_price),
      target_price: numText(row.target_price),
      margin: numText(row.margin),
      leverage: numText(row.leverage),
      fee: numText(row.fee),
      risk_amount: numText(row.risk_amount),
      rr: numText(row.rr),
      planned_win_rate:
        row.planned_win_rate === null || row.planned_win_rate === undefined
          ? ""
          : numText(Number(row.planned_win_rate) * 100),
      attribution: row.attribution ?? "",
      plan_note: row.plan_note ?? "",
      review_note: row.review_note ?? "",
      tags: row.tags.join(", "),
    });
  }
  Object.assign(draft, base);
  clearErrors();
  submitError.value = "";
}

watch(
  () => [props.open, props.trade] as const,
  ([open]) => {
    if (open) seed();
  },
  { immediate: true },
);

function onSymbolInput(): void {
  const value = draft.symbol.trim().toUpperCase();
  const hint = SYMBOLS.find((item) => item.symbol === value);
  if (hint) {
    draft.symbol = hint.symbol;
    draft.name = hint.name;
    draft.asset_class = hint.asset_class;
    delete errors.symbol;
    return;
  }
  // 6 位数字按 A 股代码处理（如 600519）
  if (/^\d{6}$/.test(value)) {
    draft.asset_class = "stock";
    draft.symbol = value;
  }
}

/** 数值输入 → number | null（非法也返回 null，校验阶段单独报错） */
function parseNum(key: NumericKey): number | null {
  // 注意：<input type="number"> 配 v-model 时 Vue 会把值转成 number，这里统一 string 化后再解析
  const raw = String(draft[key] ?? "").trim();
  if (!raw) return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

const previewQty = computed(() => parseNum("filled_qty") ?? parseNum("planned_qty"));

const previewPnl = computed<number | null>(() => {
  const entry = parseNum("entry_price");
  const exit = parseNum("exit_price");
  const qty = previewQty.value;
  if (entry === null || exit === null || qty === null) return null;
  const sign = draft.direction === "long" ? 1 : -1;
  return (exit - entry) * qty * sign - (parseNum("fee") ?? 0);
});

const previewReturn = computed<number | null>(() => {
  const pnl = previewPnl.value;
  const margin = parseNum("margin");
  if (pnl === null || margin === null || margin <= 0) return null;
  return (pnl / margin) * 100;
});

const previewRr = computed<number | null>(() => {
  const entry = parseNum("entry_price");
  const stop = parseNum("stop_price");
  const target = parseNum("target_price");
  if (entry === null || stop === null || target === null) return null;
  const risk = Math.abs(entry - stop);
  if (!risk) return null;
  return Math.abs(target - entry) / risk;
});

const previewPnlText = computed(() => fmtSigned(previewPnl.value, 2));
const previewReturnText = computed(() => fmtPct(previewReturn.value, 1));
const previewRrText = computed(() => fmtNumber(previewRr.value, 2));

// 按需求固定语义：正绿负红（不随「涨跌配色」偏好翻转）
const previewPnlClass = computed(() =>
  previewPnl.value !== null && previewPnl.value > 0 ? "tf-pos" : "tf-neg",
);
const previewReturnClass = computed(() =>
  previewReturn.value !== null && previewReturn.value > 0 ? "tf-pos" : "tf-neg",
);

const rawTags = computed(() =>
  draft.tags
    .split(/[,，、\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean),
);
const tagCount = computed(() => rawTags.value.length);

function parseTags(): string[] {
  return rawTags.value.slice(0, 8);
}

function validate(): boolean {
  clearErrors();
  let ok = true;

  if (!draft.trade_date) {
    errors.trade_date = "请选择交易日";
    ok = false;
  } else if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.trade_date)) {
    errors.trade_date = "交易日格式应为 YYYY-MM-DD";
    ok = false;
  }

  const symbol = draft.symbol.trim();
  if (!symbol) {
    errors.symbol = "请填写交易品种";
    ok = false;
  } else if (symbol.length > 32) {
    errors.symbol = "品种代码最多 32 个字符";
    ok = false;
  }

  if (!draft.asset_class) {
    errors.asset_class = "请选择品种类型";
    ok = false;
  }
  if (!draft.direction) {
    errors.direction = "请选择交易方向";
    ok = false;
  }
  if (draft.name.trim().length > 64) {
    errors.name = "品种名称最多 64 个字符";
    ok = false;
  }
  if (draft.strategy.trim().length > 200) {
    errors.strategy = "策略最多 200 个字符";
    ok = false;
  }
  if (draft.attribution.trim().length > 400) {
    errors.attribution = "盈亏归因最多 400 个字符";
    ok = false;
  }
  if (draft.plan_note.trim().length > 2000) {
    errors.plan_note = "计划说明最多 2000 个字符";
    ok = false;
  }
  if (draft.review_note.trim().length > 2000) {
    errors.review_note = "复盘结论最多 2000 个字符";
    ok = false;
  }

  for (const key of NUMERIC_FIELDS) {
    const raw = String(draft[key] ?? "").trim();
    if (!raw) continue;
    if (!Number.isFinite(Number(raw))) {
      errors[key] = "请输入数字";
      ok = false;
    }
  }

  const winRate = String(draft.planned_win_rate ?? "").trim();
  if (winRate && Number.isFinite(Number(winRate))) {
    const value = Number(winRate);
    if (value < 0 || value > 100) {
      errors.planned_win_rate = "预计胜率需在 0–100 之间";
      ok = false;
    }
  }

  if (rawTags.value.length > 8) {
    errors.tags = "最多 8 个标签";
    ok = false;
  } else if (rawTags.value.some((tag) => tag.length > 16)) {
    errors.tags = "单个标签最多 16 个字符";
    ok = false;
  }

  if (!ok) {
    const first = Object.keys(errors)[0];
    document.querySelector<HTMLElement>(`[data-field="${first}"]`)?.focus();
  }
  return ok;
}

function buildPayload(): TradeInput {
  const payload: TradeInput = {
    trade_date: draft.trade_date,
    symbol: draft.symbol.trim(),
    name: draft.name.trim() || null,
    asset_class: draft.asset_class,
    direction: draft.direction,
    status: draft.status,
    strategy: draft.strategy.trim() || null,
    planned_qty: parseNum("planned_qty"),
    filled_qty: parseNum("filled_qty"),
    entry_price: parseNum("entry_price"),
    exit_price: parseNum("exit_price"),
    stop_price: parseNum("stop_price"),
    target_price: parseNum("target_price"),
    margin: parseNum("margin"),
    leverage: parseNum("leverage"),
    fee: parseNum("fee"),
    risk_amount: parseNum("risk_amount"),
    attribution: draft.attribution.trim() || null,
    plan_note: draft.plan_note.trim() || null,
    review_note: draft.review_note.trim() || null,
    tags: parseTags(),
  };
  // 表单按「%」录入，后端与库统一存 0–1 小数（与 Excel「预计胜率 0.25」口径一致）
  const winRatePct = parseNum("planned_win_rate");
  if (winRatePct !== null) payload.planned_win_rate = winRatePct / 100;
  // 盈亏比留空则省略，让后端按开/止/目标价补算；手填值优先
  const rr = parseNum("rr");
  if (rr !== null) payload.rr = rr;
  return payload;
}

async function submit(): Promise<void> {
  if (saving.value) return;
  submitError.value = "";
  if (!validate()) return;
  saving.value = true;
  try {
    const payload = buildPayload();
    const item = props.trade
      ? await updateTrade(props.trade.id, payload)
      : await createTrade(payload);
    emit("saved", item);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    submitError.value = message;
    toast.bad(`保存失败：${message}`);
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.tf-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tf-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tf-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 9.5px;
  letter-spacing: 1.2px;
  color: var(--dim);
}

.tf-group-title::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border);
}

.tf-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px 10px;
}

.tf-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.tf-field--full {
  grid-column: 1 / -1;
}

.tf-label {
  font-size: 10px;
  color: var(--muted);
}

.tf-label em {
  font-style: normal;
  margin-left: 2px;
  color: var(--up);
}

.tf-field input,
.tf-field select,
.tf-field textarea {
  width: 100%;
  min-width: 0;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 11.5px;
  outline: none;
  transition: border-color .12s, box-shadow .12s;
}

.tf-field select {
  cursor: pointer;
}

.tf-field textarea {
  height: auto;
  padding: 6px 8px;
  line-height: 1.6;
  resize: vertical;
}

.tf-field input:focus,
.tf-field select:focus,
.tf-field textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}

.tf-field input[type="number"]::-webkit-inner-spin-button,
.tf-field input[type="number"]::-webkit-outer-spin-button {
  margin: 0;
  -webkit-appearance: none;
}

.tf-field input[type="number"] {
  -moz-appearance: textfield;
  appearance: textfield;
}

.tf-err {
  font-size: 9.5px;
  color: var(--up);
}

.tf-hint {
  font-size: 9px;
  line-height: 1.5;
  color: var(--dim);
}

.tf-preview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 9px 10px;
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface-2) 70%, transparent);
}

.tf-preview-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.tf-preview-item span {
  font-size: 9px;
  color: var(--dim);
}

.tf-preview-item b {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 650;
}

/* 按需求固定语义：正绿负红 */
.tf-pos {
  color: var(--ok);
}

.tf-neg {
  color: var(--up);
}

.tf-submit-error {
  max-width: 46%;
  overflow: hidden;
  font-size: 10px;
  color: var(--up);
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 560px) {
  .tf-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .tf-preview {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
