<template>
  <div class="view active cyc-root">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">研究分析 · 周期定位 · EPIC-C 2.0</div>
        <h1 class="page-h1">
          周期罗盘
          <span class="page-sub">五层周期 · 长债务 / 短债务 / 库存 / 流动性 / 政治窗口 —— 先定位，再判断</span>
        </h1>
      </div>
      <div class="page-actions">
        <RouterLink class="btn btn--sm btn--ghost" to="/analysis#cycle-regime">市场隐含象限</RouterLink>
        <RouterLink class="btn btn--sm btn--ghost" to="/history">世界长河</RouterLink>
        <RouterLink class="btn btn--sm btn--ghost" to="/alerts">周期规则预警</RouterLink>
        <span v-if="payload?.asof" class="badge badge--sm">数据日 {{ fmtDate(payload.asof) }}</span>
        <span v-if="payload?.status" class="badge badge--sm" :class="runTone(payload.status)">
          {{ runText(payload.status) }}
        </span>
        <button class="btn btn--sm" type="button" :disabled="running" @click="recalc">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中…" : "立即重算" }}
        </button>
      </div>
    </div>

    <p v-if="payload?.generated_at" class="cyc-generated">生成于 {{ generatedLabel }}</p>

    <p v-if="recalcError" class="cyc-inline-error">
      <svg class="ic"><use href="#i-alert" /></svg>
      <span>重算失败：{{ recalcError }}</span>
      <button class="btn btn--ghost btn--sm" type="button" :disabled="running" @click="recalc">重试</button>
    </p>

    <p v-if="error && payload" class="cyc-inline-error">
      <svg class="ic"><use href="#i-alert" /></svg>
      <span>自动刷新失败：{{ error.message }}；当前展示上一次成功的数据。</span>
      <button class="btn btn--ghost btn--sm" type="button" @click="refresh()">重试</button>
    </p>

    <SkeletonBlock v-if="!payload && loading" :rows="6" :cells="3" :height="16" />
    <ErrorState v-else-if="!payload && error" :error="error" @retry="refresh" />
    <EmptyState v-else-if="!payload" text="暂无周期状态" hint="请先运行一次周期引擎，再查看周期罗盘。" />

    <template v-else-if="value">
      <!-- A. Hero：长债务周期定位 -->
      <section class="cyc-hero">
        <div class="cyc-hero-main">
          <div class="cyc-hero-eyebrow">周期定位 · 美国 / 全球长周期</div>
          <h1 class="cyc-hero-h1">{{ heroTitle }}</h1>
          <p class="cyc-hero-sub">{{ heroSub }}</p>
          <div class="cyc-hero-tags">
            <span v-for="tag in heroTags" :key="tag.key" class="cyc-tag">
              <i class="cyc-tag-dot"></i>
              <span>{{ tag.label }}</span>
              <b>{{ tag.value }}</b>
              <span v-if="tag.z !== null" class="cyc-tag-z">z {{ fmtSigned(tag.z, 1) }}</span>
            </span>
          </div>
        </div>
        <div class="cyc-hero-badges">
          <div class="cyc-meta-badge">
            <span>数据覆盖</span>
            <b>{{ coverageText }}</b>
          </div>
          <div class="cyc-meta-badge">
            <span>规则版本</span>
            <b>{{ ruleVersion }}</b>
          </div>
          <div class="cyc-meta-badge">
            <span>下次校准</span>
            <b>{{ nextCalibration }}</b>
          </div>
        </div>
      </section>

      <!-- B. 周期罗盘 + 五力仪表 -->
      <div class="cyc-row2">
        <CycleCompass
          :growth="compassGrowth"
          :inflation="compassInflation"
          :state="short.state"
          :confidence="longConfidencePct"
        />
        <CycleForces :forces="forces" :stress-count="stressCount" />
      </div>

      <!-- C. 关键读数：直连 /api/v2/cycle/readings（缺失 showReason，不填占位值） -->
      <div class="cyc-section-label">
        <span class="cyc-sl-title">关键读数</span>
        <span>
          均为北京时间 {{ readingsAsof || asofLabel }} · z = 相对 5 年 z-score ·
          {{ readingItems.length ? `${readingItems.length - missingReadings} / ${readingItems.length} 项可用` : "读数待加载" }}
        </span>
      </div>
      <div v-if="readingsUnavailable" class="card cyc-readings-fallback">
        <span class="badge badge--sm badge--warn">读数接口不可用</span>
        <span class="cyc-readings-fallback-text">
          {{ readingsErrorText }}；其余区块照常展示。
        </span>
        <button class="btn btn--ghost btn--sm" type="button" @click="readingsPoll.refresh()">重试</button>
      </div>
      <SkeletonBlock v-else-if="!readingItems.length && readingsPoll.loading.value" :rows="2" :cells="4" :height="80" />
      <EmptyState
        v-else-if="!readingItems.length"
        text="暂无关键读数"
        hint="/api/v2/cycle/readings 未返回任何读数。"
      />
      <div v-else class="cyc-kpi-grid">
        <div
          v-for="kpi in kpis"
          :key="kpi.id"
          class="cyc-kpi-card"
          :title="kpi.tooltip"
        >
          <div class="cyc-kpi-top">
            <span class="cyc-kpi-label">{{ kpi.label }}</span>
            <span class="cyc-kpi-z" :class="kpi.zClass">
              {{ kpi.z === null ? "z —" : `z ${fmtSigned(kpi.z, 1)}` }}
            </span>
          </div>
          <div class="cyc-kpi-val">
            <b>{{ kpi.value }}</b>
            <span v-if="kpi.unit && !kpi.missing" class="cyc-kpi-unit">{{ kpi.unit }}</span>
            <span v-if="kpi.missing" class="cyc-kpi-miss">数据缺失</span>
            <span v-if="kpi.deltaText" class="cyc-kpi-chg" :class="`cyc-kpi-chg--${kpi.deltaClass}`">
              {{ kpi.deltaText }}
            </span>
          </div>
          <div class="cyc-kpi-foot">
            <svg
              v-if="kpi.spark"
              class="cyc-spark"
              viewBox="0 0 120 24"
              preserveAspectRatio="none"
              role="img"
              :aria-label="`${kpi.label} 近 30 个观测走势`"
            >
              <polyline
                :points="kpi.spark"
                fill="none"
                :stroke="kpi.sparkColor"
                stroke-width="1.4"
                stroke-linejoin="round"
                stroke-linecap="round"
              />
            </svg>
            <span v-else class="cyc-kpi-note">{{ kpi.missing ? (kpi.reason ?? "数据缺失") : kpi.source ?? "—" }}</span>
            <RouterLink
              class="cyc-kpi-ev"
              :to="{ path: '/pipeline', query: { code: 'cycle.state.world' } }"
              :title="kpi.tooltip"
            >
              {{ kpi.evidence }} 证据
            </RouterLink>
          </div>
        </div>
      </div>

      <!-- D. 今日预警 -->
      <section class="card cyc-alerts">
        <div class="card-head">
          <span class="card-title">
            今日预警
            <span class="badge badge--up badge--sm">{{ alertCount }} 条</span>
          </span>
          <span class="cyc-card-sub">生成于 {{ generatedLabel }}</span>
          <div class="card-actions">
            <RouterLink class="btn btn--ghost btn--sm" to="/alerts">全部 ›</RouterLink>
          </div>
        </div>
        <div v-if="topAlerts.length" class="cyc-alert-list">
          <div v-for="alert in topAlerts" :key="alert.id" class="cyc-alert-row">
            <span class="cyc-sev" :class="`cyc-sev--${sevClass(alert.severity)}`">
              <i></i>{{ sevLabel(alert.severity) }}
            </span>
            <div class="cyc-alert-main">
              <div class="cyc-alert-title">{{ alert.name ?? alert.metric_name ?? "未命名预警" }}</div>
              <div class="cyc-alert-cond" :title="alert.why ?? ''">{{ alert.why ?? "—" }}</div>
            </div>
            <div class="cyc-alert-val">
              <b>{{ alertValue(alert) }}</b>
              <span>{{ alertThreshold(alert) }}</span>
            </div>
            <div class="cyc-alert-meta">{{ alertAsOf(alert) }}</div>
            <RouterLink class="btn btn--ghost btn--sm cyc-alert-src" to="/alerts">溯源</RouterLink>
          </div>
        </div>
        <EmptyState v-else text="今日无触发预警" hint="规则均未达到阈值；全部预警可在预警中心查看。" />
      </section>

      <!-- E. 历史类比 Top3 -->
      <div class="cyc-section-label">
        <span class="cyc-sl-title">历史类比 Top3</span>
        <span>
          {{
            analogs
              ? `${analogs.n ?? 0} 个样本内近邻 · 剔除最近 ${analogs.min_gap_months ?? 12} 个月`
              : "样本内近邻"
          }}
        </span>
      </div>
      <div v-if="topAnalogs.length" class="cyc-analogy-row">
        <template v-for="(item, index) in analogSlots" :key="item?.month ?? `empty-${index}`">
          <RouterLink
            v-if="item"
            class="cyc-analogy"
            :to="{ path: '/pipeline', query: { code: 'cycle.analogs' } }"
          >
            <div>
              <div class="cyc-analogy-name">{{ item.month }}</div>
              <div class="cyc-analogy-sub">
                增长 {{ fmtNumber(item.state?.growth, 0) }} · 通胀 {{ fmtNumber(item.state?.inflation, 0) }}
              </div>
            </div>
            <div class="cyc-analogy-sim">
              <b>{{ ratioText(item.similarity) }}</b>
              <span>相似度</span>
            </div>
          </RouterLink>
          <div v-else class="cyc-analogy cyc-analogy--empty">
            <div>
              <div class="cyc-analogy-name">暂无更多类比</div>
              <div class="cyc-analogy-sub">样本内近邻不足 3 条</div>
            </div>
            <div class="cyc-analogy-sim"><b>—</b><span>相似度</span></div>
          </div>
        </template>
      </div>
      <EmptyState v-else text="暂无历史类比" hint="样本不足 24 个月时不会生成类比。" />
      <p v-if="Array.isArray(analogs?.caveats) && analogs.caveats.length" class="cyc-caveat">
        {{ analogs.caveats[0] }}
      </p>

      <!-- F. 设计区块之后：保留全部原有功能 -->
      <div class="cyc-section-label cyc-section-label--retain">
        <span class="cyc-sl-title">周期定位概览</span>
        <span>原有定位指标 · 与上方设计区块并存的完整口径</span>
      </div>
      <div class="cyc-ov-grid">
        <article class="card cyc-ov-card">
          <div class="cyc-ov-top">
            <span class="cyc-ov-icon"><svg class="ic"><use href="#i-target" /></svg></span>
            <span class="cyc-ov-label">长债务周期</span>
            <span class="badge badge--sm" :class="toneClass(longTone)">{{ long.phase }}</span>
          </div>
          <div class="cyc-ov-value">{{ fmtNumber(long.score, 1) }}<small>DMI</small></div>
          <div class="cyc-ov-sub">
            区间 {{ long.bandText }} · 位置上沿 {{ long.positionPct === null ? "—" : `${long.positionPct}%` }} · 置信
            {{ fmtNumber(long.confidence, 2) }}
          </div>
        </article>
        <article class="card cyc-ov-card">
          <div class="cyc-ov-top">
            <span class="cyc-ov-icon"><svg class="ic"><use href="#i-activity" /></svg></span>
            <span class="cyc-ov-label">短债务周期</span>
            <span class="badge badge--sm" :class="toneClass(shortTone)">{{ short.state }}</span>
          </div>
          <div class="cyc-ov-value">
            增长 {{ fmtNumber(short.variables.growth, 0) }}<small>通胀 {{ fmtNumber(short.variables.inflation, 0) }}</small>
          </div>
          <div class="cyc-ov-sub">
            流动性 {{ fmtNumber(short.variables.liq, 0) }} · 12 月增长变化
            {{ fmtSigned(short.variables.d12, 1) }}<template v-if="short.hysteresis_held"> · 滞回保持</template>
          </div>
        </article>
        <article class="card cyc-ov-card">
          <div class="cyc-ov-top">
            <span class="cyc-ov-icon"><svg class="ic"><use href="#i-rates" /></svg></span>
            <span class="cyc-ov-label">债务可持续性</span>
            <span class="badge badge--sm badge--warn">{{ sustainability?.mode ?? "—" }}</span>
          </div>
          <div class="cyc-ov-value">{{ fmtNumber(sustainability?.interest_to_revenue, 1) }}<small>利息 / 收入 %</small></div>
          <div class="cyc-ov-sub">
            r−g {{ fmtSigned(sustainability?.r_minus_g, 1) }}pp · 赤字
            {{ fmtNumber(sustainability?.deficit_to_gdp, 1) }}% GDP
          </div>
        </article>
        <article class="card cyc-ov-card">
          <div class="cyc-ov-top">
            <span class="cyc-ov-icon"><svg class="ic"><use href="#i-layers" /></svg></span>
            <span class="cyc-ov-label">历史类比（样本内）</span>
            <span class="badge badge--sm">{{ analogs?.n ?? 0 }} 个</span>
          </div>
          <div class="cyc-ov-value">
            {{ topAnalogs[0] ? ratioText(topAnalogs[0].similarity) : "—" }}<small>最相似</small>
          </div>
          <div class="cyc-ov-sub">
            {{ topAnalogs[0]?.month ?? "—" }} · 相似≠相同，需人工核对时代背景
          </div>
        </article>
      </div>

      <div class="cyc-retain-grid">
        <section class="card">
          <div class="card-head">
            <span class="card-title">六分量罗盘</span>
            <span class="cyc-card-sub">0–100 归一：越高代表压力/强度越大</span>
            <div class="card-actions">
              <span class="cyc-card-sub">{{ fmtInt(indicators.length) }} 个指标参与</span>
            </div>
          </div>
          <div class="card-body cyc-six-body">
            <svg class="cyc-six-svg" viewBox="0 0 260 260" role="img" aria-label="六分量罗盘">
              <circle v-for="ring in rings" :key="ring" cx="130" cy="130" :r="ring" class="cyc-six-ring" />
              <line
                v-for="axis in axes"
                :key="axis.key"
                x1="130"
                y1="130"
                :x2="axis.tipX"
                :y2="axis.tipY"
                class="cyc-six-axis"
              />
              <polygon :points="polygon" class="cyc-six-shape" />
              <circle
                v-for="axis in axes"
                :key="`dot-${axis.key}`"
                :cx="axis.pointX"
                :cy="axis.pointY"
                r="2.6"
                class="cyc-six-dot"
              />
              <text
                v-for="axis in axes"
                :key="`label-${axis.key}`"
                :x="axis.labelX"
                :y="axis.labelY"
                :text-anchor="axis.anchor"
                class="cyc-six-label"
              >
                {{ axis.label }}
              </text>
              <text x="130" y="126" text-anchor="middle" class="cyc-six-center">{{ long.phase }}</text>
              <text x="130" y="142" text-anchor="middle" class="cyc-six-center-sub">DMI {{ fmtNumber(long.score, 1) }}</text>
            </svg>
            <ul class="cyc-six-legend">
              <li v-for="axis in axes" :key="`legend-${axis.key}`" class="cyc-six-legend-row">
                <span class="cyc-six-legend-name">{{ axis.label }}</span>
                <span class="cyc-six-legend-bar"><i :style="{ width: `${Math.max(2, Math.min(100, axis.value))}%` }"></i></span>
                <b class="mono">{{ fmtNumber(axis.value, 1) }}</b>
                <em class="mono">{{ fmtNumber(axis.confidence, 2) }}</em>
              </li>
            </ul>
          </div>
          <div class="card-foot">
            <span>压力类：DMI / ICI / ECI 越高，债务、内部秩序、外部秩序越紧张。</span>
            <span class="mono">DMI {{ fmtNumber(long.score, 1) }} · 滞回 {{ long.hysteresis_held ? "保持" : "无" }}</span>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <span class="card-title">五层周期</span>
            <span class="cyc-card-sub">嵌套定位 · 每层给出当前状态与含义</span>
          </div>
          <div class="card-body cyc-layer-list">
            <div class="cyc-layer-row">
              <div class="cyc-layer-head">
                <span class="cyc-layer-name">长债务周期</span>
                <span class="badge badge--sm" :class="toneClass(longTone)">{{ long.phase }}</span>
                <span class="cyc-layer-val mono">{{ fmtNumber(long.score, 1) }}</span>
              </div>
              <div class="cyc-bar">
                <i :style="{ width: `${barWidth(long.position === null ? null : long.position * 100)}%` }"></i>
              </div>
              <p class="cyc-layer-meaning">{{ long.meaning }}</p>
              <p class="cyc-layer-meta">下一阶段：{{ long.next_phase ?? "—" }} · {{ long.exit_condition }}</p>
            </div>
            <div class="cyc-layer-row">
              <div class="cyc-layer-head">
                <span class="cyc-layer-name">短债务周期</span>
                <span class="badge badge--sm" :class="toneClass(shortTone)">{{ short.state }}</span>
                <span v-if="short.hysteresis_held" class="badge badge--sm badge--warn">二次确认中</span>
                <span class="cyc-layer-val mono">{{ fmtNumber(short.confidence, 2) }}</span>
              </div>
              <p class="cyc-layer-meaning">{{ short.meaning }}</p>
              <p class="cyc-layer-meta">
                原始命中：{{ short.raw_state }} · 增长 {{ fmtNumber(short.variables.growth, 1) }} / 通胀
                {{ fmtNumber(short.variables.inflation, 1) }}
              </p>
            </div>
            <div class="cyc-layer-row">
              <div class="cyc-layer-head">
                <span class="cyc-layer-name">库存周期</span>
                <span class="badge badge--sm">{{ inventory.state }}</span>
                <span v-if="inventory.degraded" class="badge badge--sm badge--warn">代理口径</span>
                <span class="cyc-layer-val mono">{{ fmtNumber(inventory.confidence, 2) }}</span>
              </div>
              <p class="cyc-layer-meaning">{{ inventory.meaning ?? "—" }}</p>
              <p class="cyc-layer-meta">{{ inventory.degrade_reason ?? "使用库存与价格动量的合成口径。" }}</p>
            </div>
            <div class="cyc-layer-row">
              <div class="cyc-layer-head">
                <span class="cyc-layer-name">信用 / 流动性</span>
                <span class="badge badge--sm" :class="toneClass(liquidityTone)">{{ liq.state }}</span>
                <span class="cyc-layer-val mono">{{ fmtNumber(liq.score, 1) }}</span>
              </div>
              <p class="cyc-layer-meaning">{{ liq.meaning }}</p>
              <p class="cyc-layer-meta">证据 {{ liq.evidence }} · 置信 {{ fmtNumber(liq.confidence, 2) }}</p>
            </div>
            <div class="cyc-layer-row">
              <div class="cyc-layer-head">
                <span class="cyc-layer-name">政治 / 事件窗口</span>
                <span class="badge badge--sm" :class="political.window === '高不确定性窗口' ? 'badge--warn' : ''">
                  {{ political.window }}
                </span>
                <span class="cyc-layer-val mono">{{ political.days_to_nearest ?? "—" }}<small>天</small></span>
              </div>
              <p class="cyc-layer-meaning">{{ political.nearest?.name ?? "无临近事件" }}</p>
              <p class="cyc-layer-meta">
                {{
                  political.nearest
                    ? `${political.nearest.date} · ${political.nearest.note}`
                    : "政治日历为空，请检查 config/cycle.yaml。"
                }}
              </p>
            </div>
          </div>
        </section>
      </div>

      <section class="card cyc-trans-card">
        <div class="card-head">
          <span class="card-title">结构性 / 人工观测</span>
          <span class="cyc-card-sub">
            这些指标没有可自动回算的序列，由人工观测登记；逐条列出证据等级、来源与观测时效，方便核对口径
          </span>
          <div class="card-actions">
            <span class="badge badge--sm">{{ structuralRows.length }} 条</span>
            <span class="badge badge--sm" :class="structuralDegradedCount ? 'badge--warn' : 'badge--live'">
              降级 {{ structuralDegradedCount }}
            </span>
            <span class="gen-at mono" :title="oldestStaleTitle">最旧 {{ oldestStaleText }}</span>
          </div>
        </div>
        <SkeletonBlock v-if="indicatorPoll.loading.value && !structuralRows.length" :rows="6" />
        <ErrorState
          v-else-if="indicatorPoll.error.value && !structuralRows.length"
          :error="indicatorPoll.error.value"
          @retry="refreshIndicators"
        />
        <div v-else class="table-wrap cyc-trans-wrap">
          <table class="data-table cyc-trans-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>分量</th>
                <th class="num">数值</th>
                <th class="num">z</th>
                <th class="num">得分</th>
                <th>证据</th>
                <th>来源</th>
                <th>观测时效</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in structuralRows" :key="row.id">
                <td class="cyc-trans-name">
                  {{ row.name }}
                  <div class="cyc-trans-id mono">{{ row.id }}</div>
                </td>
                <td><span class="badge badge--sm">{{ scoreLabel(row.score) }}</span></td>
                <td class="num">
                  {{ fmtNumber(row.value, 2) }}<small v-if="row.unit" class="cyc-trans-unit">{{ row.unit }}</small>
                </td>
                <td class="num">{{ fmtSigned(row.z, 2) }}</td>
                <td class="num">{{ fmtNumber(row.score_value, 1) }}</td>
                <td>
                  <span class="badge badge--sm" :class="evidenceTone(row.evidence)" :title="evidenceTitle(row.evidence)">
                    {{ row.evidence || "—" }}
                  </span>
                </td>
                <td>
                  <span class="cyc-trans-source" :title="row.source || '未登记来源'">{{ row.source || "—" }}</span>
                </td>
                <td>
                  <span
                    v-if="typeof row.stale_days === 'number'"
                    class="badge badge--sm"
                    :class="staleTone(row.stale_days)"
                    :title="staleTitle(row)"
                  >
                    {{ row.stale_days }} 天
                  </span>
                  <span v-else class="dim" :title="`观测日 ${fmtDate(row.asof)}：后端未给出 stale_days`">未记录</span>
                </td>
                <td>
                  <span
                    v-if="row.degraded"
                    class="badge badge--sm badge--warn cyc-trans-degraded"
                    :title="row.degrade_reason || '后端标记为降级，但未给出原因'"
                  >
                    降级
                  </span>
                  <span v-else class="badge badge--sm badge--live">正常</span>
                </td>
              </tr>
              <tr v-if="!structuralRows.length">
                <td colspan="9">
                  <EmptyState
                    text="没有结构性 / 人工观测指标"
                    hint="后端 /api/v2/cycle/indicators 返回的条目里没有 layer 为「结构性 / 人工观测」的指标：先确认 config/cycle.yaml 的 structural 段未被清空，再点右上角「刷新」。"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="card-foot cyc-trans-foot">
          <span class="cyc-trans-legend">
            <b>证据等级</b>：E1 本地序列可回算 · E2 官方数据（人工口径） · E3 估算 / 代理 · E4 人工研判；折算权重
            1.0 / 0.95 / 0.90 / 0.75 / 0.50。
          </span>
          <span class="cyc-trans-legend">
            <b>观测时效</b>：stale_days 是「人工观测日距今的天数」，超过 30 天标黄、超过 90 天标红；降级条目的
            degrade_reason 放在状态标记的 tooltip 里。
          </span>
        </div>
      </section>

      <section class="card cyc-history-card">
        <div class="card-head">
          <span class="card-title">分量历史轨迹</span>
          <span class="cyc-card-sub">{{ historyMonths.length }} 个月 · 月度末值 · 覆盖不足的分量留空</span>
          <div class="card-actions"><span class="cyc-card-sub mono">{{ historyRange }}</span></div>
        </div>
        <EChart v-if="chartHasData" :option="chartOption" :height="240" />
        <EmptyState v-else text="暂无历史轨迹" hint="至少有 24 个月数据后才会生成月度序列。" />
        <div class="card-foot">
          <span>历史轨迹用于判断「现在与过去哪里相似」，不作为拐点预测。</span>
          <span class="mono">样本从 {{ historyMonths[0] ?? "—" }} 起</span>
        </div>
      </section>

      <div class="cyc-bottom">
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

        <section class="card">
          <div class="card-head">
            <span class="card-title">债务可持续性</span>
            <span class="cyc-card-sub">r−g / 利息负担 / 赤字三模式判别 · 证据 {{ sustainability?.evidence ?? "—" }}</span>
          </div>
          <div class="card-body">
            <EmptyState
              v-if="!sustainability"
              text="债务可持续性数据缺失"
              hint="本次运行未返回 sustainability 段；模式判别与阈值读数暂不可用。"
            />
            <template v-else>
            <div class="cyc-sustain-head">
              <span class="badge badge--sm badge--warn">{{ sustainability?.mode ?? "—" }}</span>
              <span class="mono cyc-sustain-risk">{{ sustainability?.risk ?? "" }}</span>
            </div>
            <p class="cyc-layer-meaning">{{ sustainability?.explanation ?? "" }}</p>
            <div class="cyc-metric-grid">
              <div class="cyc-metric">
                <span class="cyc-metric-label">r−g</span>
                <b class="mono">{{ fmtSigned(sustainability?.r_minus_g, 1) }}<small>pp</small></b>
              </div>
              <div class="cyc-metric">
                <span class="cyc-metric-label">利息 / 财政收入</span>
                <b class="mono">{{ fmtNumber(sustainability?.interest_to_revenue, 1) }}<small>%</small></b>
              </div>
              <div class="cyc-metric">
                <span class="cyc-metric-label">赤字 / GDP</span>
                <b class="mono">{{ fmtNumber(sustainability?.deficit_to_gdp, 1) }}<small>%</small></b>
              </div>
              <div class="cyc-metric">
                <span class="cyc-metric-label">债务 / GDP</span>
                <b class="mono">{{ fmtNumber(sustainability?.debt_to_gdp, 0) }}<small>%</small></b>
              </div>
            </div>
            <p class="cyc-layer-meta">
              关注阈值：利息/收入 ≥{{ sustainabilityThresholds.interest_watch ?? "—" }}%（警戒）、≥{{
                sustainabilityThresholds.interest_alarm ?? "—"
              }}%（警报）；赤字/GDP ≥{{ sustainabilityThresholds.deficit_watch ?? "—" }}%。
            </p>
            </template>
          </div>
        </section>
      </div>

      <div class="cyc-bottom">
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

        <section class="card">
          <div class="card-head">
            <span class="card-title">历史类比明细</span>
            <span class="cyc-card-sub">20 维状态向量近邻 · 剔除最近 {{ analogs?.min_gap_months ?? 12 }} 个月</span>
            <div class="card-actions">
              <RouterLink class="cyc-card-sub cyc-inline-link" :to="{ path: '/pipeline', query: { code: 'cycle.analogs' } }">
                为什么 →
              </RouterLink>
            </div>
          </div>
          <div class="card-body">
            <ul v-if="analogList.length" class="cyc-analog-list">
              <li v-for="item in analogList.slice(0, 4)" :key="item.month" class="cyc-analog-line">
                <span class="cyc-analog-month mono">{{ item.month }}</span>
                <span class="cyc-analog-sim-bar">
                  <i :style="{ width: `${barWidth(item.similarity * 100, 4)}%` }"></i>
                </span>
                <b class="mono">{{ ratioText(item.similarity) }}</b>
                <span class="cyc-analog-state mono">
                  增长 {{ fmtNumber(item.state.growth, 0) }} · 通胀 {{ fmtNumber(item.state.inflation, 0) }}
                </span>
              </li>
            </ul>
            <EmptyState v-else text="暂无类比结果" hint="样本内近邻不足或未生成 analogs 段。" />
            <p v-if="Array.isArray(analogs?.caveats) && analogs.caveats.length" class="cyc-layer-meta">
              {{ analogs.caveats[0] ?? "" }}
            </p>
          </div>
          <div class="card-foot">
            <span>类比是「样本内比较」，相似不保证同路径。</span>
          </div>
        </section>
      </div>

      <div v-if="degradedReasons.length" class="cyc-degraded-box">
        <svg class="ic"><use href="#i-alert" /></svg>
        <div>
          <b>本次运行有 {{ degradedReasons.length }} 项降级</b>
          <div v-for="(reason, index) in degradedReasons.slice(0, 6)" :key="reason.code ?? index" class="cyc-degraded-reason">
            {{ reason.message ?? "未提供降级说明" }}（{{ reason.code ?? "unknown" }}）
          </div>
        </div>
      </div>

      <div class="cyc-foot">
        <span class="mono">run {{ payload?.run_id ?? "—" }}</span>
        <span class="mono">method {{ payload?.state?.method_id ?? "—" }}</span>
        <span class="mono"> asof {{ asofLabel }} · 生成于 {{ generatedLabel }} </span>
        <span class="mono">
          confidence {{ longConfidencePct === null ? "—" : `${longConfidencePct}%` }} ·
          {{ payload?.state?.evidence_grade ?? "—" }}
        </span>
      </div>
    </template>
    <EmptyState
      v-else
      text="周期状态字段缺失"
      hint="接口已返回运行记录，但缺少 state.value（旧版运行结果可能不完整）；请点击上方「立即重算」重新生成。"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { EChartsOption } from "echarts";
