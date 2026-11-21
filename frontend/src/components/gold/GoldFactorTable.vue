<template>
  <!-- 因子明细 -->
  <div class="sec-row">
    <span class="sec-title">因子明细</span>
    <span class="sec-count">{{ sortedFactors.length }} 项</span>
    <span class="sec-meta">按 |贡献| 降序 · 不可用因子弱化显示</span>
    <div class="sec-actions">
      <span class="badge badge--sm">{{ availableFactorCount }} 项可用</span>
    </div>
  </div>
  <section class="card table-card">
    <div class="table-wrap detail-wrap">
      <table class="data-table detail-table">
        <colgroup>
          <col style="width: 104px" />
          <col style="width: 210px" />
          <col style="width: 106px" />
          <col style="width: 80px" />
          <col style="width: 52px" />
          <col style="width: 50px" />
          <col style="width: 70px" />
          <col style="width: 62px" />
          <col />
        </colgroup>
        <thead>
          <tr>
            <th>类别</th>
            <th>指标</th>
            <th class="num">数值</th>
            <th class="num">变化</th>
            <th>方向</th>
            <th class="num">权重</th>
            <th class="num">贡献</th>
            <th>信号</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="factor in sortedFactors"
            :key="factor.code"
            :class="{ 'row-off': !factor.available }"
          >
            <td class="dim cat-cell">{{ factor.category_label }}</td>
            <td class="name-cell">
              <span class="nm" :title="`${factor.name}（${factor.code}）`">{{ factor.name }}</span>
              <button v-if="factor.manual" class="link-btn entry-link" type="button" @click="$emit('entry', factor)">
                录入
              </button>
            </td>
            <td class="num">{{ factor.available ? factorValueText(factor) : "—" }}</td>
            <td class="num" :class="factor.available ? trendClass(factor.change) : 'dim'">
              {{ factor.available ? fmtPct(factor.change) : "—" }}
            </td>
            <td class="dir-cell">{{ factor.direction >= 0 ? "↑ 正向" : "↓ 逆向" }}</td>
            <td class="num dim">{{ factor.weight }}</td>
            <td class="num" :class="factor.available ? trendClass(factor.contribution) : 'dim'">
              {{ factor.available ? fmtSigned(factor.contribution, 2) : "—" }}
            </td>
            <td>
              <span class="badge badge--sm" :class="signalClass(factor.signal)">{{ signalLabel(factor.signal) }}</span>
            </td>
            <td class="note-cell" :title="factor.available ? factor.explain || factor.note : factor.note">
              {{ factor.available ? factor.explain || factor.note : factor.note }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card-foot">
      <svg class="ic"><use href="#i-info" /></svg>
      <span>
        数值为最新观测，变化为近 30 日（月/季频为环比）变动；方向为因子对金价的正/逆向作用，
        贡献为评分分值。CFTC 分类持仓为公开代理指标。
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fmtPct, fmtSigned, trendClass } from "@/composables/useFormat";
import type { GoldFactor } from "@/api/types";
import { factorValueText, signalClass, signalLabel } from "@/utils/goldFormat";

defineProps<{
  sortedFactors: GoldFactor[];
  availableFactorCount: number;
}>();

defineEmits<{ (e: "entry", factor: GoldFactor): void }>();
</script>

<style scoped>
/* ---------- 因子明细表 ---------- */
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
.detail-wrap {
  max-height: none;
}
.detail-table {
  table-layout: fixed;
}
.detail-table tbody td {
  font-size: 11.5px;
}
.detail-table td.cat-cell {
  font-size: 10.5px;
  color: var(--muted);
}
.detail-table .name-cell {
  overflow: hidden;
}
.detail-table .name-cell .nm {
  overflow: hidden;
  font-size: 11.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-table .name-cell .entry-link {
  margin-left: 5px;
  vertical-align: baseline;
}
.detail-table td.dir-cell {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--dim);
}
.detail-table .note-cell {
  overflow: hidden;
  font-size: 10px;
  color: var(--dim);
  text-overflow: ellipsis;
}
.detail-table tbody tr.row-off {
  background: color-mix(in srgb, var(--surface-2) 30%, transparent);
}
.detail-table tbody tr.row-off td {
  opacity: 0.72;
}
</style>
