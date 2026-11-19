<template>
  <div class="view active">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 黄金 · 数据截至 {{ earliestFactorAsOf }}</div>
        <h1 class="page-h1">
          黄金研判
          <span class="page-sub">央行购金 · 全球 ETF · 租赁/掉期/存储 · 库存与实物 · 做市商持仓 · 价格与宏观驱动</span>
        </h1>
        <span class="gen-at">（生成于 {{ updatedLabel }}）</span>
      </div>
      <div class="page-actions">
        <span v-if="error && overview" class="badge badge--warn badge--sm">
          <svg class="ic" style="width: 11px; height: 11px"><use href="#i-alert" /></svg>刷新失败
        </span>
                <button class="btn btn--sm" type="button" :disabled="collecting" @click="triggerRefresh()">
          <svg class="ic" :class="{ spin: collecting }"><use href="#i-refresh" /></svg>
          {{ collecting ? "采集中" : "刷新数据" }}
        </button>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="loading" @click="refresh()">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>重新加载
        </button>
      </div>
    </div>

    <!-- 首次加载骨架 -->
    <template v-if="!overview && loading">
      <div class="score-grid">
        <section class="card">
          <div class="card-head"><span class="card-title">综合评分</span></div>
          <div class="card-body"><SkeletonBlock :rows="3" :cells="2" :height="28" :gap="12" /></div>
        </section>
        <section class="card">
          <div class="card-head"><span class="card-title">结论与关键驱动</span></div>
          <div class="card-body"><SkeletonBlock :rows="5" :cells="4" :height="14" :gap="10" /></div>
        </section>
      </div>
      <section class="card table-card skeleton-block">
        <div class="card-head"><span class="card-title">走势图表</span></div>
        <div class="card-body"><SkeletonBlock :rows="4" :cells="2" :height="42" :gap="10" /></div>
      </section>
      <section class="card table-card skeleton-block">
        <div class="card-head"><span class="card-title">因子明细</span></div>
        <div class="card-body"><SkeletonBlock :rows="8" :cells="8" :height="12" :gap="9" /></div>
      </section>
    </template>

    <section v-else-if="!overview" class="card">
      <ErrorState :error="error" @retry="refresh()" />
    </section>

    <template v-else>
      <!-- 评分 + 结论 -->
      <div class="score-grid">
        <section class="card score-card">
          <div class="card-head">
            <span class="card-title">综合评分</span>
            <span class="badge badge--sm" :class="scoreBadgeClass">{{ scoreLabel }}</span>
            <div class="card-actions"><span class="card-sub">−100 强空 ~ +100 强多</span></div>
          </div>
          <div class="card-body score-body">
            <div class="score-main">
              <div class="gauge-col">
                <div class="gauge">
                  <svg class="gauge-svg" viewBox="0 0 220 130" role="img" :aria-label="`综合评分 ${fmtSigned(scoreValue, 1)}，${scoreLabel}`">
                    <path class="gauge-track" d="M 25 115 A 85 85 0 0 1 195 115" pathLength="100" />
                    <path
                      class="gauge-fill"
                      :class="scoreTrend"
                      d="M 25 115 A 85 85 0 0 1 195 115"
                      pathLength="100"
                      stroke-dasharray="100"
                      :stroke-dashoffset="gaugeOffset"
                    />
                    <line class="gauge-tick" x1="25" y1="115" x2="20" y2="122" />
                    <line class="gauge-tick" x1="195" y1="115" x2="200" y2="122" />
                    <line class="gauge-tick gauge-zero" x1="110" y1="26" x2="110" y2="38" />
                  </svg>
                  <div class="gauge-center">
                    <span class="gauge-score" :class="scoreTrend">{{ fmtSigned(scoreValue, 1) }}</span>
                    <span class="gauge-unit">/ 100</span>
                  </div>
                </div>
                <div class="gauge-scale"><span>−100 强空</span><span>0</span><span>+100 强多</span></div>
              </div>
              <div class="score-stats">
                <div class="stat-row"><span>综合判断</span><b :class="scoreTrend">{{ scoreLabel }}</b></div>
                <div class="stat-row"><span>覆盖率</span><b>{{ fmtNumber(coverage, 1) }}%</b></div>
                <div class="cov-bar"><i :style="{ width: `${coveragePct}%` }"></i></div>
                <div class="stat-row"><span>可用权重</span><b>{{ fmtNumber(availableWeight, 0) }} / {{ fmtNumber(totalWeight, 0) }}</b></div>
                <div class="stat-row"><span>可用因子</span><b>{{ availableFactorCount }} / {{ factors.length }}</b></div>
                <div class="stat-row"><span>评分生成</span><b class="stat-time">{{ generatedLabel }}</b></div>
              </div>
            </div>
            <div class="method-brief">
              <span class="mb-label">方法论摘要</span>
              <p>{{ methodologyBrief }}</p>
            </div>
          </div>
        </section>

        <section class="card drivers-card">
          <div class="card-head">
            <span class="card-title">结论与关键驱动</span>
            <span class="badge badge--sm">按 |贡献| 前 5</span>
            <div class="card-actions"><span class="card-sub">贡献 = 权重 × 标准化得分 × 方向</span></div>
          </div>
          <div class="card-body drivers-body">
            <p class="conclusion">{{ conclusionText }}</p>
            <p class="conclusion-sub">{{ coverageNote }}</p>
            <div class="driver-list">
              <div v-for="driver in topDrivers" :key="driver.code" class="driver-row">
                <span class="d-name" :title="`${driver.name}（${driver.code}）`">{{ driver.name }}</span>
                <span class="d-value">{{ factorValueText(driver) }}</span>
                <span class="d-contrib" :class="trendClass(driver.contribution)">{{ fmtSigned(driver.contribution, 2) }}</span>
                <span class="badge badge--sm" :class="signalClass(driver.signal)">{{ signalLabel(driver.signal) }}</span>
              </div>
              <EmptyState v-if="!topDrivers.length" text="暂无可用因子" hint="等待黄金采集任务写入数据。" />
            </div>
          </div>
          <div class="card-foot">
            <svg class="ic"><use href="#i-info" /></svg>
            <span>贡献正值为利多、负值为利空；未采集因子不计入评分，覆盖率 {{ fmtNumber(coverage, 1) }}%。</span>
          </div>
        </section>
      </div>

      <!-- 因子分组 -->
      <div class="sec-row">
        <span class="sec-title">因子分组</span>
        <span class="sec-count">{{ groups.length }} 组</span>
        <span class="sec-meta">{{ factors.length }} 项因子 · {{ availableFactorCount }} 项已采集 · 按类别聚合</span>
        <div class="sec-actions">
          <span class="badge badge--sm" :class="pendingCount ? 'badge--warn' : 'badge--live'">
            {{ pendingCount ? `${pendingCount} 项待采集` : "全部已采集" }}
          </span>
        </div>
      </div>
      <div class="group-grid">
        <section v-for="group in groups" :key="group.key" class="card group-card">
          <div class="card-head">
            <svg class="ic group-ic"><use :href="group.icon" /></svg>
            <span class="card-title">{{ group.label }}</span>
            <span class="badge badge--sm">{{ group.factors.length }} 项</span>
            <div class="card-actions">
              <span class="card-sub">
                可用 {{ group.available }}/{{ group.factors.length }} ·
                组贡献
                <b class="group-contrib" :class="trendClass(group.contribution)">{{ fmtSigned(group.contribution, 2) }}</b>
              </span>
            </div>
          </div>
          <div class="group-body">
            <div
              v-for="factor in group.factors"
              :key="factor.code"
              class="frow"
              :class="{ 'frow--off': !factor.available }"
            >
              <div class="frow-top">
                <span class="frow-name" :title="`${factor.name}（${factor.code}）`">{{ factor.name }}</span>
                <span v-if="factor.manual" class="badge badge--sm badge--accent">手动录入</span>
                <span v-else-if="!factor.available" class="badge badge--sm">待接入</span>
                <span v-if="factor.available" class="badge badge--sm" :class="signalClass(factor.signal)">
                  {{ signalLabel(factor.signal) }}
                </span>
                <button v-if="factor.manual" class="link-btn entry-link" type="button" @click="openEntry(factor)">
                  <svg class="ic"><use href="#i-plus" /></svg>录入
                </button>
              </div>
              <div class="frow-mid">
                <span class="frow-val">{{ factorValueText(factor) }}</span>
                <span v-if="factor.available" class="frow-chg" :class="trendClass(factor.change)">{{ fmtPct(factor.change) }}</span>
                <span v-else class="frow-chg dim">—</span>
                <span
                  class="frow-asof"
                  :class="{ 'frow-asof--stale': isFactorStale(factor) }"
                  :title="factor.as_of ? `该因子最新观测日 ${fmtDate(factor.as_of)}（${factor.freq || '—'} 频）` : '尚未采集到观测值'"
                >
                  {{ factorAsOfText(factor) }}
                </span>
                <span class="frow-weight">权重 {{ factor.weight }}</span>
                <span class="frow-contrib">
                  贡献
                  <b :class="factor.available ? trendClass(factor.contribution) : 'dim'">
                    {{ factor.available ? fmtSigned(factor.contribution, 2) : "—" }}
                  </b>
                </span>
              </div>
              <div class="frow-desc" :title="factor.available ? factor.explain || factor.note : factor.note">
                {{ factor.available ? factor.explain || factor.note : factor.note }}
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- 图表 -->
      <div class="sec-row">
        <span class="sec-title">走势图表</span>
        <span class="sec-count">{{ chartCards.length }} 张</span>
        <span class="sec-meta">数据来自本地数据库 · 默认不叠加金价，可按图表叠加伦敦金价对比</span>
        <div class="sec-actions">
          <div class="chart-ranges" role="group" aria-label="图表时间范围">
            <button
              v-for="item in HISTORY_RANGES"
              :key="item.value"
              type="button"
              :class="{ active: chartRange === item.value }"
              @click="setChartRange(item.value)"
            >
              {{ item.label }}
            </button>
          </div>
          <span class="badge badge--sm">{{ seriesCount }} 条序列</span>
        </div>
      </div>
      <div class="charts-grid">
        <section
          v-for="chart in chartCards"
          :key="chart.key"
          class="card chart-card"
          :class="{ 'chart-wide': chart.wide }"
        >
          <div class="card-head">
            <span class="card-title">{{ chart.title }}</span>
            <span class="badge badge--sm">{{ chart.unit }}</span>
            <span class="chart-legend">
              <span v-for="item in chart.legend" :key="item.label" class="lg-item" :class="{ 'lg-dim': !item.available }">
                <i class="lg-dot" :class="item.cls"></i>{{ item.label }}
              </span>
            </span>
            <span v-if="chart.note" class="chart-note">{{ chart.note }}</span>
            <div class="card-actions">
              <button
                type="button"
                class="chart-toggle"
                :class="{ active: priceOverlays[chart.key] }"
                :aria-pressed="!!priceOverlays[chart.key]"
                :title="priceOverlays[chart.key] ? '移除伦敦金价对比' : '叠加伦敦金价趋势对比'"
                @click="togglePriceOverlay(chart.key)"
              >
                叠加金价
              </button>
              <span class="card-sub">{{ chartMeta(chart) }}</span>
            </div>
          </div>
          <div class="card-body chart-body">
            <EChart v-if="chartHasData(chart)" :option="chart.option" :height="chart.height" />
            <EmptyState v-else :text="chart.emptyText" :hint="chart.emptyHint" />
          </div>
        </section>
      </div>

      <!-- 因子明细 -->
      <div class="sec-row">
        <span class="sec-title">因子明细</span>
        <span class="sec-count">{{ sortedFactors.length }} 项</span>
        <span class="sec-meta">按 |贡献| 降序 · 不可用因子弱化显示</span>
        <div class="sec-actions">
          <span class="badge badge--sm">{{ availableFactorCount }} 项可用</span>
        </div>
      </div>
      <section class="card table-card">
        <div class="table-wrap detail-wrap">
          <table class="data-table detail-table">
            <colgroup>
              <col style="width: 104px" />
              <col style="width: 210px" />
              <col style="width: 106px" />
              <col style="width: 80px" />
              <col style="width: 52px" />
              <col style="width: 50px" />
              <col style="width: 70px" />
              <col style="width: 62px" />
              <col />
            </colgroup>
            <thead>
              <tr>
                <th>类别</th>
                <th>指标</th>
                <th class="num">数值</th>
                <th class="num">变化</th>
                <th>方向</th>
                <th class="num">权重</th>
                <th class="num">贡献</th>
                <th>信号</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="factor in sortedFactors"
                :key="factor.code"
                :class="{ 'row-off': !factor.available }"
              >
                <td class="dim cat-cell">{{ factor.category_label }}</td>
                <td class="name-cell">
                  <span class="nm" :title="`${factor.name}（${factor.code}）`">{{ factor.name }}</span>
                  <button v-if="factor.manual" class="link-btn entry-link" type="button" @click="openEntry(factor)">
                    录入
                  </button>
                </td>
                <td class="num">{{ factor.available ? factorValueText(factor) : "—" }}</td>
                <td class="num" :class="factor.available ? trendClass(factor.change) : 'dim'">
                  {{ factor.available ? fmtPct(factor.change) : "—" }}
                </td>
                <td class="dir-cell">{{ factor.direction >= 0 ? "↑ 正向" : "↓ 逆向" }}</td>
                <td class="num dim">{{ factor.weight }}</td>
                <td class="num" :class="factor.available ? trendClass(factor.contribution) : 'dim'">
                  {{ factor.available ? fmtSigned(factor.contribution, 2) : "—" }}
                </td>
                <td>
                  <span class="badge badge--sm" :class="signalClass(factor.signal)">{{ signalLabel(factor.signal) }}</span>
                </td>
                <td class="note-cell" :title="factor.available ? factor.explain || factor.note : factor.note">
                  {{ factor.available ? factor.explain || factor.note : factor.note }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="card-foot">
          <svg class="ic"><use href="#i-info" /></svg>
          <span>
            数值为最新观测，变化为近 30 日（月/季频为环比）变动；方向为因子对金价的正/逆向作用，
            贡献为评分分值。CFTC 分类持仓为公开代理指标。
          </span>
        </div>
      </section>

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
              <button class="link-btn entry-link" type="button" @click="openEntry(item)">
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

      <!-- 方法论 -->
      <div class="sec-row">
        <span class="sec-title">方法论与局限</span>
        <span class="sec-meta">综合评分为多因子加权代理，不构成投资建议</span>
      </div>
      <section class="card method-card">
        <div class="card-head">
          <svg class="ic group-ic"><use href="#i-book" /></svg>
          <span class="card-title">评分方法论</span>
          <div class="card-actions"><span class="card-sub">{{ factors.length }} 项因子 · 权重合计 {{ fmtNumber(totalWeight, 0) }}</span></div>
        </div>
        <div class="card-body method-body">
          <p class="method-text">{{ methodology }}</p>
          <div class="limits">
            <span class="limits-title">局限</span>
            <ul>
              <li>CFTC 分类持仓（管理基金 / 掉期商）与银行参与报告是公开可得的最佳代理指标，不等同于摩根大通、汇丰等个体做市商账簿。</li>
              <li>BIS 不公布可机读的黄金掉期/存储序列，这两项默认权重 0、不参与评分；黄金租赁利率以上金所「黄金租借基准费率 3M」替代（人民币口径）。</li>
              <li>COMEX 库存来自 MetalCharts 免费 CSV 镜像（周频、需署名 metalcharts.org）；上金所不公布库存，以上期所黄金仓单代理。</li>
              <li>中国官方黄金储备为美元计价，已通过「储备变动 − 金价变动」剔除金价重估影响，得到购金代理值。</li>
            </ul>
          </div>
        </div>
        <div class="card-foot">
          <svg class="ic"><use href="#i-info" /></svg>
          <span>数据截至 {{ earliestFactorAsOf }}（各因子里最早的观测日）· 覆盖率 {{ fmtNumber(coverage, 1) }}% · 评分区间 −100（强空）~ +100（强多）。</span>
        </div>
      </section>
    </template>

    <!-- 手动指标录入弹层 -->
    <Drawer :open="entry.open" title="录入手动指标" :sub="entry.code" @close="closeEntry()">
      <template #icon>
        <svg class="ic" style="color: var(--accent)"><use href="#i-plus" /></svg>
      </template>
      <div class="entry-intro">
        <b>{{ entry.name }}</b>
        <span>{{ entry.unit }} · {{ freqLabel(entry.freq) }} · 来源 {{ entry.manualSource }}</span>
      </div>
      <label class="entry-label" for="gold-entry-value">数值（{{ entry.unit || "—" }}）</label>
      <input
        id="gold-entry-value"
        v-model="entry.value"
        class="entry-input"
        type="number"
        step="any"
        placeholder="请输入数值，支持小数"
        @keyup.enter="submitEntry()"
      />
      <label class="entry-label" for="gold-entry-date">数据日期</label>
      <input id="gold-entry-date" v-model="entry.asOf" class="entry-input" type="date" />
      <label class="entry-label" for="gold-entry-note">备注（可选）</label>
      <input
        id="gold-entry-note"
        v-model="entry.note"
        class="entry-input"
        type="text"
        maxlength="200"
        placeholder="数据来源 / 口径说明"
      />
      <div class="entry-tip">
        <svg class="ic"><use href="#i-info" /></svg>
        <span>仅标记为 manual 的指标允许手动写入；保存后自动刷新评分与覆盖率。</span>
      </div>
      <p v-if="entry.noteTip" class="entry-hint">{{ entry.noteTip }}</p>
      <template #footer>
        <button class="btn btn--sm btn--ghost" type="button" @click="closeEntry()">取消</button>
        <span class="spacer"></span>
        <button
          class="btn btn--sm btn--primary"
          type="button"
          :disabled="entry.saving || !entry.value"
          @click="submitEntry()"
        >
          {{ entry.saving ? "保存中…" : "保存并刷新" }}
        </button>
      </template>
    </Drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import type { EChartsOption } from "echarts";
import EChart from "@/components/charts/EChart.vue";
import Drawer from "@/components/ui/Drawer.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import {
  fmtDate,
  fmtDateTime,
  fmtInt,
  fmtMacro,
  fmtNumber,
  fmtPct,
  fmtSigned,
  fmtTime,
  trendClass,
} from "@/composables/useFormat";
import { getGoldOverview, refreshGold, saveGoldMetric } from "@/api/endpoints";
import type { GoldFactor, GoldScore } from "@/api/types";
import { HISTORY_RANGES, cutByRange, type HistoryRange } from "@/stores/history";
import { usePrefsStore } from "@/stores/prefs";
import { useToast } from "@/stores/toast";

