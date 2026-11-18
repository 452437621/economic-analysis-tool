<template>
  <Drawer :open="!!derivationId" :title="title" :sub="sub" @close="emit('close')">
    <template #icon>
      <svg class="ic" style="color: var(--accent)"><use href="#i-branch" /></svg>
    </template>

    <SkeletonBlock v-if="loading" :rows="8" />
    <ErrorState v-else-if="error" :error="error" @retry="load" />

    <template v-else-if="detail">
      <!-- L1 结论 -->
      <section class="db-section">
        <div class="db-label">L1 · 结论</div>
        <div class="db-claim">{{ detail.derivation.claim }}</div>
        <div class="db-meta">
          <span class="badge badge--sm" :class="gradeClass(detail.derivation.evidence_grade)">
            {{ detail.derivation.evidence_grade }}
          </span>
          <span class="db-conf" :title="`置信度 ${detail.derivation.confidence ?? '—'}`">
            置信 {{ confidenceText(detail.derivation.confidence) }}
          </span>
          <span class="badge badge--sm">{{ detail.derivation.code }}</span>
          <span class="spacer"></span>
          <span class="db-dim">观测日 {{ fmtDate(detail.derivation.asof) }}</span>
        </div>
        <pre v-if="detail.derivation.value" class="db-value">{{ pretty(detail.derivation.value) }}</pre>
      </section>

      <!-- L2 过程 -->
      <section class="db-section">
        <div class="db-label">L2 · 推导过程（{{ detail.derivation.steps.length }} 步）</div>
        <ol v-if="detail.derivation.steps.length" class="db-steps">
          <li v-for="(step, index) in detail.derivation.steps" :key="index">
            <b>{{ step.name ?? `步骤 ${index + 1}` }}</b>
            <span v-if="step.detail" class="db-dim"> — {{ step.detail }}</span>
          </li>
        </ol>
        <EmptyState
          v-else
          text="未登记推导步骤"
          hint="方法实现没有输出 steps 时抽屉里就没有步骤：先看下方 inputs 与 caveats，它们记录了输入和已知局限。"
        />
      </section>

      <!-- L3 规则命中 -->
      <section class="db-section">
        <div class="db-label">L3 · 规则命中（{{ detail.derivation.rules_hit.length }} 条）</div>
        <ul v-if="detail.derivation.rules_hit.length" class="db-rules">
          <li v-for="(rule, index) in detail.derivation.rules_hit" :key="index">
            <span class="badge badge--sm badge--accent">{{ rule.rule_id ?? "rule" }}</span>
            <span>{{ rule.message ?? "" }}</span>
          </li>
        </ul>
        <div v-else class="db-note">
          本次量化推导未命中阈值规则；结论来自连续指标合成，而非离散规则触发。
        </div>
      </section>

      <!-- L4 输入 -->
      <section class="db-section">
        <div class="db-label">L4 · 输入（{{ detail.derivation.inputs.length }} 项）</div>
        <div v-if="detail.derivation.inputs.length" class="db-chips">
          <span v-for="code in detail.derivation.inputs" :key="code" class="db-chip mono">{{ code }}</span>
        </div>
        <div v-else class="db-note">未登记具体输入序列。</div>
      </section>

      <!-- L5 反证与失效 -->
      <section class="db-section">
        <div class="db-label">L5 · 反证、失效条件与已知局限</div>
        <dl class="db-kv">
          <template v-if="detail.derivation.caveats.length">
            <dt>已知局限</dt>
            <dd>
              <ul class="db-list">
                <li v-for="item in detail.derivation.caveats" :key="item">{{ item }}</li>
              </ul>
            </dd>
          </template>
          <template v-if="detail.derivation.falsifiers.length">
            <dt>失效条件</dt>
            <dd>
              <ul class="db-list db-list--warn">
                <li v-for="item in detail.derivation.falsifiers" :key="item">{{ item }}</li>
              </ul>
            </dd>
          </template>
          <template v-if="detail.derivation.opposing.length">
            <dt>反对证据</dt>
            <dd>
              <ul class="db-list">
                <li v-for="item in detail.derivation.opposing" :key="item">{{ item }}</li>
              </ul>
            </dd>
          </template>
        </dl>
        <div v-if="!hasEvidenceNote" class="db-note">本次推导未登记反证材料，请降低对结论的依赖。</div>
      </section>

      <!-- 方法 -->
      <section v-if="detail.method" class="db-section">
        <div class="db-label">方法</div>
        <dl class="db-kv">
          <dt>方法</dt>
          <dd class="mono">{{ detail.method.method_id }} · v{{ detail.method.version }}</dd>
          <dt>代码指纹</dt>
          <dd class="mono">{{ detail.method.code_sha ?? "未登记" }}</dd>
          <dt>说明</dt>
          <dd>{{ detail.method.description ?? "—" }}</dd>
        </dl>
      </section>

      <!-- 谱系 -->
      <section v-if="detail.parents.length || detail.children.length" class="db-section">
        <div class="db-label">谱系</div>
        <div v-for="parent in detail.parents" :key="parent.id" class="db-rel">
          <span class="badge badge--sm">上级</span>{{ parent.claim }}
        </div>
        <div v-for="child in detail.children" :key="child.id" class="db-rel">
          <span class="badge badge--sm">下级</span>{{ child.claim }}
        </div>
      </section>
    </template>

    <template #footer>
      <span class="db-dim mono">{{ derivationId?.slice(0, 10) ?? "" }}</span>
      <span class="spacer"></span>
      <button class="btn btn--sm btn--primary" type="button" @click="emit('close')">关闭</button>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { getV2Derivation } from "@/api/endpoints";
