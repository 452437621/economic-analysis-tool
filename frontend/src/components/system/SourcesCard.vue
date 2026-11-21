<template>
  <section class="card">
    <div class="card-head">
      <span class="card-title">数据源健康</span>
      <span class="card-sub">官方优先 · 失败重试 · 最近检查</span>
      <div class="card-actions"><span class="card-sub">{{ sources.length }} 个来源</span></div>
    </div>
    <div class="table-wrap sys-wrap">
      <SkeletonBlock v-if="!sources.length && sourcesLoading" :rows="5" />
      <ErrorState v-else-if="sourcesError" :error="sourcesError" @retry="emit('retry')" />
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>来源</th>
            <th>角色 / 数据域</th>
            <th>类型</th>
            <th>等级</th>
            <th>状态</th>
            <th>24h 成功率</th>
            <th>连续失败</th>
            <th>最近检查</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="source in sources" :key="source.id">
            <td>{{ source.name }}</td>
            <td class="muted">
              <span class="badge badge--sm">{{ (source.roles ?? []).join("/") || "—" }}</span>
              <span class="dim"> {{ (source.domains ?? []).join(" · ") }}</span>
            </td>
            <td class="muted">{{ source.kind }}</td>
            <td><span class="badge badge--sm">{{ source.tier ?? "—" }}</span></td>
            <td>
              <span
                class="badge badge--sm"
                :class="source.last_ok === false || source.cooldown_until ? 'badge--warn' : 'badge--live'"
                :title="source.last_error || (source.base_url ?? '')"
              >
                {{ source.cooldown_until ? "冷却中" : source.last_ok === true ? "正常" : source.last_ok === false ? "失败" : "未检查" }}
              </span>
            </td>
            <td class="num mono">{{ source.success_rate_24h === null || source.success_rate_24h === undefined ? "—" : `${(source.success_rate_24h * 100).toFixed(0)}%` }}</td>
            <td class="num mono">{{ source.consecutive_failures ?? "—" }}</td>
            <td class="muted">{{ fmtDateTime(source.last_check) }}</td>
          </tr>
          <tr v-if="!sources.length">
            <td colspan="8">
              <EmptyState
                text="暂无数据源记录"
                hint="数据源在 backend 的 sources 表里登记；空表说明采集器还没跑过，先运行一次采集任务再刷新。"
              />
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="chains.length" class="cov-method">
        <div class="cov-method-title">备用链</div>
        <ul class="cov-method-list">
          <li v-for="chain in chains" :key="chain.id">
            <b>{{ chain.title }}</b>（{{ chain.status }}{{ chain.single_source ? " · 单源" : "" }}）：
            {{ chain.candidates.map((item) => item.source).join(" → ") }}
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { SourceChain, SourceHealth } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { fmtDateTime } from "@/composables/useFormat";

defineProps<{
  sources: SourceHealth[];
  chains: SourceChain[];
  sourcesLoading: boolean;
  sourcesError: Error | null;
}>();

const emit = defineEmits<{ retry: [] }>();
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}
.sys-wrap {
  max-height: none;
}
.cov-method {
  padding: 9px 11px;
  border: 1px dashed var(--border);
  border-radius: 8px;
}
.cov-method-title {
  margin-bottom: 5px;
  font-size: 9.5px;
  letter-spacing: 0.5px;
  color: var(--dim);
}
.cov-method-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding-left: 16px;
}
.cov-method-list li {
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--muted);
}
</style>
