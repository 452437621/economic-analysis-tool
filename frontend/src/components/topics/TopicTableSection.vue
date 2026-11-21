<template>
  <div class="topic-tables">
    <section v-for="table in tables" :key="table.id || table.title" class="card table-card">
      <div v-if="table.title" class="card-head">
        <span class="card-title">{{ table.title }}</span>
        <span class="card-sub">{{ table.rows.length }} 行</span>
      </div>
      <div v-if="table.rows.length" class="card-body table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th
                v-for="column in table.columns"
                :key="column.key"
                :style="{ textAlign: column.align || 'left' }"
              >
                {{ column.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in table.rows" :key="index">
              <td
                v-for="column in table.columns"
                :key="column.key"
                :style="{ textAlign: column.align || 'left' }"
                :class="{ 'cell-wrap': column.wrap }"
              >
                {{ formatCell(row[column.key], column) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else text="暂无数据" hint="该表依赖的数据尚未采集。" />
      <div v-if="table.note" class="card-foot">{{ table.note }}</div>
    </section>
    <EmptyState v-if="!tables.length" text="暂无表格" hint="等待专题数据返回。" />
  </div>
</template>

<script setup lang="ts">
import EmptyState from "@/components/ui/EmptyState.vue";
import type { TopicTableSpec } from "@/api/types";
import { formatCell } from "@/utils/topicFormat";

defineProps<{ tables: TopicTableSpec[] }>();
</script>

<style scoped>
.topic-tables {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