import EChart from "@/components/charts/EChart.vue";
import CycleCompass from "@/components/cycle/CycleCompass.vue";
import CycleForces from "@/components/cycle/CycleForces.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import ErrorState from "@/components/ui/ErrorState.vue";
import SkeletonBlock from "@/components/ui/SkeletonBlock.vue";
import { usePolling } from "@/composables/usePolling";
import {
  fmtDate,
  fmtDateTime,
  fmtInt,
  fmtNumber,
  fmtSigned,
  fmtTime,
} from "@/composables/useFormat";
import { getJson } from "@/api/client";
import { getCycleConfig, getCycleReadings, getCycleIndicators, getCycleState, runCycle } from "@/api/endpoints";
import type {
  CycleAlert,
  CycleAnalog,
  CycleAnalogs,
  CycleHistory,
  CycleIndicator,
  CycleIndicatorsResponse,
  CycleInventory,
  CycleKey,
  CycleLiquidity,
  CycleLongCycle,
  CyclePolitical,
  CycleReading,
  CycleReadingCard,
  CycleReadingsResponse,
  CycleScenarioItem,
  CycleShortCycle,
  CycleStage,
  CycleStateResponse,
  CycleSustainability,
  CycleWorld,
} from "@/api/types";

const { data, error, loading, refresh } = usePolling<CycleStateResponse>(getCycleState, {
  interval: 60_000,
});

