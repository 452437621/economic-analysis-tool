<template>
  <Drawer :open="evidence.open" :title="title" :sub="sub" @close="evidence.close()">
    <template #icon>
      <svg class="ic" style="color: var(--accent)"><use href="#i-shield-check" /></svg>
    </template>

    <SkeletonBlock v-if="evidence.loading" :rows="6" />
    <ErrorState v-else-if="evidence.error" :error="evidence.error" @retry="reload" />
    <EmptyState
      v-else-if="!doc"
      text="暂无证据内容"
      hint="这条结论没有关联原文证据：到「分析过程」查看推导来源，或确认采集 / 断言抽取作业已经跑过。"
    />

    <template v-else>
      <div class="ev-source">
        <div class="ev-source-top">
          <span class="badge badge--accent badge--sm">证据原文</span>
          <span class="ev-source-name">{{ doc.source?.name ?? "未知来源" }}</span>
          <span class="spacer"></span>
          <span class="badge badge--sm">{{ doc.source?.tier ?? "—" }}</span>
        </div>
        <dl class="ev-kv">
          <dt>发布时间</dt>
          <dd>{{ fmtDateTime(doc.published_at) }}</dd>
          <dt>抓取时间</dt>
          <dd>{{ fmtDateTime(doc.body?.extracted_at) }}</dd>
          <dt>正文状态</dt>
          <dd>{{ doc.status ?? "—" }}</dd>
          <dt>字数</dt>
          <dd>{{ doc.body?.word_count ?? "—" }}</dd>
          <dt>指纹</dt>
          <dd>{{ (doc.body?.sha256 ?? "—").slice(0, 16) }}</dd>
        </dl>
      </div>

      <div class="ev-section">
        <div class="ev-label">原文摘录 · 数字断言已高亮</div>
        <div class="ev-quote">
          <template v-if="bodySegments.length">
            <template v-for="(segment, index) in bodySegments" :key="index">
              <mark v-if="segment.claim" :title="segment.claim">{{ segment.text }}</mark>
              <span v-else>{{ segment.text }}</span>
            </template>
          </template>
          <span v-else class="dim">
            未抓取到正文（可能为 PDF / 动态页面），可打开原文查看。
          </span>
        </div>
      </div>

      <div class="ev-section">
        <div class="ev-label">可提取断言 · {{ doc.claims.length }} 条</div>
        <div class="ev-claims">
          <span v-for="claim in doc.claims.slice(0, 24)" :key="claim.id" class="claim">
            <b>{{ claim.subject }}</b> · {{ claim.predicate }}
            {{ claim.value === null ? "" : claim.value }}{{ claim.unit ?? "" }}
            <span class="claim-conf">置信 {{ Math.round(claim.confidence * 100) }}%</span>
          </span>
          <span v-if="!doc.claims.length" class="claim">暂未抽取到断言</span>
        </div>
      </div>

      <div class="ev-section">
        <div class="ev-label">对判断的影响</div>
        <div class="ev-impact">
          该证据来自 {{ doc.source?.tier === "S1" ? "官方一手来源" : "公开来源" }}，可用于校准主线判断；
          断言置信度由规则抽取给出，需结合原文语境判断。
        </div>
      </div>
    </template>

    <template #footer>
      <button class="btn btn--sm btn--ghost" type="button" @click="copy">
        <svg class="ic"><use href="#i-copy" /></svg>复制引用
      </button>
      <span class="spacer"></span>
      <a v-if="doc?.url" class="btn btn--sm" :href="doc.url" target="_blank" rel="noopener">
        <svg class="ic"><use href="#i-external" /></svg>打开原文
      </a>
      <button class="btn btn--sm btn--primary" type="button" @click="evidence.close()">关闭</button>
    </template>
  </Drawer>
</template>

<script setup lang="ts">
import { computed } from "vue";
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { useEvidenceStore } from "@/stores/evidence";
import { useToast } from "@/stores/toast";
import { fmtDateTime } from "@/composables/useFormat";

const evidence = useEvidenceStore();
const toast = useToast();

const doc = computed(() => evidence.doc);
const title = computed(() => (evidence.loading ? "加载证据…" : doc.value?.title ?? "证据"));
const sub = computed(() => {
  if (!doc.value) return "原文 · 断言 · 可信度";
  return `${doc.value.claims.length} 条断言 · ${doc.value.source?.tier ?? "—"}`;
});

interface Segment {
  text: string;
  claim?: string;
}

/** 按 claim.span 切片，命中区段用 <mark> 高亮 */
const bodySegments = computed<Segment[]>(() => {
  const text = doc.value?.body?.text;
  if (!text) return [];
  const spans = (doc.value?.claims ?? [])
    .filter((claim) => claim.span.start !== null && claim.span.end !== null)
    .map((claim) => ({
      start: Math.max(0, claim.span.start as number),
      end: Math.min(text.length, claim.span.end as number),
      claim: `${claim.subject} ${claim.predicate} ${claim.value ?? ""}${claim.unit ?? ""}`,
    }))
    .filter((span) => span.end > span.start)
    .sort((a, b) => a.start - b.start);
  const segments: Segment[] = [];
  let position = 0;
  for (const span of spans) {
    const start = Math.max(span.start, position);
    if (start > position) segments.push({ text: text.slice(position, start) });
    if (span.end > start) segments.push({ text: text.slice(start, span.end), claim: span.claim });
    position = Math.max(position, span.end);
  }
  if (position < text.length) segments.push({ text: text.slice(position) });
  return segments;
});

function reload(): void {
  if (evidence.doc?.id) void evidence.load(evidence.doc.id);
}

async function copy(): Promise<void> {
  if (!doc.value) return;
  const text = `${doc.value.title}\n${doc.value.source?.name ?? ""} ${doc.value.published_at ?? ""}\n${doc.value.url ?? ""}`;
  try {
    await navigator.clipboard.writeText(text);
    toast.ok("引用已复制");
  } catch {
    toast.warn("浏览器拒绝剪贴板访问");
  }
}
</script>

<style scoped>
.dim {
  color: var(--dim);
}
.claim-conf {
  color: var(--dim);
  margin-left: 4px;
}
</style>
