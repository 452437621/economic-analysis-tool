# UI 差异审计：设计原型 vs 现有 Vue 前端

- 审计对象：设计原型 `docs/design/mockup-merged/index.html`（4442 行，Chrome headless dump 合并版）、现有前端 `frontend/src`、后端 `backend/app/api/*.py`。
- 审计方式：静态阅读（grep + read），未运行浏览器、未跑测试/构建；所有结论附 `文件路径:行号`。
- 原型事实基线：V1 四页数据冻结在 2026-11-13（`docs/design/mockup-merged/README.md:13-49`）；V2 页徽标为 2026-11-17 09:30；原型页内按钮除 `data-go` 跳转外均无行为（同上）。
- 结论口径：本文把「原型元素」当作视觉与信息架构目标，把「现有页面」当作功能真实来源；判断缺失只针对**可见元素与数据字段**，不评价视觉打磨程度。

---

## 一、总览

### 1.1 原型 8 视图清单

原型由两代版本拼合而成：V1 四页是冻结 DOM `<template id="v1-tpl-*">`（首次切页时挂到 `attachShadow` 的空壳上，见 `docs/design/mockup-merged/index.html:3234-3237`），V2 四页是直出 DOM。

| # | 视图 | 原型类型 | 原型行号 | 现有路由 | 现有视图文件（模板行数） |
|---|------|----------|----------|----------|--------------------------|
| 1 | overview 总览 | V1 冻结模板 | 1920–2056 | `/` | `frontend/src/views/OverviewView.vue`（模板 1–312） |
| 2 | market 市场行情 | V1 冻结模板 | 2059–2156 | `/market` | `frontend/src/views/MarketView.vue`（1–321） |
| 3 | brief 每日简报 | V1 冻结模板 | 2159–2308 | `/briefs` | `frontend/src/views/BriefsView.vue`（1–276） |
| 4 | compass 周期罗盘 | V2 直出 | 2540–2715 | `/cycle` | `frontend/src/views/CycleView.vue`（1–368） |
| 5 | history 世界长河 | V2 直出 | 2716–2854 | `/history` | `frontend/src/views/HistoryView.vue`（1–338） |
| 6 | pipeline 透明管线 | V2 直出 | 2856–3034 | `/pipeline` | `frontend/src/views/PipelineView.vue`（1–198） |
| 7 | alerts 预警台 | V2 直出 | 3036–3232 | `/alerts` | `frontend/src/views/AlertsView.vue`（1–197） |
| 8 | tokens 设计规范 | V1 冻结模板 | 2312–2462 | 无 | 无（最接近的 `/system` 是运行状态页） |

补充：原型壳层与全局件位置 —— 侧栏 2463–2503、顶栏 2506–2537、抽屉 3240–3262、命令面板 3264–3274、视图注册表 `VIEWS` 3331–3340。

### 1.2 现有路由清单（`frontend/src/router/index.ts`）

> 事实修正：任务描述写「14 个页面」，实际 `router/index.ts` 有 **15 条**页面路由（多出 `/analysis` 分析引擎，`router/index.ts:23-26`），另有 1 条兜底重定向 `/:pathMatch(.*)* → "/"`（`router/index.ts:95-97`）。下文按 15 条处理。

| # | 路径 | 标题 / 分组 | 视图文件 | 行号 | 原型对应 |
|---|------|-------------|----------|------|----------|
| 1 | `/` | 总览 / 工作台 | `OverviewView.vue` | 5-8 | overview |
| 2 | `/market` | 市场行情 / 工作台 | `MarketView.vue` | 11-14 | market |
| 3 | `/rates` | 利率与流动性 / 研究分析 | `RatesView.vue` | 17-20 | 无（原型是「待接入」占位，index.html:2480） |
| 4 | `/analysis` | 分析引擎 / 研究分析 | `AnalysisView.vue` | 23-26 | 无 |
| 5 | `/pipeline` | 透明管线 / 研究分析 | `PipelineView.vue` | 29-32 | pipeline |
| 6 | `/cycle` | 周期罗盘 / 研究分析 | `CycleView.vue` | 35-38 | compass |
| 7 | `/alerts` | 预警台 / 研究分析 | `AlertsView.vue` | 41-44 | alerts |
| 8 | `/history` | 世界长河 / 研究分析 | `HistoryView.vue` | 47-50 | history |
| 9 | `/ledger` | 预测台账 / 研究分析 | `LedgerView.vue` | 53-56 | 无 |
| 10 | `/principles` | 原则库 / 研究分析 | `PrinciplesView.vue` | 59-62 | 无 |
| 11 | `/signals` | 交易信号 / 研究分析 | `SignalsView.vue` | 65-68 | 无 |
| 12 | `/gold` | 黄金研判 / 研究分析 | `GoldView.vue` | 71-74 | 无 |
| 13 | `/theses` | 论点与证据 / 研究分析 | `ThesesView.vue` | 77-80 | 无 |
| 14 | `/briefs` | 简报与日志 / 内容 | `BriefsView.vue` | 83-86 | brief |
| 15 | `/system` | 系统状态 / 系统 | `SystemView.vue` | 89-92 | tokens（仅部分：无设计规范） |

### 1.3 一句话结论

**差异最大的是 pipeline（现有是「运行列表 + 步骤链 + 推导表」三卡，原型是「运行摘要条 + 6 节点 DAG + 五层溯源树 + 反事实沙盘 + 模型卡」）、其次是 compass 与 alerts（原型核心区块整套缺失），差异最小的是 overview / market / brief（现有基本就是 V1 原型的落地，只差细节与少量字段）。** 整体判断：现有前端实现的是 **V1（2026-11-13）原型**，merged 版的 **V2 壳层与 4 个 V2 视图尚未落地**；`frontend/src/styles/app.css` 甚至完全没有 V2 组件的类（见 §3.8），这是「壳层+4 页」需要重做样式而不是改样式的原因。

---

## 二、逐视图差异表

列含义：**原型区块（行号）** → **原型字段/控件** → **现有实现 · 缺 · 多** → **视觉差异** → **所需后端接口**（`backend/app/api/` 下）。「需新增接口」均给建议响应字段。

