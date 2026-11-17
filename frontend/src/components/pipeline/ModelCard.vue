<template>
  <section class="card pipe-model-card">
    <header class="card-head">
      <span class="card-title">
        模型卡 · 方法登记与校准
        <span class="pipe-model-sub">影子模型 · 透明可核验</span>
      </span>
      <div class="card-actions pipe-model-head">
        <span class="pipe-model-head-note mono">最近回测 n={{ sampleText }} · Brier {{ brierText }}</span>
      </div>
    </header>

    <div class="card-body pipe-model-body">
      <div class="pipe-model-grid">
        <div class="pipe-model-cell">
          <span>方法登记</span>
          <b class="mono">{{ fmtInt(methods.length) }} 个</b>
        </div>
        <div class="pipe-model-cell">
          <span>校准样本</span>
          <b class="mono">{{ sampleText }}</b>
        </div>
        <div class="pipe-model-cell">
          <span>Brier 分数</span>
          <b class="mono">{{ brierText }}</b>
        </div>
        <div class="pipe-model-cell">
          <span>方向命中率</span>
          <b class="mono">{{ hitText }}</b>
        </div>
        <div class="pipe-model-cell">
          <span>样本状态</span>
          <b class="badge badge--sm" :class="sampleBadge">{{ sampleState }}</b>
        </div>
        <div class="pipe-model-cell">
          <span>规则版本</span>
          <b class="mono">{{ meta?.rule_version ?? "—" }}</b>
        </div>
      </div>

      <div class="pipe-model-section">
        <div class="pipe-model-section-head">
          <span class="pipe-model-label">方法登记</span>
          <span class="pipe-model-hint">method_id · 版本 · code_sha · 说明</span>
        </div>
        <SkeletonBlock v-if="methodsLoading && !methods.length" :rows="3" />
        <ErrorState v-else-if="methodsError && !methods.length" :error="methodsError" @retry="emit('retry')" />
        <EmptyState v-else-if="!methods.length" text="暂无方法登记" hint="运行带 method_id 的分析后，这里会列出方法版本与代码指纹。" />
        <ul v-else class="pipe-method-list">
          <li v-for="method in methods" :key="method.method_id" class="pipe-method">
            <div class="pipe-method-top">
              <span class="pipe-method-id mono">{{ method.method_id }}</span>
              <span class="badge badge--sm">{{ method.kind }}</span>
              <span class="badge badge--sm">v{{ method.version }}</span>
              <span class="spacer"></span>
              <span class="pipe-method-sha mono" :title="method.code_sha ?? '未记录 code_sha'">{{ shortSha(method.code_sha) }}</span>
            </div>
            <div class="pipe-method-name">{{ method.name }}</div>
            <div class="pipe-method-desc">{{ method.description ?? "未登记方法说明。" }}</div>
          </li>
        </ul>
      </div>

      <div class="pipe-model-section">
        <div class="pipe-model-section-head">
          <span class="pipe-model-label">Brier 与校准</span>
          <span class="pipe-model-hint">
            n&lt;20 视为样本不足 · 分期限 Brier
          </span>
        </div>
        <SkeletonBlock v-if="calibrationLoading && !calibration" :rows="2" />
        <ErrorState
          v-else-if="calibrationError && !calibration && sample === null"
          :error="calibrationError"
          @retry="emit('retry')"
        />
        <div v-else-if="calibrationError && !calibration" class="pipe-model-none">
          校准接口异常，以下为周期元数据中的最近校准摘要（{{ errorText(calibrationError) }}）。
        </div>
        <template v-else>
          <div class="pipe-calib-row">
            <span class="pipe-calib-item">n <b class="mono">{{ sampleText }}</b></span>
            <span class="pipe-calib-item">Brier <b class="mono">{{ brierText }}</b></span>
            <span class="pipe-calib-item">命中率 <b class="mono">{{ hitText }}</b></span>
            <span v-if="coverageText" class="pipe-calib-item">序列覆盖 <b class="mono">{{ coverageText }}</b></span>
            <span v-if="meta?.next_calibration" class="pipe-calib-item">下次校准 <b class="mono">{{ meta.next_calibration }}</b></span>
            <span class="pipe-calib-item" :class="sampleBadge === 'badge--warn' ? 'pipe-sample-warn' : 'pipe-sample-ok'">{{ sampleState }}</span>
          </div>
          <div v-if="calibration && calibration.by_horizon.length" class="pipe-horizon-list">
            <div v-for="horizon in calibration.by_horizon" :key="horizon.bucket" class="pipe-horizon">
              <span class="pipe-horizon-bucket">{{ horizon.bucket }}</span>
              <span class="mono">n={{ fmtInt(horizon.n) }}</span>
              <span class="mono pipe-horizon-brier">Brier {{ fmtNumber(horizon.brier, 3) }}</span>
            </div>
          </div>
          <div v-else class="pipe-model-none">{{ calibration ? "暂无分期限校准样本。" : "暂无校准数据。" }}</div>
          <div v-if="calibration?.note" class="pipe-model-none">{{ calibration.note }}</div>
        </template>
      </div>

      <div class="pipe-limits">
        <div class="pipe-limits-title">已知局限与失效条件</div>
        <div class="pipe-limits-grid">
          <div v-for="(item, index) in LIMITS" :key="index" class="pipe-limit-item">
            <span class="pipe-limit-tag mono">{{ index + 1 }}</span>
            <span>{{ item }}</span>
          </div>
        </div>
        <div class="pipe-limits-note">
          以上为设计原型示例条目；单条推导的真实失效条件、反证与注意事项以「为什么」抽屉为准。
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { LedgerCalibration, V2Method } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtInt, fmtNumber, fmtPct } from "@/composables/useFormat";