/** 关键读数走独立接口：失败时只降级 C 段，不影响其余区块。 */
const readingsPoll = usePolling<CycleReadingsResponse>(getCycleReadings, { interval: 60_000 });

/** 指标全量（32 条，含 evidence / source / stale_days / degraded）：独立轮询，只用于透明度卡。 */
const indicatorPoll = usePolling<CycleIndicatorsResponse>(getCycleIndicators, { interval: 120_000 });
const refreshIndicators = (): void => {
  void indicatorPoll.refresh();
};

const STRUCTURAL_LAYER = "结构性";
const structuralRows = computed<CycleIndicator[]>(() =>
  (indicatorPoll.data.value?.items ?? []).filter((row) => (row.layer ?? "").includes(STRUCTURAL_LAYER)),
);
const structuralDegradedCount = computed(() => structuralRows.value.filter((row) => row.degraded).length);
const oldestStaleDays = computed<number | null>(() => {
  const days = structuralRows.value
    .map((row) => row.stale_days)
    .filter((value): value is number => typeof value === "number");
  return days.length ? Math.max(...days) : null;
});
const oldestStaleText = computed(() =>
  oldestStaleDays.value === null ? "—" : `${oldestStaleDays.value} 天`,
);
const oldestStaleTitle = computed(() => {
  if (oldestStaleDays.value === null) return "后端未给出 stale_days，无法判断观测时效";
  const oldest = structuralRows.value
    .filter((row) => row.stale_days === oldestStaleDays.value)
    .map((row) => `${row.name}（观测日 ${fmtDate(row.asof)}）`);
  return `最旧的人工观测：${oldest.join("、")}`;
});