### 2.1 overview → `/` `OverviewView.vue`

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口（现状） |
|---|---|---|---|---|---|
| 1 | hero 主体 1921-1942 | hero-eyebrow 日期周几、hero-title 今日主线、hero-desc、hero-tags 4（标签/值/▲▼delta） | 有（`OverviewView.vue:19-42`）；字段来自 `/api/overview` 的 `brief` | 基本一致；原型 tag 是 4 列 pill 行 | `GET /api/overview`（`overview.py:46`，含 `brief`） |
| 2 | hero-top 右侧「✓ 简报已生成 · 12 条证据」1925-1931 | 证据计数 | 缺（仅 hero-meta 文本），无「已生成」状态徽标 | 缺一个 success badge | 需在 `/api/overview` 返回 `brief.evidence_count`（现 `brief` 无该字段） |
| 3 | hero-foot「查看证据 E-01」1937-1941 | 证据深链按钮 | **缺**（`OverviewView.vue:44-55` 只有查看日报/打印/复制摘要/更新于） | 少一个 link-btn | `GET /api/documents/{document_id}/evidence`（`knowledge.py:256`）可用；需 `brief.evidence_ids` 暴露 |
| 4 | 现有多：hero-cycle 周期摘要 `OverviewView.vue:56-67` | 长债务周期/短周期/预警 + 3 个跳转 | 原型无 | 多一行 pill 区 | `GET /api/v2/cycle/state`（`cycle.py:93`） |
| 5 | 市场时钟 1943-1959 | badge live、北京/伦敦/纽约 3 行时钟、夜盘倒计时 | 有（`OverviewView.vue:70-92`） | 一致；原型 badge 文案「外盘交易中」，现为状态徽标 | 无接口（`useClock` 前端计算） |
| 6 | KPI·系统状态 1962-1971 | 6/6、后端·数据库·调度器·6 数据源在线、meter 100% | 有（`:96-113`），但无 meter 条 | 缺进度条与「6 项」拆解；卡片信息量下降 | `GET /api/system/health`（`system.py:52`） |
| 7 | KPI·行情覆盖 1973-1984 | 28/35 标的、覆盖率 80.0%、badge warn「7 待接入」 | 有（`:115-131`，`snapshotMeta.with_quote/count/coveragePct`） | 缺覆盖率 meter 与「待接入」badge | `GET /api/market/snapshot`（`market.py:52`） |
| 8 | KPI·数据量 1986-1995 | 27,804 条、覆盖 14 张表、行情/宏观/持仓三色 meter | 有（`:133-149`）但无三色 meter 与表数 | 缺 meter；数据维度文案弱 | `GET /api/system/meta`（`system.py:123`）+ `counts`（`overview.py:95`） |
| 9 | KPI·调度器 1997-2003 | 7 个任务、6 成功、下次 21:00、badge「1 运行中」 | 有（`:151-162`，`jobsInfo.total/next_run`） | 缺「运行中」badge | `GET /api/system/jobs`（`system.py:87`） |
| 10 | 重点关注 + watch-grid 2005-2013 | 标题 + count 7 + 管理自选 + 每卡 name/code/price/unit/chg/20日/spark | 有（`:165-207`，`WatchlistManager` + `Sparkline`） | 一致（同类卡组） | `GET /api/overview`（`watchlist`）+ `GET /api/market/bars`（`market.py:58`） |
| 11 | 跨资产热力图 2016-2025 | 类别行 + heat-tile（name + pct，色阶） | 有（`:210-240`，`heatGroups/heatStyle`） | 一致 | `GET /api/market/snapshot`（`market.py:52`） |
| 12 | 利率快照 2026-2034 | rate-row（name/val/chg/70×15 spark）、card-foot 口径、详情链接 | 有（`:242-260`） | 缺 SOFR−EFFR 利差的「pp」单位说明行与 foot 出处文案（现用 `macroAsOf`） | `GET /api/macro/latest`（`market.py:94`）+ `GET /api/macro/series`（`market.py:119`） |
| 13 | 告警卡 2038-2046 | badge「3 条未读」、4 行（sev + 文本 + 「分类 / 规则已启用」+ 时间）、foot 统计 + 告警设置 | 有（`:265-288`） | 缺「规则已启用」meta 与 foot 统计文案 | `GET /api/alerts`（`alerts.py:16`） |
| 14 | 财经日历 2047-2054 | 3 行日历（时间/地区/名称/预期）+ 近期事件分隔 + 3 行 tl-row + 完整日历 | 部分（`:290-307`，4 行 `calendar` + 星级） | 缺 cal-sep 与 tl-row「近期事件」；「完整日历」链接现有指向 `/theses`（`OverviewView.vue:295`，**错误目标**） | `GET /api/calendar`（`market.py:226`，无预期值字段） |

### 2.2 market → `/market` `MarketView.vue`

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口（现状） |
|---|---|---|---|---|---|
| 1 | page-head 2059-2069 | eyebrow 快照日期、h1、sub「28/35 标的已接入 · 更新于 15:00」、三按钮（刷新 / 导出 CSV / 数据质检 primary） | 有：eyebrow/h1/sub/刷新/数据质检（`MarketView.vue:3-22`）；**缺导出 CSV** | 少一个按钮；主按钮层级不同 | 导出可在前端做（`GET /api/market/snapshot` 数据即可） |
| 2 | 搜索框 2071-2076 | placeholder「搜索代码 / 名称，例如 CU、沪铜」+ kbd「/」 | 有搜索（`:25-40`），**无 kbd 提示** | 缺快捷键提示 | 无（前端过滤） |
| 3 | 分段 全部/国内/外盘 2077-2082 | seg 三态 | 有（`SEGMENTS`） | 一致 | 无（前端过滤） |
| 4 | 类别 chip 行 2083-2087 | 8 chip 带 `em` 计数（全部35/贵金属5/…） | 有计数 chip（`:42-56`） | 一致 | `GET /api/market/snapshot` |
| 5 | 表格头排序 2092-2100 | 三个 num 列表头 `th-sort` 按钮 | **缺**（固定排序） | 表头无排序箭头 | 前端即可 |
| 6 | 表格主体 2090-2126 | 8 列（品种/名称/最新/涨跌/涨跌幅/数据源/时点/证据）+ group-row（类别 + count + 涨跌统计） | 有 8 列 + group-row（`:69-179`） | 数据源列现多 freshness badge（`src-badge`），密度更高 | `GET /api/market/snapshot`（`market.py:52`） |
| 7 | 证据列 2100 / 2110 | 每行 `E-04` link-btn | **固定「—」占位**（title「暂无关联证据」） | 列存在但无内容 | `GET /api/documents/{id}/evidence`（`knowledge.py:256`）需按标的关联，现无映射 |
| 8 | table-foot 2120-2125 | 显示 35/35、排序说明、源正常数、涨跌色例 | 有（`:181-193`） | 基本一致 | `GET /api/system/sources`（`market.py` 内 `/system/sources`，325 行） |
| 9 | 现有多：持仓结构卡 `MarketView.vue:197-248` | 6 列（品种/多头/空头/净持仓/净占比/多空变化） | 原型**无**此卡（原型会员持仓只在 members-card） | 多一张卡，页面变长 | `GET /api/positions`（`market.py:143`） |
| 10 | 会员持仓卡头 2128-2135 | 标题 Top20 + sub（品种 · 日期 · 净持仓公式）+ seg 沪金/沪银/沪铜 | 有卡头；**筛选是 `select` 下拉**（`MarketView.vue:256-268`） | 筛选器形态不同（原型为 seg 三态） | `GET /api/positions/products`（`market.py:171`） |
| 11 | 多空两列 Top10 2136-2150 | 每列 10 行：rank/name/pos/chg | 有，但 **Top20**（后端 `limit` 默认 20，`market.py:188-207`） | 每列行数翻倍，卡片高度不同 | `GET /api/positions/members`（`market.py:188`，含 `side`，可拆多空） |
| 12 | members-foot 2151-2155 | 数据出处 + 净持仓 +18,420 手 + 多空比 1.08 | 有（`:313-318`） | 一致 | 同上（前端算净持仓/多空比） |

### 2.3 brief → `/briefs` `BriefsView.vue`

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口（现状） |
|---|---|---|---|---|---|
| 1 | page-head 2159-2168 | eyebrow「生成于…·由分析引擎自动撰写」、h1、sub 第 N 期、导出 Markdown / 打印 PDF | 有（`BriefsView.vue:3-28`），action 多「服务端打印版」 | 多一个按钮 | `GET /api/briefs`（`knowledge.py:105`）、`/print`（211）、`/markdown`（243） |
| 2 | 工具栏 2170-2186 | seg 日报/周报/月报 + 上一期/date-chip/下一期/今天 + 已引用证据 + 复制全文 | 有（`:31-95`），seg 带 `tab-count`；**多一个「期次」`issue-select` 下拉** | 多一个下拉；date-chip 布局更密 | `GET /api/briefs/kinds`（`knowledge.py:138`）、`GET /api/briefs` |
| 3 | 三栏左：文内目录 2189-2205 | 固定 5 项 01–05 编号 + toc-foot 4 指标 | 有，但**目录由 markdown 的 h2 动态生成**（`:117-138`） | 编号/条目随正文变，视觉不确定 | 前端（解析 headings） |
| 4 | 三栏中：article-eyebrow/meta 2207-2220 | 日报 badge、日期、期次、引擎、字数、阅读、证据数、红涨绿跌、复制全文 | 有（`:140-160`） | 基本一致 | `GET /api/briefs/{id}`（`knowledge.py:203`） |
| 5 | 主线判断引用块 2222-2232 | `div.quote` + 结论段 + 4 个 quote-tag badge | **无专用结构**：正文走 `v-html` markdown（`:170-176`），`app.css:619 .quote` / `633 .brief-table` 定义了却**不产出对应 class** | 缺「主线判断」高亮块 | 需后端 markdown 模板产出（见 §4.2-7），或前端渲染器加规则 |
| 6 | 5 个编号区块 2234-2290 | h2.a-h2 01–05（市场主线/跨资产表现/利率与流动性/商品与权益/风险提示） | 由 markdown headings 渲染，编号与顺序**不保证** | 无编号样式、无固定段落节奏 | `GET /api/briefs/{id}/markdown`（`knowledge.py:243`） |
| 7 | 02 跨资产表现表 2244-2262 | `table.brief-table` 5 列（资产/最新/日涨跌/周涨跌/20日分位）8 行 + 脚注 | 渲染器只产出裸 `<table>`（`backend/app/narrative/render.py:46-60`） | 表头背景/斑马纹/数字列对齐缺失 | 需新增数据列（周涨跌、20 日分位）→ `GET /api/market/bars` 可算，建议后端预算好 |
| 8 | 03 利率 badge 行 2266-2272 | `brief-tag-line` 9 个 rate badge | 无对应元素 | 缺 badge 行 | `GET /api/macro/latest`（`market.py:94`） |
| 9 | 04/05 列表 2274-2288 | `brief-list` 4 条 + 3 条 | 渲染为普通 ul/li | 无 list 卡样式 | 前端 markdown 渲染器加类即可 |
| 10 | 右栏：本期概览/关联标的/关联证据/导出 2290-2308 | 4 卡；**关联证据 E-01..E-04 按钮列表** | 有 3 卡（`:179-221`），**缺「关联证据」卡** | 少一张卡 | `GET /api/briefs/{id}` 需返回 `evidence_ids`（现 `serializers.py:281-292` 无） |
| 11 | 现有多：交易日志卡 `BriefsView.vue:225-274` | textarea 2000 字 + Ctrl+Enter + 历史列表 | 原型无 | 多一张卡（功能真实，建议保留） | `GET/POST /api/journal`（`journal.py:23,44`） |

