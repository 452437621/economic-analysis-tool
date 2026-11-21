<template>
  <section class="card drivers-card">
    <div class="card-head">
      <span class="card-title">结论与关键驱动</span>
      <span class="badge badge--sm">按 |贡献| 前 5</span>
      <div class="card-actions"><span class="card-sub">贡献 = 权重 × 标准化得分 × 方向</span></div>
    </div>
    <div class="card-body drivers-body">
      <p class="conclusion">{{ conclusionText }}</p>
      <p class="conclusion-sub">{{ coverageNote }}</p>
      <div class="driver-list">
        <div v-for="driver in topDrivers" :key="driver.code" class="driver-row">
          <span class="d-name" :title="`${driver.name}（${driver.code}）`">{{ driver.name }}</span>
          <span class="d-value">{{ factorValueText(driver) }}</span>
          <span class="d-contrib" :class="trendClass(driver.contribution)">{{ fmtSigned(driver.contribution, 2) }}</span>
          <span class="badge badge--sm" :class="signalClass(driver.signal)">{{ signalLabel(driver.signal) }}</span>
        </div>
        <EmptyState v-if="!topDrivers.length" text="暂无可用因子" hint="等待黄金采集任务写入数据。" />
      </div>
    </div>
    <div class="card-foot">
      <svg class="ic"><use href="#i-info" /></svg>
      <span>贡献正值为利多、负值为利空；未采集因子不计入评分，覆盖率 {{ fmtNumber(coverage, 1) }}%。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtNumber, fmtSigned, trendClass } from "@/composables/useFormat";
import type { GoldFactor } from "@/api/types";
import { factorValueText, signalClass, signalLabel } from "@/utils/goldFormat";

defineProps<{
  conclusionText: string;
  coverageNote: string;
  topDrivers: GoldFactor[];
  coverage: number;
}>()
</script>

<style scoped>
/* ---------- 结论与关键驱动 ---------- */
.drivers-card {
  display: flex;
  flex-direction: column;
}
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
.drivers-body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 8px;
}
.conclusion {
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text);
}
.conclusion-sub {
  font-size: 9.5px;
  line-height: 1.55;
  color: var(--dim);
}
.driver-list {
  display: grid;
  gap: 2px;
  margin-top: 2px;
}
.driver-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 60px 54px;
  align-items: center;
  gap: 8px;
  min-height: 27px;
  border-bottom: 1px dashed var(--border);
}
.driver-row:last-of-type {
  border-bottom: 0;
}
.d-name {
  min-width: 0;
  overflow: hidden;
  font-size: 11px;
  color: var(--text);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.d-value {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
  text-align: right;
  white-space: nowrap;
}
.d-contrib {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 650;
  text-align: right;
}
.driver-row .badge {
  justify-self: end;
}
</style>
