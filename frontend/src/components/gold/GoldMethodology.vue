<template>
  <!-- 方法论 -->
  <div class="sec-row">
    <span class="sec-title">方法论与局限</span>
    <span class="sec-meta">综合评分为多因子加权代理，不构成投资建议</span>
  </div>
  <section class="card method-card">
    <div class="card-head">
      <svg class="ic group-ic"><use href="#i-book" /></svg>
      <span class="card-title">评分方法论</span>
      <div class="card-actions"><span class="card-sub">{{ factorsCount }} 项因子 · 权重合计 {{ fmtNumber(totalWeight, 0) }}</span></div>
    </div>
    <div class="card-body method-body">
      <p class="method-text">{{ methodology }}</p>
      <div class="limits">
        <span class="limits-title">局限</span>
        <ul>
          <li>CFTC 分类持仓（管理基金 / 掉期商）与银行参与报告是公开可得的最佳代理指标，不等同于摩根大通、汇丰等个体做市商账簿。</li>
          <li>BIS 不公布可机读的黄金掉期/存储序列，这两项默认权重 0、不参与评分；黄金租赁利率以上金所「黄金租借基准费率 3M」替代（人民币口径）。</li>
          <li>COMEX 库存来自 MetalCharts 免费 CSV 镜像（周频、需署名 metalcharts.org）；上金所不公布库存，以上期所黄金仓单代理。</li>
          <li>中国官方黄金储备为美元计价，已通过「储备变动 − 金价变动」剔除金价重估影响，得到购金代理值。</li>
        </ul>
      </div>
    </div>
    <div class="card-foot">
      <svg class="ic"><use href="#i-info" /></svg>
      <span>数据截至 {{ earliestFactorAsOf }}（各因子里最早的观测日）· 覆盖率 {{ fmtNumber(coverage, 1) }}% · 评分区间 −100（强空）~ +100（强多）。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fmtNumber } from "@/composables/useFormat";

defineProps<{
  factorsCount: number;
  totalWeight: number;
  methodology: string;
  earliestFactorAsOf: string;
  coverage: number;
}>();
</script>

<style scoped>
/* ---------- 方法论 ---------- */
.group-ic {
  width: 13px;
  height: 13px;
  color: var(--accent);
}
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
.method-body {
  display: grid;
  gap: 10px;
}
.method-text {
  font-size: 10.5px;
  line-height: 1.7;
  color: var(--muted);
}
.limits {
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
.limits-title {
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.4px;
  color: var(--text);
}
.limits ul {
  margin: 5px 0 0;
  padding-left: 16px;
  display: grid;
  gap: 3px;
}
.limits li {
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
</style>
