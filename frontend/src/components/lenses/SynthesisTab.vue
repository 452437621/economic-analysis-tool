<template>
  <section class="card lens-card">
    <div class="card-head">
      <span class="card-title">七类资产 · 多透镜共振表</span>
      <span class="spacer"></span>
      <span class="lens-muted">
        综合分 −2…+2 由 {{ state.synthesis.lens_count ?? 13 }} 套透镜加权；
        方向按 |共识| ≥ 0.25 判定；仓位按风险预算推导
      </span>
    </div>
    <div class="lens-table-wrap">
      <table class="lens-table">
        <thead>
          <tr>
            <th>资产</th><th>最新</th><th>美联储</th><th>宋鸿兵</th><th>参与</th>
            <th>共识</th><th>一致度</th><th>方向</th><th>胜率</th>
            <th>仓位</th><th>止损</th><th>权重</th><th>操作建议</th>
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
            <td class="mono lens-muted" title="参与该资产共识的透镜数量（两套主透镜之外的宏观、微观与人物透镜计入共识分）">
              {{ asset.lenses ?? 2 }}
            </td>
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
            <td class="mono" :class="asset.plan?.actionable ? `lens-dir lens-dir--${asset.direction}` : 'lens-muted'">
              {{ asset.plan?.actionable ? asset.plan.side_label : "观望" }}
            </td>
            <td class="mono lens-muted" :title="asset.plan?.stop_note || ''">
              {{ asset.plan?.actionable ? `${asset.plan.stop_pct.toFixed(1)}%` : "—" }}
            </td>
            <td class="mono">{{ asset.plan?.actionable ? `${asset.plan.weight_pct.toFixed(1)}%` : "—" }}</td>
            <td class="lens-advice">{{ asset.advice }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <section v-if="portfolio" class="card lens-card">
    <div class="card-head">
      <span class="card-title">组合层 · 仓位 / 止损 / 权重</span>
      <span class="spacer"></span>
      <span class="lens-muted">{{ portfolio.basis }}</span>
    </div>
    <div class="card-body">
      <div class="lens-metrics">
        <div class="lens-metric">
          <span class="lens-metric-label">总敞口</span>
          <span class="mono">{{ portfolio.gross_weight_pct.toFixed(1) }}%</span>
        </div>
        <div class="lens-metric">
          <span class="lens-metric-label">多 / 空</span>
          <span class="mono">
            {{ portfolio.long_weight_pct.toFixed(1) }}% / {{ portfolio.short_weight_pct.toFixed(1) }}%
          </span>
        </div>
        <div class="lens-metric">
          <span class="lens-metric-label">净敞口</span>
          <span class="mono">{{ portfolio.net_weight_pct.toFixed(1) }}%</span>
        </div>
        <div class="lens-metric">
          <span class="lens-metric-label">现金</span>
          <span class="mono">{{ portfolio.cash_weight_pct.toFixed(1) }}%</span>
        </div>
        <div class="lens-metric">
          <span class="lens-metric-label">组合风险</span>
          <span class="mono lens-warn">{{ portfolio.portfolio_risk_pct.toFixed(2) }}%</span>
        </div>
      </div>
      <div class="lens-table-wrap" style="margin-top: 12px">
        <table class="lens-table">
          <thead>
            <tr><th>资产</th><th>方向</th><th>权重</th><th>风险</th><th>止损距离</th><th>止损位</th></tr>
          </thead>
          <tbody>
            <tr v-for="position in portfolio.positions" :key="position.asset">
              <td>{{ position.label }}</td>
              <td>
                <span class="lens-dir" :class="`lens-dir--${position.side === 'long' ? 'up' : 'down'}`">
                  {{ position.side_label }}
                </span>
              </td>
              <td class="mono">{{ position.weight_pct.toFixed(1) }}%</td>
              <td class="mono">{{ position.risk_pct.toFixed(2) }}%</td>
              <td class="mono">{{ position.stop_pct.toFixed(1) }}%</td>
              <td class="mono">
                {{ position.stop_level === null ? "—" : fmtNumber(position.stop_level, priceDigits(position.stop_level)) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="lens-muted" style="margin-top: 10px">{{ portfolio.note }}</div>
      <ul class="lens-rules-inline">
        <li v-for="rule in portfolio.rules" :key="rule">{{ rule }}</li>
      </ul>
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
          text="当前没有明显分歧"
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

<script setup lang="ts">
import { computed } from "vue";
import type { LensStateResponse } from "@/api/types";
import EmptyState from "@/components/ui/EmptyState.vue";
import { agreementClass, scoreClass } from "@/composables/useLensState";
import { fmtNumber, fmtRatioPct, fmtSigned, priceDigits } from "@/composables/useFormat";

const props = defineProps<{ state: LensStateResponse }>();

const portfolio = computed(() => props.state.portfolio ?? props.state.synthesis.portfolio ?? null);
const cycle = computed(() => props.state.synthesis.cycle_context ?? null);
</script>

<style scoped>
.lens-card { overflow: hidden; }
.card-body { padding: 12px; }
.lens-muted { color: var(--muted); font-size: 10.5px; }
.lens-grid { display: grid; gap: 12px; }
.lens-grid--2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.lens-table-wrap { overflow-x: auto; }
.lens-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 8px;
}
.lens-metric {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.lens-metric-label { font-size: 10.5px; color: var(--dim); }
.lens-warn { color: var(--warn); }
.lens-rules-inline {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}
.lens-rules-inline li {
  font-size: 10.5px;
  color: var(--dim);
}
.lens-rules-inline li::before { content: "· "; }
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
@media (max-width: 1200px) {
  .lens-grid--2 { grid-template-columns: 1fr; }
  .lens-outlook { grid-template-columns: 1fr; }
  .lens-cycle { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