const SCORE_LABEL: Record<string, string> = {
  DMI: "债务动量",
  GROWTH: "增长",
  INFLATION: "通胀",
  LIQUIDITY: "流动性",
  ECI: "信用环境",
  ICI: "库存周期",
};
function scoreLabel(score: string | null): string {
  if (!score) return "—";
  return SCORE_LABEL[score] ?? score;
}

const EVIDENCE_TEXT: Record<string, string> = {
  E1: "本地序列可回算（权重 1.0）",
  E2: "官方数据、人工录入口径（权重 0.95）",
  E3: "估算 / 代理指标（权重 0.75）",
  E4: "人工研判，无自动来源（权重 0.50）",
};
function evidenceTone(evidence: string | null): string {
  if (evidence === "E1") return "badge--live";
  if (evidence === "E2") return "badge--accent";
  if (evidence === "E3") return "badge--warn";
  if (evidence === "E4") return "badge--down";
  return "";
}
function evidenceTitle(evidence: string | null): string {
  if (!evidence) return "后端未给出证据等级：该指标无法按等级折算权重";
  return EVIDENCE_TEXT[evidence] ?? `未识别的证据等级 ${evidence}`;
}

function staleTone(days: number): string {
  if (days >= 90) return "badge--down";
  if (days > 30) return "badge--warn";
  return "";
}
function staleTitle(row: CycleIndicator): string {
  if (row.stale_days === null) return "后端未给出 stale_days";
  const days = row.stale_days;
  const level = days >= 90 ? "超过 90 天，观测已明显过期" : days > 30 ? "超过 30 天，建议更新观测" : "在 30 天以内";
  return `观测日 ${fmtDate(row.asof)}，已 ${days} 天未更新（${level}）。`;
}

const running = ref(false);
const recalcError = ref<string | null>(null);
const payload = computed(() => data.value);
const value = computed(() => payload.value?.state?.value ?? null);
const indicators = computed<CycleReading[]>(() => {
  const list = payload.value?.indicators;
  if (!Array.isArray(list)) return [];
  return list.filter((item): item is CycleReading => !!item && typeof item === "object");
});

// ── 防御式归一 ───────────────────────────────────────────
// 旧运行记录可能缺 long_cycle.band / short_cycle.variables / world.power_index 等字段，
// 统一在 computed 里补齐默认值；模板只读归一后的对象，任何缺失都不会触发下标崩溃。
type RawOf<T> = Partial<T> | null | undefined;

function asNumber(input: unknown): number | null {
  if (typeof input !== "number" || !Number.isFinite(input)) return null;
  return input;
}

/** 0–100 分量的安全取值；缺失按中性 50 处理 */
function asScore(input: unknown): number | null {
  const value = asNumber(input);
  if (value === null) return null;
  return Math.max(0, Math.min(100, value));
}

function asText(input: unknown, fallback = "—"): string {
  if (typeof input !== "string") return fallback;
  const text = input.trim();
  return text || fallback;
}

interface SafeLongCycle {
  phase: string;
  phase_id: string;
  score: number | null;
  band: [number, number] | null;
  bandText: string;
  position: number | null;
  positionPct: number | null;
  meaning: string;
  asset: string;
  confidence: number | null;
  next_phase: string | null;
  exit_condition: string;
  hysteresis_held: boolean;
}

const long = computed<SafeLongCycle>(() => {
  const raw = value.value?.long_cycle as RawOf<CycleLongCycle>;
  const band = Array.isArray(raw?.band) ? raw.band : null;
  const bandStart = asNumber(band?.[0]);
  const bandEnd = asNumber(band?.[1]);
  const position = asNumber(raw?.position);
  return {
    phase: asText(raw?.phase, "未知阶段"),
    phase_id: asText(raw?.phase_id, "unknown"),
    score: asScore(raw?.score),
    band: bandStart !== null && bandEnd !== null ? [bandStart, bandEnd] : null,
    bandText: bandStart !== null && bandEnd !== null ? `${bandStart}–${bandEnd}` : "—",
    position,
    positionPct: position === null ? null : Math.max(0, Math.min(100, Math.round(position * 100))),
    meaning: asText(raw?.meaning, "长债务周期阶段含义缺失（该运行记录未返回 meaning）。"),
    asset: asText(raw?.asset, "—"),
    confidence: asNumber(raw?.confidence),
    next_phase: typeof raw?.next_phase === "string" ? raw.next_phase : null,
    exit_condition: asText(raw?.exit_condition, "—"),
    hysteresis_held: raw?.hysteresis_held === true,
  };
});

interface SafeShortCycle {
  state: string;
  raw_state: string;
  hysteresis_held: boolean;
  variables: { growth: number | null; inflation: number | null; liq: number | null; d12: number | null };
  meaning: string;
  confidence: number | null;
  growth_12m_change: number | null;
}

const short = computed<SafeShortCycle>(() => {
  const raw = value.value?.short_cycle as RawOf<CycleShortCycle>;
  const variables = (raw?.variables ?? {}) as Partial<CycleShortCycle["variables"]>;
  return {
    state: asText(raw?.state, "未知状态"),
    raw_state: asText(raw?.raw_state, "—"),
    hysteresis_held: raw?.hysteresis_held === true,
    variables: {
      growth: asNumber(variables.growth),
      inflation: asNumber(variables.inflation),
      liq: asNumber(variables.liq),
      d12: asNumber(variables.d12),
    },
    meaning: asText(raw?.meaning, "短周期含义缺失（该运行记录未返回 meaning）。"),
    confidence: asNumber(raw?.confidence),
    growth_12m_change: asNumber(raw?.growth_12m_change),
  };
});

interface SafeLiquidity {
  available: boolean;
  state: string;
  score: number | null;
  meaning: string;
  confidence: number | null;
  evidence: string;
}

const liq = computed<SafeLiquidity>(() => {
  const raw = value.value?.liquidity as RawOf<CycleLiquidity>;
  return {
    available: raw?.available !== false,
    state: asText(raw?.state, "未知"),
    score: asScore(raw?.score),
    meaning: asText(raw?.meaning, "流动性判定缺失（该运行记录未返回）。"),
    confidence: asNumber(raw?.confidence),
    evidence: asText(raw?.evidence, "—"),
  };
});

interface SafeInventory {
  state: string;
  degraded: boolean;
  degrade_reason: string | null;
  meaning: string | null;
  confidence: number | null;
}

const inventory = computed<SafeInventory>(() => {
  const raw = value.value?.inventory as RawOf<CycleInventory>;
  return {
    state: asText(raw?.state, "未知"),
    degraded: raw?.degraded === true,
    degrade_reason: typeof raw?.degrade_reason === "string" ? raw.degrade_reason : null,
    meaning: typeof raw?.meaning === "string" ? raw.meaning : null,
    confidence: asNumber(raw?.confidence),
  };
});

interface SafeNearestEvent {
  name: string;
  date: string;
  note: string;
}

interface SafePolitical {
  window: string;
  nearest: SafeNearestEvent | null;
  days_to_nearest: number | null;
}

const political = computed<SafePolitical>(() => {
  const raw = value.value?.political as RawOf<CyclePolitical>;
  const nearest = raw?.nearest as { name?: unknown; date?: unknown; note?: unknown } | null | undefined;
  return {
    window: asText(raw?.window, "窗口未知"),
    nearest: nearest
      ? {
          name: asText(nearest.name, "临近事件"),
          date: asText(nearest.date, "—"),
          note: asText(nearest.note, "—"),
        }
      : null,
    days_to_nearest: asNumber(raw?.days_to_nearest),
  };
});

const sustainability = computed(() => payload.value?.sustainability?.value ?? null);
/** thresholds 可能整段缺失，单独归一，模板不再直接点属性 */
const sustainabilityThresholds = computed<Partial<CycleSustainability["thresholds"]>>(
  () => (sustainability.value?.thresholds ?? {}) as Partial<CycleSustainability["thresholds"]>,
);

const scenarios = computed(() => payload.value?.scenarios?.value ?? null);
/** 情景条目逐项归一：probability/name/desc/assets 任一缺失都不影响渲染 */
const scenarioList = computed<CycleScenarioItem[]>(() => {
  const list = scenarios.value?.scenarios;
  if (!Array.isArray(list)) return [];
  return list
    .filter((item): item is CycleScenarioItem => !!item && typeof item === "object")
    .map((item) => ({
      id: asText(item.id, "—"),
      name: asText(item.name, "未命名情景"),
      probability: asNumber(item.probability) ?? 0,
      base: asNumber(item.base) ?? 0,
      adjustment: asNumber(item.adjustment) ?? 0,
      desc: asText(item.desc, "—"),
      assets: asText(item.assets, "—"),
      triggers: Array.isArray(item.triggers) ? item.triggers : [],
    }));
});
const analogs = computed<RawOf<CycleAnalogs>>(() => (payload.value?.analogs?.value as RawOf<CycleAnalogs>) ?? null);
const analogList = computed<CycleAnalog[]>(() => {
  const list = analogs.value?.analogs;
  if (!Array.isArray(list)) return [];
  return list
    .filter((item): item is CycleAnalog => !!item && typeof item === "object")
    .map((item) => {
      const state = (item.state ?? {}) as Partial<CycleAnalog["state"]>;
      return {
        month: asText(item.month, "—"),
        similarity: asNumber(item.similarity) ?? 0,
        distance: asNumber(item.distance) ?? 0,
        state: { growth: asNumber(state.growth), inflation: asNumber(state.inflation) },
      };
    });
});

