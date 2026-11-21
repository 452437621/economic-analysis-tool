<template>
  <section class="card cyc-trans-card">
    <div class="card-head">
      <span class="card-title">结构性 / 人工观测</span>
      <span class="cyc-card-sub">
        这些指标没有可自动回算的序列，由人工观测登记；逐条列出证据等级、来源与观测时效，方便核对口径
      </span>
      <div class="card-actions">
        <span class="badge badge--sm">{{ structuralRows.length }} 条</span>
        <span class="badge badge--sm" :class="degradedCount ? 'badge--warn' : 'badge--live'">
          降级 {{ degradedCount }}
        </span>
        <span class="gen-at mono" :title="oldestStaleTitle">最旧 {{ oldestStaleText }}</span>
      </div>
    </div>
    <SkeletonBlock v-if="loading && !structuralRows.length" :rows="6" />
    <ErrorState
      v-else-if="error && !structuralRows.length"
      :error="error"
      @retry="$emit('retry')"
    />
    <div v-else class="table-wrap cyc-trans-wrap">
      <table class="data-table cyc-trans-table">
        <thead>
          <tr>
            <th>指标</th>
            <th>分量</th>
            <th class="num">数值</th>
            <th class="num">z</th>
            <th class="num">得分</th>
            <th>证据</th>
            <th>来源</th>
            <th>观测时效</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in structuralRows" :key="row.id">
            <td class="cyc-trans-name">
              {{ row.name }}
              <div class="cyc-trans-id mono">{{ row.id }}</div>
            </td>
            <td><span class="badge badge--sm">{{ scoreLabel(row.score) }}</span></td>
            <td class="num">
              {{ fmtNumber(row.value, 2) }}<small v-if="row.unit" class="cyc-trans-unit">{{ row.unit }}</small>
            </td>
            <td class="num">{{ fmtSigned(row.z, 2) }}</td>
            <td class="num">{{ fmtNumber(row.score_value, 1) }}</td>
            <td>
              <span class="badge badge--sm" :class="evidenceTone(row.evidence)" :title="evidenceTitle(row.evidence)">
                {{ row.evidence || "—" }}
              </span>
            </td>
            <td>
              <span class="cyc-trans-source" :title="row.source || '未登记来源'">{{ row.source || "—" }}</span>
            </td>
            <td>
              <span
                v-if="typeof row.stale_days === 'number'"
                class="badge badge--sm"
                :class="staleTone(row.stale_days)"
                :title="staleTitle(row)"
              >
                {{ row.stale_days }} 天
              </span>
              <span v-else class="dim" :title="`观测日 ${fmtDate(row.asof)}：后端未给出 stale_days`">未记录</span>
            </td>
            <td>
              <span
                v-if="row.degraded"
                class="badge badge--sm badge--warn cyc-trans-degraded"
                :title="row.degrade_reason || '后端标记为降级，但未给出原因'"
              >
                降级
              </span>
              <span v-else class="badge badge--sm badge--live">正常</span>
            </td>
          </tr>
          <tr v-if="!structuralRows.length">
            <td colspan="9">
              <EmptyState
                text="没有结构性 / 人工观测指标"
                hint="后端 /api/v2/cycle/indicators 返回的条目里没有 layer 为「结构性 / 人工观测」的指标：先确认 config/cycle.yaml 的 structural 段未被清空，再点右上角「刷新」。"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card-foot cyc-trans-foot">
      <span class="cyc-trans-legend">
        <b>证据等级</b>：E1 本地序列可回算 · E2 官方数据（人工口径） · E3 估算 / 代理 · E4 人工研判；折算权重
        1.0 / 0.95 / 0.90 / 0.75 / 0.50。
      </span>
      <span class="cyc-trans-legend">
        <b>观测时效</b>：stale_days 是「人工观测日距今的天数」，超过 30 天标黄、超过 90 天标红；降级条目的
        degrade_reason 放在状态标记的 tooltip 里。
      </span>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDate, fmtNumber, fmtSigned } from "@/composables/useFormat";
import type { CycleIndicator } from "@/api/types";
import { evidenceTitle, evidenceTone, scoreLabel, staleTitle, staleTone } from "@/utils/cycleFormat";

defineProps<{
  structuralRows: CycleIndicator[];
  degradedCount: number;
  oldestStaleTitle: string;
  oldestStaleText: string;
  loading: boolean;
  error: Error | null;
}>();

defineEmits<{ (e: "retry"): void }>();
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
/* ── 结构性 / 人工观测透明度卡 ── */
.cyc-trans-card {
  margin-top: 10px;
}
/* 16 条人工观测全部展开，不套全站 table-wrap 的 411px 内部滚动 */
.cyc-trans-wrap {
  max-height: none;
}
.cyc-trans-table tbody td {
  height: auto;
  padding: 6px 10px;
  vertical-align: top;
}
.cyc-trans-name {
  font-weight: 600;
  white-space: normal;
}
.cyc-trans-id {
  font-size: 9px;
  color: var(--dim);
  font-weight: 400;
  letter-spacing: 0.2px;
}
.cyc-trans-unit {
  margin-left: 2px;
  font-size: 9px;
  color: var(--dim);
}
.cyc-trans-source {
  display: inline-block;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.4;
  vertical-align: bottom;
  color: var(--muted);
  font-size: 10px;
}
.cyc-trans-degraded {
  cursor: help;
}
.cyc-trans-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
}
.cyc-trans-legend {
  flex: 1 1 320px;
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
.cyc-trans-legend b {
  color: var(--muted);
  font-weight: 600;
}
</style>
