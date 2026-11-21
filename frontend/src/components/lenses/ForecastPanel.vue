<template>
  <section class="card lens-card">
    <div class="card-head">
      <span class="card-title">研判登记（进入预测台账）</span>
      <span class="spacer"></span>
      <span class="lens-muted">code 前缀 lens.*；到期按标的收盘对账</span>
    </div>
    <div class="card-body">
      <div class="lens-form">
        <label>资产
          <select v-model="form.asset">
            <option v-for="asset in state.synthesis.assets" :key="asset.id" :value="asset.id">
              {{ asset.label }}
            </option>
          </select>
        </label>
        <label>方向
          <select v-model="form.direction">
            <option value="up">看涨</option>
            <option value="down">看跌</option>
            <option value="flat">震荡</option>
          </select>
        </label>
        <label>期限
          <select v-model.number="form.horizon_days">
            <option :value="21">21 天</option>
            <option :value="63">63 天</option>
            <option :value="126">126 天</option>
          </select>
        </label>
        <label>概率
          <input v-model.number="form.probability" type="number" min="0" max="1" step="0.01" />
        </label>
        <label class="lens-form-wide">备注
          <input v-model="form.notes" type="text" maxlength="200" placeholder="写下你的依据与失效条件" />
        </label>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="submitting" @click="emit('submit')">
          {{ submitting ? "登记中" : "登记预测" }}
        </button>
      </div>

      <div v-if="forecasts.length" class="lens-forecast-list">
        <div v-for="row in forecasts" :key="row.id" class="lens-forecast">
          <span class="badge badge--sm" :class="`lens-dir--${row.direction}`">{{ dirText(row.direction) }}</span>
          <span>{{ assetLabel(row.asset) }}</span>
          <span class="mono">目标 {{ row.target_date ?? "—" }}</span>
          <span class="mono">p {{ fmtRatioPct(row.probability) }}</span>
          <span class="badge badge--sm">{{ row.status === "open" ? "待验证" : row.status }}</span>
        </div>
      </div>
      <EmptyState v-else text="还没有登记研判" hint="登记后进入统一预测台账；到期由台账按标的收盘价（长债按 30 年期收益率）结算，形成可校准记录。" />
    </div>
  </section>
</template>

<script setup lang="ts">
import type { LensForecast, LensStateResponse } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import { dirText, type LensForecastForm } from "@/composables/useLensState";
import { fmtRatioPct } from "@/composables/useFormat";

const props = defineProps<{
  state: LensStateResponse;
  form: LensForecastForm;
  forecasts: LensForecast[];
  submitting: boolean;
}>();

const emit = defineEmits<{ submit: [] }>();

function assetLabel(id: string): string {
  const found = props.state.synthesis.assets.find((a) => a.id === id);
  return found?.label ?? id;
}
</script>

<style scoped>
.lens-card { overflow: hidden; }
.card-body { padding: 12px; }
.lens-muted { color: var(--muted); font-size: 10.5px; }
.lens-form {
  display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end;
}
.lens-form label {
  display: flex; flex-direction: column; gap: 4px; font-size: 10.5px; color: var(--dim);
}
.lens-form input, .lens-form select {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 5px;
  color: var(--text); font-size: 12px; padding: 6px 8px; min-width: 110px;
}
.lens-form-wide { flex: 1 1 240px; }
.lens-form-wide input { width: 100%; }
.lens-forecast-list { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.lens-forecast {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  font-size: 11.5px; color: var(--muted); padding: 6px 8px;
  border: 1px solid var(--border); border-radius: 5px;
}
.lens-dir { font-size: 11px; }
.lens-dir--up { color: var(--up); }
.lens-dir--down { color: var(--down); }
.lens-dir--flat { color: var(--muted); }
</style>
