<template>
  <div class="view tokens-view">
    <div class="page-head">
      <div>
        <div class="page-eyebrow">系统 · 设计规范</div>
        <h1 class="page-h1">设计规范 · 设计系统单一事实源</h1>
        <div class="page-sub">
          所有页面共用同一套 token、字号、间距与组件；改这里等于改全站。原型页 <code>docs/design/mockup-merged/index.html</code> 与本页保持同源。
        </div>
      </div>
      <div class="page-actions">
        <span class="badge badge--sm">CSS 变量</span>
        <span class="badge badge--sm">深 / 浅两套</span>
        <span class="badge badge--sm badge--accent">红涨绿跌</span>
      </div>
    </div>

    <section class="card">
      <header class="card-head">
        <span class="card-title">色板 · Color</span>
        <span class="card-sub">语义色 · 深浅两套 · 红涨绿跌（右上角可切换主题）</span>
      </header>
      <div class="card-body tk-swatches">
        <div v-for="token in colors" :key="token.name" class="tk-swatch">
          <span class="tk-chip" :style="{ background: token.value, borderColor: token.border ?? 'var(--border)' }"></span>
          <div class="tk-meta">
            <b>--{{ token.name }}</b>
            <span class="tk-hex mono">{{ token.value }}</span>
            <span class="tk-note">{{ token.note }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <header class="card-head">
        <span class="card-title">字阶 · Typography</span>
        <span class="card-sub">system-ui / Segoe UI / Microsoft YaHei · 数字等宽</span>
      </header>
      <div class="card-body tk-type">
        <div v-for="row in typeScale" :key="row.size" class="tk-type-row">
          <span class="tk-type-label mono">{{ row.size }}</span>
          <span :style="{ fontSize: row.size, fontWeight: row.weight }">{{ row.sample }}</span>
          <span class="tk-type-use">{{ row.use }}</span>
        </div>
      </div>
    </section>

    <section class="card">
      <header class="card-head">
        <span class="card-title">按钮与徽标</span>
        <span class="card-sub">控件 8px 圆角 · 徽标 999px 全圆角</span>
      </header>
      <div class="card-body tk-row">
        <button class="btn btn--primary" type="button">主操作</button>
        <button class="btn btn--ghost" type="button">次操作</button>
        <button class="btn btn--ghost btn--sm" type="button">小号</button>
        <span class="badge">中性</span>
        <span class="badge badge--accent">强调</span>
        <span class="badge badge--up">上涨</span>
        <span class="badge badge--down">下跌</span>
        <span class="badge badge--warn">预警</span>
        <span class="badge badge--sm">小徽标</span>
      </div>
    </section>

    <section class="card">
      <header class="card-head">
        <span class="card-title">间距 · 圆角 · 卡片</span>
        <span class="card-sub">8pt 栅格</span>
      </header>
      <div class="card-body tk-row">
        <span v-for="space in spaces" :key="space" class="tk-space">
          <i :style="{ width: space, height: space }"></i>
          <b class="mono">{{ space }}</b>
        </span>
        <span class="tk-demo-card">卡片 --surface · 圆角 10px · 边框 1px</span>
      </div>
    </section>

    <section class="card">
      <header class="card-head">
        <span class="card-title">表单控件</span>
        <span class="card-sub">输入框 32px 高</span>
      </header>
      <div class="card-body tk-form">
        <label class="tk-field">
          <span>文本输入</span>
          <input class="tk-input" placeholder="如：US10Y" />
        </label>
        <label class="tk-field">
          <span>下拉选择</span>
          <select class="tk-input">
            <option>全部</option>
            <option>仅触发</option>
          </select>
        </label>
        <div class="tk-field">
          <span>分段控件</span>
          <div class="seg">
            <button class="active" type="button">全部</button>
            <button type="button">高</button>
            <button type="button">中</button>
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <header class="card-head">
        <span class="card-title">数据表格</span>
        <span class="card-sub">行高 36 · 数字右对齐 · 等宽字体</span>
      </header>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>代码</th>
              <th class="num">最新</th>
              <th class="num">日变动</th>
              <th>时点</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tableRows" :key="row.code">
              <td>{{ row.name }}</td>
              <td class="mono">{{ row.code }}</td>
              <td class="num mono">{{ row.price }}</td>
              <td class="num mono" :class="row.chg.startsWith('-') ? 'down' : row.chg === '—' ? 'flat' : 'up'">{{ row.chg }}</td>
              <td class="mono dim">{{ row.time }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <header class="card-head">
        <span class="card-title">反馈与状态</span>
        <span class="card-sub">骨架 / 空态 / 徽标状态</span>
      </header>
      <div class="card-body tk-row">
        <div class="tk-skeleton"><i></i><i></i><i></i></div>
        <div class="tk-empty">空态：暂无数据 · 从左侧选择一条运行</div>
        <div class="tk-states">
          <span class="tk-state"><i class="tk-dot tk-dot--live"></i>运行中</span>
          <span class="tk-state"><i class="tk-dot tk-dot--warn"></i>降级</span>
          <span class="tk-state"><i class="tk-dot tk-dot--down"></i>失败</span>
        </div>
      </div>
    </section>

    <section class="card">
      <header class="card-head">
        <span class="card-title">口径说明</span>
      </header>
      <div class="card-body tk-note">
        本页所有示例均为静态展示；真实数值请到对应页面查看。颜色以 CSS 变量为准（见
        <code>frontend/src/styles/app.css</code> 顶部 <code>:root</code> 与
        <code>[data-theme="light"]</code> 段），与 <code>docs/design/mockup-merged/index.html</code> 的
        token 同名同值。
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
interface ColorToken {
  name: string;
  value: string;
  note: string;
  border?: string;
}

const colors: ColorToken[] = [
  { name: "bg", value: "#0A0E13", note: "页面底色（深色）" },
  { name: "surface", value: "#111721", note: "卡片" },
  { name: "surface-2", value: "#172030", note: "次级面板 / 输入框" },
  { name: "surface-3", value: "#1D2839", note: "hover / 选中" },
  { name: "border", value: "rgba(148,163,184,.14)", note: "常规边框", border: "rgba(148,163,184,.4)" },
  { name: "border-strong", value: "#223047", note: "强调边框" },
  { name: "text", value: "#E6EDF5", note: "主文字（浅色 #0F172A）" },
  { name: "muted", value: "#93A4B8", note: "次文字" },
  { name: "dim", value: "#64748B", note: "弱文字 / 时点" },
  { name: "accent", value: "#4CC2FF", note: "强调（浅色 #0B6FB3）" },
  { name: "up", value: "#F0544F", note: "涨（浅色 #D64541）" },
  { name: "down", value: "#2FBF71", note: "跌（浅色 #1B8A55）" },
  { name: "warn", value: "#F5A524", note: "预警 / 降级" },
  { name: "ok", value: "#2FBF71", note: "正常 / 通过" },
];

const typeScale = [
  { size: "26px", weight: 650, sample: "今日主线", use: "页面标题" },
  { size: "20px", weight: 650, sample: "周期罗盘", use: "区块主标题" },
  { size: "15px", weight: 600, sample: "美国 · 长债务周期晚期", use: "卡片标题" },
  { size: "13px", weight: 400, sample: "跨资产热力图与利率快照", use: "正文" },
  { size: "12px", weight: 400, sample: "数据时点 2026-11-17 09:30", use: "次要说明" },
  { size: "11px", weight: 500, sample: "E2 · 交叉验证", use: "标签 / 徽标" },
  { size: "10.5px", weight: 500, sample: "研究分析 / 预警台", use: "面包屑 / 分组" },
  { size: "9.5px", weight: 500, sample: "US10Y · 2.92%", use: "等宽脚注" },
];

const spaces = ["4px", "8px", "12px", "16px", "24px"];

const tableRows = [
  { name: "美国 10Y", code: "US10Y", price: "5.12%", chg: "+0.03", time: "11-17 09:30" },
  { name: "黄金", code: "XAUUSD", price: "3,864.23", chg: "-0.42%", time: "11-17 09:28" },
  { name: "沪深 300", code: "000300", price: "3,957.54", chg: "—", time: "11-17 15:00" },
];
</script>

<style scoped>
.tokens-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tk-swatches {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 8px;
}

.tk-swatch {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}

.tk-chip {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: 1px solid var(--border);
  flex: none;
}

.tk-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.tk-meta b {
  font-size: 11px;
  font-weight: 600;
}

.tk-hex {
  font-size: 9.5px;
  color: var(--dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tk-note {
  font-size: 9.5px;
  color: var(--muted);
}

.tk-type {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tk-type-row {
  display: grid;
  grid-template-columns: 64px 1fr 160px;
  align-items: baseline;
  gap: 12px;
  padding-bottom: 6px;
  border-bottom: 1px dashed var(--border);
}

.tk-type-label {
  font-size: 10px;
  color: var(--dim);
}

.tk-type-use {
  font-size: 10px;
  color: var(--muted);
  text-align: right;
}

.tk-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.tk-space {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tk-space i {
  display: inline-block;
  background: var(--accent-weak, rgba(76, 194, 255, 0.14));
  border: 1px solid var(--accent-line, rgba(76, 194, 255, 0.32));
  border-radius: 3px;
}

.tk-space b {
  font-size: 10px;
  color: var(--muted);
}

.tk-demo-card {
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
  font-size: 11px;
  color: var(--muted);
}

.tk-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.tk-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 10.5px;
  color: var(--muted);
}

.tk-input {
  height: 32px;
  min-width: 160px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--border-strong);
  background: var(--surface-2);
  color: var(--text);
  font-size: 12px;
  font-family: var(--sans);
  outline: none;
}

.tk-input:focus {
  border-color: var(--accent);
}

.tk-skeleton {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 200px;
}

.tk-skeleton i {
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--surface-2), var(--surface-3), var(--surface-2));
}

.tk-skeleton i:nth-child(2) {
  width: 80%;
}

.tk-skeleton i:nth-child(3) {
  width: 60%;
}

.tk-empty {
  padding: 18px 22px;
  border: 1px dashed var(--border-strong);
  border-radius: 10px;
  font-size: 11px;
  color: var(--muted);
}

.tk-states {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tk-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--muted);
}

.tk-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.tk-dot--live {
  background: var(--ok);
}

.tk-dot--warn {
  background: var(--warn);
}

.tk-dot--down {
  background: var(--down);
}

.tk-note {
  font-size: 11px;
  line-height: 1.7;
  color: var(--muted);
}

code {
  font-family: var(--mono);
  font-size: 10.5px;
  color: var(--accent);
}

@media (max-width: 1024px) {
  .tk-type-row {
    grid-template-columns: 56px 1fr;
  }

  .tk-type-use {
    display: none;
  }
}
</style>