/* ---------- 常量映射 ---------- */
const SIGNAL_LABELS: Record<string, string> = {
  bullish: "利多",
  bearish: "利空",
  neutral: "中性",
  unavailable: "待接入",
};
const SIGNAL_BADGES: Record<string, string> = {
  bullish: "badge--up",
  bearish: "badge--down",
  neutral: "",
  unavailable: "",
};
const GROUP_ICONS: Record<string, string> = {
  central_bank: "#i-shield-check",
  etf: "#i-layers",
  lease: "#i-rates",
  inventory: "#i-db",
  market_maker: "#i-users",
  price: "#i-chart",
};
const PROVIDER_LABELS: Record<string, string> = {
  lbma: "LBMA 伦敦金库",
  wgc_etf: "WGC 全球 ETF",
  wgc_cbd: "WGC 全球央行储备",
  cftc: "CFTC COT",
  cftc_bpr: "CFTC 银行参与报告",
  sge_lease: "上金所黄金租借费率",
  metalcharts: "MetalCharts · COMEX 库存",
  shfe_stock: "上期所黄金仓单",
  eastmoney: "东方财富 · 中国央行",
  derived: "本地派生",
};
const FREQ_LABELS: Record<string, string> = { d: "日频", w: "周频", m: "月频", q: "季频" };