### 2.4 compass → `/cycle` `CycleView.vue`

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口（现状） |
|---|---|---|---|---|---|
| 1 | hero 2541-2557 | eyebrow「周期定位 · 美国/全球长周期」、h1 结论句（长债务周期晚期：债务货币化与秩序重构）、sub「短周期：类滞胀（增长↓ 通胀↑）· 综合置信度 73%」 | **缺**：现有页头是 eyebrow+页面名（`CycleView.vue:3-22`） | 缺整块 2 行 hero 与结论句 | `GET /api/v2/cycle/state`（`cycle.py:93`）：`state.value.long_cycle.phase/confidence`、`short_cycle.state/confidence` 已有 |
| 2 | hero-tags 3 条 2549-2555 | 实际利率与金价背离 / 曲线陡峭化 +29bp / 中日利差倒挂 349bp | **缺** | 无 | readings 已含 `us_real10y`、`us_curve_slope`、`cn_curve_slope`（`config/cycle.yaml:46,103,130`），需聚合 |
| 3 | hero-badges 3 个 meta-badge 2556-2557 | 数据覆盖 14/18、规则版本 R-2026.11、下次校准 2026-12-05 | **缺** | 无 | 规则版本=`GET /api/v2/cycle/config`（`cycle.py:154`）的 `version`；**数据覆盖/下次校准无接口** |
| 4 | 周期罗盘卡 2560-2577 | 520×280 SVG 四象限 + 指针、图例 4 态（复苏/过热/滞胀/衰退）、「+20° 偏过热」、link「如何判定 ›」 | 有，但形态不同：260×260 **六分量雷达** + rings/axes（`CycleView.vue:83-144`） | 图形语义不同（雷达 vs 四象限指针）；缺角度文案与「如何判定」 | 角度需前端由 `long_cycle.position`/`short_cycle.variables` 计算 |
| 5 | 五力仪表 2579-2608 | 5 行：债务/货币 82、内部冲突 68、外部冲突 61、自然冲击 34、技术革命 78；每行 track+ticks(25/50/75)+num+「依据 N 项 · 状态」+「为什么」按钮 | **缺整卡** | 无 | `state.value.composites`（`engine.py:217-228`）只有 6 个：DMI/ICI/ECI/GROWTH/INFLATION/LIQUIDITY（`config/cycle.yaml:25-42`）→ **缺「自然冲击 / 技术革命」两项评分** |
| 6 | force-scale 0/25/50/75/100 2605-2607 | 轴刻度 | 缺 | 无 | 前端 |
| 7 | 关键读数 8 KPI 2612-2653 | 美债10Y / 10Y实际利率 / 10Y−2Y / 黄金 / 金银比 / LME铜 / 美元指数 / 中美10Y利差，各带值+z+变动 | **缺整组**：现有 4 张 KPI 是「长债务周期/短债务周期/债务可持续性/历史类比」（`:28-79`），语义完全不同 | 缺 8 卡网格（4×2）与 z-score 角标 | readings 有 `us_10y`、`us_real10y`、`us_curve_slope`、`gold_level_mom`、`us_copper_gold`、`cn_curve_slope`（`config/cycle.yaml:46-184`）；**缺金银比 / LME 铜绝对价 / 美元指数水平 / 中美利差** |
| 8 | KPI 内 spark-slot 2615-2651 | 每卡一条序列 spark（`data-series`）+「E2 证据」按钮 | 缺（现有 CycleView 无 spark） | 无 | spark 需 `GET /api/macro/series`（`market.py:119`）或多序列接口 |
| 9 | 今日预警卡 2655-2695 | badge「3 条」、更新于、全部 ›、3 行（sev/标题/条件/当前值/阈值/置信度/时间/溯源） | **缺**（周期页无预警区块） | 无 | `GET /api/v2/cycle/alerts`（`cycle.py:143`，payload 含 `claim/value/confidence/rules_hit`）或 `GET /api/alerts`（`alerts.py:16`） |
| 10 | 历史类比 Top3 2701-2714 | 3 个 button（名称/副标题/相似度 71/68/64%） | 部分：历史类比在页底卡内（`:222-278`），非 Top3 行 | 位置与形态不同 | `GET /api/v2/cycle/analogs`（`cycle.py:121`）或 `GET /api/analytics/analogs`（`analytics.py:136`） |
| 11 | row-2 布局 2558-2608 | 左 2fr 罗盘 / 右 1fr 五力 | 现有为 main+aside 两栏（`:82-205`） | 网格比例不同 | 前端 |

