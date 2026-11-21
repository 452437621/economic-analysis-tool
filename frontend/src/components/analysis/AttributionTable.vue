<template>
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
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtNumber, fmtPct, trendClass } from "@/composables/useFormat";

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

defineProps<{
  attributionRows: AttributionRow[];
  attrWindow: number | null;
  attrDays: number | null;
}>();
</script>

<style scoped>
.analysis-block {
  margin-top: 10px;
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
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
</style>