/** 世界秩序是顶层推导 payload（payload.world.value）；缺失时兼容旧形态 local state.value.world。 */
const world = computed<RawOf<CycleWorld>>(() => {
  const response = payload.value;
  if (!response) return null;
  const top = response.world?.value as RawOf<CycleWorld>;
  if (top) return top;
  // 兼容旧后端把 world 挂在 state.value 下的形态
  const legacy = (response.state?.value as unknown as { world?: CycleWorld | null } | undefined)?.world;
  return (legacy as RawOf<CycleWorld>) ?? null;
});

type PowerComponent = Partial<CycleWorld["power_index"]["components"][number]>;
const powerIndex = computed<RawOf<CycleWorld["power_index"]>>(() => world.value?.power_index ?? null);
interface SafePowerComponent {
  id: string;
  name: string;
  value: number;
  weight: number;
}
/** 八项实力逐项归一：value 归一到 0–100 保证进度条可用，weight 转百分比 */
const powerComponents = computed<SafePowerComponent[]>(() => {
  const list = powerIndex.value?.components;
  if (!Array.isArray(list)) return [];
  return list.map((item) => ({
    id: asText(item.id, "—"),
    name: asText(item.name, "未命名分项"),
    value: barWidth(asNumber(item.value) ?? 0),
    weight: (asNumber(item.weight) ?? 0) * 100,
  }));
});
const reserveCurrency = computed<RawOf<CycleWorld["reserve_currency"]>>(() => world.value?.reserve_currency ?? null);

interface SafeStage {
  id: string;
  name: string;
  stage: number | null;
  stage_name: string;
  confidence: number | null;
  reason: string;
  falsifier: string;
}

const stages = computed<SafeStage[]>(() => {
  const list: Array<Partial<CycleStage> | null | undefined> = [
    world.value?.us_internal,
    world.value?.global_order,
  ];
  return list
    .filter((stage): stage is Partial<CycleStage> => !!stage)
    .map((stage) => ({
      id: asText(stage.id, "—"),
      name: asText(stage.name, "未命名秩序"),
      stage: asNumber(stage.stage),
      stage_name: asText(stage.stage_name, "—"),
      confidence: asNumber(stage.confidence),
      reason: asText(stage.reason, "—"),
      falsifier: asText(stage.falsifier, "—"),
    }));
});

const history = computed<RawOf<CycleHistory>>(() => (payload.value?.history?.value as RawOf<CycleHistory>) ?? null);
const historyMonths = computed<string[]>(() => {
  const months = history.value?.months;
  return Array.isArray(months) ? months : [];
});

interface DegradedReason {
  code?: string;
  message?: string;
}

const degradedReasons = computed<DegradedReason[]>(() => {
  const list = payload.value?.degraded_reasons;
  return Array.isArray(list) ? list : [];
});

// ── 时间标签：只展示数据自身时点，不展示系统当前时间 ────────
const generatedLabel = computed<string>(() => {
  const raw = payload.value?.generated_at;
  return raw ? fmtDateTime(raw) : "—";
});
const asofLabel = computed<string>(() => fmtDate(payload.value?.asof));

/** 通用进度条宽度（0–100，缺失给最小宽度），避免任何 NaN 写入 style */
function barWidth(value: number | null | undefined, min = 2): number {
  if (value === null || value === undefined || !Number.isFinite(value)) return min;
  return Math.max(min, Math.min(100, Math.round(value)));
}