### 2.5 history → `/history` `HistoryView.vue`

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口（现状） |
|---|---|---|---|---|---|
| 1 | view-head 2717-2726 | eyebrow 1500–2100、h1、副标题「四条帝国泳道 × 五类历史图层 · 点击任意年份…」、view-meta 徽标「示意数据 / 来源：达利欧」 | 有页头（`HistoryView.vue:3-20`），但徽标是「数据日 / 事件数 / 状态」 | 副标题文案不同；缺「示意数据」「来源」两个 meta 徽标 | `GET /api/v2/timeline/overview`（`timeline.py:118`） |
| 2 | filterbar 时间窗 2728-2735 | seg 三档（1500–2100 / 1700–2100 / 1900–2100） | 有：`windows` seg（`HistoryView.vue:86-97`，`applyWindow`） | 一致（但放在卡头而非独立 filterbar） | 前端 |
| 3 | 图层 5 个 chip-toggle 2736-2743 | 帝国兴衰/储备货币/债务危机/战争与革命/技术革命，带色点 | 有 `layerFilters` seg（`:74-85`） | 形态是 seg 而非 chip-toggle，无图例色点 | `GET /api/v2/timeline/overview`（`labels.layers`，`timeline.py:138-141`） |
| 4 | filterbar hint 2744 | 说明文案 | 缺 | 无 | 前端 |
| 5 | 时间轴卡头 2748-2757 | 标题「帝国兴衰 × 储备货币份额」+ zoomOut / 缩放百分比 / zoomIn | 有卡头与 `tl-actions`，**缺 zoom 控件** | 缩放按钮与百分比缺失 | 前端 |
| 6 | 时间轴主体 2758-2770 | SVG `#timelineSvg` height 420：4 条帝国泳道 + 储备份额虚曲线 + 事件标记 | 有泳道实现但为 **div + tl-dot + axis**（`:101-136`），无储备份额曲线 | 视觉差异大：无曲线、无 SVG 精度缩放 | `GET /api/v2/timeline/powers`（`timeline.py:188`，`reserve` 序列）+ `GET /api/v2/timeline/events`（146） |
| 7 | 图例 7 项 + 「储备份额为示意数据」2767-2771 | 7 色点图例 + 免责说明 | 有 tl-legend + era-legend（`:137-149`），无「示意数据」说明 | 多一层 legend（帝国色带） | 前端 |
| 8 | 事件详情 aside 2773-2788 | 右侧内嵌：kicker、事件名、年份 + 帝国 lane badge、描述、3 项 kv（类型/置信度/影响资产）、来源、同期关键事件 | 有，但是 **Teleport 全屏抽屉**（`:289-334`），且缺「影响资产」与「同期关键事件」 | 交互形态不同（抽屉 vs 右侧栏） | `GET /api/v2/timeline/events`（payload 含 `summary/source_url/evidence_grade/power_label`，`timeline.py:31-43`）；缺「影响资产/同期事件」 |
| 9 | 周期对照表 2791-2839 | `table.hist-table` 7 列：国家/崛起期/黄金期/顶峰/转折/衰落/当前阶段，4 行（荷/英/美/中） | 有「霸权更替」表 7 列：时期/崛起/顶点/衰退/储备货币/创新制度/教训（`:225-258`） | **列定义不同**（缺黄金期/转折/当前阶段，多储备货币/创新制度/教训），且只有 4 行相同 | `GET /api/v2/timeline/eras`（`timeline.py:183`，返回 `dataset.ERAS`：name/rise/peak/decline/reserve/innovation/lesson）→ **缺 3 列字段** |
| 10 | 历史规律 6 条 2841-2854 | `laws-grid` 6 张 `law-card`（序号 01–06 + 标题 + 说明） | 有「十条历史规律」`lesson-grid`（`:260-277`），字段 lesson.id/name/mechanism/computable | 6 vs 10 条；卡片多一列「可计算」 | `GET /api/v2/timeline/overview`（`lessons`，`timeline.py:137`） |
| 11 | 现有多：GDP 份额 / 储备份额双 EChart `HistoryView.vue:153-178` | — | 原型无这两张图 | 页面更长 | `GET /api/v2/timeline/powers`（`timeline.py:188`） |
| 12 | 现有多：当下坐标·五维对照 `:180-199` | 五维 current/判断/历史锚点 | 原型无（原型把这类内容放事件详情） | 多一卡 | `GET /api/v2/timeline/position`（`timeline.py:197`） |

### 2.6 pipeline → `/pipeline` `PipelineView.vue`

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口（现状） |
|---|---|---|---|---|---|
| 1 | view-head 2857-2866 | sub「RUN-2026-11-17-0712 · 6 个节点 · 点击节点查看输入输出端点日志」+ 徽标「运行成功」「影子模型 R-2026.11」 | 有页头，徽标为「状态 / 更新于」（`PipelineView.vue:3-20`） | 缺 run id 与「影子模型」徽标 | `GET /api/v2/status`（`glassbox.py:235`） |
| 2 | run-strip 2868-2875 | 6 个 run-cell：运行编号/耗时 42.6s/成功率 96%/覆盖 14/18/环境/完成时间 | **缺整条** | 无（这是「一眼看运行摘要」的核心） | `/api/v2/status`（`counts.runs/derivations/degraded/failed`）+ `/api/v2/runs`（`glassbox.py:104`） |
| 3 | DAG 卡头 2877-2884 | 「成功 4 / 警告 2 / 跳过 0」 | **缺** | 无 | `/api/v2/runs/{run_id}`（`glassbox.py:128`，`steps[].status`）可聚合 |
| 4 | DAG 6 节点 2885-2925 | ①采集 → ②质检 → ③特征 → ④周期引擎 → ⑤情景 → ⑥输出；每节点 idx/name/status/dn-en/耗时+行数/时间+错误数 | **缺整卡**；现有是「运行记录列表 + 步骤链」两卡（`:60-148`） | 结构完全不同：无横向 DAG、无节点卡 | `/api/v2/runs/{run_id}` 的 `steps[]`（`seq/name/kind/duration_ms/outputs/error`，`PipelineView.vue:115-126` 已消费） |
| 5 | 节点状态样式 st-ok / st-warn 2890-2925 | 状态色点/边框与错误数 | 部分：现有 `run-dot--status`、`step` 行（`:78,115-126`） | 缺警告态聚合与错误数角标 | 同上 |
| 6 | 溯源卡头 2933-2941 | 「本次研判溯源」+ badge「静态展开」+ 结论 ID C-2026-11-17-042 | **缺**；现有「推导清单」表（`:150-192`）+ 抽屉 | 无结论 ID 锚点 | `/api/v2/derivations`（`glassbox.py:160`）、`/api/v2/derivations/{id}`（176） |
| 7 | L1 结论 2943-2948 | 黄金：超配，目标权重 12%（基准 6%），置信度 68%，有效期至 2026-12-15 | 缺（现有 drawer 内展示 claim/confidence） | 无 | `/api/v2/derivations/{id}`（含 `claim/confidence/inputs/steps/rules_hit`，`cycle.py:45-64` 同构） |
| 8 | L2 贡献分解瀑布 2952-2963 | 5 行贡献（实际利率 35% / 央行购金 27% / 美元 18% / 避险 12% / 残差 8%） | **缺**（抽屉里有 inputs/steps 原文，无瀑布） | 无 | 需 `/api/v2/derivations/{id}` 返回 `contributions[]`（现无该字段） |
| 9 | L3 规则命中 2970-2975 | 3 条 R-GOLD-03 / R-GOLD-07 / R-CYC-11 + 「命中」 | 缺（`rules_hit` 字段存在但现有前端未展示，`cycle.py:63`） | 无 | `/api/v2/derivations/{id}`（`rules_hit`） |
| 10 | L4 特征 mini-table 2978-2982 | 5 列（特征/值/z-score/分位/动量）3 行 | 缺 | 无 | `/api/v2/derivations/{id}`（`inputs[]` 含 readings，缺「分位/动量」列） |
| 11 | L5 原始数据 2984-2990 | 4 个来源 + 时间戳 | 缺 | 无 | `/api/v2/derivations/{id}`（`inputs[].source/asof`） |
| 12 | 反事实沙盘 2984-3012 | 重置 + 3 slider（实际利率 −100..+100bp / 美元指数 −8..+8% / 央行购金 −40..+40）+ 结论强度 68/100 + 进度条 + 演示公式 | **缺整卡** | 无 | **需新增** `POST /api/v2/cycle/scenario`（见 §4.2-2）；短期可用前端公式 |
| 13 | 模型卡 3015-3034 | 6 个 model-cell：输入 14 序列 / 参数 9 / 最近回测 2026-10 / Brier 0.19 / 规则版本 R-2026.11 / 失效条件 3 条 | **缺**；失效条件仅在抽屉与 degraded-box 中出现 | 无 6 格模型卡 | `/api/v2/cycle/config`（`cycle.py:154`）有 `version`；**缺回测/Brier/参数计数** |
| 14 | 现有多：运行列表 + 步骤链 + 推导清单表 `PipelineView.vue:60-192` | 三条工作流（含 code 过滤、证据等级、置信措辞） | 原型无这三块 | 页面信息密度方向相反 | `/api/v2/runs`、`/api/v2/runs/{id}`、`/api/v2/derivations` |

