<template>
  <!-- 黄金研判（独立轮询 /api/gold/overview，不阻塞下方分析区块） -->
  <section class="card gold-card">
    <div class="card-head">
      <span class="card-title">黄金研判</span>
      <span v-if="goldError && gold" class="badge badge--warn badge--sm">
        <svg class="ic" style="width: 11px; height: 11px"><use href="#i-alert" /></svg>刷新失败
      </span>
      <div class="card-actions">
        <span v-if="goldScore" class="card-sub">生成于 {{ goldGeneratedLabel }}</span>
      </div>
    </div>

    <div v-if="goldLoading && !gold" class="card-body">
      <SkeletonBlock :rows="2" :cells="4" :height="16" :gap="10" />
    </div>

    <ErrorState v-else-if="goldError && !gold" :error="goldError" @retry="$emit('retry')" />

    <div v-else-if="goldScore" class="card-body gold-body">
      <div class="gold-main">
        <div class="gold-score-line">
          <span class="gold-score" :class="goldTone">{{ goldScoreText }}</span>
          <span class="gold-scale">/ 100</span>
          <span class="badge badge--sm" :class="goldLabelClass">{{ goldLabel }}</span>
        </div>
        <div class="gold-meta">
          覆盖率 <b>{{ goldCoverageText }}</b>
          <span class="gold-meta-sep">·</span>
          已获取权重 <b>{{ goldAvailableWeight }}</b> / {{ goldTotalWeight }}
        </div>
        <div class="gold-sub">
          {{ goldAvailableCount }}/{{ goldTotalCount }} 因子可用 · 评分区间 −100 ～ +100
        </div>
        <RouterLink class="link-btn gold-link" to="/topics/gold">查看完整黄金研判 →</RouterLink>
      </div>

      <div class="gold-factors">
        <div v-for="factor in goldTopFactors" :key="factor.code" class="gold-factor">
          <div class="gf-top">
            <span class="gf-name" :title="`${factor.name} · ${factor.category_label}`">{{ factor.name }}</span>
            <span class="badge badge--sm" :class="goldSignalClass(factor.signal)">{{ goldSignalText(factor.signal) }}</span>
          </div>
          <div class="gf-value" :title="factor.explain">{{ goldFactorValue(factor) }}</div>
          <div class="gf-foot">
            <span class="gf-contrib" :class="trendClass(factor.contribution)">贡献 {{ fmtSigned(factor.contribution, 2) }}</span>
            <span class="gf-cat">{{ factor.category_label }}</span>
          </div>
        </div>
        <EmptyState v-if="!goldTopFactors.length" text="暂无可评分因子" hint="等待黄金监控任务产出因子数据。" />
      </div>
    </div>

    <div v-else class="card-body">
      <EmptyState text="黄金评分暂不可用" hint="等待黄金监控任务产出评分。" />
    </div>

    <div v-if="goldScore" class="card-foot gold-foot">
      <svg class="ic"><use href="#i-info" /></svg>
      <span class="gold-method" :title="goldMethodology">{{ goldMethodology }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtSigned, trendClass } from "@/composables/useFormat";
import type { GoldFactor, GoldOverviewResponse, GoldScore } from "@/api/types";
import { goldFactorValue, goldSignalClass, goldSignalText } from "@/utils/analysisFormat";

defineProps<{
  gold: GoldOverviewResponse | null;
  goldError: Error | null;
  goldLoading: boolean;
  goldScore: GoldScore | null;
  goldGeneratedLabel: string;
  goldScoreText: string;
  goldTone: "up" | "down" | "flat";
  goldLabelClass: string;
  goldLabel: string;
  goldCoverageText: string;
  goldAvailableWeight: number;
  goldTotalWeight: number;
  goldAvailableCount: number;
  goldTotalCount: number;
  goldTopFactors: GoldFactor[];
  goldMethodology: string;
}>();

defineEmits<{ (e: "retry"): void }>();
</script>

<style scoped>
/* ---------- 黄金研判 ---------- */
.gold-card {
  margin-bottom: 10px;
}
.gold-body {
  display: flex;
  align-items: stretch;
  gap: 18px;
  padding: 11px 13px 12px;
}
.gold-main {
  display: flex;
  flex: none;
  flex-direction: column;
  min-width: 208px;
  max-width: 252px;
  padding-right: 18px;
  border-right: 1px solid var(--border);
}
.gold-score-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.gold-score {
  font-family: var(--mono);
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -1px;
  line-height: 1.05;
}
.gold-scale {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--dim);
}
.gold-score-line .badge {
  margin-left: auto;
  flex: none;
}
.gold-meta {
  margin-top: 4px;
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.55;
}
.gold-meta b {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 650;
  color: var(--text);
}
.gold-meta-sep {
  padding: 0 3px;
  color: var(--dim);
}
.gold-sub {
  margin-top: 3px;
  font-size: 9px;
  line-height: 1.5;
  color: var(--dim);
}
.gold-link {
  align-self: flex-start;
  margin-top: auto;
  padding-top: 6px;
}
.gold-factors {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  min-width: 0;
}
.gold-factor {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 7px 9px 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.gf-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.gf-name {
  min-width: 0;
  overflow: hidden;
  font-size: 10.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gf-top .badge {
  flex: none;
  margin-left: auto;
}
.gf-value {
  margin-top: 5px;
  overflow: hidden;
  font-family: var(--mono);
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.3px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gf-foot {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  margin-top: 2px;
  font-size: 9px;
  color: var(--dim);
}
.gf-contrib {
  flex: none;
  font-family: var(--mono);
  font-weight: 600;
  white-space: nowrap;
}
.gf-cat {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gold-foot {
  min-width: 0;
}
.gold-method {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
@media (max-width: 1240px) {
  .gold-factors {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 980px) {
  .gold-body {
    flex-direction: column;
  }
  .gold-main {
    max-width: none;
    padding-right: 0;
    padding-bottom: 9px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
  .gold-link {
    margin-top: 6px;
  }
}
</style>