const prefs = usePrefsStore();
const toast = useToast();

/* ---------- 取数 ---------- */
const { data: overview, error, loading, lastUpdated, refresh } = usePolling(getGoldOverview, {
  interval: 60000,
});

const score = computed<GoldScore | null>(() => overview.value?.score ?? null);
const factors = computed<GoldFactor[]>(() => overview.value?.score.factors ?? []);
const providers = computed(() => overview.value?.providers ?? []);
const manual = computed(() => overview.value?.manual ?? []);
const categories = computed(() => overview.value?.score.categories ?? []);

const scoreValue = computed(() => score.value?.score ?? 0);
const scoreLabel = computed(() => score.value?.label ?? "—");
const coverage = computed(() => score.value?.coverage ?? 0);
const availableWeight = computed(() => score.value?.available_weight ?? 0);
const totalWeight = computed(() => score.value?.total_weight ?? 0);
const generatedAt = computed(() => score.value?.generated_at ?? overview.value?.generated_at ?? null);
const methodology = computed(() => score.value?.methodology ?? "—");

const generatedLabel = computed(() => (generatedAt.value ? fmtDateTime(generatedAt.value) : "—"));

/** 各频率因子的「过旧」阈值（天）：日频 5、周频 12、月频 50、季频 130 */
const STALE_DAYS: Record<string, number> = { d: 5, w: 12, m: 50, q: 130 };