### 2.7 alerts → `/alerts` `AlertsView.vue`

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口（现状） |
|---|---|---|---|---|---|
| 1 | view-head 3037-3046 | sub「全量 15 条预警 · 最近 7 天 6 个财经事件 · 阈值改动需人工确认」+ 徽标「监控中」「上次巡检 09:02」 | 有页头，徽标为「数据日 / 已触发 n/m」（`AlertsView.vue:3-21`） | 缺「监控中 / 上次巡检」 | `GET /api/alerts`（`alerts.py:16`，`meta.count/unread`） |
| 2 | 汇总 4 卡 3048-3053 | 高 3「需当日处理」/ 中 5「本周复核」/ 低 7「观察列表」/ 日历事件 6「3 个三星」 | 语义相近但字段不同：高风险/中风险/低风险/临近政治事件 4 KPI（`:27-60`） | 第 4 卡从「日历事件」变「政治事件数」；说明文案不同 | `alerts.counts`（前端算）+ `GET /api/calendar`（`market.py:226`） |
| 3 | 预警表头 + 严重度 seg 3056-3070 | 「全量 15 条 · 显示最近 10 条」+ seg 全部/高/中/低 | 有表头，**缺严重度筛选 seg**（只有排序文案） | 缺筛选器 | 前端过滤 |
| 4 | 预警表 8 列 3072-3146 | 严重度 / 名称+分类·地区 / 当前值 / 阈值 / 距离 / 触发后 20 日胜率（条形）/ 置信度 / 更新时间 | 有 9 列：sev-dot / 严重度 / 规则（name+id）/ 指标 / 当前值 / 阈值 / 距离 / 状态 / 观测日（`:70-131`） | **列不同**：现有多「指标」「状态」，缺「胜率」「置信度」；名称列缺「分类·地区」子行 | `GET /api/alerts` 字段仅 `id/level/kind/title/message/acknowledged/created_at`（`alerts.py:33-44`）→ **缺当前值/阈值/距离/置信度/胜率** |
| 5 | 胜率列 winrate 条 3100-3130 | 每行 `winrate` 进度条 + 百分比 | **缺** | 无 | **需数据**：无触发后回测结果表 |
| 6 | 展开详情（现有）`AlertsView.vue:109-127` | 为什么是这条规则 / 失效条件 / 数据来源与口径 3 列 | 原型无展开行 | 现有多一层交互 | `GET /api/v2/cycle/alerts`（`cycle.py:143`）含 `why/falsifiers` |
| 7 | 阈值编辑器 3150-3174 | badge「示意」+ select 3 项（US30Y/USDJPY/CN10Y，带 unit/cur/min/max/step）+ 当前值 + 阈值 slider + 刻度 + 3 行影响估算 | **缺整卡**；现有「规则与阈值」是**只读表**，注释「修改请编辑 config/cycle.yaml 后重算」（`:139-170`） | 从只读表变成可编辑卡 | `GET /api/v2/cycle/config`（`cycle.py:154`，只读）→ **需新增写接口** |
| 8 | 保存阈值 / 恢复默认 3168-3173 | primary 保存 + ghost 恢复 + 备注 | **缺** | 无 | **需新增** `PATCH /api/v2/cycle/config`（见 §4.2-1） |
| 9 | th-impact 3 行 3160-3165 | 当前距离 / 预计触发 / 影响资产 | 缺 | 无 | 前端可算距离；「预计触发/影响资产」需规则元数据 |
| 10 | 财经日历卡 3177-3232 | 6 行 cal-row：日期+星期时间 / 名称+地区·类别 / ★★★ / 预期·前值 / 影响资产 chips | 有「政治日历」卡（`:172-191`）：日期 / 星级 / 名称+note / 剩余天数 | 形态不同：缺时间、预期/前值、影响资产 chips | `GET /api/calendar`（`market.py:226-270`）只有 `ts/name/category/country/importance` → **缺 forecast/previous/affected** |
| 11 | 现有多：规则与阈值表 `AlertsView.vue:139-170` | 6 列 ID/等级/规则/指标/阈值/失效条件 | 原型无（原型把阈值放编辑器） | 多一张表 | `GET /api/v2/cycle/config`（`rules`） |

### 2.8 tokens（设计规范）→ 无对应页面

| # | 原型区块（行号） | 原型字段/控件 | 现有 · 缺 · 多 | 视觉差异 | 后端接口 |
|---|---|---|---|---|---|
| 1 | page-head 2312-2320 | 「设计规范 · Design Tokens v0.1 · 2026-11-13」、sub（深色默认/浅色可切/圆角/字阶/组件状态）、按钮「切换主题预览」 | **无页面**；`/system` 是运行状态（`SystemView.vue:1-140`） | 整套页面缺失 | 无（静态前端） |
| 2 | 色板卡 2322-2345 | 背景层级 / 文字 / 涨跌 / 状态色 + hex | 无页面，但 token 已在 `app.css:10-29`（`--bg/--surface/--text/--up/--down/--warn`） | — | 前端直接读 CSS 变量即可 |
| 3 | 字阶卡 2347-2368 | 字号/行高/字重样张 | 无 | — | 前端 |
| 4 | 按钮与徽标卡 2370-2392 | primary/ghost/icon、badge 各语义 | 无页面（组件真实存在：`.badge--live/warn/accent`，`app.css:306-310`） | — | 前端 |
| 5 | 间距圆角卡片 2394-2415 | 间距标尺、`--radius-card/control` | 无 | — | 前端（`app.css:30-31`） |
| 6 | 表单控件卡 2417-2432 | input/select/slider/seg 态 | 无 | — | 前端 |
| 7 | 数据表格卡 2434-2448 | 表头/斑马纹/数字列/空态行 | 无 | — | 前端（`.data-table`） |
| 8 | 反馈与状态卡 2450-2462 | toast / 空态 / 加载 / 骨架 | 无页面（组件存在：`components/ui/ToastHost.vue`、`EmptyState.vue`、`SkeletonBlock.vue`） | — | 前端 |
| 9 | 现有最接近：`/system` `SystemView.vue` | 服务/数据库/调度器/验收 4 KPI + 任务表 + 数据源表 + 质检/验收 | 与「设计规范」主题无关 | — | `GET /api/system/health/jobs/sources/data-quality/acceptance` |
| 10 | 建议载体 | 新增 `/system/design` 子路由或 SystemView 顶部 tab「规范」 | — | — | 前端即可（1 天内） |

---

## 三、全局壳层差异

对照文件：原型 2463-2537（壳层）、3240-3274（抽屉/命令面板）；现有 `frontend/src/layouts/Sidebar.vue`、`Topbar.vue`、`AppShell.vue`、`frontend/src/styles/app.css`、`frontend/src/components/domain/CommandPalette.vue`。