interface ModelMeta {
  rule_version?: string | null;
  next_calibration?: string | null;
  brier?: number | null;
  calibration_n?: number | null;
  coverage?: { series_covered?: number | null; series_total?: number | null } | null;
}

const props = defineProps<{
  methods: V2Method[];
  methodsLoading: boolean;
  methodsError: Error | null;
  calibration: LedgerCalibration | null;
  calibrationLoading: boolean;
  calibrationError: Error | null;
  meta: ModelMeta | null;
}>();

const emit = defineEmits<{ retry: [] }>();

const LIMITS = [
  "实际利率 > 3.5%，且金价与利率 60 日相关性转正",
  "央行净购金连续 2 个季度 < 200 吨",
  "美元指数 > 112，且全球流动性同步收缩",
];

const sample = computed<number | null>(() => {
  const n = props.calibration?.n ?? props.meta?.calibration_n;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
});

const sampleText = computed(() => (sample.value === null ? "—" : String(sample.value)));
const brierText = computed(() => {
  if (sample.value === 0) return "—";
  const brier = props.calibration?.brier ?? props.meta?.brier;
  return typeof brier === "number" && Number.isFinite(brier) ? fmtNumber(brier, 3) : "—";
});
const hitText = computed(() => {
  const hit = props.calibration?.hit_rate;
  return typeof hit === "number" && Number.isFinite(hit) ? fmtPct(hit * 100, 1) : "—";
});
const sampleState = computed(() => {
  if (sample.value === null) return "暂无样本";
  if (sample.value === 0) return "暂无样本";
  if (sample.value < 20) return "样本不足";
  return "样本充足";
});
const sampleBadge = computed(() => {
  if (sample.value === null || sample.value < 20) return "badge--warn";
  return "badge--live";
});

const coverageText = computed(() => {
  const coverage = props.meta?.coverage;
  const covered = coverage?.series_covered;
  const total = coverage?.series_total;
  if (typeof covered !== "number" || typeof total !== "number" || !Number.isFinite(total) || total <= 0) return "";
  return `${fmtInt(covered)} / ${fmtInt(total)}`;
});

function errorText(error: Error | null): string {
  return error ? error.message : "";
}

function shortSha(sha: string | null): string {
  if (!sha) return "sha —";
  return `sha ${sha.slice(0, 8)}`;
}
</script>

<style scoped>
.pipe-model-card {
  margin-top: 12px;
}
.pipe-model-sub {
  margin-left: 5px;
  font-size: 10px;
  font-weight: 400;
  color: var(--dim);
}
.pipe-model-head-note {
  font-size: 9.5px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-model-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pipe-model-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 7px;
}
.pipe-model-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 6px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
}
.pipe-model-cell span {
  font-size: 8.5px;
  color: var(--dim);
}
.pipe-model-cell b {
  font-size: 11.5px;
  color: var(--text);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pipe-model-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pipe-model-section-head {
  display: flex;
  align-items: baseline;
  gap: 7px;
  flex-wrap: wrap;
}
.pipe-model-label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
}
.pipe-model-hint {
  font-size: 9px;
  color: var(--dim);
}

.pipe-method-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.pipe-method {
  padding: 6px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
  min-width: 0;
}
.pipe-method-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.pipe-method-id {
  font-size: 9.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pipe-method-sha {
  flex: none;
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
}
.pipe-method-name {
  margin-top: 2px;
  font-size: 10px;
  font-weight: 550;
  color: var(--muted);
}
.pipe-method-desc {
  margin-top: 1px;
  font-size: 9.5px;
  color: var(--dim);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.pipe-calib-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 5px 12px;
  font-size: 9.5px;
  color: var(--dim);
}
.pipe-calib-item b {
  font-size: 10.5px;
  color: var(--text);
  font-weight: 600;
}
.pipe-sample-warn {
  color: var(--warn);
}
.pipe-sample-ok {
  color: var(--ok);
}
.pipe-horizon-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 5px;
}
.pipe-horizon {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  font-size: 9px;
  color: var(--muted);
  white-space: nowrap;
}
.pipe-horizon-bucket {
  color: var(--text);
  font-weight: 550;
}
.pipe-horizon-brier {
  margin-left: auto;
  color: var(--dim);
}
.pipe-model-none {
  font-size: 9.5px;
  color: var(--dim);
}

.pipe-limits {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
.pipe-limits-title {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--warn);
}
.pipe-limits-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 5px;
}
.pipe-limit-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 5px 9px;
  border: 1px solid color-mix(in srgb, var(--warn) 30%, var(--border));
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 7%, transparent);
  font-size: 9.5px;
  color: var(--muted);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.pipe-limit-tag {
  flex: none;
  color: var(--warn);
  font-size: 9px;
}
.pipe-limits-note {
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
}

@media (max-width: 1240px) {
  .pipe-model-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 1024px) {
  .pipe-model-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