/** 距今天数：按自然日取 UTC 差值，避免时区与夏令时造成 ±1 天误差 */
function daysSince(date: string | null | undefined): number | null {
  if (!date) return null;
  const target = new Date(date);
  if (Number.isNaN(target.getTime())) return null;
  const now = new Date();
  const from = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate());
  const to = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((to - from) / 86400000);
}

function factorAsOfText(factor: GoldFactor): string {
  if (!factor.as_of) return "—";
  const days = daysSince(factor.as_of) ?? 0;
  const day = fmtDate(factor.as_of).slice(5);
  return days <= 0 ? `${day} 当日` : `${day}·${days}天`;
}

function isFactorStale(factor: GoldFactor): boolean {
  const days = daysSince(factor.as_of);
  if (days === null) return false;
  return days > (STALE_DAYS[(factor.freq || "d").toLowerCase()] ?? 7);
}

/** 展示口径：各可用因子里最早的观测日（而非评分生成时间），避免用「刚算过」掩盖「数据很旧」 */
const earliestFactorAsOf = computed(() => {
  const dates = factors.value.filter((factor) => factor.available && factor.as_of).map((factor) => factor.as_of as string);
  if (!dates.length) return generatedLabel.value;
  const earliest = dates.reduce((min, current) => (current < min ? current : min), dates[0]);
  return fmtDate(earliest);
});
const updatedLabel = computed(() => (lastUpdated.value ? fmtTime(lastUpdated.value.toISOString(), true) : "—"));
const scoreTrend = computed<"up" | "down" | "flat">(() => {
  const value = scoreValue.value;
  if (Math.abs(value) < 10) return "flat";
  return value > 0 ? "up" : "down";
});
const scoreBadgeClass = computed(() => {
  if (scoreLabel.value.includes("多")) return "badge--up";
  if (scoreLabel.value.includes("空")) return "badge--down";
  return "";
});
const gaugeOffset = computed(() => {
  const percent = Math.max(0, Math.min(100, (scoreValue.value + 100) / 2));
  return (100 - percent).toFixed(1);
});
const coveragePct = computed(() => Math.max(0, Math.min(100, coverage.value)));
const availableFactorCount = computed(() => factors.value.filter((item) => item.available).length);
const pendingCount = computed(() => factors.value.filter((item) => !item.available).length);
const pendingManualCount = computed(
  () => manual.value.filter((item) => item.weight > 0 && !item.available).length,
);
const okCount = computed(() => providers.value.filter((item) => item.ok).length);
const providerCheckedLabel = computed(() => {
  const times = providers.value
    .map((item) => item.checked_at)
    .filter((item): item is string => Boolean(item))
    .sort();
  if (!times.length) return "—";
  return fmtDateTime(providerTime(times[times.length - 1]));
});
const seriesCount = computed(() => {
  const series = overview.value?.series;
  if (!series) return 0;
  return Object.values(series).filter((points) => Array.isArray(points) && points.length > 0).length;
});

const methodologyBrief = computed(() => {
  const text = methodology.value.trim();
  if (!text) return "—";
  const first = text.indexOf("。");
  if (first < 0) return text;
  const second = text.indexOf("。", first + 1);
  const end = second < 0 ? first : second;
  return `${text.slice(0, end + 1)}${end < text.length - 1 ? "…" : ""}`;
});
const coverageNote = computed(
  () =>
    `当前 ${availableFactorCount.value} / ${factors.value.length} 项因子可用，覆盖率 ${fmtNumber(
      coverage.value,
      1,
    )}%；未采集因子不参与评分（可用权重 ${fmtNumber(availableWeight.value, 0)} / ${fmtNumber(
      totalWeight.value,
      0,
    )}）。`,
);

/* ---------- 因子分组 / 明细 ---------- */
interface GroupView {
  key: string;
  label: string;
  icon: string;
  factors: GoldFactor[];
  contribution: number;
  available: number;
}

const sortedFactors = computed(() =>
  [...factors.value].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)),
);
const topDrivers = computed(() => sortedFactors.value.filter((item) => item.available).slice(0, 5));