| # | 项目 | 原型 | 现有 | 差异定性 |
|---|---|---|---|---|
| 1 | 侧栏品牌 | `E2` 方块 + 「EPIC V2」+「周期研判 · 宏观工作台」（`index.html:2464-2470`） | `EP` 方块 + 「EPIC」+「宏观 · 市场 · 交易工作台」（`Sidebar.vue:3-9`） | 文案与标记不同，需改两个字符串 |
| 2 | 侧栏分组 | 4 组：今日 / 市场 / 研判 / 系统（`index.html:2471-2494`），共 10 个导航项（8 个可用 + 2 个待接入） | 4 组：工作台 / 研究分析 / 内容 / 系统（`Sidebar.vue:56-88`），共 15 项 | **分组名与归属全不同**；项数与可用状态也不同 |
| 3 | 侧栏「待接入」占位 | 利率、日历两项带「待接入」标记（`2480-2481`） | 无占位；`/rates` 是真实页面，且**无日历页面** | 原型有 2 个待接入项需要映射到真实页面或加 `待接入` 徽标 |
| 4 | 侧栏图标 | 内联 SVG（`2485-2492`） | `<use href="#i-*">`（`IconSprite.vue`），`i-rates/i-bell/...` | 机制不同但视觉可对齐，成本低 |
| 5 | 侧栏徽标 | 「预警台」带 `nav-badge hot`「3」（`2488`） | `nav-badge` 只给 `/market`（行情数）与 `/theses`（论点数），**预警台无 badge**（`Sidebar.vue:101-105`） | 缺预警未读数 badge（`alerts.unread` 已有） |
| 6 | 侧栏底栏 | 数据健康 97.2% + 进度条 + 序列覆盖 14/18 + 最近同步 09:30 + 「v2.0.0-mockup · 离线原型」（`2495-2503`） | 后端 API host / 行情标的数 / 调度器状态 / 版本 + 时钟（`Sidebar.vue:26-40`） | **信息项完全不同**：缺健康度进度条与序列覆盖；且原型是「产品版本」口径 |
| 7 | 顶栏面包屑 | 3 段：EPIC V2 / 研判 / 周期罗盘（`2507-2513`） | 2 段：`meta.group` / `meta.title`（`Topbar.vue:3-7`） | 缺根级产品名段 |
| 8 | 搜索触发按钮 | 「搜索视图、指标或命令」+ kbd「Ctrl K」（`2514-2518`） | 「搜索标的、页面或执行命令」+ kbd「Ctrl K」（`Topbar.vue:8-12`） | 文案差异；快捷键一致 |
| 9 | 数据时点 pill | 绿点 + 「数据时点」+ `2026-11-17 09:30` + `·` + 「健康 97.2%」（`2520-2526`） | 绿点/黄点 + 「刷新于 HH:MM」（`Topbar.vue:14-17`） | **口径不同**：原型是数据时点+健康度，现有是「页面刷新时刻」，缺健康度百分比与数据时点 |
| 10 | 告警按钮 | 带 `notif-dot`（`2527-2530`） | 有（`alerts.unread` 驱动，`Topbar.vue:18-26`） | 一致 |
| 11 | 主题切换 | moon/sun 双 svg（`2531-2534`） | 有（`Topbar.vue:27-30`，`prefs.setThemeMode`） | 一致 |
| 12 | 设置按钮/头像 | 原型无 | 有 icon-btn「设置」+ `avatar EP`（`Topbar.vue:31-35`） | 现有多两个元素（功能真实，建议保留但与原型对齐位置） |
| 13 | 版本徽标 | 「v2.0 原型」pill（`2535`） | **无** | 缺版本 pill（可用 `health.health.version`） |
| 14 | 命令面板 | 占位「搜索视图或操作：罗盘 / 长河 / 管线 / 预警 / 主题 …」+ kbd「Esc」+ foot「共 4 个视图 · 5 个操作」（`3264-3274`） | 占位「搜索页面、标的或执行命令…」+ kbd「ESC」+ foot「N 项」（`CommandPalette.vue:11,19,39-45`）；分组：页面 9 / 操作 / 标的（`:80-120`） | 文案与计数口径不同；现有功能**更强**（含标的搜索） |
| 15 | 抽屉结构 | mask + kicker「溯源 · E2 证据」+ 标题 + tabs（溯源分层 / 历史类比）+ body + foot 四按钮（复制引用 / 查看 SQL / 导出 JSON / 标记存疑）（`3240-3262`） | `ui/Drawer.vue`：scrim + head(icon/title/sub/close) + body + foot slot；**无 kicker、无 tabs**（`Drawer.vue:3-24`） | 缺 kicker 与 tabs；缺 foot 的 SQL/JSON/存疑三按钮 |
| 16 | 抽屉用例 | 溯源统一用同一抽屉 | 三个抽屉：`EvidenceDrawer`（证据原文/断言/影响，foot：复制引用/打开原文/关闭）、`DerivationDrawer`、`AlertsDrawer`（`AppShell.vue:12-17`） | 结构分散，建议以原型为骨架统一 |
| 17 | 空/错误/加载态 | 原型只有示意样式（tokens 页 `2450-2462`） | 通用组件齐全：`EmptyState.vue` / `ErrorState.vue`（带重试）/ `SkeletonBlock.vue` | **现有更完整**，无需补齐，只需按 tokens 统一视觉 |
| 18 | 页脚 | 原型无页脚 | 现有无页脚（`AppShell.vue:2-18`） | 一致（都不做） |
| 19 | 响应式断点 | 1240 / 1024 / 760 三档 + print（`index.html:823,833,867,877`、V1 同 `1891,1901`） | 1240 / 1024 两档 + print（`app.css:826,841,849`） | **缺 760 移动档**（侧栏折叠、表格横滚策略） |
| 20 | 主题与涨跌色 | V1 用 `--up-color/--down-color`，V2 用 `--up/--down`（`index.html:1168` 内 v1-css），默认红涨绿跌 | 两套命名都兼容（`app.css:22-29`）；另支持设置抽屉切换「绿涨红跌」（`html[data-updown="green"]` 时互换 up/down，`app.css:70-74`） | 现有**多一个涨跌色开关**（原型无）；建议保留并在设计规范页登记 |
| 21 | 全局 CSS 类覆盖 | V2 专用类：`alert-summary/sum-card/dag-track/dag-node/meta-badge/run-strip/run-cell/trace-tree/threshold-card/th-impact/laws-grid/law-card/hist-table/analogy/model-card/force-row/kpi-z/version-pill/drawer-tabs/chip-toggle/winrate/cal-star/cal-chips/sf-bar` | `app.css` **全部缺失**（已逐类检索）；而 V1 类 `kpi-grid/watch-card/heat-tile/toc-card/article/quote/brief-table/seg/pill/search-trigger/notif-dot/nav-badge/palette` 均存在（`app.css:95-787`） | **这是本次改造最大的样式工作量**：V2 四页 + 壳层需新增约 20+ 类，而非改现有类 |
| 22 | 键盘快捷键 | 原型：Ctrl+K、`/` 聚焦搜索（`index.html:3278+` 脚本内） | 有：Ctrl/Cmd+K、`/` 打开命令面板、Esc 逐层关闭（`AppShell.vue:53-72`） | 一致（现有 `/` 打开的是命令面板，原型是聚焦搜索框，行为近似） |
| 23 | 深链兼容 | 原型 `?view=&theme=&open=` 与 hash（`index.html:3278+`） | 现有 `?palette=1/?settings=1/?alerts=1/?doc=/?history=/?brief=`（`AppShell.vue:100-116`） | 参数体系不同；迁移期需保留现有深链 |
| 24 | 主题持久化 | localStorage `epic-v2-prefs`（`3278+`） | `stores/prefs.ts`（含 density 紧凑模式，`AppShell.vue:82-88`） | 现有多 density 能力，原型无；键名不兼容 |

---

## 四、缺口功能清单（可落地）

优先级：P0 = 一周内可落地且影响原型还原度；P1 = 需接口/数据但可在两周内；P2 = 依赖采集或长期。

### 4.1 前端即可（不新增后端接口）

