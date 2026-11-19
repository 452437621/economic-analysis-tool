<template>
  <div class="view active lens-view">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">
          专题 · 双透镜
          <template v-if="state?.asof"> · 数据截至 {{ fmtDate(state.asof) }}</template>
          <template v-if="state?.config_version"> · 配置 v{{ state.config_version }}</template>
        </div>
        <h1 class="page-h1">
          双透镜研判
          <span class="page-sub">美联储主席一脉的反应函数 × 宋鸿兵的美元环流与债务货币化</span>
        </h1>
        <span v-if="state?.run" class="gen-at">
          运行 {{ state.run.status }} · 耗时 {{ state.run.duration_ms ?? "—" }} ms ·
          置信度 {{ fmtRatioPct(state.confidence) }} · 证据 {{ state.evidence_grade }}
        </span>
      </div>
      <div class="page-actions">
        <span v-if="state?.run?.degraded" class="badge badge--warn badge--sm">降级运行</span>
        <button class="btn btn--sm btn--primary" type="button" :disabled="running" @click="runNow()">
          <svg class="ic" :class="{ spin: running }"><use href="#i-refresh" /></svg>
          {{ running ? "重算中" : "重算双透镜" }}
        </button>
        <button class="btn btn--sm btn--ghost" type="button" :disabled="loading" @click="reload()">
          <svg class="ic" :class="{ spin: loading }"><use href="#i-refresh" /></svg>刷新
        </button>
      </div>
    </div>

    <div v-if="state?.disclaimer" class="lens-disclaimer">
      <svg class="ic"><use href="#i-shield-check" /></svg>
      <span>{{ state.disclaimer }}</span>
    </div>

    <template v-if="!state && loading">
      <div class="lens-stats">
        <section v-for="i in 4" :key="i" class="card lens-stat">
          <SkeletonBlock :rows="2" :cells="2" :height="18" />
        </section>
      </div>
      <section class="card"><div class="card-body"><SkeletonBlock :rows="8" :cells="6" :height="14" /></div></section>
    </template>

    <section v-else-if="!state" class="card">
      <ErrorState :error="error" @retry="bootstrap()" />
      <div class="lens-empty-hint">
        首次打开需要先运行一次双透镜；点击「重算双透镜」或上方重试。
      </div>
    </section>

    <template v-else>
      <!-- 四张总览卡 -->
      <div class="lens-stats">
        <section class="card lens-stat">
          <div class="lens-stat-label">美联储立场</div>
          <div class="lens-stat-value">
            {{ state.fed.state.stance ?? "—" }}<small>/100</small>
          </div>
          <div class="lens-stat-meta">
            <span class="badge badge--sm" :class="stanceBadge">{{ state.fed.state.stance_label }}</span>
            <span class="mono">{{ state.fed.state.regime.label }}</span>
          </div>
          <div class="lens-bar"><i :style="{ width: `${state.fed.state.stance ?? 0}%` }"></i></div>
        </section>

        <section class="card lens-stat">
          <div class="lens-stat-label">美元环流</div>
          <div class="lens-stat-value lens-stat-value--text">{{ state.song.state.phase.label }}</div>
          <div class="lens-stat-meta">
            <span class="badge badge--sm" :class="heartBadge">{{ state.song.state.dollar_heart.label }}</span>
            <span class="mono">{{ state.song.state.dollar_heart.level_bp ?? "—" }}bp</span>
          </div>
          <div class="lens-stat-note">{{ state.song.state.phase.note }}</div>
        </section>

        <section class="card lens-stat">
          <div class="lens-stat-label">黄金状态</div>
          <div class="lens-stat-value lens-stat-value--text" :class="goldClass">
            {{ state.song.state.gold_regime.label }}
          </div>
          <div class="lens-stat-meta">
            <span class="mono">收割 {{ state.song.state.harvest_risk ?? "—" }}</span>
            <span class="mono">债务 {{ state.song.state.debt_risk ?? "—" }}</span>
          </div>
          <div class="lens-stat-note">{{ state.song.state.gold_regime.note }}</div>
        </section>

        <section class="card lens-stat">
          <div class="lens-stat-label">双镜合成</div>
          <div class="lens-stat-value">
            {{ state.synthesis.consensus_count }}<small>项共振</small>
          </div>
          <div class="lens-stat-meta">
            <span class="badge badge--sm">{{ state.synthesis.divergences.length }} 项分歧</span>
            <span class="mono">{{ state.synthesis.outlook.horizon_days }} 天</span>
          </div>
          <div class="lens-stat-note">{{ state.synthesis.narrative }}</div>
        </section>
      </div>

      <div class="lens-tabs">
        <button
          v-for="tab in TABS"
          :key="tab.id"
          class="lens-tab"
          :class="{ active: activeTab === tab.id }"
          type="button"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
          <span v-if="tab.id === 'evidence'" class="lens-tab-count">
            {{ firedCount }}/{{ totalRules }}
          </span>
        </button>
      </div>

      <!-- 合成研判 -->
      <template v-if="activeTab === 'synthesis'">
        <section class="card lens-card">
          <div class="card-head">
            <span class="card-title">七类资产 · 两镜共振表</span>
            <span class="spacer"></span>
            <span class="lens-muted">综合分 −2…+2；方向按 |共识| ≥ 0.25 判定</span>
          </div>
          <div class="lens-table-wrap">
            <table class="lens-table">
              <thead>
                <tr>
                  <th>资产</th><th>最新</th><th>美联储</th><th>宋鸿兵</th>
                  <th>共识</th><th>一致度</th><th>方向</th><th>胜率</th><th>操作建议</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="asset in state.synthesis.assets" :key="asset.id">
                  <td>
                    <div class="lens-asset-name">{{ asset.label }}</div>
                    <div class="lens-muted mono">{{ asset.symbol }}</div>
                  </td>
                  <td class="mono">{{ fmtNumber(asset.last, priceDigits(asset.last)) }}</td>
                  <td class="mono" :class="scoreClass(asset.fed)">{{ fmtSigned(asset.fed) }}</td>
                  <td class="mono" :class="scoreClass(asset.song)">{{ fmtSigned(asset.song) }}</td>
                  <td>
                    <div class="lens-score-cell">
                      <span class="mono" :class="scoreClass(asset.consensus)">{{ fmtSigned(asset.consensus) }}</span>
                      <div class="lens-score-bar">
                        <i :class="scoreClass(asset.consensus)"
                           :style="{ width: `${Math.min(50, Math.abs(asset.consensus ?? 0) * 25)}%`, [asset.consensus && asset.consensus < 0 ? 'right' : 'left']: '50%' }"></i>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span class="badge badge--sm" :class="agreementClass(asset.agreement)">{{ asset.agreement }}</span>
                  </td>
                  <td>
                    <span class="lens-dir" :class="`lens-dir--${asset.direction}`">
                      {{ asset.direction === "up" ? "看涨" : asset.direction === "down" ? "看跌" : "震荡" }}
                    </span>
                  </td>
                  <td class="mono">{{ fmtRatioPct(asset.probability) }}</td>
                  <td class="lens-advice">{{ asset.advice }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <div class="lens-grid lens-grid--2">
          <section class="card lens-card">
            <div class="card-head"><span class="card-title">预警与触发器</span></div>
            <div class="card-body">
              <ul v-if="state.synthesis.warnings.length" class="lens-list">
                <li v-for="w in state.synthesis.warnings" :key="w.id">
                  <span class="lens-sev" :class="`lens-sev--${w.severity}`"></span>
                  <div>
                    <div class="lens-list-title">{{ w.title }}</div>
                    <div class="lens-muted">{{ w.detail }}</div>
                  </div>
                </li>
              </ul>
              <EmptyState v-else text="当前没有触发预警" hint="规则命中会在这里出现；预警是条件成立，不是方向保证。" />
            </div>
          </section>

          <section class="card lens-card">
            <div class="card-head"><span class="card-title">分歧清单</span></div>
            <div class="card-body">
              <ul v-if="state.synthesis.divergences.length" class="lens-list">
                <li v-for="d in state.synthesis.divergences" :key="d.asset">
                  <div>
                    <div class="lens-list-title">
                      {{ d.label }}
                      <span class="mono lens-muted">差 {{ fmtSigned(d.spread) }}</span>
                    </div>
                    <div class="lens-muted">{{ d.reading }}；催化剂：{{ d.catalyst }}</div>
                  </div>
                </li>
              </ul>
              <EmptyState
                v-else
                text="两镜当前没有明显分歧"
                hint="没有分歧时以共振项为仓位来源；出现分歧时单一透镜的结论只能做研究。"
              />
            </div>
          </section>
        </div>

        <section class="card lens-card">
          <div class="card-head"><span class="card-title">未来 {{ state.synthesis.outlook.horizon_days }} 天情景</span></div>
          <div class="card-body lens-outlook">
            <div class="lens-outlook-col">
              <div class="lens-outlook-label">基准</div>
              <p>{{ state.synthesis.outlook.base_case }}</p>
            </div>
            <div class="lens-outlook-col lens-outlook--up">
              <div class="lens-outlook-label">上行风险</div>
              <p>{{ state.synthesis.outlook.bull_case }}</p>
            </div>
            <div class="lens-outlook-col lens-outlook--down">
              <div class="lens-outlook-label">下行风险</div>
              <p>{{ state.synthesis.outlook.bear_case }}</p>
            </div>
          </div>
          <div class="card-body lens-invalidators">
            <div class="lens-outlook-label">失效条件</div>
            <ul>
              <li v-for="item in state.synthesis.outlook.invalidators" :key="item">{{ item }}</li>
            </ul>
          </div>
        </section>

        <section v-if="cycle" class="card lens-card">
          <div class="card-head"><span class="card-title">周期引擎上下文</span></div>
          <div class="card-body lens-cycle">
            <div><span class="lens-muted">长周期</span><strong>{{ cycle.long_cycle?.phase ?? "—" }}</strong><span class="lens-muted">{{ cycle.long_cycle?.meaning }}</span></div>
            <div><span class="lens-muted">短周期</span><strong>{{ cycle.short_cycle?.state_name ?? cycle.short_cycle?.state ?? "—" }}</strong></div>
            <div><span class="lens-muted">流动性</span><strong>{{ cycle.liquidity?.state ?? "—" }}</strong><span class="mono">{{ cycle.liquidity?.value ?? "—" }}</span></div>
            <div><span class="lens-muted">政治窗口</span><strong>{{ cycle.political?.window ?? "—" }}</strong></div>
          </div>
        </section>
      </template>

      <!-- 美联储透镜 -->
      <template v-else-if="activeTab === 'fed'">
        <div class="lens-grid lens-grid--3">
          <section class="card lens-card">
            <div class="card-head"><span class="card-title">政策立场</span></div>
            <div class="card-body">
              <div class="lens-big">{{ state.fed.state.stance ?? "—" }}<small>/100 {{ state.fed.state.stance_label }}</small></div>
              <div class="lens-bar lens-bar--lg"><i :style="{ width: `${state.fed.state.stance ?? 0}%` }"></i></div>
              <ul class="lens-components">
                <li v-for="c in state.fed.state.stance_components" :key="c.label">
                  <span>{{ c.label }}</span>
                  <span class="mono">{{ fmtRatioPct(c.percentile) }}</span>
                  <span class="lens-muted">权重 {{ c.weight }}</span>
                </li>
              </ul>
            </div>
          </section>

          <section class="card lens-card">
            <div class="card-head"><span class="card-title">经济象限与看跌期权</span></div>
            <div class="card-body">
              <div class="lens-kv"><span>象限</span><strong>{{ state.fed.state.regime.label }}</strong></div>
              <p class="lens-muted">{{ state.fed.state.regime.note }}</p>
              <div class="lens-kv"><span>Fed Put</span><strong>{{ state.fed.state.fed_put.label }}</strong></div>
              <p class="lens-muted">{{ state.fed.state.fed_put.note }}</p>
              <div class="lens-kv"><span>行权 / 现价</span><span class="mono">{{ fmtNumber(state.fed.state.fed_put.strike, 0) }} / {{ fmtNumber(state.fed.state.fed_put.spot, 0) }}</span></div>
              <div class="lens-kv"><span>距离行权</span><span class="mono">{{ fmtRatioPct(state.fed.state.fed_put.distance_pct) }}</span></div>
              <div class="lens-kv"><span>政策倾向</span><span>{{ state.fed.state.policy.bias }} · 3 个月降息概率 {{ fmtRatioPct(state.fed.state.policy.cut_probability_3m) }}</span></div>
            </div>
          </section>

          <section class="card lens-card">
            <div class="card-head"><span class="card-title">资产评分（美联储透镜）</span></div>
            <div class="card-body">
              <div v-for="[id, score] in fedScores" :key="id" class="lens-score-row">
                <div class="lens-score-row-head">
                  <span>{{ assetLabel(id) }}</span>
                  <span class="mono" :class="scoreClass(score.score)">{{ fmtSigned(score.score) }} {{ score.label }}</span>
                </div>
                <div class="lens-score-bar lens-score-bar--wide">
                  <i :class="scoreClass(score.score)" :style="{ width: `${Math.min(50, Math.abs(score.score ?? 0) * 25)}%`, [score.score && score.score < 0 ? 'right' : 'left']: '50%' }"></i>
                </div>
                <div class="lens-muted">{{ score.why }}</div>
              </div>
            </div>
          </section>
        </div>

        <section class="card lens-card">
          <div class="card-head"><span class="card-title">美联储读数（{{ state.fed.coverage.available }}/{{ state.fed.coverage.total }}）</span></div>
          <div class="card-body">
            <div class="lens-readings">
              <div v-for="r in state.fed.readings" :key="r.id" class="lens-reading" :class="{ 'is-missing': r.value === null }">
                <div class="lens-reading-label">{{ r.label }}</div>
                <div class="lens-reading-value mono">
                  {{ r.value === null ? "缺失" : fmtNumber(r.value, r.digits) }}<small>{{ r.value === null ? "" : r.unit }}</small>
                </div>
                <div v-if="r.value !== null" class="lens-reading-meta">
                  <span :class="trendClass(r.change)" class="mono">{{ fmtSigned(r.change, r.digits) }} {{ r.change_label }}</span>
                  <span class="mono">z {{ fmtSigned(r.z) }}</span>
                  <span class="mono">分位 {{ fmtRatioPct(r.percentile) }}</span>
                </div>
                <div v-else class="lens-reading-meta lens-muted">{{ r.missing_reason }}</div>
                <div class="lens-reading-source">
                  <span class="badge badge--sm">{{ r.evidence }}</span>
                  <span class="lens-muted">{{ r.note || r.source }}</span>
                </div>
              </div>
            </div>
            <p class="lens-narrative">{{ state.fed.state.narrative }}</p>
          </div>
        </section>
      </template>

      <!-- 宋鸿兵透镜 -->
      <template v-else-if="activeTab === 'song'">
        <div class="lens-grid lens-grid--3">
          <section class="card lens-card">
            <div class="card-head"><span class="card-title">美元环流</span></div>
            <div class="card-body">
              <div class="lens-big">{{ state.song.state.phase.label }}</div>
              <p class="lens-muted">{{ state.song.state.phase.note }}</p>
              <div class="lens-kv"><span>美元心脏</span><strong>{{ state.song.state.dollar_heart.label }}</strong></div>
              <div class="lens-kv"><span>SOFR−EFFR</span><span class="mono">{{ state.song.state.dollar_heart.level_bp ?? "—" }}bp / 脉冲 {{ state.song.state.dollar_heart.spike_bp ?? "—" }}bp</span></div>
              <p class="lens-muted">{{ state.song.state.dollar_heart.note }}</p>
            </div>
          </section>

          <section class="card lens-card">
            <div class="card-head"><span class="card-title">风险温度</span></div>
            <div class="card-body">
              <div class="lens-risk">
                <div class="lens-kv"><span>收割风险</span><span class="mono">{{ state.song.state.harvest_risk ?? "—" }}/100</span></div>
                <div class="lens-bar lens-bar--risk"><i :style="{ width: `${state.song.state.harvest_risk ?? 0}%` }"></i></div>
              </div>
              <div class="lens-risk">
                <div class="lens-kv"><span>债务货币化风险</span><span class="mono">{{ state.song.state.debt_risk ?? "—" }}/100</span></div>
                <div class="lens-bar lens-bar--risk"><i :style="{ width: `${state.song.state.debt_risk ?? 0}%` }"></i></div>
              </div>
              <div class="lens-kv"><span>黄金状态</span><strong>{{ state.song.state.gold_regime.label }}</strong></div>
              <p class="lens-muted">{{ state.song.state.gold_regime.note }}</p>
            </div>
          </section>

          <section class="card lens-card">
            <div class="card-head"><span class="card-title">资产评分（宋鸿兵透镜）</span></div>
            <div class="card-body">
              <div v-for="[id, score] in songScores" :key="id" class="lens-score-row">
                <div class="lens-score-row-head">
                  <span>{{ assetLabel(id) }}</span>
                  <span class="mono" :class="scoreClass(score.score)">{{ fmtSigned(score.score) }} {{ score.label }}</span>
                </div>
                <div class="lens-score-bar lens-score-bar--wide">
                  <i :class="scoreClass(score.score)" :style="{ width: `${Math.min(50, Math.abs(score.score ?? 0) * 25)}%`, [score.score && score.score < 0 ? 'right' : 'left']: '50%' }"></i>
                </div>
                <div class="lens-muted">{{ score.why }}</div>
              </div>
            </div>
          </section>
        </div>

        <section class="card lens-card">
          <div class="card-head"><span class="card-title">宋鸿兵读数（{{ state.song.coverage.available }}/{{ state.song.coverage.total }}）</span></div>
          <div class="card-body">
            <div class="lens-readings">
              <div v-for="r in state.song.readings" :key="r.id" class="lens-reading" :class="{ 'is-missing': r.value === null }">
                <div class="lens-reading-label">{{ r.label }}</div>
                <div class="lens-reading-value mono">
                  {{ r.value === null ? "缺失" : fmtNumber(r.value, r.digits) }}<small>{{ r.value === null ? "" : r.unit }}</small>
                </div>
                <div v-if="r.value !== null" class="lens-reading-meta">
                  <span :class="trendClass(r.change)" class="mono">{{ fmtSigned(r.change, r.digits) }} {{ r.change_label }}</span>
                  <span class="mono">z {{ fmtSigned(r.z) }}</span>
                  <span class="mono">分位 {{ fmtRatioPct(r.percentile) }}</span>
                </div>
                <div v-else class="lens-reading-meta lens-muted">{{ r.missing_reason }}</div>
                <div class="lens-reading-source">
                  <span class="badge badge--sm">{{ r.evidence }}</span>
                  <span class="lens-muted">{{ r.note || r.source }}</span>
                </div>
              </div>
            </div>
            <p class="lens-narrative">{{ state.song.state.narrative }}</p>
          </div>
        </section>
      </template>

      <!-- 宏观层 / 微观层 -->
      <template v-else-if="activeTab === 'layers'">
        <div v-if="!state.macro && !state.micro" class="card lens-card">
          <EmptyState text="尚无宏观/微观层推导" hint="点击「重算双透镜」生成宏观层与微观层。" />
        </div>
        <div v-else class="lens-grid lens-grid--2">
          <section v-if="state.macro" class="card lens-card">
            <div class="card-head">
              <span class="card-title">宏观层 · 象限与流动性</span>
              <span class="spacer"></span>
              <span class="badge badge--sm">{{ state.macro.coverage.available }}/{{ state.macro.coverage.total }}</span>
            </div>
            <div class="card-body">
              <div class="lens-big">{{ state.macro.state.regime.label }}</div>
              <p class="lens-muted">{{ state.macro.state.regime.note }}</p>
              <div class="lens-kv"><span>净流动性 13 周</span><strong class="mono">{{ state.macro.state.liquidity.value ?? "—" }}% {{ state.macro.state.liquidity.label }}</strong></div>
              <div class="lens-kv"><span>财政脉冲（TTM 赤字/GDP）</span><strong class="mono">{{ state.macro.state.fiscal.value ?? "—" }}% {{ state.macro.state.fiscal.label }}</strong></div>
              <div class="lens-kv"><span>融资紧张度</span><strong class="mono">{{ state.macro.state.funding.value ?? "—" }}bp {{ state.macro.state.funding.label }}</strong></div>
              <div v-if="state.macro.state.flags.length" class="lens-flags">
                <span v-for="flag in state.macro.state.flags" :key="flag" class="badge badge--warn badge--sm">{{ flag }}</span>
              </div>
              <p class="lens-narrative">{{ state.macro.state.narrative }}</p>
              <div class="lens-score-grid">
                <div v-for="[id, score] in macroScores" :key="id" class="lens-score-row">
                  <div class="lens-score-row-head">
                    <span>{{ assetLabel(id) }}</span>
                    <span class="mono" :class="scoreClass(score.score)">{{ fmtSigned(score.score) }} {{ score.label }}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section v-if="state.micro" class="card lens-card">
            <div class="card-head">
              <span class="card-title">微观层 · 价格结构与实物紧张</span>
              <span class="spacer"></span>
              <span class="badge badge--sm">{{ state.micro.coverage.available }}/{{ state.micro.coverage.total }}</span>
            </div>
            <div class="card-body">
              <div class="lens-big">{{ state.micro.state.risk_appetite.label }}</div>
              <div class="lens-kv"><span>黄金微观评分</span><strong class="mono" :class="scoreClass(state.micro.state.gold_micro)">{{ fmtSigned(state.micro.state.gold_micro) }}</strong></div>
              <div v-if="state.micro.state.crowding.length" class="lens-flags">
                <span v-for="flag in state.micro.state.crowding" :key="flag" class="badge badge--warn badge--sm">{{ flag }}</span>
              </div>
              <p class="lens-narrative">{{ state.micro.state.narrative }}</p>
              <div class="lens-score-grid">
                <div v-for="[id, score] in microScores" :key="id" class="lens-score-row">
                  <div class="lens-score-row-head">
                    <span>{{ assetLabel(id) }}</span>
                    <span class="mono" :class="scoreClass(score.score)">{{ fmtSigned(score.score) }} {{ score.label }}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <section v-if="macroLayer" class="card lens-card">
          <div class="card-head"><span class="card-title">宏观层读数（{{ macroLayer.coverage.available }}/{{ macroLayer.coverage.total }}）</span></div>
          <div class="card-body">
            <div class="lens-readings">
              <div v-for="r in macroLayer.readings" :key="r.id" class="lens-reading" :class="{ 'is-missing': r.value === null }">
                <div class="lens-reading-label">{{ r.label }}</div>
                <div class="lens-reading-value mono">
                  {{ r.value === null ? "缺失" : fmtNumber(r.value, r.digits) }}<small>{{ r.value === null ? "" : r.unit }}</small>
                </div>
                <div class="lens-reading-source"><span class="badge badge--sm">{{ r.evidence }}</span><span class="lens-muted">{{ r.note || r.source }}</span></div>
              </div>
            </div>
          </div>
        </section>

        <section v-if="microLayer" class="card lens-card">
          <div class="card-head"><span class="card-title">微观层读数（{{ microLayer.coverage.available }}/{{ microLayer.coverage.total }}）</span></div>
          <div class="card-body">
            <div class="lens-readings">
              <div v-for="r in microLayer.readings" :key="r.id" class="lens-reading" :class="{ 'is-missing': r.value === null }">
                <div class="lens-reading-label">{{ r.label }}</div>
                <div class="lens-reading-value mono">
                  {{ r.value === null ? "缺失" : fmtNumber(r.value, r.digits) }}<small>{{ r.value === null ? "" : r.unit }}</small>
                </div>
                <div class="lens-reading-source"><span class="badge badge--sm">{{ r.evidence }}</span><span class="lens-muted">{{ r.note || r.source }}</span></div>
              </div>
            </div>
          </div>
        </section>
      </template>

      <!-- 人物透镜 -->
      <template v-else-if="activeTab === 'personas'">
        <div v-if="!state.personas.length" class="card lens-card">
          <EmptyState text="尚无人物透镜" hint="确认 config/personas/*.yaml 存在后重算。" />
        </div>
        <div v-else class="lens-grid lens-grid--3">
          <section v-for="persona in state.personas" :key="persona.id" class="card lens-card">
            <div class="card-head">
              <span class="card-title">{{ persona.name }}</span>
              <span class="spacer"></span>
              <span class="badge badge--sm" :class="persona.state.lean.score >= 0 ? 'badge--up' : 'badge--warn'">
                {{ persona.state.lean.label }} {{ fmtSigned(persona.state.lean.score) }}
              </span>
            </div>
            <div class="card-body">
              <div class="lens-muted">{{ persona.title }}</div>
              <div class="lens-muted">{{ persona.school }}</div>
              <div class="lens-kv"><span>覆盖率</span><span class="mono">{{ persona.state.coverage.available }}/{{ persona.state.coverage.total }}</span></div>
              <div class="lens-kv"><span>命中规则</span><span class="mono">{{ persona.state.fired_rules.length }} 条</span></div>
              <div v-if="persona.state.fired_rules.length" class="lens-flags">
                <span v-for="ruleId in persona.state.fired_rules" :key="ruleId" class="badge badge--warn badge--sm">{{ ruleId }}</span>
              </div>
              <p class="lens-muted">{{ persona.state.narrative }}</p>
            </div>
          </section>
        </div>

        <section class="card lens-card">
          <div class="card-head"><span class="card-title">人物评分矩阵</span><span class="spacer"></span><span class="lens-muted">{{ personaMatrix.length }} 套透镜 × {{ matrixAssets.length }} 类资产</span></div>
          <div class="card-body lens-table-wrap">
            <table class="lens-table">
              <thead>
                <tr>
                  <th>透镜</th>
                  <th>倾向</th>
                  <th v-for="asset in matrixAssets" :key="asset.id">{{ asset.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in personaMatrix" :key="row.id">
                  <td>{{ row.name }}</td>
                  <td class="mono" :class="scoreClass(row.lean)">{{ fmtSigned(row.lean) }}</td>
                  <td v-for="asset in matrixAssets" :key="asset.id" class="mono" :class="scoreClass(row.scores[asset.id] ?? null)">
                    {{ row.scores[asset.id] === undefined ? "—" : fmtSigned(row.scores[asset.id] ?? null) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <!-- 规则与证据 -->
      <template v-else>
        <div class="lens-grid lens-grid--2">
          <section class="card lens-card">
            <div class="card-head"><span class="card-title">数据缺口</span><span class="spacer"></span><span class="lens-muted">{{ state.data_gaps.length }} 项</span></div>
            <div class="card-body">
              <ul class="lens-list lens-list--gaps">
                <li v-for="gap in state.data_gaps" :key="gap.id">
                  <span class="badge badge--warn badge--sm">{{ gap.id }}</span>
                  <div>
                    <div class="lens-list-title">{{ gap.label }}</div>
                    <div class="lens-muted">{{ gap.reason }} · {{ gap.impact }}</div>
                  </div>
                </li>
              </ul>
            </div>
          </section>

          <section class="card lens-card">
            <div class="card-head"><span class="card-title">推导谱系</span></div>
            <div class="card-body">
              <div v-for="row in derivationRows" :key="row.code" class="lens-deriv">
                <div class="lens-kv">
                  <span class="mono">{{ row.code }}</span>
                  <span class="mono lens-muted">{{ row.method_id }}</span>
                </div>
                <div class="lens-muted">{{ row.claim }}</div>
                <div class="lens-deriv-links">
                  <span class="badge badge--sm">{{ row.evidence_grade }}</span>
                  <span class="mono">置信 {{ fmtRatioPct(row.confidence) }}</span>
                  <RouterLink class="lens-link" :to="`/pipeline?code=${row.code}`">证据抽屉 →</RouterLink>
                </div>
              </div>
            </div>
          </section>
        </div>

        <section class="card lens-card">
          <div class="card-head">
            <span class="card-title">美联储规则 F1–F12</span>
            <span class="spacer"></span>
            <span class="lens-muted">命中 {{ fired.fed }} / {{ state.rules.fed.length }}</span>
          </div>
          <div class="lens-table-wrap">
            <table class="lens-table lens-table--rules">
              <thead><tr><th>规则</th><th>状态</th><th>条件</th><th>失效条件</th></tr></thead>
              <tbody>
                <tr v-for="rule in state.rules.fed" :key="rule.id" :class="`is-${rule.status}`">
                  <td><div class="lens-rule-id mono">{{ rule.id }}</div><div class="lens-muted">{{ rule.name }}</div></td>
                  <td><span class="lens-status" :class="`lens-status--${rule.status}`">{{ statusText(rule.status) }}</span></td>
                  <td>
                    <div>{{ rule.message }}</div>
                    <div v-if="rule.trace?.length" class="lens-trace mono">
                      <div v-for="t in rule.trace" :key="t.condition" :class="{ met: t.met }">{{ t.met ? "✓" : "✗" }} {{ t.condition }}</div>
                    </div>
                  </td>
                  <td class="lens-muted">{{ rule.falsifier || "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card lens-card">
          <div class="card-head">
            <span class="card-title">宋鸿兵规则 S1–S13</span>
            <span class="spacer"></span>
            <span class="lens-muted">命中 {{ fired.song }} / {{ state.rules.song.length }}</span>
          </div>
          <div class="lens-table-wrap">
            <table class="lens-table lens-table--rules">
              <thead><tr><th>规则</th><th>状态</th><th>条件</th><th>失效条件</th></tr></thead>
              <tbody>
                <tr v-for="rule in state.rules.song" :key="rule.id" :class="`is-${rule.status}`">
                  <td><div class="lens-rule-id mono">{{ rule.id }}</div><div class="lens-muted">{{ rule.name }}</div></td>
                  <td><span class="lens-status" :class="`lens-status--${rule.status}`">{{ statusText(rule.status) }}</span></td>
                  <td>
                    <div>{{ rule.message }}</div>
                    <div v-if="rule.trace?.length" class="lens-trace mono">
                      <div v-for="t in rule.trace" :key="t.condition" :class="{ met: t.met }">{{ t.met ? "✓" : "✗" }} {{ t.condition }}</div>
                    </div>
                  </td>
                  <td class="lens-muted">{{ rule.falsifier || "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <!-- 预测登记 -->
      <section class="card lens-card">
        <div class="card-head">
          <span class="card-title">研判登记（进入预测台账）</span>
          <span class="spacer"></span>
          <span class="lens-muted">code 前缀 lens.*；到期按标的收盘对账</span>
        </div>
        <div class="card-body">
          <div class="lens-form">
            <label>资产
              <select v-model="form.asset">
                <option v-for="asset in state.synthesis.assets" :key="asset.id" :value="asset.id">
                  {{ asset.label }}
                </option>
              </select>
            </label>
            <label>方向
              <select v-model="form.direction">
                <option value="up">看涨</option>
                <option value="down">看跌</option>
                <option value="flat">震荡</option>
              </select>
            </label>
            <label>期限
              <select v-model.number="form.horizon_days">
                <option :value="21">21 天</option>
                <option :value="63">63 天</option>
                <option :value="126">126 天</option>
              </select>
            </label>
            <label>概率
              <input v-model.number="form.probability" type="number" min="0" max="1" step="0.01" />
            </label>
            <label class="lens-form-wide">备注
              <input v-model="form.notes" type="text" maxlength="200" placeholder="写下你的依据与失效条件" />
            </label>
            <button class="btn btn--sm btn--ghost" type="button" :disabled="submitting" @click="submitForecast()">
              {{ submitting ? "登记中" : "登记预测" }}
            </button>
          </div>

          <div v-if="forecasts.length" class="lens-forecast-list">
            <div v-for="row in forecasts" :key="row.id" class="lens-forecast">
              <span class="badge badge--sm" :class="`lens-dir--${row.direction}`">{{ dirText(row.direction) }}</span>
              <span>{{ assetLabel(row.asset) }}</span>
              <span class="mono">目标 {{ row.target_date ?? "—" }}</span>
              <span class="mono">p {{ fmtRatioPct(row.probability) }}</span>
              <span class="badge badge--sm">{{ row.status === "open" ? "待验证" : row.status }}</span>
            </div>
          </div>
          <EmptyState v-else text="还没有登记研判" hint="登记后进入统一预测台账；到期由台账按标的收盘价（长债按 30 年期收益率）结算，形成可校准记录。" />
        </div>
      </section>

      <!-- AI 解读 -->
      <section class="card lens-card">
        <div class="card-head">
          <span class="card-title">AI 解读（可选）</span>
          <span class="spacer"></span>
          <span class="badge badge--sm" :class="ping?.available ? 'badge--up' : 'badge--warn'">
            {{ ping?.available ? `LLM 可用 · ${ping.model}` : "LLM 未配置" }}
          </span>
        </div>
        <div class="card-body">
          <div class="lens-form">
            <label class="lens-form-wide">问题
              <input v-model="question" type="text" maxlength="200" placeholder="不填则让模型给当前状态做 300 字解读" />
            </label>
            <button class="btn btn--sm" type="button" :disabled="commentLoading || !ping?.available" @click="askAI()">
              {{ commentLoading ? "生成中" : "生成解读" }}
            </button>
          </div>
          <p v-if="commentError" class="lens-comment-error">{{ commentError }}</p>
          <p v-if="commentary" class="lens-commentary">{{ commentary }}</p>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import EmptyState from "../components/ui/EmptyState.vue";
import ErrorState from "../components/ui/ErrorState.vue";
import SkeletonBlock from "../components/ui/SkeletonBlock.vue";
import { ApiError } from "../api/client";
import {
  createLensForecast,
  getLensForecasts,
  getLensPing,
  getLensState,
  postLensCommentary,
  runLenses,
} from "../api/endpoints";
import type {
  LensForecast,
  LensPing,
  LensStateResponse,
  LensTab,
} from "../api/types";
import { usePolling } from "../composables/usePolling";
import { fmtDate, fmtNumber, fmtRatioPct, fmtSigned, priceDigits, trendClass } from "../composables/useFormat";
import { useToast } from "../stores/toast";

const TABS: Array<{ id: LensTab; label: string }> = [
  { id: "synthesis", label: "合成研判" },
  { id: "fed", label: "美联储透镜" },
  { id: "song", label: "宋鸿兵透镜" },
  { id: "layers", label: "宏观 / 微观" },
  { id: "personas", label: "人物透镜" },
  { id: "evidence", label: "规则与证据" },
];

const toast = useToast();
const activeTab = ref<LensTab>("synthesis");
const override = ref<LensStateResponse | null>(null);
const running = ref(false);
const submitting = ref(false);
const commentLoading = ref(false);
const commentary = ref("");
const commentError = ref("");
const question = ref("");
const ping = ref<LensPing | null>(null);
const forecasts = ref<LensForecast[]>([]);
const form = reactive({
  asset: "gold",
  direction: "up" as "up" | "down" | "flat",
  horizon_days: 63,
  probability: 0.6,
  notes: "",
});

const { data, error, loading, refresh } = usePolling(getLensState, {
  interval: 120000,
  immediate: false,
});
const state = computed(() => override.value ?? data.value);
const cycle = computed(() => state.value?.synthesis.cycle_context ?? null);
const fedScores = computed(() =>
  Object.entries(state.value?.fed.state.asset_scores ?? {}) as Array<[string, { score: number | null; label: string; why: string }]>,
);
const songScores = computed(() =>
  Object.entries(state.value?.song.state.asset_scores ?? {}) as Array<[string, { score: number | null; label: string; why: string }]>,
);
const fired = computed(() => ({
  fed: (state.value?.rules.fed ?? []).filter((r) => r.fired).length,
  song: (state.value?.rules.song ?? []).filter((r) => r.fired).length,
}));
const totalRules = computed(() => {
  if (!state.value) return 0;
  const rules = state.value.rules;
  let total = (rules.fed?.length ?? 0) + (rules.song?.length ?? 0);
  total += (rules.macro?.length ?? 0) + (rules.micro?.length ?? 0);
  for (const list of Object.values(rules.personas ?? {})) total += list.length;
  return total;
});
const firedCount = computed(() => {
  if (!state.value) return 0;
  const rules = state.value.rules;
  let total = fired.value.fed + fired.value.song;
  total += (rules.macro ?? []).filter((r) => r.fired).length;
  total += (rules.micro ?? []).filter((r) => r.fired).length;
  for (const list of Object.values(rules.personas ?? {})) total += list.filter((r) => r.fired).length;
  return total;
});

const stanceBadge = computed(() => {
  const value = state.value?.fed.state.stance ?? 50;
  return value >= 70 ? "badge--warn" : value <= 30 ? "badge--up" : "badge--accent";
});
const heartBadge = computed(() => {
  const id = state.value?.song.state.dollar_heart.id;
  return id === "infarction" ? "badge--down" : id === "angina" ? "badge--warn" : "badge--accent";
});
const goldClass = computed(() => {
  const id = state.value?.song.state.gold_regime.id;
  return id === "strategic" || id === "accumulate" ? "is-up" : id === "avoid" ? "is-down" : "";
});
const derivationRows = computed(() => {
  if (!state.value) return [];
  const rows = [state.value.fed.derivation, state.value.song.derivation];
  if (state.value.macro?.derivation) rows.push(state.value.macro.derivation);
  if (state.value.micro?.derivation) rows.push(state.value.micro.derivation);
  for (const persona of state.value.personas) {
    if (persona.derivation) rows.push(persona.derivation);
  }
  rows.push(state.value.synthesis.derivation);
  return rows;
});

const macroLayer = computed(() => state.value?.macro ?? null);
const microLayer = computed(() => state.value?.micro ?? null);
const macroScores = computed(() => toScoreEntries(state.value?.macro?.scores));
const microScores = computed(() => toScoreEntries(state.value?.micro?.scores));

/** 人物评分矩阵：行=人物透镜，列=七类资产 */
const personaMatrix = computed(() =>
  (state.value?.personas ?? []).map((persona) => {
    const scores: Record<string, number | null> = {};
    for (const [assetId, item] of Object.entries(persona.scores ?? {})) {
      scores[assetId] = item?.score ?? null;
    }
    return { id: persona.id, name: persona.name, lean: persona.state.lean.score, scores };
  }),
);
const matrixAssets = computed(() =>
  (state.value?.synthesis.assets ?? []).map((asset) => ({ id: asset.id, label: asset.label })),
);

function toScoreEntries(
  scores: Record<string, { score: number | null; label: string }> | undefined,
): Array<[string, { score: number | null; label: string }]> {
  return Object.entries(scores ?? {});
}

function scoreClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "is-flat";
  return value >= 0.25 ? "is-up" : value <= -0.25 ? "is-down" : "is-flat";
}
function agreementClass(value: string): string {
  if (value.includes("空")) return "badge--down";
  if (value.includes("多")) return "badge--up";
  if (value.includes("分歧")) return "badge--warn";
  return "badge--accent";
}
function assetLabel(id: string): string {
  const found = state.value?.synthesis.assets.find((a) => a.id === id);
  return found?.label ?? id;
}
function statusText(status: string): string {
  return status === "fired" ? "命中" : status === "unknown" ? "缺数据" : "未命中";
}
function dirText(direction: string): string {
  return direction === "up" ? "看涨" : direction === "down" ? "看跌" : "震荡";
}
function errText(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.message) as { detail?: string };
      return parsed.detail ?? err.message;
    } catch {
      return err.message;
    }
  }
  return err instanceof Error ? err.message : String(err);
}

async function bootstrap(): Promise<void> {
  override.value = null;
  await refresh();
  if (!data.value) {
    try {
      override.value = await runLenses();
      toast.ok("双透镜已首次运行");
    } catch (err) {
      toast.bad(`运行失败：${errText(err)}`);
    }
  }
  void loadPing();
  void loadForecasts();
}

async function runNow(): Promise<void> {
  running.value = true;
  try {
    override.value = await runLenses();
    toast.ok("双透镜已重算");
    void loadForecasts();
  } catch (err) {
    toast.bad(`重算失败：${errText(err)}`);
  } finally {
    running.value = false;
  }
}

async function reload(): Promise<void> {
  override.value = null;
  await refresh();
}

async function loadPing(): Promise<void> {
  try {
    ping.value = await getLensPing();
  } catch {
    ping.value = null;
  }
}

async function loadForecasts(): Promise<void> {
  try {
    const payload = await getLensForecasts();
    forecasts.value = payload.items.slice(0, 8);
  } catch {
    forecasts.value = [];
  }
}

async function submitForecast(): Promise<void> {
  const asset = state.value?.synthesis.assets.find((a) => a.id === form.asset);
  submitting.value = true;
  try {
    await createLensForecast({
      asset: form.asset,
      direction: form.direction,
      horizon_days: form.horizon_days,
      probability: form.probability,
      baseline_value: asset?.last ?? null,
      notes: form.notes || null,
    });
    form.notes = "";
    toast.ok("预测已登记");
    void loadForecasts();
  } catch (err) {
    toast.bad(`登记失败：${errText(err)}`);
  } finally {
    submitting.value = false;
  }
}

async function askAI(): Promise<void> {
  commentLoading.value = true;
  commentError.value = "";
  try {
    const result = await postLensCommentary(question.value || undefined);
    commentary.value = result.text;
  } catch (err) {
    commentError.value = errText(err);
  } finally {
    commentLoading.value = false;
  }
}

onMounted(() => {
  void bootstrap();
});
</script>

<style scoped>
.lens-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lens-disclaimer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 11px;
}
.lens-disclaimer .ic {
  width: 13px;
  height: 13px;
  color: var(--accent);
  flex: none;
}
.lens-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.lens-stat {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.lens-stat-label {
  font-size: 10.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--dim);
}
.lens-stat-value {
  font-family: var(--font-mono, monospace);
  font-size: 26px;
  line-height: 1.1;
  color: var(--text);
}
.lens-stat-value small {
  font-size: 11px;
  color: var(--muted);
  margin-left: 2px;
}
.lens-stat-value--text {
  font-size: 20px;
  font-family: inherit;
  font-weight: 600;
}
.lens-stat-value--text.is-up { color: var(--up); }
.lens-stat-value--text.is-down { color: var(--down); }
.lens-stat-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--muted);
}
.lens-stat-note {
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--dim);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.lens-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--surface-3, rgba(148, 163, 184, 0.18));
  overflow: hidden;
}
.lens-bar i {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent), var(--warn));
}
.lens-bar--lg {
  height: 7px;
  margin: 10px 0 12px;
}
.lens-bar--risk i {
  background: linear-gradient(90deg, var(--warn), var(--down));
}
.lens-tabs {
  display: flex;
  gap: 2px;
  border-bottom: 1px solid var(--border);
}
.lens-tab {
  appearance: none;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 7px 12px;
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}
.lens-tab:hover { color: var(--text); }
.lens-tab.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}
.lens-tab-count {
  margin-left: 5px;
  font-family: var(--font-mono, monospace);
  font-size: 10px;
  color: var(--dim);
}
.lens-card { overflow: hidden; }
.card-body { padding: 12px; }
.lens-muted { color: var(--muted); font-size: 10.5px; }
.lens-grid { display: grid; gap: 12px; }
.lens-grid--2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.lens-grid--3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.lens-table-wrap { overflow-x: auto; }
.lens-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}
.lens-table th {
  text-align: left;
  font-weight: 500;
  color: var(--dim);
  font-size: 10.5px;
  padding: 7px 10px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.lens-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.lens-table tbody tr:hover { background: var(--surface-2); }
.lens-table tbody tr.is-fired td { background: color-mix(in srgb, var(--warn) 7%, transparent); }
.lens-asset-name { font-size: 12px; color: var(--text); }
.lens-score-cell {
  position: relative;
  min-width: 74px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.lens-score-bar {
  display: none;
}
.lens-score-bar--wide {
  display: block;
  position: relative;
  height: 4px;
  margin: 4px 0 6px;
  background: var(--surface-3, rgba(148, 163, 184, 0.18));
  border-radius: 2px;
}
.lens-score-bar i {
  position: absolute;
  top: 0;
  height: 100%;
  border-radius: 2px;
  background: var(--muted);
}
.lens-score-bar i.is-up { background: var(--up); }
.lens-score-bar i.is-down { background: var(--down); }
.lens-advice { color: var(--muted); max-width: 220px; line-height: 1.5; }
.lens-dir { font-size: 11px; }
.lens-dir--up { color: var(--up); }
.lens-dir--down { color: var(--down); }
.lens-dir--flat { color: var(--muted); }
.is-up { color: var(--up); }
.is-down { color: var(--down); }
.is-flat { color: var(--muted); }
.lens-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.lens-list li { display: flex; gap: 8px; align-items: flex-start; line-height: 1.5; }
.lens-list-title { font-size: 11.5px; color: var(--text); }
.lens-list--gaps li { align-items: flex-start; }
.lens-sev {
  width: 6px; height: 6px; border-radius: 50%; margin-top: 5px; flex: none;
  background: var(--muted);
}
.lens-sev--watch { background: var(--accent); }
.lens-sev--warn { background: var(--warn); }
.lens-sev--critical { background: var(--down); }
.lens-outlook { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.lens-outlook-col p { margin: 4px 0 0; font-size: 11.5px; line-height: 1.6; color: var(--muted); }
.lens-outlook-label {
  font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dim);
}
.lens-outlook--up .lens-outlook-label { color: var(--up); }
.lens-outlook--down .lens-outlook-label { color: var(--down); }
.lens-invalidators { border-top: 1px solid var(--border); }
.lens-invalidators ul { margin: 6px 0 0; padding-left: 16px; font-size: 11px; line-height: 1.6; color: var(--muted); }
.lens-cycle { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.lens-cycle > div { display: flex; flex-direction: column; gap: 3px; font-size: 11.5px; }
.lens-big {
  font-family: var(--font-mono, monospace); font-size: 30px; line-height: 1.15; color: var(--text);
}
.lens-big small { font-size: 11px; color: var(--muted); margin-left: 4px; font-family: inherit; }
.lens-kv {
  display: flex; justify-content: space-between; gap: 10px; font-size: 11.5px;
  padding: 4px 0; color: var(--muted);
}
.lens-kv strong { color: var(--text); font-weight: 600; }
.lens-components { list-style: none; margin: 6px 0 0; padding: 0; font-size: 11px; }
.lens-components li {
  display: grid; grid-template-columns: 1fr auto auto; gap: 8px;
  padding: 4px 0; border-bottom: 1px dashed var(--border); color: var(--muted);
}
.lens-readings {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;
}
.lens-reading {
  border: 1px solid var(--border); border-radius: 6px; padding: 8px;
  display: flex; flex-direction: column; gap: 4px; background: var(--surface-2);
}
.lens-reading.is-missing { opacity: 0.65; }
.lens-reading-label { font-size: 11px; color: var(--text); }
.lens-reading-value { font-size: 18px; line-height: 1.2; color: var(--text); }
.lens-reading-value small { font-size: 10px; color: var(--muted); margin-left: 2px; }
.lens-reading-meta { display: flex; gap: 8px; flex-wrap: wrap; font-size: 10px; color: var(--muted); }
.lens-reading-source { display: flex; gap: 6px; align-items: center; font-size: 10px; }
.lens-narrative {
  margin: 12px 0 0; padding-top: 10px; border-top: 1px dashed var(--border);
  font-size: 11.5px; line-height: 1.7; color: var(--muted);
}
.lens-risk { margin-bottom: 8px; }
.lens-form {
  display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end;
}
.lens-form label {
  display: flex; flex-direction: column; gap: 4px; font-size: 10.5px; color: var(--dim);
}
.lens-form input, .lens-form select {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 5px;
  color: var(--text); font-size: 12px; padding: 6px 8px; min-width: 110px;
}
.lens-form-wide { flex: 1 1 240px; }
.lens-form-wide input { width: 100%; }
.lens-forecast-list { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.lens-forecast {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  font-size: 11.5px; color: var(--muted); padding: 6px 8px;
  border: 1px solid var(--border); border-radius: 5px;
}
.lens-deriv { padding: 8px 0; border-bottom: 1px dashed var(--border); }
.lens-deriv:last-child { border-bottom: none; }
.lens-deriv-links { display: flex; align-items: center; gap: 10px; margin-top: 6px; font-size: 10.5px; color: var(--muted); }
.lens-link { color: var(--accent); text-decoration: none; font-size: 10.5px; }
.lens-link:hover { text-decoration: underline; }
.lens-table--rules td { font-size: 11px; }
.lens-rule-id { font-size: 12px; color: var(--text); }
.lens-status {
  display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10.5px;
  border: 1px solid var(--border); color: var(--muted); white-space: nowrap;
}
.lens-status--fired { color: var(--warn); border-color: var(--warn); }
.lens-status--unknown { color: var(--muted); border-style: dashed; }
.lens-trace { margin-top: 4px; font-size: 10px; color: var(--dim); }
.lens-trace .met { color: var(--warn); }
.lens-commentary { margin: 12px 0 0; font-size: 12px; line-height: 1.75; color: var(--text); white-space: pre-wrap; }
.lens-comment-error { margin: 10px 0 0; font-size: 11.5px; color: var(--down); }
.lens-empty-hint { padding: 0 12px 14px; font-size: 11px; color: var(--dim); }
@media (max-width: 1200px) {
  .lens-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .lens-grid--3 { grid-template-columns: 1fr; }
  .lens-grid--2 { grid-template-columns: 1fr; }
  .lens-outlook { grid-template-columns: 1fr; }
  .lens-cycle { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