/** 比例 → 百分比文案（0.71 → 71%），缺失显示 — */
function ratioText(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

/** 后端 /api/v2/cycle/meta 为新增端点：返回失败时静默回退到 config.version。 */
interface CycleMeta {
  rule_version?: string | null;
  next_calibration?: string | null;
  brier?: number | null;
  calibration_n?: number | null;
  coverage?: { series_covered?: number | null; series_total?: number | null } | null;
}

const meta = ref<CycleMeta | null>(null);
const configVersion = ref<string | null>(null);

async function loadMeta(): Promise<void> {
  try {
    meta.value = await getJson<CycleMeta>("/api/v2/cycle/meta");
  } catch {
    meta.value = null;
  }
}

async function loadConfigVersion(): Promise<void> {
  try {
    const config = await getCycleConfig();
    configVersion.value = config.version ?? null;
  } catch {
    configVersion.value = null;
  }
}

onMounted(() => {
  void loadMeta();
  void loadConfigVersion();
});

const ruleVersion = computed<string>(() => meta.value?.rule_version || configVersion.value || "—");
const nextCalibration = computed<string>(() => meta.value?.next_calibration || "—");

const coverageText = computed<string>(() => {
  const coverage = meta.value?.coverage;
  const covered = coverage?.series_covered ?? null;
  const total = coverage?.series_total ?? null;
  if (covered !== null && total !== null && total > 0) return `${covered}/${total}`;
  const list = indicators.value;
  if (!list.length) return "—";
  return `${list.filter((reading) => reading.value !== null).length}/${list.length}`;
});

// ── 通用读数查找 ─────────────────────────────────────────
function findReading(ids: string[]): CycleReading | null {
  const list = indicators.value;
  for (const wanted of ids) {
    const hit = list.find((reading) => reading.id.toLowerCase() === wanted.toLowerCase());
    if (hit && hit.value !== null) return hit;
  }
  for (const wanted of ids) {
    const hit = list.find((reading) => reading.id.toLowerCase().includes(wanted.toLowerCase()));
    if (hit && hit.value !== null) return hit;
  }
  return null;
}

function compositeValue(key: CycleKey): number | null {
  const raw = value.value?.composites?.[key]?.value;
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return null;
  return Math.max(0, Math.min(100, raw));
}

function readingsForScore(key: CycleKey): number {
  return indicators.value.filter((reading) => {
    const raw = (reading as unknown as { score?: string | number | null }).score;
    return raw === key && reading.score_value !== null;
  }).length;
}

// ── A. Hero ──────────────────────────────────────────────
const heroTitle = computed<string>(() => {
  const meaning = (long.value.meaning ?? "").replace(/\s+/g, " ").trim();
  const shortMeaning = meaning ? meaning.slice(0, 18) : "阶段定位";
  return `美国 · 长债务周期${long.value.phase}：${shortMeaning}`;
});

const compassGrowth = computed<number | null>(
  () => compositeValue("GROWTH") ?? short.value.variables.growth ?? null,
);
const compassInflation = computed<number | null>(
  () => compositeValue("INFLATION") ?? short.value.variables.inflation ?? null,
);

function directionArrow(score: number | null): string {
  if (score === null) return "—";
  return score >= 50 ? "↑" : "↓";
}

const growthArrow = computed(() => directionArrow(compositeValue("GROWTH")));
const inflationArrow = computed(() => directionArrow(compositeValue("INFLATION")));

/** 综合置信度（百分比；兼容 0–1 与 0–100 两种存量口径） */
const longConfidencePct = computed<number | null>(() => {
  const raw = long.value.confidence;
  if (raw === null || !Number.isFinite(raw)) return null;
  const scaled = raw <= 1 ? raw * 100 : raw;
  return Math.max(0, Math.min(100, Math.round(scaled)));
});

const heroSub = computed<string>(() => {
  const confidence = longConfidencePct.value;
  const confText = confidence === null ? "—" : `${confidence}%`;
  return `短周期：${short.value.state} · 综合置信度 ${confText} · 增长${growthArrow.value} 通胀${inflationArrow.value}`;
});

interface HeroTag {
  key: string;
  label: string;
  value: string;
  z: number | null;
}

const alertsPayload = computed(() => payload.value?.alerts?.value ?? null);
const alertList = computed<CycleAlert[]>(() => {
  const list = alertsPayload.value?.alerts;
  if (!Array.isArray(list)) return [];
  return list.filter((alert): alert is CycleAlert => !!alert && typeof alert === "object");
});
const spreadAlert = computed(
  () => alertList.value.find((alert) => alert.metric === "cn_us_spread" || (alert.metric_name ?? "").includes("中美")) ?? null,
);

const heroTags = computed<HeroTag[]>(() => {
  const tags: Array<HeroTag | null> = [];
  const real = findReading(["us_real10y", "US10Y_REAL"]);
  if (real && real.value !== null) {
    tags.push({
      key: "real10y",
      label: "10Y 实际利率",
      value: `${fmtNumber(real.value, 2)}${real.unit ? ` ${real.unit}` : ""}`,
      z: real.z,
    });
  }
  const curve = findReading(["us_curve_slope"]);
  if (curve && curve.value !== null) {
    tags.push({ key: "curve", label: "10Y–2Y 利差", value: `${fmtSigned(curve.value * 100, 0)} bp`, z: curve.z });
  }
  if (spreadAlert.value && spreadAlert.value.value !== null) {
    tags.push({
      key: "cnus",
      label: "中美 10Y 利差",
      value: `${fmtSigned(spreadAlert.value.value, 0)} ${spreadAlert.value.unit ?? "bp"}`,
      z: null,
    });
  }
  const us10y = findReading(["us_10y"]);
  if (us10y && us10y.value !== null) {
    tags.push({
      key: "us10y",
      label: "美债 10Y",
      value: `${fmtNumber(us10y.value, 2)}${us10y.unit ? ` ${us10y.unit}` : ""}`,
      z: us10y.z,
    });
  }
  const breakeven = findReading(["us_breakeven"]);
  if (breakeven && breakeven.value !== null) {
    tags.push({
      key: "breakeven",
      label: "10Y 盈亏平衡",
      value: `${fmtNumber(breakeven.value, 2)}${breakeven.unit ? ` ${breakeven.unit}` : ""}`,
      z: breakeven.z,
    });
  }
  return tags.filter((tag): tag is HeroTag => tag !== null).slice(0, 3);
});

// ── C. 关键读数（直连 /api/v2/cycle/readings，缺失只显示原因） ─────────
interface KpiView {
  id: string;
  label: string;
  value: string;
  unit: string;
  z: number | null;
  zClass: string;
  missing: boolean;
  reason: string | null;
  source: string | null;
  evidence: string;
  deltaText: string;
  deltaClass: "up" | "down" | "flat";
  spark: string;
  sparkColor: string;
  tooltip: string;
}

const readingItems = computed<CycleReadingCard[]>(() => {
  const list = readingsPoll.data.value?.items;
  if (!Array.isArray(list)) return [];
  return list.filter((item): item is CycleReadingCard => !!item && typeof item === "object");
});
const missingReadings = computed<number>(() => readingItems.value.filter((item) => item.missing).length);
/** 设计稿固定的 8 张卡顺序：接口返回顺序不同也按此排，其余读数追加在后。 */
const KPI_ORDER = ["us10y", "us10y_real", "us10y_2y", "gold", "gold_silver", "lme_copper", "dxy", "cn_us_spread"];
const orderedReadings = computed<CycleReadingCard[]>(() => {
  const rank = (id: string): number => {
    const index = KPI_ORDER.indexOf(id);
    return index === -1 ? KPI_ORDER.length : index;
  };
  return readingItems.value.slice().sort((a, b) => rank(a.id) - rank(b.id));
});
const readingsUnavailable = computed<boolean>(
  () => !!readingsPoll.error.value && readingItems.value.length === 0,
);
const readingsErrorText = computed<string>(() => readingsPoll.error.value?.message ?? "请求失败");

/** 卡片右上角日期：取全部读数里最新的 asof。 */
const readingsAsof = computed<string>(() => {
  const dates = readingItems.value
    .map((item) => item.asof)
    .filter((value): value is string => !!value);
  if (!dates.length) return "";
  return fmtDate(dates.reduce((a, b) => (a > b ? a : b)));
});

/** 30 点序列压进 120×24 折线；后端 spark 可能以小数或 ×100 基点存放，只做相对归一。 */
function sparkPolyline(points: CycleReadingCard["spark"]): string {
  const list = Array.isArray(points) ? points : [];
  const values = list
    .map((point) => (point && typeof point === "object" ? point.value : null))
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = 120 / (values.length - 1);
  return values
    .map((value, index) => `${(index * step).toFixed(1)},${(22 - ((value - min) / span) * 20).toFixed(1)}`)
    .join(" ");
}

function deltaTone(delta: number | null): "up" | "down" | "flat" {
  if (delta === null || !Number.isFinite(delta) || delta === 0) return "flat";
  return delta > 0 ? "up" : "down";
}

const kpis = computed<KpiView[]>(() =>
  orderedReadings.value.map((item) => {
    const digits = item.digits ?? 2;
    const unit = item.unit ?? "";
    const raw = item.value;
    const usable = !item.missing && raw !== null && raw !== undefined && Number.isFinite(raw);
    const delta = item.delta_1d === undefined || item.delta_1d === null ? null : item.delta_1d;
    const z = item.z ?? null;
    return {
      id: item.id,
      label: item.label ?? "未命名读数",
      value: usable ? fmtNumber(raw, digits) : "—",
      unit,
      z,
      zClass: z === null ? "" : z > 0 ? "cyc-kpi-z--pos" : z < 0 ? "cyc-kpi-z--neg" : "",
      missing: !usable,
      reason: item.reason ?? null,
      source: item.source ?? null,
      evidence: item.evidence ?? "E2",
      deltaText: usable && delta !== null ? `${fmtSigned(delta, digits)}${unit}` : "",
      deltaClass: deltaTone(delta),
      spark: usable ? sparkPolyline(item.spark) : "",
      sparkColor: z !== null && z > 0 ? "var(--up)" : z !== null && z < 0 ? "var(--down)" : "var(--accent)",
      tooltip: [item.source ?? "", item.asof ? `asof ${item.asof}` : "", item.reason ?? ""]
        .filter(Boolean)
        .join(" · "),
    };
  }),
);

// ── D. 今日预警 ──────────────────────────────────────────
const triggeredAlerts = computed(() =>
  alertList.value.filter((alert) => alert.triggered === true || alert.status === "triggered"),
);
const alertCount = computed<number>(() => alertsPayload.value?.triggered ?? triggeredAlerts.value.length);
const topAlerts = computed<CycleAlert[]>(() => triggeredAlerts.value.slice(0, 3));

function sevClass(severity: CycleAlert["severity"]): string {
  return severity === "high" ? "high" : severity === "medium" ? "mid" : severity === "low" ? "low" : "unknown";
}

function sevLabel(severity: CycleAlert["severity"]): string {
  return severity === "high" ? "高" : severity === "medium" ? "中" : severity === "low" ? "低" : "未知";
}

function alertValue(alert: CycleAlert): string {
  if (alert.value === null || !Number.isFinite(alert.value)) return "—";
  return `${fmtNumber(alert.value, 2)}${alert.unit ?? ""}`;
}

function alertThreshold(alert: CycleAlert): string {
  const op = alert.op ? String(alert.op) : "—";
  const threshold = fmtNumber(alert.threshold, 2);
  return `阈值 ${op} ${threshold}${alert.unit ?? ""}`;
}

function alertAsOf(alert: CycleAlert): string {
  if (!alert.asof) return "—";
  return alert.asof.length <= 10 ? fmtDate(alert.asof) : fmtTime(alert.asof, true);
}

// ── E. 历史类比 Top3 ─────────────────────────────────────
const topAnalogs = computed<CycleAnalog[]>(() => analogList.value.slice(0, 3));
const analogSlots = computed<Array<CycleAnalog | null>>(() => {
  const slots: Array<CycleAnalog | null> = topAnalogs.value.slice(0, 3);
  while (slots.length < 3) slots.push(null);
  return slots;
});

// ── B. 五力仪表 ──────────────────────────────────────────
interface ForceRow {
  key: string;
  name: string;
  score: number | null;
  basis: number;
  proxy: string | null;
  missing: boolean;
}

const oilReading = computed<CycleReading | null>(() => {
  const direct = findReading(["oil_mom"]);
  if (direct) return direct;
  return (
    indicators.value.find(
      (reading) => reading.value !== null && (/oil/i.test(reading.id) || /原油|油价/.test(reading.name)),
    ) ?? null
  );
});

/** cycle.yaml 的 pct 类读数以小数存放（0.0085 = 0.85%），展示与换算时统一放大。 */
function pctReading(reading: CycleReading | null): number | null {
  if (!reading || reading.value === null || !Number.isFinite(reading.value)) return null;
  const unit = (reading.unit ?? "").toLowerCase();
  if (unit === "pct" && Math.abs(reading.value) <= 1) return reading.value * 100;
  return reading.value;
}

const naturalShock = computed<{ score: number | null; basis: number; proxy: string | null }>(() => {
  const oil = oilReading.value;
  const pct = pctReading(oil);
  if (pct === null) {
    return { score: null, basis: 0, proxy: "代理口径 E1 · 原油价格读数缺失" };
  }
  const momentum = Math.max(-25, Math.min(25, pct));
  const score = Math.round(Math.max(0, Math.min(100, 50 + momentum * 2)));
  return { score, basis: 1, proxy: "代理口径 E1 · 50+2×原油60日动量（当前 " + `${fmtSigned(momentum, 1)}%）` };
});

const techRevolution = computed<{ score: number | null; basis: number; proxy: string | null }>(() => {
  const ndx = indicators.value.find(
    (reading) => reading.value !== null && /ndx|nasdaq|纳斯达克/i.test(`${reading.id} ${reading.name}`),
  );
  if (!ndx || ndx.value === null) {
    return { score: null, basis: 0, proxy: "代理口径 E1 · NDX/SPX 相对动量读数缺失" };
  }
  return { score: null, basis: 1, proxy: "代理口径 E1 · NDX 相对 SPX 60 日动量" };
});

const forces = computed<ForceRow[]>(() => {
  const dmi = compositeValue("DMI");
  const ici = compositeValue("ICI");
  const eci = compositeValue("ECI");
  return [
    { key: "DMI", name: "债务 / 货币", score: dmi, basis: readingsForScore("DMI"), proxy: null, missing: dmi === null },
    { key: "ICI", name: "内部冲突", score: ici, basis: readingsForScore("ICI"), proxy: null, missing: ici === null },
    { key: "ECI", name: "外部冲突", score: eci, basis: readingsForScore("ECI"), proxy: null, missing: eci === null },
    {
      key: "NAT",
      name: "自然冲击",
      score: naturalShock.value.score,
      basis: naturalShock.value.basis,
      proxy: naturalShock.value.proxy,
      missing: naturalShock.value.score === null,
    },
    {
      key: "TECH",
      name: "技术革命",
      score: techRevolution.value.score,
      basis: techRevolution.value.basis,
      proxy: techRevolution.value.proxy,
      missing: true,
    },
  ];
});

const stressCount = computed<number>(() => forces.value.filter((force) => force.score !== null && force.score >= 75).length);

// ── F. 保留：六分量罗盘（原功能）──────────────────────────
const COMPASS: Array<{ key: CycleKey; label: string }> = [
  { key: "DMI", label: "债务货币" },
  { key: "ICI", label: "内部秩序" },
  { key: "ECI", label: "外部秩序" },
  { key: "GROWTH", label: "增长" },
  { key: "INFLATION", label: "通胀" },
  { key: "LIQUIDITY", label: "流动性" },
];

const rings = [23, 46, 69, 92];

const axes = computed(() =>
  COMPASS.map((item, index) => {
    const composite = value.value?.composites?.[item.key];
    const raw = composite?.value ?? 0;
    const score = raw === null || raw === undefined || !Number.isFinite(raw) ? 0 : Math.max(0, Math.min(100, raw));
    const angle = ((-90 + index * 60) * Math.PI) / 180;
    const radius = 92 * (score / 100);
    return {
      ...item,
      value: score,
      confidence: composite?.confidence ?? 0,
      tipX: 130 + Math.cos(angle) * 92,
      tipY: 130 + Math.sin(angle) * 92,
      pointX: 130 + Math.cos(angle) * radius,
      pointY: 130 + Math.sin(angle) * radius,
      labelX: 130 + Math.cos(angle) * 112,
      labelY: 130 + Math.sin(angle) * 112 + (Math.abs(Math.sin(angle)) < 0.1 ? 3 : 0),
      anchor: Math.abs(Math.cos(angle)) < 0.1 ? "middle" : Math.cos(angle) > 0 ? "start" : "end",
    };
  }),
);

const polygon = computed(() =>
  axes.value.map((axis) => `${axis.pointX.toFixed(1)},${axis.pointY.toFixed(1)}`).join(" "),
);

type Tone = "ok" | "warn" | "up" | "down" | "accent" | "plain";
const PHASE_TONE: Record<string, Tone> = {
  normal: "ok",
  bubble_early: "ok",
  bubble_late: "warn",
  top: "warn",
  deflationary: "up",
  printing: "warn",
  debasement: "up",
};
const longTone = computed<Tone>(() => PHASE_TONE[long.value.phase_id] ?? "accent");
const SHORT_TONE: Record<string, Tone> = {
  复苏: "ok",
  过热: "warn",
  放缓: "plain",
  衰退: "up",
  萧条: "up",
};
const shortTone = computed<Tone>(() => SHORT_TONE[short.value.state] ?? "accent");
const LIQ_TONE: Record<string, Tone> = { 宽松: "ok", 中性: "plain", 收紧: "warn" };
const liquidityTone = computed<Tone>(() => LIQ_TONE[liq.value.state] ?? "plain");

function toneClass(tone: Tone): string {
  if (tone === "ok") return "badge--live";
  if (tone === "warn") return "badge--warn";
  if (tone === "up") return "badge--up";
  if (tone === "down") return "badge--down";
  if (tone === "accent") return "badge--accent";
  return "";
}

function runTone(status: string): string {
  return status === "ok" ? "badge--live" : status === "failed" ? "badge--up" : "badge--warn";
}

function runText(status: string): string {
  return status === "ok" ? "运行成功" : status === "failed" ? "运行失败" : "部分降级";
}

const historyRange = computed(() => {
  const months = historyMonths.value;
  if (!months.length) return "—";
  return `${months[0]} ~ ${months[months.length - 1]}`;
});

const chartHasData = computed(() => {
  const series = history.value?.series;
  if (!series || typeof series !== "object") return false;
  return Object.values(series).some((points) => (Array.isArray(points) ? points : []).some((point) => point !== null));
});

function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const chosen = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return chosen || fallback;
}