import type { V2DerivationDetail } from "@/api/types";
import { fmtDate } from "@/composables/useFormat";

const props = defineProps<{ derivationId: string | null }>();
const emit = defineEmits<{ close: [] }>();

const detail = ref<V2DerivationDetail | null>(null);
const loading = ref(false);
const error = ref<Error | null>(null);
let seq = 0;

const title = computed(() => (loading.value ? "加载推导…" : detail.value?.derivation.claim ?? "推导详情"));
const sub = computed(() => {
  const item = detail.value?.derivation;
  if (!item) return "L1 结论 · L2 过程 · L3 规则 · L4 输入 · L5 反证";
  return `${item.code} · ${item.evidence_grade} · ${item.method_id ?? "未登记方法"}`;
});

const hasEvidenceNote = computed(() => {
  const item = detail.value?.derivation;
  return !!item && (item.caveats.length > 0 || item.falsifiers.length > 0 || item.opposing.length > 0);
});

function confidenceText(value: number | null): string {
  if (value === null || value === undefined) return "—";
  const pct = Math.round(value * 100);
  let label = "无法判断";
  if (value >= 0.8) label = "很可能";
  else if (value >= 0.65) label = "较可能";
  else if (value >= 0.5) label = "可能存在";
  else if (value >= 0.35) label = "证据不足";
  return `${pct}% · ${label}`;
}

function gradeClass(grade: string): string {
  if (grade === "E4") return "badge--warn";
  if (grade === "E3") return "badge--accent";
  return "";
}

function pretty(value: Record<string, unknown>): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

async function load(): Promise<void> {
  if (!props.derivationId) return;
  const current = ++seq;
  loading.value = true;
  error.value = null;
  try {
    const result = await getV2Derivation(props.derivationId);
    if (current === seq) detail.value = result;
  } catch (err) {
    if (current === seq) error.value = err instanceof Error ? err : new Error(String(err));
  } finally {
    if (current === seq) loading.value = false;
  }
}

watch(
  () => props.derivationId,
  (id) => {
    if (!id) {
      detail.value = null;
      error.value = null;
      return;
    }
    void load();
  },
  { immediate: true },
);
</script>

<style scoped>
.db-section {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.db-section:last-child {
  border-bottom: 0;
}
.db-label {
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dim);
  margin-bottom: 6px;
}
.db-claim {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.55;
}
.db-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--muted);
  flex-wrap: wrap;
}
.db-conf {
  font-family: var(--mono);
}
.db-dim {
  color: var(--dim);
  font-size: 11px;
}
.db-value {
  margin: 8px 0 0;
  padding: 8px 10px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  font-family: var(--mono);
  font-size: 11px;
  line-height: 1.55;
  color: var(--muted);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.db-steps {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.8;
  color: var(--muted);
}
.db-steps b {
  color: var(--text);
  font-weight: 600;
}
.db-rules {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}
.db-rules li {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.db-note {
  font-size: 11px;
  color: var(--dim);
  line-height: 1.6;
}
.db-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.db-chip {
  font-size: 10px;
  padding: 2px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  background: var(--surface-2);
}
.db-kv {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  gap: 6px 10px;
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
}
.db-kv dt {
  color: var(--dim);
}
.db-kv dd {
  margin: 0;
  color: var(--muted);
}
.db-list {
  margin: 0;
  padding-left: 16px;
}
.db-list--warn li {
  color: var(--warn);
}
.db-rel {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
  padding: 4px 0;
}
</style>
