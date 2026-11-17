<template>
  <section class="card cyc-forces-card">
    <div class="card-head">
      <span class="card-title">五力仪表 <span class="cyc-card-sub">达利欧大周期驱动</span></span>
      <span class="cyc-card-right">{{ stressCount }} 项进入压力区</span>
    </div>
    <p class="cyc-forces-sub">
      0–100 分数越高压力 / 强度越大 · 前三力为六分量口径，后两力为代理口径 E1（仅供方向参考）
    </p>
    <div class="cyc-forces-body">
      <div v-for="force in forces" :key="force.key" class="cyc-force-row">
        <div class="cyc-force-head">
          <span class="cyc-force-name">{{ force.name }}</span>
          <span class="cyc-force-track">
            <i
              class="cyc-force-fill"
              :class="`cyc-force-fill--${level(force.score).cls}`"
              :style="{ width: force.score === null ? '100%' : `${Math.max(0, Math.min(100, force.score))}%` }"
            ></i>
            <i class="cyc-force-tick" style="left: 25%"></i>
            <i class="cyc-force-tick" style="left: 50%"></i>
            <i class="cyc-force-tick" style="left: 75%"></i>
          </span>
          <b class="cyc-force-num mono">{{ force.score === null ? "—" : fmtNumber(force.score, 0) }}</b>
        </div>
        <div class="cyc-force-meta">
          <span>
            依据 {{ force.basis }} 项 · {{ level(force.score).label }}
            <template v-if="force.proxy"> · {{ force.proxy }}</template>
          </span>
          <RouterLink
            class="btn btn--ghost btn--sm cyc-force-why"
            :to="{ path: '/pipeline', query: { code: 'cycle.state.world' } }"
          >
            为什么
          </RouterLink>
        </div>
      </div>
    </div>
    <div class="cyc-force-scale">
      <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fmtNumber } from "@/composables/useFormat";

interface ForceRow {
  key: string;
  name: string;
  score: number | null;
  basis: number;
  proxy: string | null;
  missing: boolean;
}

defineProps<{ forces: ForceRow[]; stressCount: number }>();

function level(score: number | null): { cls: string; label: string } {
  if (score === null || !Number.isFinite(score)) return { cls: "missing", label: "数据缺失" };
  if (score >= 75) return { cls: "hot", label: "压力区" };
  if (score >= 60) return { cls: "warn", label: "偏高" };
  if (score < 40) return { cls: "ok", label: "低位" };
  return { cls: "flat", label: "中性" };
}
</script>

<style scoped>
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
  margin-left: 4px;
}
.cyc-card-right {
  margin-left: auto;
  font-size: 9.5px;
  color: var(--muted);
  white-space: nowrap;
}
.cyc-forces-card {
  display: flex;
  flex-direction: column;
  min-height: 334px;
  overflow: hidden;
}
.cyc-forces-sub {
  margin: 0;
  padding: 0 12px;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.45;
}
.cyc-forces-body {
  flex: 1 1 auto;
  padding: 2px 12px 4px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.cyc-force-row {
  flex: 1 1 20%;
  min-height: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  border-bottom: 1px dashed var(--border);
}
.cyc-force-row:last-child {
  border-bottom: 0;
}
.cyc-force-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cyc-force-name {
  width: 84px;
  flex: none;
  font-size: 10.5px;
  color: var(--muted);
  white-space: nowrap;
}
.cyc-force-track {
  position: relative;
  flex: 1 1 auto;
  height: 7px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-force-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: inherit;
  background: var(--accent);
  transition: width 0.2s ease;
}
.cyc-force-fill--hot {
  background: var(--up);
}
.cyc-force-fill--warn {
  background: var(--warn);
}
.cyc-force-fill--ok {
  background: var(--down);
}
.cyc-force-fill--missing {
  background: repeating-linear-gradient(
    90deg,
    color-mix(in srgb, var(--dim) 22%, transparent) 0 6px,
    transparent 6px 10px
  );
}
.cyc-force-tick {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.2);
}
.cyc-force-num {
  width: 24px;
  flex: none;
  text-align: right;
  font-size: 12px;
  font-weight: 600;
}
.cyc-force-meta {
  display: flex;
  align-items: center;
  gap: 7px;
  padding-left: 92px;
  font-size: 8.5px;
  color: var(--dim);
}
.cyc-force-meta > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cyc-force-why {
  margin-left: auto;
  height: 18px;
  padding: 0 6px;
  font-size: 8.5px;
  border-radius: 5px;
  flex: none;
  text-decoration: none;
}
.cyc-force-scale {
  display: flex;
  justify-content: space-between;
  padding: 3px 74px 6px 92px;
  font-family: var(--mono);
  font-size: 8px;
  color: var(--dim);
}
@media (max-width: 1023px) {
  .cyc-force-meta {
    padding-left: 0;
  }
  .cyc-force-scale {
    padding-left: 92px;
  }
}
</style>