| # | 功能 | 原型位置 | 现有替代 | 缺失原因 | 建议实现（文件 + 签名） |
|---|---|---|---|---|---|
| F1 | 侧栏分组/文案/占位徽标对齐 | `index.html:2463-2503` | `Sidebar.vue:56-88` 现有 15 项 4 组 | 分组名与产品文案不同 | 改 `NAV_GROUPS`，加 `pending?: boolean` 字段渲染「待接入」；根级 brand 文案改 `Sidebar.vue:3-9` |
| F2 | 顶栏数据时点 + 健康度 pill + 版本徽标 | `2520-2535` | `Topbar.vue:14-17`「刷新于」 | 无健康度聚合与数据时点口径 | `Topbar.vue` 新增 `healthPill` computed：`dataAsOf` 取 `health.health.time_local` 或 `overview.asof`；版本 `v{{ health.health?.version }}` |
| F3 | 预警台侧栏未读 badge | `2488` | `Sidebar.vue:101-105` 无 `/alerts` 分支 | 遗漏 | `badgeFor("/alerts") → alerts.unread`（`stores/alerts.ts` 已有 unread） |
| F4 | 命令面板文案与计数 | `3264-3274` | `CommandPalette.vue:11,39-45` | 文案未对齐 | 改 placeholder；foot 加「共 N 个视图 · M 个操作」，N/M 由 `PAGES.length`/`actions.length` 计算 |
| F5 | 周期页 hero + hero-tags + 3 meta-badge | `2541-2557` | 无（`CycleView.vue:3-22` 仅页面头） | 该区块未实现 | `CycleView.vue` 顶部新增 `<section class="hero">`；数据绑 `state.value.long_cycle`、`short_cycle`、`composites`；tags 由 readings 前 3 条异常项生成；meta 徽标见 F6 接口 |
| F6 | 周期罗盘四象限 + 指针 + 角度文案 | `2560-2577` | 六分量雷达（`CycleView.vue:83-144`） | 图形语义不同 | 新增 `components/domain/CompassQuadrant.vue`，props `{ angle:number; phase:string }`；角度由 `short_cycle.variables`（增长/通胀）映射 −45..+45 |
| F7 | 五力仪表卡（先按现有 6 力中的 5 力） | `2579-2608` | 无 | 未实现 | 新增 `components/domain/ForceGauge.vue`，props `rows: {key,label,value,evidenceCount,status}[]`；数据 `state.value.composites`（DMI/ICI/ECI/GROWTH/LIQUIDITY 取 5 项，缺失 2 力标「待接入」） |
| F8 | 关键读数 8 KPI 网格 | `2612-2653` | 4 张语义不同的 KPI（`CycleView.vue:28-79`） | 未实现 | 新增 `components/domain/ReadingKpi.vue` + `CycleView` 中 `kpi-grid` 8 卡；数据 `state.value.readings` 过滤 `us_10y/us_real10y/us_curve_slope/gold_mom/cn_curve_slope`，金银比/铜/美元指数走 F11 接口或先显「—」 |
| F9 | 今日预警卡（周期页） | `2655-2695` | 无 | 未实现 | 复用 `AlertsDrawer` 数据源：`alerts.items.slice(0,3)`；新增 `components/domain/AlertMiniList.vue` |
| F10 | 历史类比 Top3 按钮行 | `2701-2714` | 类比卡在页底（`CycleView.vue:222-278`） | 位置/形态不同 | 卡片上移，3 个 `button.analogy`，点击 `router.push('/pipeline?code=cycle.analogs')` |
| F11 | 管线 run-strip + DAG 6 节点 | `2868-2930` | 运行列表 + 步骤链（`PipelineView.vue:60-148`） | 未实现 | 新增 `components/domain/PipelineDag.vue`；数据 `GET /api/v2/runs/{run_id}` 的 `steps[]`（`seq/name/kind/duration_ms/outputs/error`）；节点数由 `steps.length` 驱动 |
| F12 | 溯源 L1–L5 静态展开面板 | `2933-2990` | `DerivationDrawer`（抽屉） | 未实现内嵌面板 | 抽出 `components/domain/TracePanel.vue`（props `derivationId`），L2 瀑布缺数据时降级为 `inputs[]` 列表；L3 用 `rules_hit`，L4 用 `inputs[]`，L5 用 `inputs[].source/asof` |
| F13 | 反事实沙盘（前端公式版） | `2984-3012` | 无 | 未实现 | 新增 `components/domain/ScenarioSandbox.vue`，3 个 `input[type=range]`；强度 = `base 68 + 0.1*Δreal10y − 0.8*Δdxy + 0.15*ΔcbGold`（演示公式，明确标注「示意」）；后续替换为 F20 接口 |
| F14 | 预警台严重度 seg 筛选 + 表头列 | `3056-3148` | 无筛选（`AlertsView.vue:62-70`） | 未实现 | `AlertsView.vue` 加 `severityFilter` ref + `computed filteredAlerts`；表头补「置信度」列（先「—」） |
| F15 | 阈值编辑器（只读 + 待保存态） | `3150-3174` | 只读规则表（`:139-170`） | 未实现 | 新增 `components/domain/ThresholdEditor.vue`，`select` 项来自 `GET /api/v2/cycle/config` 的 `alerts`，保存按钮先置灰并提示「需接口 F19」 |
| F16 | 会员持仓 seg 化 + Top10 | `2128-2155` | `select` + Top20（`MarketView.vue:250-318`） | 形态与行数不同 | 改 `select` 为 `seg` 三态（products 只有 3 个，可用）；`getPositionMembers(product, 10)` |
| F17 | 导出 CSV / 表头排序 / 搜索 kbd | `2066, 2092-2100, 2073` | 无导出、无排序、无 kbd（`MarketView.vue:3-66`） | 未实现 | `exportCsv()` 用 `snapshot` 数据 `Blob`；`th-sort` 加 `sortKey/sortDir` ref；搜索框尾加 `<span class="kbd">/</span>` |
| F18 | 设计规范页（tokens） | `2312-2462` | 无（`SystemView.vue` 是运行状态） | 整套页面缺失 | 新增 `views/DesignSystemView.vue` + 路由 `/system/design`，7 张卡直接读 `app.css` 变量；`router/index.ts:89` 后追加 |
| F19 | 世界长河 filterbar/zoom/图例对齐 | `2728-2771` | 两个 seg 在卡头（`HistoryView.vue:74-97`） | 布局差异 | 抽出独立 `filterbar` 行；加 `zoom` 百分比与 ± 按钮（仅改 `window` 区间，不重绘 SVG） |
| F20 | 抽屉 kicker + tabs 骨架 | `3240-3262` | `ui/Drawer.vue:3-24` 无 kicker/tabs | 结构缺失 | 给 `Drawer.vue` 加可选 `kicker` prop 与 `tabs` slot；三个抽屉按原型统一 foot 按钮文案（复制引用 / 查看 SQL / 导出 JSON / 标记存疑），其中「查看 SQL/导出 JSON」先做前端导出 |
| F21 | 760 断点 | `867, 1901` | `app.css:841/849` 只到 1024 | 缺移动档 | `app.css` 追加 `@media (max-width: 760px)`：侧栏收成 rail、表格横向滚动、kpi-grid 1 列 |

### 4.2 需后端接口（含扩展）

| # | 接口 | 用途 / 原型位置 | 现状 | 缺失原因 | 建议签名与响应字段 |
|---|---|---|---|---|---|
| A1 | `PATCH /api/v2/cycle/config` | 阈值编辑器保存（`3150-3174`） | 只有 `GET /api/v2/cycle/config`（`cycle.py:154`） | 写接口不存在；原型也声明「阈值改动需人工确认」 | `PATCH /api/v2/cycle/config` body `{alerts: {US30Y?: {threshold: number}, ...}}` → `{ok: boolean, version: string, requires_run: true}`；审计日志建议复用 `AnalysisRun` 或新表 |
| A2 | `POST /api/v2/cycle/scenario` | 反事实沙盘（`2984-3012`） | `GET /api/v2/cycle/scenarios` 是静态情景（`cycle.py:132`） | 无参数化计算 | body `{us_real10y_bp: number, dxy_pct: number, cb_gold_pct: number}` → `{strength: number, base: number, contributions: [{key,value}], asof, method_version}` |
| A3 | `GET /api/v2/alerts`（或扩展 `/api/alerts`） | 预警表列 + 胜率 + 置信度（`3056-3148`） | `GET /api/alerts` 仅 7 字段（`alerts.py:33-44`）；`GET /api/v2/cycle/alerts` 是 derivation payload（`cycle.py:143`） | 两套数据源都不含「当前值/阈值/距离/置信度/胜率/asof」 | 建议新接口返回 `{items:[{id,severity,label,category,region,current,threshold,op,distance,confidence,winrate,asof,why,falsifier,source}], counts:{high,medium,low}, asof}`；`winrate` 允许 null |
| A4 | `GET /api/v2/cycle/readings` | compass 8 卡 + spark（`2612-2653`） | readings 嵌在 `GET /api/v2/cycle/state` 内（`cycle.py:88`），无 spark、缺 4 个指标 | 无聚合序列接口 | `GET /api/v2/cycle/readings?ids=us_10y,us_real10y,...` → `{asof, items:[{id,name,value,unit,z,pct,score_value,delta,spark:[number]}]}`；`gold_silver_ratio/usd_index/lme_copper/cn_us_spread` 需先补指标（见 B2） |
| A5 | `GET /api/system/coverage` | 顶栏健康 97.2% + 侧栏序列覆盖 14/18（`2495-2526`） | `GET /api/system/sources`（`market.py:325`）只有源级健康 | 无覆盖率聚合 | `{series_total, series_ok, coverage_pct, health_pct, last_sync, sources:[{name,status,stale_sec}]}` |
| A6 | `GET /api/v2/cycle/meta` | hero 的「规则版本 R-2026.11 / 下次校准 2026-12-05」+ 模型卡（`3015-3034`） | `GET /api/v2/cycle/config` 有 `version`，无校准日期/回测/Brier | 元数据未暴露 | `{rules_version, next_calibration, shadow_model, inputs_series, params_count, last_backtest, brier, falsifier_count}` |
| A7 | 扩展 `GET /api/calendar` | 财经日历预期/前值/影响资产（`3177-3232`） | 仅 `ts/name/category/country/importance`（`market.py:259-263`） | 表无字段 | 增加 `forecast, previous, unit, affected_assets[]`（可从 `CalendarEvent` 模型扩列） |
| A8 | 扩展 `GET /api/v2/timeline/eras` | 周期对照表 7 列（`2791-2839`） | 返回 `dataset.ERAS`：`name/rise/peak/decline/reserve/innovation/lesson`（`timeline.py:183`，`timeline.py:99-102` 计数字段） | 缺 `golden_age/turning/current_stage` | 在 `dataset.ERAS` 增 3 字段并透出；无数据时返回 null 由前端降级 |
| A9 | 扩展 `GET /api/v2/derivations/{id}` | 溯源 L2 瀑布 / L4 分位 | 现有 `claim/value/confidence/inputs/steps/rules_hit`（`cycle.py:45-64` 同构） | 无 `contributions[]` 与 `pct/momentum` | 增 `contributions:[{key,label,share}]`、`inputs[].pct/inputs[].momentum` |
| A10 | 扩展 `GET /api/briefs/{id}` | 关联证据卡（`2290-2308`）+ quote 块 | `serializers.py:281-292` 无 `evidence_ids` | 未关联 | 增 `evidence_ids: string[]` 与 `main_thesis: {claim, tags[]}` |