const groups = computed<GroupView[]>(() => {
  const order = categories.value.length
    ? categories.value.map((item) => ({ key: item.key, label: item.label }))
    : Array.from(
        new Map(factors.value.map((item) => [item.category, item.category_label])).entries(),
      ).map(([key, label]) => ({ key, label }));
  return order
    .map((item) => {
      const items = factors.value.filter((factor) => factor.category === item.key);
      return {
        key: item.key,
        label: item.label,
        icon: GROUP_ICONS[item.key] ?? "#i-dot-list",
        factors: items,
        contribution: items.reduce((sum, factor) => sum + factor.contribution, 0),
        available: items.filter((factor) => factor.available).length,
      };
    })
    .filter((item) => item.factors.length > 0);
});

const conclusionText = computed(() => {
  const drivers = topDrivers.value;
  if (!drivers.length) return "暂无可用的关键因子，等待采集任务写入数据。";
  const bullish = drivers.filter((item) => item.contribution > 0.05).map((item) => item.name);
  const bearish = drivers.filter((item) => item.contribution < -0.05).map((item) => item.name);
  const parts: string[] = [];
  if (bullish.length) parts.push(`${bullish.join("、")}偏多`);
  if (bearish.length) parts.push(`${bearish.join("、")}偏空`);
  const head = parts.length ? parts.join("；") : "多空因子势均力敌";
  return `${head}，综合判断「${scoreLabel.value}」（${fmtSigned(scoreValue.value, 1)} / 100）。`;
});

/* ---------- 格式化 ---------- */
function signalLabel(signal: string): string {
  return SIGNAL_LABELS[signal] ?? signal ?? "—";
}
function signalClass(signal: string): string {
  return SIGNAL_BADGES[signal] ?? "";
}
function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}
function freqLabel(freq: string): string {
  return FREQ_LABELS[freq] ?? freq ?? "—";
}
function factorDigits(value: number): number {
  const abs = Math.abs(value);
  if (abs >= 10000) return 0;
  if (abs >= 1000) return 1;
  return 2;
}
function factorValueText(factor: GoldFactor): string {
  if (factor.value === null || !Number.isFinite(factor.value)) return "—";
  return fmtMacro(factor.value, factor.unit, factorDigits(factor.value));
}
/** provider.checked_at 后端为无时区 UTC（如 2026-11-14T14:32:52），补 Z 后再格式化。 */
function providerTime(iso: string | null): string | null {
  if (!iso) return null;
  if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(iso)) return iso;
  return `${iso}Z`;
}

/* ---------- 手动录入 ---------- */
interface ManualTarget {
  code: string;
  name: string;
  unit: string;
  freq: string;
  note: string;
  weight?: number;
  source?: string;
}
interface EntryState {
  open: boolean;
  code: string;
  name: string;
  unit: string;
  freq: string;
  manualSource: string;
  value: string;
  asOf: string;
  note: string;
  noteTip: string;
  saving: boolean;
}

function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

const entry = reactive<EntryState>({
  open: false,
  code: "",
  name: "",
  unit: "",
  freq: "",
  manualSource: "",
  value: "",
  asOf: todayIso(),
  note: "",
  noteTip: "",
  saving: false,
});

function openEntry(target: ManualTarget): void {
  const current = factors.value.find((factor) => factor.code === target.code);
  entry.open = true;
  entry.code = target.code;
  entry.name = target.name;
  entry.unit = target.unit;
  entry.freq = target.freq;
  entry.manualSource = target.source ?? "手动录入";
  entry.value = current?.value === null || current?.value === undefined ? "" : String(current.value);
  entry.asOf = current?.as_of ? fmtDate(current.as_of) : todayIso();
  entry.note = "";
  entry.noteTip = current?.note ?? target.note ?? "";
}

function closeEntry(): void {
  entry.open = false;
  entry.saving = false;
}

async function submitEntry(): Promise<void> {
  if (entry.saving) return;
  const value = Number(entry.value);
  if (!entry.value || !Number.isFinite(value)) {
    toast.warn("请输入有效数值");
    return;
  }
  entry.saving = true;
  try {
    await saveGoldMetric({
      code: entry.code,
      value,
      as_of: entry.asOf || undefined,
      note: entry.note || undefined,
    });
    toast.ok(`已保存「${entry.name}」`);
    closeEntry();
    await refresh();
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : "保存失败");
  } finally {
    entry.saving = false;
  }
}

/* ---------- 刷新（异步采集） ---------- */
const collecting = ref(false);
let collectTimer: number | null = null;

async function triggerRefresh(): Promise<void> {
  if (collecting.value) return;
  collecting.value = true;
  try {
    await refreshGold();
    toast.info("已触发采集，约 1 分钟后刷新");
    if (collectTimer !== null) window.clearTimeout(collectTimer);
    collectTimer = window.setTimeout(() => {
      collectTimer = null;
      void refresh();
    }, 65000);
  } catch (err) {
    toast.bad(err instanceof Error ? err.message : "触发采集失败");
  } finally {
    collecting.value = false;
  }
}

onBeforeUnmount(() => {
  if (collectTimer !== null) {
    window.clearTimeout(collectTimer);
    collectTimer = null;
  }
});

/* ---------- ECharts（颜色从 CSS 变量计算，参考 HistoryModal） ---------- */
function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

const palette = computed(() => {
  // 显式依赖主题与涨跌配色，切换后图表重算
  void prefs.resolvedTheme;
  void prefs.updown;
  const upRaw = cssVar("--up", "#F0544F");
  const downRaw = cssVar("--down", "#2FBF71");
  return {
    up: prefs.updown === "green" ? downRaw : upRaw,
    down: prefs.updown === "green" ? upRaw : downRaw,
    muted: cssVar("--muted", "#93A4B8"),
    border: cssVar("--border", "rgba(148,163,184,.22)"),
    surface: cssVar("--surface", "#111721"),
    text: cssVar("--text", "#E6EDF5"),
    accent: cssVar("--accent", "#4CC2FF"),
    warn: cssVar("--warn", "#F5A524"),
    gold: cssVar("--gold", "#E7B84B"),
  };
});

interface SeriesSpec {
  code: string;
  label: string;
  color: string;
  axis?: number;
  format: (value: number) => string;
}
interface AxisSpec {
  format: (value: number) => string;
}
interface ChartCard {
  key: string;
  title: string;
  unit: string;
  wide?: boolean;
  height: number;
  codes: string[];
  legend: Array<{ label: string; cls: string; available: boolean }>;
  note: string;
  emptyText: string;
  emptyHint: string;
  option: EChartsOption;
}

