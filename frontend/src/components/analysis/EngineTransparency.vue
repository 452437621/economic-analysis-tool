<template>
  <!-- 引擎透明度：方法注册表（摘要）· 最新运行 · 证据等级 · 数据质量
       完整清单统一收在「分析过程」页，这里只保留读结论所需的摘要与入口，避免整表重复。 -->
  <section class="card ana-block">
    <div class="card-head">
      <span class="card-title">方法注册表</span>
      <span class="badge badge--sm">{{ methodTotal }} 个方法</span>
      <div class="card-actions">
        <span class="card-sub">每个结论都能追到方法 id 与代码指纹</span>
        <RouterLink class="link-btn" to="/pipeline">分析过程 →</RouterLink>
      </div>
    </div>
    <div v-if="methodsLoading && !methods" class="card-body">
      <SkeletonBlock :rows="2" :cells="3" :height="12" :gap="9" />
    </div>
    <ErrorState v-else-if="methodsError && !methods" :error="methodsError" @retry="$emit('retry-methods')" />
    <div v-else-if="!methodRows.length" class="card-body">
      <EmptyState
        text="方法注册表为空"
        hint="后端 /api/v2/methods 没有返回任何方法：先确认后端已启动并注册了方法表，再点右上角「刷新」重试。"
      />
    </div>
    <div v-else class="card-body ana-method-summary">
      <span class="ams-item">
        <span class="ams-label">方法构成</span>
        <b>{{ methodKindSummary }}</b>
      </span>
      <span class="ams-item">
        <span class="ams-label">代码指纹</span>
        <b class="mono" :title="methodShaTitle">{{ methodShaSummary }}</b>
      </span>
      <span class="ams-item">
        <span class="ams-label">最近运行</span>
        <b>{{ runs.length ? runStatusText(runs[0].status) : "—" }}</b>
      </span>
    </div>
    <div class="card-foot">
      <svg class="ic"><use href="#i-info" /></svg>
      <span>完整方法清单（类型 / 版本 / 代码指纹 / 说明）见「分析过程 → 方法注册表」。</span>
    </div>
  </section>

  <div class="ana-engine-grid">
    <!-- 最新运行结论：只展示最近一次，完整运行序列与步骤链在「分析过程」 -->
    <section class="card table-card">
      <div class="card-head">
        <span class="card-title">最新运行结论</span>
        <span class="badge badge--sm">{{ runs.length }} 次记录</span>
        <div class="card-actions"><span class="card-sub">按开始时间倒序 · 只展示最近一次</span></div>
      </div>
      <div v-if="runsLoading && !runs" class="card-body">
        <SkeletonBlock :rows="4" :cells="2" :height="12" :gap="9" />
      </div>
      <ErrorState v-else-if="runsError && !runs" :error="runsError" @retry="$emit('retry-runs')" />
      <div v-else-if="!runs.length" class="card-body">
        <EmptyState
          text="尚无运行记录"
          hint="玻璃盒每次运行都会落一条 run。先运行一次分析 / 周期 / 台账任务，或等下一次调度，再点「刷新」。"
        />
      </div>
      <div v-else class="card-body ana-latest-run">
        <div class="ana-run-top">
          <span class="badge badge--sm" :class="runStatusClass(runs[0].status)">{{ runStatusText(runs[0].status) }}</span>
          <span class="mono ana-run-kind">{{ runs[0].kind }} / {{ runs[0].subject }}</span>
          <span class="dim ana-run-time">{{ fmtTime(runs[0].started_at, true) }}</span>
        </div>
        <div class="ana-run-sub">
          <span>方法 <b class="mono">{{ runs[0].method_id || "—" }}</b></span>
          <span>耗时 {{ runs[0].duration_ms === null ? "—" : `${fmtInt(runs[0].duration_ms)} ms` }}</span>
          <span>数据日 {{ runs[0].asof ? fmtDate(runs[0].asof) : "—" }}</span>
        </div>
        <div v-if="summaryChips(runs[0]).length" class="ana-run-chips">
          <span v-for="chip in summaryChips(runs[0])" :key="chip">{{ chip }}</span>
        </div>
        <div
          v-if="runs[0].degraded_reasons.length"
          class="ana-run-degraded"
          :title="runs[0].degraded_reasons.map((item) => `${item.code}: ${item.message}`).join(' · ')"
        >
          降级 {{ runs[0].degraded_reasons.length }} 项：{{ runs[0].degraded_reasons[0].code }}
        </div>
        <div v-else-if="runs[0].error" class="ana-run-degraded" :title="runs[0].error">失败：{{ runs[0].error }}</div>
        <RouterLink class="link-btn ana-run-more" to="/pipeline">查看全部运行与步骤链 →</RouterLink>
      </div>
      <div class="card-foot">结论摘要只列本次运行产出的条目数；完整步骤与规则命中见「分析过程」。</div>
    </section>

    <!-- 证据等级分布 -->
    <section class="card table-card">
      <div class="card-head">
        <span class="card-title">证据等级分布</span>
        <span class="badge badge--sm">{{ derivTotal }} 条推导</span>
        <div class="card-actions"><span class="card-sub">E1 最强 → E4 最弱</span></div>
      </div>
      <div v-if="derivationsLoading && !derivations" class="card-body">
        <SkeletonBlock :rows="3" :cells="2" :height="12" :gap="9" />
      </div>
      <ErrorState v-else-if="derivationsError && !derivations" :error="derivationsError" @retry="$emit('retry-derivations')" />
      <div v-else-if="!derivations" class="card-body">
        <EmptyState
          text="尚无推导记录"
          hint="推导由分析 / 周期 / 台账 / 黄金任务运行时写入；先运行一次任务或等待下一次调度，再点「刷新」。"
        />
      </div>
      <template v-else>
        <div class="card-body">
          <div class="ana-grades">
            <div v-for="row in gradeRows" :key="row.grade" class="ana-grade">
              <span class="ana-grade-key mono">{{ row.grade }}</span>
              <span class="ana-grade-track"><i :class="row.cls" :style="{ width: row.width }" /></span>
              <span class="ana-grade-n mono">{{ row.n }}</span>
            </div>
          </div>
          <div class="ana-grade-legend">
            E1 本地序列可回算 · E2 官方数据（含人工口径） · E3 估算 / 代理 · E4 人工研判；折算权重 1.0 / 0.95 / 0.90 / 0.75 / 0.50（见 config/cycle.yaml）。
          </div>
          <RouterLink class="link-btn ana-run-more" to="/pipeline">查看全部推导明细 →</RouterLink>
        </div>
        <div class="card-foot">证据等级衡量「这条结论能否回算」，不衡量它的重要性。</div>
      </template>
    </section>
  </div>

  <!-- 数据质量：权威页在「系统状态」，这里只给通过率与入口，避免同表重复渲染 -->
  <section class="card ana-block">
    <div class="card-head">
      <span class="card-title">数据质量</span>
      <span class="badge badge--sm" :class="qualityPassedClass">{{ qualitySummaryText }}</span>
      <div class="card-actions">
        <span class="card-sub">{{ qualityDateLabel }}</span>
        <RouterLink class="link-btn" to="/system">系统状态 →</RouterLink>
      </div>
    </div>
    <div v-if="qualityLoading && !quality" class="card-body">
      <SkeletonBlock :rows="1" :cells="4" :height="12" :gap="9" />
    </div>
    <ErrorState v-else-if="qualityError && !quality" :error="qualityError" @retry="$emit('retry-quality')" />
    <div v-else-if="!quality?.summary" class="card-body">
      <EmptyState
        text="尚无质检结果"
        hint="新鲜度 / 覆盖率 / 连续性 / 对账检查由定时作业写入；到「系统状态」确认作业是否跑过，再回来点「刷新」。"
      />
    </div>
    <div v-else class="card-body ana-quality-line">
      <span class="aql-item">
        <span class="aql-label">通过率</span>
        <b :class="qualityPassedClass === 'badge--live' ? 'aql-pass' : 'aql-fail'">{{ qualitySummaryText }}</b>
      </span>
      <span class="aql-item">
        <span class="aql-label">未通过</span>
        <b>{{ qualityFailedText }}</b>
      </span>
      <span class="aql-item">
        <span class="aql-label">检查于</span>
        <b>{{ qualityDateLabel.replace("检查于 ", "") }}</b>
      </span>
      <span class="aql-note">逐项期望 / 实际 / 偏差与明细见「系统状态 → 数据质检」。</span>
    </div>
    <div class="card-foot">
      <svg class="ic"><use href="#i-info" /></svg>
      <span>未通过项会在「预警台」告警，明细里写明偏差来源。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDate, fmtInt, fmtTime } from "@/composables/useFormat";