const CHART_COLORS: Record<string, string> = {
  DMI: "#F5A524",
  GROWTH: "#4CC2FF",
  INFLATION: "#F0544F",
  LIQUIDITY: "#2FBF71",
};

/** 序列语义色统一走 CSS 变量，保证深色 / 浅色主题下轨迹颜色一致可读。 */
const CHART_COLOR_VARS: Record<string, string> = {
  DMI: "--warn",
  GROWTH: "--accent",
  INFLATION: "--up",
  LIQUIDITY: "--down",
};

const chartOption = computed<EChartsOption>(() => {
  const months = historyMonths.value;
  const seriesData = (history.value?.series ?? {}) as Record<string, unknown>;
  const pointsOf = (key: string): Array<number | null> => {
    const raw = seriesData[key];
    return Array.isArray(raw) ? (raw as Array<number | null>) : [];
  };
  const keys = ["DMI", "GROWTH", "INFLATION", "LIQUIDITY"].filter((key) =>
    pointsOf(key).some((point) => point !== null),
  );
  return {
    grid: { left: 42, right: 16, top: 26, bottom: 28 },
    tooltip: {
      trigger: "axis",
      backgroundColor: cssVar("--surface-2", "#172030"),
      borderColor: cssVar("--border-strong", "#223047"),
      textStyle: { color: cssVar("--text", "#E6EDF5"), fontSize: 11 },
    },
    legend: {
      top: 2,
      left: 8,
      itemWidth: 10,
      itemHeight: 2,
      textStyle: { color: cssVar("--muted", "#93A4B8"), fontSize: 10 },
    },
    xAxis: {
      type: "category",
      data: months,
      axisLine: { lineStyle: { color: cssVar("--border", "rgba(148,163,184,.2)") } },
      axisLabel: {
        color: cssVar("--dim", "#64748B"),
        fontSize: 9,
        interval: Math.max(0, Math.floor(months.length / 6) - 1),
      },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: cssVar("--border", "rgba(148,163,184,.12)") } },
      axisLabel: { color: cssVar("--dim", "#64748B"), fontSize: 9 },
    },
    series: keys.map((key) => {
      const color = cssVar(CHART_COLOR_VARS[key] ?? "--accent", CHART_COLORS[key] ?? "#4CC2FF");
      return {
        name: key,
        type: "line" as const,
        data: pointsOf(key),
        smooth: true,
        connectNulls: false,
        showSymbol: false,
        lineStyle: { width: 1.6, color },
        itemStyle: { color },
      };
    }),
  };
});

async function recalc(): Promise<void> {
  if (running.value) return;
  running.value = true;
  recalcError.value = null;
  try {
    await runCycle();
    await refresh();
    void readingsPoll.refresh();
    void loadMeta();
  } catch (err) {
    // 重算失败只在行内提示，绝不整页消失
    recalcError.value = err instanceof Error ? err.message : String(err);
  } finally {
    running.value = false;
  }
}
</script>

<style scoped>
/* ── 页面骨架 ───────────────────────────────────────── */
.cyc-root {
  min-width: 0;
}
/* 数据自身生成时点：小字跟随标题，不展示系统当前时间 */
.cyc-generated {
  margin: -6px 2px 10px;
  font-size: 9.5px;
  color: var(--dim);
  font-family: var(--mono);
  letter-spacing: 0.2px;
}
/* 重算失败行内提示（不阻塞页面其余内容） */
.cyc-inline-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 2px 10px;
  padding: 6px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 8%, transparent);
  font-size: 10.5px;
  color: var(--warn);
}
.cyc-inline-error .ic {
  width: 13px;
  height: 13px;
  flex: none;
}
.cyc-inline-error span {
  flex: 1;
  min-width: 0;
}
.cyc-card-sub {
  font-size: 10px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-inline-link {
  text-decoration: none;
  color: var(--accent);
  font-weight: 500;
}
.cyc-caveat {
  margin: 6px 2px 0;
  font-size: 9.5px;
  color: var(--dim);
  line-height: 1.5;
}

/* ── A. Hero ────────────────────────────────────────── */
.cyc-hero {
  position: relative;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 13px 16px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background:
    radial-gradient(680px 200px at 92% -40%, var(--accent-weak), transparent 70%),
    linear-gradient(115deg, color-mix(in srgb, var(--accent) 5%, transparent), transparent 52%),
    var(--surface);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-bottom: 10px;
}
/* 设计稿 hero 右下角装饰圆环（纯装饰，不参与交互） */
.cyc-hero::after {
  content: "";
  position: absolute;
  right: -42px;
  bottom: -96px;
  width: 250px;
  height: 250px;
  border-radius: 50%;
  box-shadow:
    0 0 0 24px transparent,
    0 0 0 25px var(--border);
  pointer-events: none;
}
.cyc-hero-main {
  min-width: 0;
  flex: 1 1 auto;
}
.cyc-hero-eyebrow {
  font-size: 9.5px;
  letter-spacing: 1.4px;
  color: var(--dim);
  margin-bottom: 2px;
}
.cyc-hero-h1 {
  margin: 0;
  font-size: 21px;
  line-height: 1.28;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: var(--text);
}
.cyc-hero-sub {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.5;
}
.cyc-hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.cyc-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 23px;
  padding: 0 9px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10.5px;
  white-space: nowrap;
  max-width: 100%;
}
.cyc-tag b {
  font-family: var(--mono);
  font-weight: 600;
  color: var(--text);
}
.cyc-tag-z {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.cyc-tag-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--warn);
  flex: none;
}
.cyc-hero-badges {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: none;
  width: 176px;
  padding-top: 3px;
}
.cyc-meta-badge {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  height: 25px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: color-mix(in srgb, var(--surface-2) 72%, transparent);
  font-size: 9.5px;
  color: var(--dim);
}
.cyc-meta-badge b {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
}

