<template>
  <!-- 数据源监控 -->
  <div class="sec-row">
    <span class="sec-title">数据源与手动指标</span>
    <span class="sec-count">{{ okCount }}/{{ providers.length }} 正常</span>
    <span class="sec-meta">自动采集 + 手动录入 · 未获取指标不参与评分</span>
    <div class="sec-actions">
      <span class="badge badge--sm" :class="pendingManualCount ? 'badge--warn' : 'badge--live'">
        {{ pendingManualCount ? `${pendingManualCount} 项手动待录入` : "评分因子已齐全" }}
      </span>
    </div>
  </div>
  <section class="card providers-card">
    <div class="card-head">
      <svg class="ic group-ic"><use href="#i-db" /></svg>
      <span class="card-title">采集数据源</span>
      <span class="badge badge--sm">{{ providers.length }} 个</span>
      <div class="card-actions"><span class="card-sub">最近检查 {{ providerCheckedLabel }}</span></div>
    </div>
    <div class="card-body provider-body">
      <div class="provider-grid">
        <div v-for="provider in providers" :key="provider.provider" class="provider-cell" :class="{ 'provider-cell--bad': !provider.ok }">
          <div class="pc-top">
            <span class="dot" :class="provider.ok ? 'dot--live' : 'dot--warn'"></span>
            <span class="pc-name" :title="provider.provider">{{ providerLabel(provider.provider) }}</span>
            <span class="badge badge--sm" :class="provider.ok ? 'badge--live' : 'badge--warn'">
              {{ provider.ok ? "正常" : "异常" }}
            </span>
          </div>
          <div class="pc-meta">
            <span>{{ fmtInt(provider.records) }} 条</span>
            <span>{{ fmtDateTime(providerTime(provider.checked_at)) }}</span>
          </div>
          <div v-if="provider.error" class="pc-err" :title="provider.error">{{ provider.error }}</div>
        </div>
      </div>
    </div>
    <div class="card-head sub-head">
      <svg class="ic group-ic"><use href="#i-plus" /></svg>
      <span class="card-title">手动指标</span>
      <span class="badge badge--sm">{{ manual.length }} 项</span>
      <div class="card-actions"><span class="card-sub">仅手动指标支持录入；权重 0 表示默认不参与评分</span></div>
    </div>
    <div class="card-body manual-body">
      <div class="manual-grid">
        <div v-for="item in manual" :key="item.code" class="manual-row">
          <span class="mr-name" :title="`${item.name}（${item.code}）`">{{ item.name }}</span>
          <span class="mr-src">{{ item.source }} · {{ item.unit }} · {{ freqLabel(item.freq) }} · 权重 {{ item.weight }}</span>
          <span class="badge badge--sm" :class="item.weight > 0 && !item.available ? 'badge--warn' : 'badge--live'">
            {{ item.weight > 0 ? (item.available ? "已录入" : "待录入") : "不参与评分" }}
          </span>
          <button class="link-btn entry-link" type="button" @click="$emit('entry', item)">
            <svg class="ic"><use href="#i-plus" /></svg>{{ item.available ? "更新" : "录入" }}
          </button>
        </div>
      </div>
      <div class="unavailable-note">
        <svg class="ic"><use href="#i-info" /></svg>
        <span>
          数据源说明：BIS 不公布可机读的黄金掉期/存储序列（保留手动录入，权重 0，默认不参与评分）；
          CME 官网在本机网络不可达，COMEX 库存改读 MetalCharts 免费镜像（metalcharts.org，按其许可需署名）；
          上金所不公布库存，以上期所黄金仓单（指定交割金库，千克→吨）作为中国黄金库存代理。
        </span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fmtDateTime, fmtInt } from "@/composables/useFormat";
import type { GoldManualIndicator, GoldProvider } from "@/api/types";
import { freqLabel, providerLabel, providerTime } from "@/utils/goldFormat";

defineProps<{
  providers: GoldProvider[];
  okCount: number;
  manual: GoldManualIndicator[];
  pendingManualCount: number;
  providerCheckedLabel: string;
}>();

defineEmits<{ (e: "entry", item: GoldManualIndicator): void }>();
</script>

<style scoped>
/* ---------- 数据源 ---------- */
.group-ic {
  width: 13px;
  height: 13px;
  color: var(--accent);
}
.entry-link {
  flex: none;
  padding: 0 2px;
}
.entry-link .ic {
  width: 10px;
  height: 10px;
}
.provider-body {
  padding-bottom: 8px;
}
.provider-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 7px;
}
.provider-cell {
  min-width: 0;
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.provider-cell--bad {
  border-color: color-mix(in srgb, var(--warn) 40%, transparent);
}
.pc-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.pc-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  font-size: 10.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.pc-err {
  margin-top: 3px;
  overflow: hidden;
  font-size: 9px;
  color: var(--warn);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sub-head {
  border-top: 1px solid var(--border);
}
.manual-body {
  padding-top: 4px;
}
.manual-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 18px;
}
.manual-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto 46px;
  align-items: center;
  gap: 8px;
  min-height: 29px;
  border-bottom: 1px dashed var(--border);
}
.manual-row:nth-last-child(-n + 2) {
  border-bottom: 0;
}
.mr-name {
  min-width: 0;
  overflow: hidden;
  font-size: 11px;
  color: var(--text);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mr-src {
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.manual-row .entry-link {
  justify-self: end;
}
.unavailable-note {
  display: flex;
  gap: 7px;
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
.unavailable-note .ic {
  width: 11px;
  height: 11px;
  margin-top: 1px;
  flex: none;
  color: var(--muted);
}
@media (max-width: 1360px) {
  .provider-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .manual-grid {
    grid-template-columns: 1fr;
  }
  .manual-row:nth-last-child(-n + 2) {
    border-bottom: 1px dashed var(--border);
  }
  .manual-row:last-child {
    border-bottom: 0;
  }
}
</style>