### 4.3 需数据 / 采集

| # | 数据 | 原型位置 | 现状 | 缺失原因 | 建议 |
|---|---|---|---|---|---|
| B1 | 金银比、LME 铜绝对价、美元指数**水平值**、中美 10Y 利差 | `2612-2653` 8 卡中的 4 卡 | `config/cycle.yaml` 只有 `us_copper_gold`（比值）、`dxy_mom`（动量）、`us_real10y` 等，无绝对水平（`cycle.yaml:56-184`） | 指标定义是动量/比值，不是水平 | 在 `config/cycle.yaml` 新增 4 个 reading（`expr: XAU/XAG`、`CU`、`DXY`、`US10Y - CN10Y`）；确认 `instrument` 表已收录 `XAG/CU/DXY`（`GET /api/market/snapshot` 可查） |
| B2 | 五力中的「自然冲击 / 技术革命」评分 | `2579-2608` 5 行中的 2 行 | `scores` 只有 6 个（DMI/ICI/ECI/GROWTH/INFLATION/LIQUIDITY，`config/cycle.yaml:25-42`） | 评分体系缺 2 个维度 | 新增 `NATURE`、`TECH` 两个 score + 指标（自然灾害指数、AI/算力资本开支等）；无数据前 UI 标「待接入」 |
| B3 | 预警「触发后 20 日胜率」 | `winrate` 列（`3100-3130`） | 无任何回测/后验表 | 需事件后验统计 | 新增后验作业（按 alert_id 记录触发日 → 20 日后收益），落 `alert_outcomes` 表；短期接口返回 null |
| B4 | 财经日历预期/前值/影响资产 | `3177-3232` | `CalendarEvent` 无这些列（`market.py:259-263`） | 采集源只入库 5 字段 | 扩采集解析（如 investing/东财日历），或先人工维护近 7 天事件 |
| B5 | 帝国「黄金期 / 转折 / 当前阶段」 | `2791-2839` 对照表 | `dataset.ERAS` 只有 rise/peak/decline | 叙事数据集字段不足 | 扩 `backend/app/timeline/dataset.py`（或等价文件）的 ERAS 结构；数据为叙事判断，标 C 级 |
| B6 | 「数据覆盖 14/18」的分母口径 | `2499, 2556` | 无可枚举的 18 个序列清单 | 序列总数未定义 | A5 接口返回 `series_total` 时以 `config/cycle.yaml` 的 indicators 总数为分母（当前约 32 个 id），或先固定口径并在 UI 标注「示意」 |

---

## 五、风险与依赖

1. **data-asof 口径不一致（最易被用户发现）**：原型顶栏统一显示 `2026-11-17 09:30` 与健康 97.2%（`index.html:2520-2526`）。现有各接口的时点来源不同：`/api/overview` 的 `asof` 来自 snapshot `meta.asof`（`overview.py:94`），`/api/v2/cycle/state` 的 `asof` 来自 derivation `asof`（`cycle.py:81`），Topbar 显示的是「页面刷新时刻」（`Topbar.vue:16,63-66`）。若直接改成原型样式，必须先生成 A5 接口并明确「数据时点 = 最新采集批次」，否则会出现顶栏时点与页面内表格时点不一致的信任问题。

2. **阈值编辑会触发重算并污染运行历史**：`POST /api/v2/cycle/run` 是唯一写操作（`cycle.py:171`），重算一次生成新 `AnalysisRun`（`cycle.py:74-86`）。原型要求「阈值改动需人工确认」（`index.html:3040`），现有只读表注释也是「改 `config/cycle.yaml` 后重算」（`AlertsView.vue:141-142`）。A1 接口若直接写入并重算，需：(a) config 版本号单调递增；(b) 每次改动写审计记录；(c) 允许「影子模式」只算不发布——否则历史 run 无法回溯。

3. **9 个「关键读数」里有 4 个当前没有水平值数据**：金银比、LME 铜价、美元指数水平、中美利差在 `config/cycle.yaml:46-184` 中没有对应 reading，现有只有比值/动量。这是「照原型做 8 卡」最容易变成假数据的地方，必须先确认 `instrument` 表覆盖（`GET /api/market/snapshot`，`market.py:52`）再排期，否则 UI 只能显示「待接入」，还原度无法达标。

4. **原型与现有页面并非一一对应**：原型 8 视图对应现有 5 个真实页面（overview/market/brief/cycle/history/pipeline/alerts = 7）+ 1 个无页面（tokens）；现有 15 路由中有 8 个（`/rates`、`/analysis`、`/ledger`、`/principles`、`/signals`、`/gold`、`/theses`、`/system`）**没有设计稿**。改造范围必须先冻结：建议「只改壳层 + 7 个有原型页面 + 新增设计规范页」，其余页面仅套用新壳层与 tokens，不重排内容。

5. **样式工作量被低估**：`app.css` 没有任何 V2 组件类（§3 第 21 项），且断点少 760 档（§3 第 19 项）。若按原型实现 compass/history/pipeline/alerts，需要新增约 20+ 个类并补第三个断点，属于「新增样式体系」而非「微调」。

6. **简报富文本结构依赖后端渲染器**：原型 brief 的 `quote / brief-table / ev-link / brief-tag-line` 在 `backend/app/narrative/render.py:46-60` 中都不产出（只输出裸 `<table>/<h2>`），而 `app.css:604-660` 已备好 `.toc-card/.article/.quote/.brief-table` 样式——现状是「样式空转」。要还原原型，需改渲染器（产生语义类名）或改 markdown 模板，属于 A10 的连带改动。

7. **历史页交互形态需要产品决策**：原型事件详情是**右侧内嵌栏**（`2773-2788`），现有是全屏抽屉（`HistoryView.vue:289-334`）。两者信息架构不同（内嵌栏可与时间轴同屏对照），改造涉及 `HistoryView` 布局重排，不是纯样式问题。

8. **会员持仓数据覆盖有限**：`GET /api/positions/members` 依赖 `MemberPosition` 表（`market.py:188-218`），只有期货会员排名；原型 Top10 双边 + 净持仓公式（`index.html:2136-2155`）在无数据品种上会空表，需要空态文案（现有 `EmptyState` 可用）。