/* ── B. row-2 ───────────────────────────────────────── */
.cyc-row2 {
  display: grid;
  grid-template-columns: minmax(0, 560px) minmax(0, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}

/* ── C. 关键读数 ────────────────────────────────────── */
.cyc-section-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 10px 2px 6px;
  font-size: 10px;
  color: var(--dim);
}
.cyc-section-label--retain {
  margin-top: 16px;
}
.cyc-sl-title {
  font-size: 10.5px;
  color: var(--muted);
  font-weight: 600;
  letter-spacing: 0.3px;
}
.cyc-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.cyc-kpi-card {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 80px;
  padding: 7px 10px 6px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow);
}
.cyc-kpi-card:hover {
  border-color: var(--border-strong);
}
.cyc-kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.cyc-kpi-label {
  font-size: 10.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-kpi-z {
  font-family: var(--mono);
  font-size: 8.5px;
  color: var(--dim);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 4px;
  line-height: 14px;
  white-space: nowrap;
}
.cyc-kpi-z--pos {
  color: var(--up);
  border-color: color-mix(in srgb, var(--up) 32%, transparent);
}
.cyc-kpi-z--neg {
  color: var(--down);
  border-color: color-mix(in srgb, var(--down) 32%, transparent);
}
.cyc-kpi-val {
  display: flex;
  align-items: baseline;
  gap: 3px;
  margin: 1px 0 2px;
  min-height: 26px;
}
.cyc-kpi-val b {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.4px;
  line-height: 1.1;
}
.cyc-kpi-unit {
  font-size: 10px;
  color: var(--muted);
}
.cyc-kpi-miss {
  margin-left: 4px;
  font-size: 8.5px;
  color: var(--warn);
  border: 1px solid color-mix(in srgb, var(--warn) 34%, transparent);
  border-radius: 4px;
  padding: 0 4px;
  line-height: 14px;
}
.cyc-kpi-chg {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 9.5px;
  white-space: nowrap;
}
.cyc-kpi-chg--up {
  color: var(--up);
}
.cyc-kpi-chg--down {
  color: var(--down);
}
.cyc-kpi-chg--flat {
  color: var(--dim);
}
.cyc-kpi-foot {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 6px;
  min-height: 22px;
}
.cyc-spark {
  flex: none;
  width: 116px;
  height: 22px;
  overflow: visible;
}
.cyc-kpi-note {
  font-size: 8.5px;
  color: var(--dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cyc-readings-fallback {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  font-size: 10.5px;
  color: var(--muted);
}
.cyc-readings-fallback-text {
  flex: 1 1 auto;
  min-width: 0;
}
.cyc-kpi-ev {
  flex: none;
  height: 15px;
  padding: 0 5px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--dim);
  font-size: 8px;
  line-height: 13px;
  letter-spacing: 0.2px;
  text-decoration: none;
  white-space: nowrap;
}
.cyc-kpi-ev:hover {
  color: var(--accent);
  border-color: var(--accent-line);
}

/* ── D. 今日预警 ────────────────────────────────────── */
.cyc-alerts {
  margin-top: 10px;
}
.cyc-alert-list {
  display: flex;
  flex-direction: column;
}
.cyc-alert-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 112px 72px 58px;
  gap: 10px;
  align-items: center;
  padding: 7px 12px;
  border-top: 1px dashed var(--border);
  min-height: 49px;
}
.cyc-alert-row:first-child {
  border-top: 0;
}
.cyc-sev {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 9.5px;
  font-weight: 600;
  white-space: nowrap;
}
.cyc-sev i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.cyc-sev--high {
  color: var(--up);
}
.cyc-sev--mid {
  color: var(--warn);
}
.cyc-sev--low {
  color: color-mix(in srgb, var(--warn) 78%, var(--text) 22%);
}
.cyc-sev--unknown {
  color: var(--dim);
}
.cyc-alert-main {
  min-width: 0;
}
.cyc-alert-title {
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.35;
}
.cyc-alert-cond {
  font-size: 9.8px;
  color: var(--muted);
  line-height: 1.4;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cyc-alert-val {
  text-align: right;
  min-width: 0;
}
.cyc-alert-val b {
  display: block;
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.cyc-alert-val span {
  display: block;
  font-family: var(--mono);
  font-size: 8.8px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-alert-meta {
  text-align: right;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.5;
  white-space: nowrap;
}
.cyc-alert-src {
  justify-self: end;
  text-decoration: none;
}

/* ── E. 历史类比 ────────────────────────────────────── */
.cyc-analogy-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.cyc-analogy {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  height: 62px;
  padding: 8px 12px;
  text-align: left;
  text-decoration: none;
  color: inherit;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow);
  transition: border-color 0.12s, background 0.12s, transform 0.12s;
}
.cyc-analogy:hover {
  border-color: var(--accent-line);
  background: color-mix(in srgb, var(--accent) 4%, var(--surface));
  transform: translateY(-1px);
}
.cyc-analogy--empty {
  cursor: default;
  border-style: dashed;
  opacity: 0.72;
}
.cyc-analogy--empty:hover {
  border-color: var(--border);
  background: var(--surface);
  transform: none;
}
.cyc-analogy-name {
  font-size: 11.5px;
  font-weight: 600;
}
.cyc-analogy-sub {
  font-size: 9.5px;
  color: var(--dim);
  margin-top: 2px;
}
.cyc-analogy-sim {
  text-align: right;
  flex: none;
}
.cyc-analogy-sim b {
  display: block;
  font-family: var(--mono);
  font-size: 17px;
  font-weight: 600;
  color: var(--accent);
  line-height: 1.1;
}
.cyc-analogy-sim span {
  font-size: 8.5px;
  color: var(--dim);
}

/* ── F. 保留区块 ────────────────────────────────────── */
.cyc-ov-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.cyc-ov-card {
  padding: 9px 11px 8px;
  min-height: 84px;
}
.cyc-ov-top {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cyc-ov-icon {
  display: inline-flex;
  color: var(--dim);
  flex: none;
}
.cyc-ov-icon svg {
  width: 14px;
  height: 14px;
}
.cyc-ov-label {
  font-size: 10.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
}
.cyc-ov-value {
  margin-top: 5px;
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
  line-height: 1.1;
}
.cyc-ov-value small {
  margin-left: 4px;
  font-family: var(--sans);
  font-size: 9.5px;
  color: var(--dim);
  font-weight: 500;
}
.cyc-ov-sub {
  margin-top: 4px;
  font-size: 9px;
  color: var(--dim);
  line-height: 1.45;
}
.cyc-retain-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
}
.cyc-six-body {
  display: grid;
  grid-template-columns: minmax(0, 220px) minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}
.cyc-six-svg {
  width: 100%;
  max-height: 240px;
}
.cyc-six-ring {
  fill: none;
  stroke: color-mix(in srgb, var(--muted) 18%, transparent);
  stroke-dasharray: 2 3;
}
.cyc-six-axis {
  stroke: color-mix(in srgb, var(--muted) 22%, transparent);
}
.cyc-six-shape {
  fill: color-mix(in srgb, var(--accent) 20%, transparent);
  stroke: var(--accent);
  stroke-width: 1.4;
}
.cyc-six-dot {
  fill: var(--accent);
}
.cyc-six-label {
  font-size: 8.5px;
  fill: var(--muted);
  font-family: var(--sans);
}
.cyc-six-center {
  font-size: 11px;
  fill: var(--text);
  font-weight: 600;
}
.cyc-six-center-sub {
  font-size: 8.5px;
  fill: var(--dim);
  font-family: var(--mono);
}
.cyc-six-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.cyc-six-legend-row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) 34px 32px;
  gap: 6px;
  align-items: center;
  font-size: 9px;
  color: var(--muted);
}
.cyc-six-legend-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-six-legend-bar {
  height: 5px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-six-legend-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
}
.cyc-six-legend-row b {
  font-size: 9px;
  text-align: right;
  color: var(--text);
}
.cyc-six-legend-row em {
  font-size: 8px;
  color: var(--dim);
  font-style: normal;
  text-align: right;
}
.cyc-layer-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cyc-layer-row {
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border);
}
.cyc-layer-row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
.cyc-layer-head {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.cyc-layer-name {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text);
}
.cyc-layer-val {
  margin-left: auto;
  font-size: 11px;
  color: var(--muted);
}
.cyc-layer-val small {
  margin-left: 2px;
  font-size: 8.5px;
  color: var(--dim);
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
.cyc-history-card {
  margin-top: 10px;
}
/* ── 结构性 / 人工观测透明度卡 ── */
.cyc-trans-card {
  margin-top: 10px;
}
/* 16 条人工观测全部展开，不套全站 table-wrap 的 411px 内部滚动 */
.cyc-trans-wrap {
  max-height: none;
}
.cyc-trans-table tbody td {
  height: auto;
  padding: 6px 10px;
  vertical-align: top;
}
.cyc-trans-name {
  font-weight: 600;
  white-space: normal;
}
.cyc-trans-id {
  font-size: 9px;
  color: var(--dim);
  font-weight: 400;
  letter-spacing: 0.2px;
}
.cyc-trans-unit {
  margin-left: 2px;
  font-size: 9px;
  color: var(--dim);
}
.cyc-trans-source {
  display: inline-block;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.4;
  vertical-align: bottom;
  color: var(--muted);
  font-size: 10px;
}
.cyc-trans-degraded {
  cursor: help;
}
.cyc-trans-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
}
.cyc-trans-legend {
  flex: 1 1 320px;
  font-size: 9.5px;
  line-height: 1.6;
  color: var(--dim);
}
.cyc-trans-legend b {
  color: var(--muted);
  font-weight: 600;
}
.cyc-bottom {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
  margin-top: 10px;
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
.cyc-sustain-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.cyc-sustain-risk {
  font-size: 9.5px;
  color: var(--muted);
}
.cyc-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}
.cyc-metric {
  padding: 7px 9px;
  border: 1px solid var(--border);
  border-radius: var(--radius-control);
  background: var(--surface-2);
}
.cyc-metric-label {
  display: block;
  font-size: 9px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-metric b {
  display: block;
  margin-top: 3px;
  font-size: 14px;
  color: var(--text);
}
.cyc-metric b small {
  margin-left: 2px;
  font-size: 8.5px;
  color: var(--dim);
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
.cyc-analog-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.cyc-analog-line {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) 34px minmax(0, 1.15fr);
  gap: 7px;
  align-items: center;
  font-size: 9px;
  color: var(--muted);
}
.cyc-analog-month {
  font-size: 9px;
}
.cyc-analog-sim-bar {
  height: 5px;
  border-radius: 99px;
  background: var(--surface-3);
  overflow: hidden;
}
.cyc-analog-sim-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
}
.cyc-analog-line b {
  font-size: 9.5px;
  text-align: right;
  color: var(--text);
}
.cyc-analog-state {
  font-size: 8.5px;
  color: var(--dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cyc-degraded-box {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  margin-top: 10px;
  padding: 9px 12px;
  border: 1px solid color-mix(in srgb, var(--warn) 38%, transparent);
  border-radius: var(--radius-card);
  background: color-mix(in srgb, var(--warn) 8%, var(--surface));
  font-size: 10px;
  color: var(--muted);
}
.cyc-degraded-box .ic {
  color: var(--warn);
  flex: none;
}
.cyc-degraded-box b {
  color: var(--text);
  font-size: 10.5px;
}
.cyc-degraded-reason {
  margin-top: 3px;
  font-size: 9.5px;
  color: var(--dim);
}
.cyc-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 12px;
  padding: 8px 2px 4px;
  border-top: 1px dashed var(--border);
  font-size: 8.5px;
  color: var(--dim);
}
.spin {
  animation: cyc-spin 1s linear infinite;
}
@keyframes cyc-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── 响应式 ─────────────────────────────────────────── */
@media (max-width: 1279px) {
  .cyc-row2 {
    grid-template-columns: minmax(0, 1fr);
  }
  .cyc-ov-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .cyc-retain-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .cyc-bottom {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 1023px) {
  .cyc-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .cyc-hero {
    flex-direction: column;
    gap: 10px;
  }
  .cyc-hero-badges {
    flex-direction: row;
    flex-wrap: wrap;
    width: 100%;
    padding-top: 0;
  }
  .cyc-meta-badge {
    flex: 1 1 140px;
    justify-content: space-between;
  }
  .cyc-alert-row {
    grid-template-columns: 40px minmax(0, 1fr) 100px 66px;
  }
  .cyc-alert-src {
    display: none;
  }
  .cyc-six-body {
    grid-template-columns: minmax(0, 1fr);
  }
  .cyc-six-svg {
    max-height: 220px;
  }
}
@media (max-width: 759px) {
  .cyc-kpi-grid,
  .cyc-ov-grid,
  .cyc-analogy-row {
    grid-template-columns: minmax(0, 1fr);
  }
  .cyc-alert-row {
    grid-template-columns: 40px minmax(0, 1fr) 100px;
  }
  .cyc-alert-meta {
    display: none;
  }
  .cyc-metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .cyc-hero-h1 {
    font-size: 18px;
  }
}
</style>
