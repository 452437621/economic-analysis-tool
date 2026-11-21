<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">世界秩序位置</span>
      <span class="cyc-card-sub">内部秩序与国际秩序分开判定 · E4 叙事级</span>
    </div>
    <div class="card-body">
      <EmptyState
        v-if="!world"
        text="世界秩序读数缺失"
        hint="本次 cycle.state 未返回 world 段；内部/国际秩序阶段与八项实力暂不可用。"
      />
      <template v-else>
        <div v-for="stage in stages" :key="stage.id" class="cyc-stage-row">
        <div class="cyc-stage-head">
          <span class="cyc-stage-name">{{ stage.name }}</span>
          <span class="badge badge--sm badge--warn">第 {{ stage.stage ?? "—" }} 阶段 · {{ stage.stage_name }}</span>
          <span class="mono cyc-stage-conf">置信 {{ fmtNumber(stage.confidence, 2) }}</span>
        </div>
        <p class="cyc-layer-meaning">{{ stage.reason }}</p>
        <p class="cyc-layer-meta">失效条件：{{ stage.falsifier }}</p>
      </div>
      <div class="cyc-power-block">
        <div class="cyc-power-head">
          <span class="cyc-layer-name">八项实力指数</span>
          <b class="mono">{{ fmtNumber(powerIndex?.value, 1) }}</b>
          <span class="badge badge--sm" :class="powerIndex?.degraded === true ? 'badge--warn' : ''">
            {{ powerIndex?.degraded === true ? "部分口径降级" : "口径完整" }}
          </span>
        </div>
        <div v-for="item in powerComponents" :key="item.id" class="cyc-power-row">
          <span class="cyc-power-name">{{ item.name }}</span>
          <span class="cyc-power-bar"><i :style="{ width: `${item.value}%` }"></i></span>
          <b class="mono">{{ fmtNumber(item.value, 0) }}</b>
          <em class="mono">{{ fmtNumber(item.weight, 0) }}%</em>
        </div>
        <p class="cyc-layer-meta">
          储备货币：{{ reserveCurrency?.code ?? "—" }} 份额 {{ fmtNumber(reserveCurrency?.share, 1) }}%（{{
            reserveCurrency?.asof ?? "—"
          }}，{{ reserveCurrency?.source ?? "—" }}）
        </p>
      </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import { fmtNumber } from "@/composables/useFormat";
import type { CycleWorld } from "@/api/types";
import type { RawOf, SafePowerComponent, SafeStage } from "@/utils/cycleNormalize";

defineProps<{
  world: RawOf<CycleWorld>;
  stages: SafeStage[];
  powerIndex: RawOf<CycleWorld["power_index"]>;
  powerComponents: SafePowerComponent[];
  reserveCurrency: RawOf<CycleWorld["reserve_currency"]>;
}>();
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-stage-row {
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 1px dashed var(--border);
}
.cyc-stage-head {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.cyc-stage-name {
  font-size: 10.5px;
  font-weight: 600;
}
.cyc-stage-conf {
  margin-left: auto;
  font-size: 9px;
  color: var(--dim);
}
.cyc-power-block {
  margin-top: 4px;
}
.cyc-power-head {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.cyc-power-head b {
  font-size: 13px;
}
.cyc-power-row {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr) 34px 32px;
  gap: 6px;
  align-items: center;
  margin-top: 5px;
  font-size: 9px;
  color: var(--muted);
}
.cyc-power-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-power-bar {
  height: 5px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-power-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--warn);
}
.cyc-power-row b {
  font-size: 9px;
  text-align: right;
  color: var(--text);
}
.cyc-power-row em {
  font-size: 8px;
  color: var(--dim);
  font-style: normal;
  text-align: right;
}
.cyc-layer-name {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
}
.cyc-layer-meaning {
  margin: 5px 0 0;
  font-size: 10px;
  color: var(--muted);
  line-height: 1.55;
}
.cyc-layer-meta {
  margin: 3px 0 0;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
}
</style>
