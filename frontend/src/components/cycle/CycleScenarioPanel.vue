<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">未来情景</span>
      <span class="cyc-card-sub">{{ scenarios?.horizon ?? "未来 6–36 个月" }} · 概率为规则化先验，未经校准</span>
      <div class="card-actions"><span class="cyc-card-sub mono">Σ {{ fmtNumber(scenarios?.sum, 2) }}</span></div>
    </div>
    <div class="card-body cyc-scenario-list">
      <div v-for="item in scenarioList" :key="item.id" class="cyc-scenario-row">
        <div class="cyc-scenario-head">
          <span class="cyc-scenario-id mono">{{ item.id }}</span>
          <span class="cyc-scenario-name">{{ item.name }}</span>
          <b class="cyc-scenario-prob mono">{{ ratioText(item.probability) }}</b>
        </div>
        <div class="cyc-bar">
          <i :style="{ width: `${barWidth(item.probability * 100)}%` }"></i>
        </div>
        <p class="cyc-scenario-desc">{{ item.desc }}</p>
        <p class="cyc-scenario-assets">资产含义：{{ item.assets }}</p>
      </div>
      <EmptyState v-if="!scenarioList.length" text="暂无情景" hint="情景由规则化先验生成。" />
    </div>
    <div class="card-foot">
      <span>{{ scenarios?.formula ?? "" }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtNumber } from "@/composables/useFormat";
import type { CycleScenarioItem, CycleScenarios } from "@/api/types";
import { barWidth, ratioText } from "@/utils/cycleFormat";

defineProps<{
  scenarios: CycleScenarios | null;
  scenarioList: CycleScenarioItem[];
}>();
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-scenario-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cyc-scenario-head {
  display: flex;
  align-items: center;
  gap: 7px;
}
.cyc-scenario-id {
  font-size: 9px;
  color: var(--dim);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 4px;
}
.cyc-scenario-name {
  font-size: 11px;
  font-weight: 600;
}
.cyc-scenario-prob {
  margin-left: auto;
  font-size: 12px;
  color: var(--accent);
}
.cyc-scenario-desc {
  margin: 5px 0 0;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.55;
}
.cyc-scenario-assets {
  margin: 3px 0 0;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
}
.cyc-bar {
  margin-top: 6px;
  height: 5px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 40%, var(--warn)));
}
</style>