/** 图表时间范围：选项与默认值与资产标的价格趋势图（HistoryModal）完全一致。 */
const chartRange = ref<HistoryRange>("1y");
/** 每张图表是否叠加伦敦金价（默认关闭，按图表单独开关）。 */
const priceOverlays = reactive<Record<string, boolean>>({});
const GOLD_PRICE_LABEL = "伦敦金价";

function seriesPoints(code: string): Array<{ t: number; v: number }> {
  const raw = overview.value?.series?.[code] ?? [];
  const points: Array<{ t: number; v: number }> = [];
  for (const point of raw) {
    const time = new Date(point.t).getTime();
    if (Number.isFinite(time) && Number.isFinite(point.v)) points.push({ t: time, v: point.v });
  }
  return cutByRange(points.sort((a, b) => a.t - b.t), chartRange.value);
}

function togglePriceOverlay(key: string): void {
  priceOverlays[key] = !priceOverlays[key];
}

function setChartRange(next: HistoryRange): void {
  chartRange.value = next;
}

function buildChartOption(specs: SeriesSpec[], axes: AxisSpec[], zeroLine = false): EChartsOption {
  const colors = palette.value;
  const formatters = new Map<string, (value: number) => string>();
  const series = specs.map((spec) => {
    formatters.set(spec.label, spec.format);
    const points = seriesPoints(spec.code);
    const singleAxis = spec.axis === undefined;
    return {
      name: spec.label,
      type: "line" as const,
      yAxisIndex: spec.axis ?? 0,
      data: points.map((point) => [point.t, point.v]),
      showSymbol: points.length <= 2,
      symbolSize: 5,
      connectNulls: true,
      lineStyle: { color: spec.color, width: 1.7 },
      itemStyle: { color: spec.color },
      areaStyle: singleAxis ? { color: spec.color, opacity: 0.07 } : undefined,
      markLine:
        zeroLine && singleAxis
          ? {
              silent: true,
              symbol: "none" as const,
              label: { show: false },
              lineStyle: { color: colors.border, type: "dashed" as const },
              data: [{ yAxis: 0 }],
            }
          : undefined,
    };
  });
  return {
    animationDuration: 350,
    grid: { left: 48, right: axes.length > 1 ? 46 : 16, top: 14, bottom: 26 },
    tooltip: {
      trigger: "axis",
      backgroundColor: colors.surface,
      borderColor: colors.border,
      textStyle: { color: colors.text, fontSize: 11 },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? (params as unknown[]) : [params];
        if (!list.length) return "";
        const first = list[0] as { axisValue?: number | string } | undefined;
        const time = Number(first?.axisValue);
        const lines: string[] = [];
        if (Number.isFinite(time)) lines.push(fmtDate(new Date(time).toISOString()));
        for (const raw of list) {
          const item = raw as { seriesName?: string; value?: unknown; marker?: string };
          const pair = Array.isArray(item.value) ? (item.value as [number, number]) : null;
          const value = pair ? Number(pair[1]) : Number(item.value);
          const format = formatters.get(item.seriesName ?? "") ?? ((input: number) => fmtNumber(input, 2));
          lines.push(`${item.marker ?? ""}${item.seriesName ?? ""} ${format(value)}`);
        }
        return lines.join("<br/>");
      },
    },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { show: false },
      axisLabel: { color: colors.muted, fontSize: 9, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: axes.map((axis) => ({
      type: "value",
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: colors.border, opacity: 0.55 } },
      axisLabel: { color: colors.muted, fontSize: 9, formatter: (value: number) => axis.format(value) },
    })),
    series,
  } as EChartsOption;
}

const contractsAxis = (value: number): string => {
  if (Math.abs(value) >= 1000) return `${Math.round(value / 1000)}k`;
  return fmtNumber(value, 0);
};