import type { QualityResponse, V2DerivationList, V2Method, V2MethodList, V2Run } from "@/api/types";
import { runStatusClass, runStatusText, summaryChips } from "@/utils/analysisFormat";

interface GradeRow {
  grade: string;
  n: number;
  width: string;
  cls: string;
}

defineProps<{
  methods: V2MethodList | null;
  methodsError: Error | null;
  methodsLoading: boolean;
  methodTotal: number;
  methodRows: V2Method[];
  methodKindSummary: string;
  methodShaTitle: string;
  methodShaSummary: string;
  runs: V2Run[];
  runsLoading: boolean;
  runsError: Error | null;
  derivations: V2DerivationList | null;
  derivationsLoading: boolean;
  derivationsError: Error | null;
  derivTotal: number;
  gradeRows: GradeRow[];
  quality: QualityResponse | null;
  qualityLoading: boolean;
  qualityError: Error | null;
  qualitySummaryText: string;
  qualityFailedText: string;
  qualityPassedClass: string;
  qualityDateLabel: string;
}>();

defineEmits<{
  (e: "retry-methods"): void;
  (e: "retry-runs"): void;
  (e: "retry-derivations"): void;
  (e: "retry-quality"): void;
}>();
</script>

<style scoped>
/* ── 引擎透明度：方法注册表 · 运行 · 证据等级 · 数据质量 ── */
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}
.ana-block {
  margin-top: 10px;
}
.ana-engine-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
  align-items: stretch;
}
.ana-engine-grid > .card {
  display: flex;
  flex-direction: column;
}
.ana-engine-grid > .card > .card-foot {
  margin-top: auto;
}
.ana-method-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 9px 28px;
  padding: 12px 13px;
}
.ams-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.ams-label {
  font-size: 9px;
  color: var(--dim);
  letter-spacing: 0.2px;
}
.ams-item b {
  overflow: hidden;
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ams-item b.mono {
  font-size: 11px;
}
.ana-latest-run {
  padding: 10px 13px 11px;
}
.ana-run-top {
  display: flex;
  align-items: center;
  gap: 7px;
}
.ana-run-kind {
  font-size: 11px;
  font-weight: 600;
}
.ana-run-time {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 10px;
}
.ana-run-sub {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 3px;
  font-size: 10px;
  color: var(--dim);
}
.ana-run-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 5px;
}
.ana-run-chips > span {
  display: inline-flex;
  align-items: center;
  height: 16px;
  padding: 0 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--dim);
  font-family: var(--mono);
  font-size: 9.5px;
}
.ana-run-degraded {
  margin-top: 5px;
  font-size: 10px;
  color: var(--warn);
}
.ana-run-more {
  display: inline-block;
  margin-top: 8px;
}
.ana-quality-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 30px;
  padding: 12px 13px;
}
.aql-item {
  display: flex;
  align-items: baseline;
  gap: 7px;
}
.aql-label {
  font-size: 9px;
  color: var(--dim);
}
.aql-item b {
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 650;
}
.aql-pass {
  color: var(--ok);
}
.aql-fail {
  color: var(--warn);
}
.aql-note {
  font-size: 10px;
  color: var(--dim);
  line-height: 1.5;
}
.ana-grades {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.ana-grade {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10.5px;
}
.ana-grade-key {
  width: 20px;
  color: var(--dim);
}
.ana-grade-track {
  flex: 1 1 auto;
  height: 6px;
  border-radius: 3px;
  background: var(--surface-2);
  overflow: hidden;
}
.ana-grade-track > i {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--dim);
}
.ana-grade-track > i.ana-grade--e1 {
  background: var(--ok);
}
.ana-grade-track > i.ana-grade--e2 {
  background: var(--accent);
}
.ana-grade-track > i.ana-grade--e3 {
  background: var(--warn);
}
.ana-grade-track > i.ana-grade--e4 {
  background: var(--down-color);
}
.ana-grade-n {
  width: 20px;
  text-align: right;
  color: var(--dim);
  font-size: 10px;
}
.ana-grade-legend {
  margin-top: 8px;
  font-size: 9.5px;
  line-height: 1.55;
  color: var(--dim);
}
@media (max-width: 1100px) {
  .ana-engine-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