const chartCards = computed<ChartCard[]>(() => {
  const colors = palette.value;
  const swapAvailable = seriesPoints("COT_SWAP_NET").length > 0;
  const priceAvailable = seriesPoints("GOLD_PRICE_USD").length > 0;
  const priceSpec = (axis: number): SeriesSpec => ({
    code: "GOLD_PRICE_USD",
    label: GOLD_PRICE_LABEL,
    color: colors.gold,
    axis,
    format: (value) => `${fmtNumber(value, 1)} 美元/盎司`,
  });
  const priceLegend = { label: GOLD_PRICE_LABEL, cls: "lg-g", available: priceAvailable };
  const cardCodes = (key: string, base: string[]): string[] =>
    priceOverlays[key] ? [...base, "GOLD_PRICE_USD"] : base;
  const cardLegend = (
    key: string,
    base: Array<{ label: string; cls: string; available: boolean }>,
  ): Array<{ label: string; cls: string; available: boolean }> =>
    priceOverlays[key] ? [...base, priceLegend] : base;
  const cardOption = (
    key: string,
    specs: SeriesSpec[],
    axes: AxisSpec[],
    zeroLine = false,
  ): EChartsOption => {
    if (!priceOverlays[key]) return buildChartOption(specs, axes, zeroLine);
    return buildChartOption(
      [...specs, priceSpec(axes.length)],
      [...axes, { format: (value) => fmtNumber(value, 0) }],
      zeroLine,
    );
  };
  return [
    {
      key: "price-real",
      title: "美债 10Y 实际利率",
      unit: "%",
      wide: true,
      height: 250,
      codes: cardCodes("price-real", ["US10Y_REAL"]),
      legend: cardLegend("price-real", [{ label: "10Y 实际利率", cls: "lg-a", available: true }]),
      note: priceOverlays["price-real"] ? "" : "可叠加金价对比",
      emptyText: "暂无实际利率序列",
      emptyHint: "等待黄金采集任务写入利率数据，或切换更长的时间范围。",
      option: cardOption(
        "price-real",
        [
          {
            code: "US10Y_REAL",
            label: "10Y 实际利率",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 2)}%`,
          },
        ],
        [{ format: (value) => `${fmtNumber(value, 1)}%` }],
      ),
    },
    {
      key: "etf-tonnes",
      title: "全球黄金 ETF 持仓",
      unit: "吨",
      height: 230,
      codes: cardCodes("etf-tonnes", ["ETF_GLOBAL_TONNES"]),
      legend: cardLegend("etf-tonnes", [{ label: "ETF 持仓", cls: "lg-a", available: true }]),
      note: "",
      emptyText: "暂无 ETF 持仓序列",
      emptyHint: "WGC 全球黄金 ETF 数据未采集，或当前时间范围无数据。",
      option: cardOption(
        "etf-tonnes",
        [
          {
            code: "ETF_GLOBAL_TONNES",
            label: "ETF 持仓",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 0)} 吨`,
          },
        ],
        [{ format: (value) => fmtNumber(value, 0) }],
      ),
    },
    {
      key: "lbma-tonnes",
      title: "伦敦金库黄金库存",
      unit: "吨",
      height: 230,
      codes: cardCodes("lbma-tonnes", ["LBMA_GOLD_TONNES"]),
      legend: cardLegend("lbma-tonnes", [{ label: "金库库存", cls: "lg-a", available: true }]),
      note: "",
      emptyText: "暂无伦敦金库库存序列",
      emptyHint: "LBMA 月度库存数据未采集，或当前时间范围无数据。",
      option: cardOption(
        "lbma-tonnes",
        [
          {
            code: "LBMA_GOLD_TONNES",
            label: "金库库存",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 0)} 吨`,
          },
        ],
        [{ format: (value) => fmtNumber(value, 0) }],
      ),
    },
    {
      key: "cftc-net",
      title: "CFTC 持仓（管理基金 / 掉期商）",
      unit: "张",
      height: 230,
      codes: cardCodes("cftc-net", ["COT_MONEY_NET", "COT_SWAP_NET"]),
      legend: cardLegend("cftc-net", [
        { label: "管理基金净持仓", cls: "lg-a", available: true },
        { label: "掉期商净持仓", cls: "lg-m", available: swapAvailable },
      ]),
      note: swapAvailable ? "" : "掉期商序列缺失",
      emptyText: "暂无 CFTC 持仓序列",
      emptyHint: "等待 CFTC COT 采集写入数据，或当前时间范围无数据。",
      option: cardOption(
        "cftc-net",
        [
          {
            code: "COT_MONEY_NET",
            label: "管理基金净持仓",
            color: colors.accent,
            format: (value) => `${fmtInt(value)} 张`,
          },
          {
            code: "COT_SWAP_NET",
            label: "掉期商净持仓",
            color: colors.muted,
            format: (value) => `${fmtInt(value)} 张`,
          },
        ],
        [{ format: contractsAxis }],
        true,
      ),
    },
    {
      key: "cn-premium",
      title: "上海金溢价",
      unit: "%",
      height: 230,
      codes: cardCodes("cn-premium", ["CN_GOLD_PREMIUM_PCT"]),
      legend: cardLegend("cn-premium", [{ label: "上海金溢价", cls: "lg-a", available: true }]),
      note: "",
      emptyText: "暂无上海金溢价序列",
      emptyHint: "等待沪金与伦敦金折算价序列写入，或当前时间范围无数据。",
      option: cardOption(
        "cn-premium",
        [
          {
            code: "CN_GOLD_PREMIUM_PCT",
            label: "上海金溢价",
            color: colors.accent,
            format: (value) => `${fmtNumber(value, 2)}%`,
          },
        ],
        [{ format: (value) => `${fmtNumber(value, 2)}%` }],
        true,
      ),
    },
  ];
});

function chartHasData(chart: ChartCard): boolean {
  return chart.codes.some((code) => seriesPoints(code).length > 0);
}

function chartMeta(chart: ChartCard): string {
  const primary = seriesPoints(chart.codes[0]);
  if (!primary.length) return "暂无数据";
  const latest = Math.max(...chart.codes.flatMap((code) => seriesPoints(code).map((point) => point.t)));
  return `${primary.length} 点 · 更新 ${fmtDate(new Date(latest).toISOString())}`;
}
</script>

<style scoped>
/* ---------- 顶部评分区 ---------- */
.score-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.96fr) minmax(0, 1.04fr);
  gap: 10px;
  align-items: stretch;
  margin-bottom: 10px;
}
.score-grid > .card {
  display: flex;
  flex-direction: column;
}
.score-grid > .card > .card-body {
  flex: 1 1 auto;
}
.score-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.score-main {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: 216px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}
.gauge-col {
  min-width: 0;
}
.gauge {
  position: relative;
  width: 100%;
}
.gauge-svg {
  display: block;
  width: 100%;
  height: auto;
}
.gauge-track,
.gauge-fill {
  fill: none;
  stroke-width: 9;
  stroke-linecap: round;
}
.gauge-track {
  stroke: var(--surface-3);
}
.gauge-fill {
  transition: stroke-dashoffset 0.4s ease;
}
.gauge-fill.up {
  stroke: var(--up-color);
}
.gauge-fill.down {
  stroke: var(--down-color);
}
.gauge-fill.flat {
  stroke: var(--muted);
}
.gauge-tick {
  stroke: var(--border-strong);
  stroke-width: 1.4;
  stroke-linecap: round;
}
.gauge-zero {
  stroke: var(--dim);
}
.gauge-center {
  position: absolute;
  right: 0;
  bottom: 16px;
  left: 0;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
}
.gauge-score {
  font-family: var(--mono);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -1px;
  line-height: 1;
}
.gauge-score.up {
  color: var(--up-color);
}
.gauge-score.down {
  color: var(--down-color);
}
.gauge-score.flat {
  color: var(--text);
}
.gauge-unit {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
}
.gauge-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
  font-size: 9px;
  color: var(--dim);
}
.score-stats {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.stat-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 10.5px;
  color: var(--muted);
}
.stat-row > b {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  text-align: right;
}
.stat-row > b.up {
  color: var(--up-color);
}
.stat-row > b.down {
  color: var(--down-color);
}
.stat-row > b.flat {
  color: var(--muted);
}
.stat-time {
  font-size: 9.5px !important;
  color: var(--muted) !important;
}
.cov-bar {
  height: 4px;
  margin: 1px 0 3px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}
.cov-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
}
.method-brief {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
.mb-label {
  font-size: 9.5px;
  letter-spacing: 0.4px;
  color: var(--dim);
}
.method-brief p {
  margin-top: 3px;
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--muted);
}

/* ---------- 结论与关键驱动 ---------- */
.drivers-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.conclusion {
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text);
}
.conclusion-sub {
  font-size: 9.5px;
  line-height: 1.55;
  color: var(--dim);
}
.driver-list {
  display: grid;
  gap: 2px;
  margin-top: 2px;
}
.driver-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 60px 54px;
  align-items: center;
  gap: 8px;
  min-height: 27px;
  border-bottom: 1px dashed var(--border);
}
.driver-row:last-of-type {
  border-bottom: 0;
}
.d-name {
  min-width: 0;
  overflow: hidden;
  font-size: 11px;
  color: var(--text);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.d-value {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
  text-align: right;
  white-space: nowrap;
}
.d-contrib {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 650;
  text-align: right;
}
.driver-row .badge {
  justify-self: end;
}

/* ---------- 因子分组 ---------- */
.group-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: start;
}
.group-card {
  overflow: hidden;
}
.group-ic {
  width: 13px;
  height: 13px;
  color: var(--accent);
}
.group-contrib {
  font-family: var(--mono);
  font-weight: 650;
}
.group-body {
  padding: 2px 13px 4px;
}
.frow {
  padding: 6px 0 5px;
  border-bottom: 1px dashed var(--border);
}
.frow:last-child {
  border-bottom: 0;
}
.frow-top {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.frow-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  font-size: 11.5px;
  font-weight: 560;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.frow-top .badge {
  flex: none;
}
.frow-mid {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-top: 2px;
}
.frow-val {
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 650;
  color: var(--text);
}
.frow-chg {
  font-family: var(--mono);
  font-size: 10px;
}
.frow-chg.dim {
  color: var(--dim);
  font-family: var(--mono);
}
.frow-weight {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.frow-asof {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
}
.frow-asof--stale {
  color: var(--warn-color, #d08700);
}
.frow-contrib {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--dim);
}
.frow-contrib b {
  font-size: 10.5px;
  font-weight: 650;
}
.frow-desc {
  display: -webkit-box;
  margin-top: 2px;
  overflow: hidden;
  font-size: 9.5px;
  line-height: 1.5;
  color: var(--dim);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.frow--off .frow-name {
  color: var(--muted);
}
.frow--off .frow-val {
  color: var(--dim);
}
.entry-link {
  flex: none;
  padding: 0 2px;
}
.entry-link .ic {
  width: 10px;
  height: 10px;
}
.frow-top .entry-link {
  margin-left: 1px;
}

/* ---------- 图表 ---------- */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.chart-card {
  min-width: 0;
  overflow: hidden;
}
.chart-wide {
  grid-column: 1 / -1;
}
.chart-body {
  padding: 6px 8px 4px;
}
.chart-legend {
  display: flex;
  gap: 9px;
  min-width: 0;
  overflow: hidden;
}
.lg-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9.5px;
  color: var(--muted);
  white-space: nowrap;
}
.lg-dim {
  color: var(--dim);
}
.lg-dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 2px;
}
.lg-a {
  background: var(--accent);
}
.lg-w {
  background: var(--warn);
}
.lg-m {
  background: var(--muted);
}
.lg-g {
  background: var(--gold);
}
.lg-dim .lg-dot {
  background: var(--dim);
}
.chart-note {
  flex: none;
  font-size: 9px;
  color: var(--warn);
  white-space: nowrap;
}
/* 时间范围切换：与资产历史走势弹窗（HistoryModal）保持同一组选项与样式 */
.chart-ranges {
  display: flex;
  gap: 3px;
}
.chart-ranges button {
  height: 24px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10.5px;
  cursor: pointer;
}
.chart-ranges button:hover {
  color: var(--text);
}
.chart-ranges button.active {
  color: var(--accent);
  border-color: var(--accent-line);
  background: var(--accent-weak);
}
/* 按图表叠加伦敦金价对比 */
.chart-toggle {
  height: 22px;
  padding: 0 7px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10px;
  cursor: pointer;
  white-space: nowrap;
}
.chart-toggle:hover {
  color: var(--gold);
  border-color: color-mix(in srgb, var(--gold) 45%, var(--border));
}
.chart-toggle.active {
  color: var(--gold);
  border-color: color-mix(in srgb, var(--gold) 55%, var(--border));
  background: color-mix(in srgb, var(--gold) 14%, transparent);
}

/* ---------- 因子明细表 ---------- */
.detail-wrap {
  max-height: none;
}
.detail-table {
  table-layout: fixed;
}
.detail-table tbody td {
  font-size: 11.5px;
}
.detail-table td.cat-cell {
  font-size: 10.5px;
  color: var(--muted);
}
.detail-table .name-cell {
  overflow: hidden;
}
.detail-table .name-cell .nm {
  overflow: hidden;
  font-size: 11.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-table .name-cell .entry-link {
  margin-left: 5px;
  vertical-align: baseline;
}
.detail-table td.dir-cell {
  font-family: var(--mono);
  font-size: 9.5px;
  color: var(--dim);
}
.detail-table .note-cell {
  overflow: hidden;
  font-size: 10px;
  color: var(--dim);
  text-overflow: ellipsis;
}
.detail-table tbody tr.row-off {
  background: color-mix(in srgb, var(--surface-2) 30%, transparent);
}
.detail-table tbody tr.row-off td {
  opacity: 0.72;
}

/* ---------- 数据源 ---------- */
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

/* ---------- 方法论 ---------- */
.method-body {
  display: grid;
  gap: 10px;
}
.method-text {
  font-size: 10.5px;
  line-height: 1.7;
  color: var(--muted);
}
.limits {
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
.limits-title {
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.4px;
  color: var(--text);
}
.limits ul {
  margin: 5px 0 0;
  padding-left: 16px;
  display: grid;
  gap: 3px;
}
.limits li {
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}

/* ---------- 录入弹层 ---------- */
.entry-intro {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.entry-intro b {
  font-size: 12px;
}
.entry-intro span {
  font-size: 9.5px;
  color: var(--dim);
}
.entry-label {
  display: block;
  margin-bottom: 4px;
  font-size: 9.5px;
  color: var(--dim);
}
.entry-input {
  width: 100%;
  height: 32px;
  margin-bottom: 12px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  outline: none;
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 12px;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.entry-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-weak);
}
.entry-input::placeholder {
  color: var(--dim);
}
.entry-tip {
  display: flex;
  gap: 6px;
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
.entry-tip .ic {
  width: 11px;
  height: 11px;
  margin-top: 1px;
  flex: none;
}
.entry-hint {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}

/* ---------- 骨架 ---------- */
.skeleton-block {
  margin-top: 10px;
}

/* 卡片脚注图标统一尺寸（避免 SVG 默认 300×150 撑开布局） */
.card-foot .ic {
  width: 11px;
  height: 11px;
  flex: none;
}

/* ---------- 响应式 ---------- */
@media (max-width: 1360px) {
  .score-grid {
    grid-template-columns: 1fr;
  }
  .group-grid {
    grid-template-columns: 1fr;
  }
  .charts-grid {
    grid-template-columns: 1fr;
  }
  .chart-wide {
    grid-column: auto;
  }
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
