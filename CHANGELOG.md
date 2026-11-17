# 变更记录（CHANGELOG）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，版本号使用 [语义化版本](https://semver.org/lang/zh-CN/) 的预发布形式（`1.0.0-rc1`）。

> 运行时版本以 `backend/app/__init__.py` 为唯一来源，`pyproject.toml` 与 `/api/system/health` 必须一致（`tests/test_release.py` 会校验）。

## [Unreleased]

### 新增（V2.0 M4 前端：预测台账与原则库，2026-11-17）

- **新增预测台账页 `/ledger`**（`frontend/src/views/LedgerView.vue`）：4 个 KPI（已结命中率、Brier 与分档说明、未结/已结与下一到期、原则命中 x/26）；「登记一条新预测」表单（12 类对象、方向、期限、主观概率、基线、备注）直接调用 `POST /api/v2/ledger/forecasts`，并自动预选第一个对象；预测清单分「全部/未结/已结」并逐条显示方向、概率、基线、登记日、到期日、实际值与 Brier；下方「校准分桶」（≤20 / 21–60 / >60 天）与「原则核对现状」（成立/接近/不成立/缺数据四态 + 命中样例）。
- **新增原则库页 `/principles`**（`frontend/src/views/PrinciplesView.vue`）：四态计数条 + 类别 chip（全部 26 / 债务与货币 / 周期与秩序 / 冲突与政治 / 市场与资产）+ 状态 chip + 关键词搜索；每条原则一张卡，显示原文/推断/争议依据级、证据级、可观测指标、信号、失效条件、当前指标与阈值-当前值、核对结论，卡片左边框按状态着色，定性原则显式标注「留待复盘时人工核对」。
- **接线**：`router/index.ts` 新增 `/ledger`、`/principles`（研究分析组）；`Sidebar.vue` 在「世界长河」后加入两项（图标 `#i-tasks`、`#i-shield-check`）；`api/types.ts` 新增台账类型 12 个，`api/endpoints.ts` 新增 `getLedgerOverview / getLedgerPrinciples / getLedgerForecasts / getLedgerCalibration / createLedgerForecast / runLedger`。
- **验证**：`npm run build` 成功（`vue-tsc --noEmit` 通过，`LedgerView-BUIZAIwr.js` 13.20KB、`PrinciplesView-xKkTUxo.js` 5.60KB）；headless Chrome 1440 宽截图复核两页结构与真实数据（原则库 12 成立 / 2 接近 / 5 不成立 / 7 缺数据，与接口一致）；修复构建期类型错误 2 处（`LedgerRunResult` 未导入、`lastUpdated` 为 `Date` 需转 ISO）与截图后发现的两处小问题（默认预测对象未预选、原则卡文案错字）。

### 新增（V2.0 M4 后端：原则库核对、预测台账与校准，2026-11-17）

- **新增原则库数据即代码**（`backend/app/ledger/principles.py`）：26 条原则（A 债务货币 8 / B 周期秩序 8 / C 冲突政治 5 / D 市场资产 5），每条带原文/推断/争议标注、可观测指标、信号、失效条件与证据级；其中 19 条配置了可自动核对的 `metric/op/threshold/near`（含观察线与「接近」判定），7 条定性原则显式保持 `unknown` 交人工复盘。
- **新增两张表**（`backend/app/models/v2.py`）：`principles` 与 `principle_checks`（唯一约束 `(principle_id, asof)`），让「今天哪条原则成立」可逐日回看。
- **新增台账编排**（`backend/app/ledger/engine.py`）：`ledger.review.v1` 在同一个 `RunRecorder` 内五步（读周期快照 → 同步原则 → 核对原则 → 对账到期预测 → 派生结论）；指标字典合并周期分量、读数、预警指标与外部结构性常量（全球债务/GDP 311%，IIF 2026H1，显式来源）；预测支持 12 类对象（周期六分量/黄金综合评分/XAUUSD/美债 10Y·30Y/中债 10Y/USDCNH），到期按 `target_date <= today` 结算，方向 up/down/flat（flat 容差 2%），Brier 用登记概率计算；校准按 ≤20 天 / 21–60 天 / >60 天分桶。派生 `ledger.principles`（E2）、`ledger.calibration`（E2，样本 <20 条时置信度 0.4）、`ledger.forecasts`（E1）。
- **新增台账接口 `/api/v2/ledger`**：`GET /overview`（空库懒触发一次运行）、`/principles`、`/forecasts?status=open|resolved`、`/calibration`；`POST /forecasts`（code/direction/horizon_days/probability/point/baseline_value/notes，服务端校验 code 与方向）；`POST /run`。
- **真实库核对结果（2026-11-17）**：26 条中命中 12（A2 利息/收入 25%、A3·B1 长周期位置 0.98、A7 全球债务/GDP 311%、A8 美元储备 56.7%、B2 增长 29.8、B4 极化 82、B5 关税 60、B6·C5 制裁 70、C2 抗议 65、C3 赤字 5.8%）、接近 2（A4 r−g +0.9pp 未转负、C4 同盟退出 50）、不成立 5（A6 SOFR−EFFR 0.02、B8 央行购金 12 个月 106 吨、C1 不平等 21、D1 黄金 60 日动量 −16%、D3 油价 60 日动量 0.85%）、缺数据 7（定性原则）。
- **验证**：新增 `tests/test_v2_ledger.py` 14 条（数据集完整性、`_eval` 四态、指标汇总与别名、同步幂等、核对状态分布、预测登记校验、到期结算与 Brier、校准分桶、端到端三条推导、API 形状与创建/运行）；全量 `pytest tests -q` → **266 passed**；`scripts/lint.py` → PASSED（0 errors, 0 warnings）。

### 新增（V2.0 M3 世界长河：1500–2026 年表、霸权周期与当下坐标，2026-11-17）

诉求：「我选择B，把所有功能全部开发完成，保质保量，不能有一点瑕疵，并创建分支保留V1.0版本，创建V2.0版本分支，在此分支上开始开发。」

- **新增长河数据即代码**（`backend/app/timeline/dataset.py`）：73 条精选事件（1500–2026，分 L 长周期/B 大周期/S 短周期/E 事件冲击四层，每条带类别、证据级 A/B/C、相关势力、摘要与来源；A 级必须有公开 URL，C 级标注「叙事判断」）；6 轮霸权时期（中国明/西葡/荷兰/英国/美国/多极，含崛起-顶点-衰退、储备货币、创新与教训）；`GDP_SHARE` 27 点（Maddison 2023）、`RESERVE_SHARE` 8 点（IMF COFER + 1913 年研究者估计）、当下坐标 6 维（储备份额/债务收入/利息收入/r−g/内部极化/外部冲突）、3 个历史类比（1937/1971–73/1900–14）、10 条历史规律 H1–H10（含「可计算」说明）。本次补齐 E 层事件冲击 9 条（1987/1997/2000/2001/2008/2011/2020/2022/2026），使四层泳道都有内容。
- **新增长河编排**（`backend/app/timeline/engine.py`）：`run_timeline()` 在同一 `RunRecorder` 内四步（事件入库 → 份额入库 → 读取周期引擎快照 → 派生结论）；事件与实力份额按稳定 id 幂等 upsert；派生 `timeline.position`（E2，六维坐标 + 三个类比 + 周期读数）、`timeline.power.shift`（E1，实力领先储备 30–50 年）、`timeline.catalog`（E1，条数与证据级分布），全部带 caveats/falsifiers/opposing；周期引擎无数据时显式降级（`timeline.cycle_missing`）。
- **新增长河接口 `/api/v2/timeline`**（`backend/app/api/timeline.py`）：`GET /overview`（空库懒触发入库）、`/events`（layer/era/power/grade/年份区间/关键词过滤，未知 era 返回 404）、`/eras`、`/powers`、`/position`（无则 503）、`POST /run`。
- **新增「世界长河」页 `/history`**（`frontend/src/views/HistoryView.vue`）：4 个 KPI（事件数与证据级分布、六轮霸权与当前「多极/待定」、美元储备份额 56.7% 对 1999 年约 71%、历史类比最相似 1971–73 62%）；自绘 HTML 时间轴（1500–2026、四层泳道、霸权时期色带与图例、时间窗切换 1500–1800/1800–1914/1914–1991/1991–2026/全部、层过滤、点击事件打开详情抽屉、支持 `/history?event=<id>` 深链）；GDP 份额与储备货币份额两张 ECharts 折线（图例用中文，储备线覆盖 USD/GBP/EUR/CNY）；当下坐标表（6 维：当前读数、历史锚点、判断、证据级）；历史类比卡（相似/不同点）；霸权更替表；十条历史规律卡；底部口径声明（精选非全集、叙事分期为 C/D 级）与降级原因。
- **ECharts 注册补充**：`EChart.vue` 增 `ScatterChart` 与 `MarkAreaComponent`，供长河时间轴等图表使用。
- **入口**：`router/index.ts` 增 `/history`（group 研究分析）；`Sidebar.vue` 研究分析组增「世界长河」（`#i-book`）；`api/types.ts` 增长河 11 个类型、`endpoints.ts` 增 `getTimelineOverview/getTimelineEvents/runTimeline`。
- **验证**：新增 `tests/test_v2_timeline.py` 11 条（数据集完整性 73 条、A 级必须有来源、跨度与 6 个霸权期、份额关键点、H1–H10 与 3 类比、入库幂等、端到端三条推导、重复运行单份目录、接口形状与过滤、POST /run）；真实库入库 73 条事件 / 6 期 / 10 条规律 / 35 行实力份额，六维读数为储备 56.7%、债务 133%、利息/收入 25.0%、r−g +0.9pp、ICI 72.8、ECI 58.2；`pytest tests -q` → **252 passed**；`scripts/lint.py` → PASSED；`npm run build` 成功；`127.0.0.1:8771` 截图验收 `/history` 四层时间轴、两张份额折线、六维坐标、三个类比与十条规律，抽屉与深链正常。

### 新增（V2.0 M2 前端：周期罗盘与预警台，2026-11-17）

诉求：「我选择B，把所有功能全部开发完成，保质保量，不能有一点瑕疵，并创建分支保留V1.0版本，创建V2.0版本分支，在此分支上开始开发。」

- **新增「周期罗盘」页 `/cycle`**（`frontend/src/views/CycleView.vue`）：4 个 KPI（长债务阶段/DMI、短债务状态、债务可持续模式、历史类比最相似月份与相似度）；自绘 SVG 六分量罗盘（DMI/ICI/ECI/GROWTH/INFLATION/LIQUIDITY，100×Φ(z) 映射，中心显示长债务阶段）；五层周期卡（长债务/短债务/库存/信用流动性/政治窗口，各带阶段、置信、含义、下一阶段与切换条件，库存代理口径显式标注）；60 个月分量历史折线（DMI/GROWTH/INFLATION/LIQUIDITY）；四情景概率与资产含义（S1 35%/S2 30%/S3 22%/S4 14%，附公式）；历史类比 Top4（月份、相似度、增长/通胀状态、样本内提示）；债务可持续性（r−g、利息/收入、赤字/GDP、债务/GDP 与阈值）；世界秩序位置（美国内部秩序与国际秩序分开判定 + 八项实力指数 + 储备份额）；底部降级原因。
- **新增「预警台」页 `/alerts`**（`frontend/src/views/AlertsView.vue`）：高/中/低风险触发计数与临近政治事件；W1–W12 预警清单（状态、严重度、规则、指标、当前值、阈值、距离、观测日，点击行展开「为什么是这条规则 / 失效条件 / 数据来源与口径」，缺失指标显式记为「未知」）；规则与阈值只读表（来自 `config/cycle.yaml`，提示改配置后重算）；政治日历（按天数排序，30 天内进入高不确定性窗口高亮，已过事件标注「已过 N 天」）。
- **周期接口补展示字段**（`backend/app/cycle/engine.py`）：`composites` 增 `name/degraded/degrade_reason`；`long_cycle` 增 `phase_id/band/confidence/evidence/next_phase/exit_condition/hysteresis_held`；`short_cycle` 增 `confidence/growth_12m_change`；`inventory` 增 `degrade_reason/meaning/asset/price_momentum_60d/inventory_proxy_20d/confidence/evidence`；`political` 增 `days_to_nearest/events`——让前端能直白展示「阶段叫什么、区间在哪、下一阶段是什么、为何降级」。
- **入口与类型**：`router/index.ts` 增 `/cycle`、`/alerts`（group 研究分析）；`Sidebar.vue` 研究分析组新增「周期罗盘」（`#i-target`）与「预警台」（`#i-bell`）；`api/types.ts` 增 18 个周期类型、`endpoints.ts` 增 `getCycleState/getCycleConfig/runCycle`。
- **验证**：`npm run build`（vue-tsc + vite）成功 8.10s；`scripts/lint.py` → PASSED；`pytest tests -q` → **241 passed**；真实库起 `127.0.0.1:8771` 截 `/cycle` 与 `/alerts`——周期罗盘显示长债务「顶部」（区间 55–70、位置 98%、置信 0.91）、短债务「衰退」（置信 0.85）、债务可持续「财政主导」、36 个历史类比（首条 2023-09 相似 68%）、四情景 35/30/22/14，预警台显示 12 条规则全部未触发（0/12）且 W1/W5/W7 距离明确、政治日历给出 2026-11-03 中期选举已过 14 天与 2027-01-10 休战到期 54 天。

### 新增（V2.0 M2 后端：EPIC-C 2.0 周期引擎与周期接口，2026-11-17）

诉求：「我选择B，把所有功能全部开发完成，保质保量，不能有一点瑕疵，并创建分支保留V1.0版本，创建V2.0版本分支，在此分支上开始开发。」

- **新增 `config/cycle.yaml`**：全部阈值/权重/来源集中配置——6 个分量（DMI/ICI/ECI/GROWTH/INFLATION/LIQUIDITY）、16 个市场指标表达式（如 `US10Y - US2Y`、`CU / XAUUSD`）、15 个结构性人工指标（债务/GDP、利息/财政收入、赤字、储备份额、r−g、极化、信任、不平等、冲突、制裁、关税等，每条带 `evidence/scale/source/url` 与观测日）、7 阶段长债务周期 band + 滞回、5 态短债务周期规则、库存四态、世界秩序六阶段与 SPI 八项权重、政治日历、四情景基准概率、W1–W12 预警阈值。
- **新增 `backend/app/cycle/`**（10 个模块）：`config`（配置加载与证据权重）、`market`（行情 + 宏观面板、表达式求值、10 年滚动 z-score）、`indicators`（指标读数与 E0–E4 证据级、缺失/陈旧降级）、`composite`（按证据质量加权重归一、覆盖率与陈旧惩罚后的置信度、E4 占比过高自动压置信）、`phases`（长债务 7 阶段 + 滞回、短周期 5 态 + 两次确认、流动性三态、库存周期、政治日历）、`history`（60 个月分量轨迹，供图表与类比）、`sustainability`（r−g、利息/收入 20%/30%、赤字三模式判别）、`world`（美国内部秩序与国际秩序分开判定、八项实力指数）、`analogs`（20 维状态向量余弦 + 欧氏、剔除最近 12 个月与样本内间隔）、`scenarios`（S1–S4 规则化调整并归一化）、`alerts`（阈值比较、缺指标记 unknown 不默认未触发）。
- **新增周期编排 `backend/app/cycle/engine.py`**：`run_cycle()` 在同一个 `RunRecorder` 内执行 10 个步骤（载入面板 → 指标读数 → 分量合成 → 历史轨迹 → 周期定位 → 债务可持续性 → 世界秩序 → 历史类比 → 情景 → 预警），派生 `cycle.state.world`、`cycle.scenarios`、`cycle.sustainability.US`、`cycle.world.order`、`cycle.analogs`、`cycle.alerts`、`cycle.history` 七条结论（含 caveats/falsifiers/opposing），并写入 `scenario_runs` 与 `cycle.*` 观测。
- **新增周期接口 `/api/v2/cycle`**（`backend/app/api/cycle.py`）：`GET /state`（无数据时懒触发一次运行）、`/indicators?layer=`、`/history`、`/analogs`、`/scenarios`、`/alerts`、`/config`，`POST /run` 手动触发；统一返回 claim/value/证据级/置信度/asof/run_id/caveats/falsifiers。
- **口径修正**：央行黄金本地序列是存量口径（WGC/IFS），预警 W5 改为「12 个月净增 >300 吨」并用最接近 365 天的观测做差分（实测 106.4 吨），`docs/24` 同步注明与 WGC 季度净购金口径不可混用；黄金/原油动量统一为百分数与阈值比较。
- **验证**：新增 `tests/test_v2_cycle.py` 23 条（配置、z-score、合成降级、长/短周期滞回、情景和为 1、可持续性、世界秩序、类比剔除近期、历史轨迹、运行幂等、六个接口形状），全量 `pytest tests -q` → **241 passed**；`scripts/lint.py` → PASSED；真实库运行 `run_cycle` 状态 ok（DMI 69.7 / ICI 72.8 / ECI 58.2 / GROWTH 29.8 / INFLATION 21.1 / LIQUIDITY 47.3，长债务处顶部区间，四情景 34.5%/29.8%/22.1%/13.6%，12 条预警当前 0 触发）。

### 新增（V2.0 M1 玻璃盒前端：透明管线页与溯源抽屉，2026-11-17）

诉求：「我选择B，把所有功能全部开发完成，保质保量，不能有一点瑕疵，并创建分支保留V1.0版本，创建V2.0版本分支，在此分支上开始开发。」

- **新增前端类型与接口**：`frontend/src/api/types.ts` 增 `V2Run/V2Step/V2RuleHit/V2Derivation/V2Method/V2RunList/V2RunDetail/V2DerivationList/V2DerivationDetail/V2MethodList/V2Status`；`endpoints.ts` 增 `getV2Status/getV2Runs/getV2Run/getV2Derivations/getV2Derivation/getV2Methods`。
- **新增「透明管线」页 `/pipeline`**（`frontend/src/views/PipelineView.vue`）：顶部 4 个 KPI（最近运行、推导条数、运行/观测/方法数、降级与失败）；左侧运行记录列表；右侧 11 个步骤的步骤链（序号、名称、类型、耗时、输入/输出 JSON、错误与降级原因）；底部推导清单（结论、code、证据级、置信度、措辞、观测日、「为什么 →」），支持 `?code=regime.US` 深链过滤与 30 秒轮询。
- **新增「为什么」抽屉**（`frontend/src/components/domain/DerivationDrawer.vue`）：L1 结论（claim/value/证据级/置信度措辞）→ L2 推导步骤 → L3 规则命中 → L4 输入指标 → L5 反证与失效条件（caveats / falsifiers / opposing，全空时提示降低依赖），另有方法登记（method_id/version/code_sha）与父子谱系（parents/children）。
- **入口接线**：`router/index.ts` 注册 `/pipeline`（group 研究分析）；`Sidebar.vue` 研究分析组新增「透明管线」（`#i-layers`）；`AnalysisView.vue` 周期区块与市场风向卡新增「为什么是这个象限 / 读数 → 溯源」，带 `code` 参数跳到管线页。
- **验证**：`npm run build`（vue-tsc + vite）成功 7.68s；临时起 `127.0.0.1:8771` 服务（新代码）截 `/pipeline` 与 `/analysis`——管线页正确显示 11 步运行链、3 条推导（`wind.market` E3 55%、`regime.CN` E3 35%、`regime.US` E3 40%）与「为什么」入口，分析页溯源链接均落到带 code 参数的管线页。

### 新增（V2.0 M0 地基：透明化血缘引擎与玻璃盒接口，2026-11-17）

诉求：「我选择B，把所有功能全部开发完成，保质保量，不能有一点瑕疵，并创建分支保留V1.0版本，创建V2.0版本分支，在此分支上开始开发。」（分支 `v1.0-final` 保留 V1.0 终点，开发在 `v2.0`）

- **新增 13 张 V2.0 表**（`backend/app/models/v2.py`）：`analysis_runs`（一次运行：kind/subject/asof/status/method_id/code_version/duration/degraded_reasons）、`analysis_steps`（步骤序号/类型/输入/输出/耗时/错误）、`derivations`（稳定 id + claim/value/confidence/evidence_grade/inputs/steps/rules_hit/caveats/falsifiers/opposing）、`derivation_links`（父子谱系）、`method_registry`（方法登记与 `code_sha`）、`rule_hits`、`observations`（含 `vintage_date` 防前视）、`indicator_catalog`、`forecasts`、`forecast_outcomes`、`scenario_runs`、`timeline_events`、`power_index`。`init_db()` 自动建表并登记 6 个方法（`analytics.run/regime/wind/indicators`、`gold.composite/providers`）。
- **新增血缘引擎 `backend/app/provenance/`**：`RunRecorder` 提供 `start/step/finish/fail/degrade/derive/record_rule`；`derive_id = sha256(method@version|inputs|params|code_sha)[:32]` 保证同输入同结论幂等；证据等级 E0–E4；降级写入 `rule_hits` 并在运行上留痕。
- **新增玻璃盒接口 `/api/v2`**（`backend/app/api/glassbox.py`）：`GET /runs`、`/runs/{id}`（运行 + 步骤 + 规则命中 + 推导）、`/derivations`、`/derivations/{id}`（含方法、父子）、`/methods`、`/observations`、`/status`。
- **分析运行全部接入血缘**：`analytics/runner.py` 重写为「载入行情 → 对齐日历 → 指标 → 周期 → 风向 → 相关性 → 归因 → 类比 → 领先滞后 → 事件研究 → 财经日历研究」11 个步骤，并派生 `regime.US`、`regime.CN`、`wind.market`（证据级 E3，附反证与失效条件）；`gold/runner.py` 采集全程记为一次 `gold` 运行，派生 `gold.composite`（置信度随覆盖率 0.40→0.85），数据源失败逐项降级。
- **验证**：`pytest tests -q` → **218 passed**（新增 `tests/test_v2_provenance.py` 8 条：步骤顺序、推导幂等、降级、失败、哈希稳定性、方法登记、API 形状与 404）；`scripts/lint.py` → PASSED；对真实库执行一次分析 → 35 指标 / 2 周期 / 1 风向 / 1 相关性 / 6 归因 / 1 类比 / 1 领先滞后 / 1 事件 / 1 日历研究，运行状态 ok、11 个步骤、3 条推导落库。

### 工程（git reset --hard 事故复盘：取证、等价重建验证、防复发快照脚本，2026-11-17）

诉求：「针对 git commit-tree 的事故，请进行全面排查处理，如果有必要请把之前丢失的文件相关工作重新做一遍，避免功能丢失，请深刻反省。」

- **事故定性（如实）**：2026-11-17 15:3x，为消除提交信息里的 UTF-8 BOM 用 `git commit-tree` 重建了两个提交，随后用 `git reset --hard 3e4bf3b` 想"同步引用"，但它把**工作区强制回滚到该 tree**，覆盖了当时未提交的 `frontend/src` 6 个源文件、`scripts/_common.ps1`、`web/index.html`。BOM 的来源是 PowerShell **5.1** 的 `Out-File -Encoding utf8`（5.1 会写 BOM）。
- **取证结论**：`git fsck --unreachable --no-reflogs` 仅 `dd8206d`、`331529f` 两个不可达提交；`git diff dd8206d 4c8c7d1` 与 `git diff 331529f 3e4bf3b` **均为空** → commit-tree 未丢任何已提交内容；无 stash / 无 remote / 无 VSCode·Cursor 历史 / 回收站无副本；丢失内容从未 `git add`，**原始字节不可恢复**，只能从事故后幸存的未跟踪新构建产物（`web/assets/*` 18 个文件）反推重建。
- **等价重建与验证**：重建后与事故前最后提交 `28bca2e` 的差异收敛为 7 个文件 +120/−13，逐 hunk 对应「时点语义 / 黄金 as_of / netstat LISTENING」三类意图；本轮重新做行为级验证——`pytest tests -q` → **210 passed**、`scripts/lint.py` → PASSED、47 个 GET 端点 200、**headless Chrome 对 9 个路由做 DOM 断言全通过**（`/market` 采集时点与 4 分钟去重文案、`/rates` `mi-asof` 与「N 天前」、`/gold` `frow-asof` 与「各因子里最早的观测日」等）。
- **新增 [25 事故复盘文档](docs/25-事故复盘-git-reset-2026-11-17.md)**：结论摘要、时间线、取证表、损失清单与恢复方式、6 条"功能没丢"的证据、5 Whys 根因、反省、预防规约 R1–R8、复发演练、残余风险声明。
- **新增 `scripts/snapshot.ps1`（防复发工具，已自测）**：破坏性操作前把工作区落盘为 `data/backups/snapshot-<时间戳>/`（`head.txt`、`status.txt`、`worktree.patch`、`index.patch`、`untracked/` 原样副本），实测可用 `git apply` 回填被 `git checkout --` 抹掉的改动。
- **预防规约 R1–R8（立即生效）**：R1 有未提交改动时禁用 `reset --hard` / `checkout -- .` / `clean -fd` / `stash drop`；R2 破坏性操作前必跑 `snapshot.ps1`；R3 历史改写只在干净工作区或独立 worktree，引用迁移用 `git update-ref` / `reset --soft`；R4 提交信息用 Python `write_text(encoding="utf-8")` 生成，不在 PS 5.1 用 `Out-File -Encoding utf8`；R5 先提交能提交的、再动引用；R6 操作前后 `git status --porcelain` 对照留档；R7 每轮收尾 `git bundle create data/backups/repo-<日期>.bundle --all`；R8 验证产物保留到提交完成。
- **残余风险**：6 个前端文件为语义等价重建（注释/空行/辅助函数写法可能与原文不同，不影响运行）；vite 资产哈希与事故前不同；无法反推"不进入编译产物"的内容（如 SFC 注释）；仓库仍无 remote，结构级兜底依赖 R7 的 bundle。

### 维护（构建产物不入库、删除过渡期旧看板、利率卡 as_of 布局修正，2026-11-17）

诉求：全面复查前序改动是否仍在、功能是否正常，并做三项收尾——构建产物不进仓库、清理历史版本里没用的文件、把编译生成的 `web/` 从版本库摘出去。

- **历史改动逐项核验（未丢失）**：`backend/app` 关键机制计数——`DAILY_BAR_LIMIT` 8 处、`_guard_tail_bar` 2、`TENCENT_SINGLE_BAR` 6、`KNOWN_GAPS` 11、`clean_holiday_stubs` 4、`fill_bar_gaps` 4、`TENCENT_QUOTE_PREFERRED` 5、`continuity.silences` 1、`CONSENSUS_SHARE` 3、`write_lock` 9；新增测试 8 个文件（continuity / bars_quality / backfill / pipeline_guard / eastmoney_yield / macro_freq / writelock / quote_preferred）全部在位。
- **功能验证**：`pytest tests -q` → **210 passed**（删除旧看板用例后少 1 条）；`scripts/lint.py` → PASSED（0 error / 0 warning）；全部无路径参数 GET 端点冒烟 **47/47 → 200**（TestClient + OpenAPI 自动补必填 query）；本地服务 `http://127.0.0.1:8765` 用 headless Chrome 实截 `/`、`/market`、`/rates`、`/gold`、`/system` 五页，均正常渲染，`/gold` 因子行按各自 `as_of` 显示新鲜度。
- **构建产物不再入库**：`git rm -r --cached web`，`.gitignore` 增补 `web/`（附注释「由 scripts/build.ps1 / npm run build 生成，不入版本库」）；README、[02 系统架构](docs/02-系统架构设计.md)、[15 前端改造方案](docs/15-前端改造方案.md) 同步注明「克隆后需先构建一次」。`web/` 工作区文件保留，运行不受影响。
- **删除过渡期旧看板（历史无用文件清理）**：删除 `web-legacy/index.html`；`backend/app/main.py` 移除 `LEGACY_DIR` 与 `/legacy` 路由；`tests/test_frontend_build.py` 去掉旧看板断言与 `LEGACY` 常量（`test_spa_fallback_routes_present` 改为断言源码中不再出现 `/legacy`）；`scripts/lint.py` 去掉 web-legacy 缺失告警；`vite.config.ts` 注释更新。现在访问 `/legacy` 由 SPA 回退承接，路由层统一 redirect 到 `/`。
- **修复（前端重建引入的布局回归）**：利率卡原把 `as_of` 拼在 `.mi-code` 内，撑宽右侧导致序列标题被省略号截断（`中国国债2年` → `中国国债...`）。改为 `.mi-code` 只放代码，新增 `.mi-value-row` 包住数值与 `.mi-asof`（右对齐、等宽 8.5px、超期标黄 `.mi-asof--stale`），标题恢复完整、`as_of` 显示在数值右侧。
- 验证：`npm run build`（vue-tsc + vite）成功；重建后重截 `/rates` 与基线（`git archive 28bca2e web`）逐张对照，标题、数值、涨跌、`as_of` 均正常。

### 文档（V2.0 改造方案设计交付：透明化 / 周期引擎 / 历史图谱 / 原则库 / 交互原型，2026-11-17）

诉求：参考 TradingEconomics 的产品范式，把 EPIC 从「数据看板」升级为「可审计的宏观研判台」；同时把达利欧《原则》《债务危机》的框架落成可计算、可证伪的市场分析工具，给出 1500–2026 的历史周期轨迹与当下定位。本轮只交付方案与原型，**未改业务代码**（工作区既有未提交改动不纳入本次提交）。

- 新增 [18 V2.0 改造总案](docs/18-V2.0改造总案.md)：差异化定位（TE 卖数字，EPIC 卖「历史中的位置 + 判断有多可靠」）、四大支柱、新旧信息架构 8 区映射、数据模型 40→约 60 表、M0–M5 共约 17 周路线、R1–R8 风险、10 条已审计技术债（T1–T10，带文件行号证据）。
- 新增 [19 透明化业务流程设计](docs/19-透明化业务流程设计.md)：四层透明 L1–L4、证据等级 E0–E4（E4 不得单独构成信号）、七段式血缘与 vintage 快照防前视、`derivation_id` 哈希、Derivation JSON 结构、8 条 mermaid 业务流程图、6 个界面入口、置信度公式与措辞映射、12 张新表与 18 个 API、T1–T10 验收。
- 新增 [20 功能与接口设计](docs/20-功能与接口设计.md)：F1–F34 功能地图、统一响应 `{items,total,asof,run_id,degraded}` 与错误码、约 59 个新端点（基线 63 个 API 操作 / 59 路径 / 56 个路由装饰器）、13 张新表、16 个前端组件、A1–A8 验收。
- 新增 [21 UI 设计规范](docs/21-UI设计规范.md)：13 节，色彩/字阶/间距/栅格、10 个核心组件、ECharts 规则、4 个页面线框、动效、可访问性、交付与验收。
- 新增 [22 EPIC-C 周期引擎 2.0](docs/22-EPIC-C周期引擎2.0.md)：三层×五层周期、30 项指标与公式、DMI/ICI/ECI 与 RISK 合成、7 阶段状态机（滞回）、债务可持续性三模式（r−g、利息/收入 20%/30% 阈值）、四情景、历史类比、回测 6 项校验、`backend/app/cycle/` 落地结构、C 级假设声明。
- 新增 [23 历史周期图谱 1500–2026](docs/23-历史周期图谱1500-2026.md)：五霸权周期表、约 60 条大事年表（L/B/S/E 层 + A–D 证据级）、10 条历史规律 H1–H10、当下五维对照、3 个历史类比、`timeline_events` DDL 与长河交互。
- 新增 [24 原则库与当下研判](docs/24-原则库与当下研判.md)：26 条原则（依据类型/指标/信号/失效条件）、「原则→规则→信号」三级落地、2026-11-17 五层周期定位（长债务晚期 0.70 / 国际秩序第六阶段 0.58 / 美国内部第五阶段 0.66 / 短债务过热后段 0.61）、四情景、12 条预警 W1–W12、决策检查清单、7 项观察点、诚实边界。
- 新增研究笔记四份：[TradingEconomics 标杆](docs/research/tradingeconomics-benchmark.md)（IA/卡片/API/付费墙实测，抄 10 不抄 5）、[达利欧框架](docs/research/dalio-framework.md)（原文出处、48 案例、7 阶段、四杠杆、五力、指标映射、8 条未核实）、[1500–2026 历史核实](docs/research/history-1500-2026.md)（MPD2023 GDP 份额、COFER 储备份额、62 条危机与战争、周期长度的学术检验、24 节点 JSON）、[代码库审计](docs/research/codebase-audit.md)（端点/表/算法/调度/EPIC-C 差距/技术债）。
- 新增高保真交互原型 [docs/design/mockup-v2/](docs/design/mockup-v2/index.html)：单文件离线 HTML（204 KB），4 视图（周期罗盘 / 世界长河 / 透明管线 / 预警台）+ 五层溯源抽屉 + 浅色主题，`?view/theme/open` 深链与 localStorage 记忆，6 张 1440×1000 截图。
- README 更新：新增 V2.0 文档索引（18–24 + research + mockup-v2）、页面预览段、里程碑 `V2.0 🚧 方案完成`。
- 数据与事实修正（相对早期草稿）：联邦债务 $40.617T、FY2026 赤字 5.8% GDP、FOMC 3.75–4.00%、美元储备份额 2026Q2 56.70%（1999 约 71%，Q1/Q2 回升，撤销「崩塌论」）、全球债务 $365T = 311% GDP、央行 Q3 购金 321 吨；1870 年 MPD 口径美国 GDP 已超英国、1913 年英镑占已知官方储备约 64%；**DB XAUUSD 3,864 与 WGC 转述 4,065–4,140 差约 5%，已标注为待对账项**。
- 验证：`scripts/lint.py` → PASSED（0 errors / 0 warnings，含 docs 链接检查）；docs 内相对链接 0 断链；原型 `node --check` 通过、headless 无控制台错误、无横向滚动。

### 修复（历史数据连续性：缺口补全 + 休市伪日线清理 + 自动连续性检查，2026-11-17）

诉求：全面检查是否存在「某天数据缺失」导致趋势图失真，补全历史数据并增加检查机制。逐标的比对后发现真正断掉的不多，但有两种问题会直接让趋势图失真：**上游串码**（一根脏 K 线造成 −100% 断崖）和**休市伪日线**（交易所休市那天新浪/腾讯伪造一根假 K 线，反过来把正常标的误报成缺数据）。

- **NDX 2026-11-16 日线被上游串码（真故障，最严重的失真）**：存的是 `O=10.09 H=10.14 L=9.88 C=10.0 V=6299265`，而当天纳斯达克100 实收 **27,197.15**，趋势图直接砸到 0 附近。根因在腾讯的**原始**端点 `us.NDX` 自己返回这条脏数据（`kline?param=us.NDX,day,,,320` 的 321 根里最后一根 close=10.0），而**不带点**的 `usNDX` 走 `fqkline` 只给当日一根、值为 27,197.15。新增 `TENCENT_SINGLE_BAR` 与 `_guard_tail_bar()`：日线末根相对前收偏离超 `MAX_TAIL_MOVE_PCT=25%` 时，用单根接口订正（日期一致且偏离回到阈值内）或直接丢弃，不再入库。存量那根已用 `backfill.repair_outliers` 订正为 27,197.15。
- **郑商所 4 个真缺口回补（真故障）**：`CF` 缺 2019-04-23 / 2024-01-30 / 2024-03-01，`SR` 缺 2019-04-23 —— 新浪连续合约（CF0/SR0）自己也缺这 4 天（重拉仍 MISSING），但郑商所官方逐日文件 `DFSStaticFiles/Future/{YYYY}/{YYYYMMDD}/FutureDataDaily.txt` 全部可取。新增 `app/ingest/backfill.py` 的 `fill_bar_gaps()`：按 `czce.main_contract()`（持仓量最大合约）取当日主力收盘，回补值 CF `15865 / 16080 / 16150`、SR `5343`，与前后日衔接自然（如 CF 2019-04-23 前一日 15845、后一日 15740）。
- **中国国债收益率历史被截断（真故障）**：`eastmoney_yield.fetch_rates` 只请求第 1 页（`pageSize=5000` 但服务端一页硬顶 500），报表实际共 9,389 行 / 19 页 → CN2Y/5Y/10Y/30Y/10Y2Y 只有 473 点（2024-12-26 起），比美/德/日序列短一年多。改为 `PAGE_SIZE=500` + `MAX_PAGES=40` 翻页直到早于 `start_year`，重采后 **473 → 1,214 点，回溯到 2022-01-04**，与 US/DE/JP 序列对齐。
- **日线入库深度被写死 2000 根（真故障）**：`pipeline` 里 7 处 `_latest(bars, 2000)` 把上游给的更长历史砍掉（新浪 CF0 有 5,319 根、2005 年起）。新增 `DAILY_BAR_LIMIT = 3000`（与 `/api/market/bars` 的 limit 上限一致），重采后 `market_bars` 从 65,533 行增至 84,229 行。
- **新增历史连续性检查（新机制）**：新增 `app/ingest/continuity.py`，**不预置交易日历**，用「同业共识日」判定：按 `CALENDAR_GROUPS`（国内期货 / 美股指数 / COMEX-NYMEX / LME / 汇率 / A股 / 港股 / 各自的宏观序列）分组，同一组里 ≥ `CONSENSUS_SHARE=0.75` 的成员有数据（至少 2 个、`floor` 向下取整）才算交易日，只有少数成员有数据的那一天判为缺口。另有 `silences()`（连续多日无新点，日线 12 天）与 `anomalies()`（近 60 天单日 |涨跌| > 25%，含 OHLC ≤ 0 等 `invalid`）。`check_data_quality` 末尾产出两条 `kind="continuity"` 的 `data_checks`（`日线行情连续性` / `宏观序列连续性`），每轮质检自动跑，System 页直接可见。
- **休市伪日线清理（新机制，含两条误伤反例）**：新浪/腾讯在休市日会造一根假 K 线（OHLC 复制前一交易日、成交量为 0 或同样被复制），这些假行会让「共识日历」把真实交易日误判成缺口（首轮报出 `CF/I/P/SR/CL:gap`）。新增 `app/ingest/bars_quality.py`：规则 1 = `open/high/low` 三者全等于前一日；规则 1b = `open/high` 相同且成交量被复制（双方都须为正数才比，容差 `max(1, 0.1%)`）；规则 2 = `high==low` 且无成交量且收盘变动 ≤ 5bp。**两条必须保留的反例**：①新浪外汇日线是「每天一个价」格式（`O=H=L=C`、无成交量），此类序列先由 `is_single_print_series()` 识别、整条跳过规则；②长假后第一个交易日上游会复制前一日开盘价和最高价，但低点/收盘是真的（`GC 2023-01-17`、`CL 2022-09-06`、`GC 2024-01-16`），不能删。清理后共删 **82 根 / 20 个标的**（国内 2015-09-03、2015-10-01/02、2017-01-02；COMEX 2016-12-26、2018-12-25、2019-01-01、各 Good Friday；LME 同期假日），入库路径（4 处 `upsert_bars` 前）同步过滤，存量由 `backfill.clean_holiday_stubs()` 清。**教训**：第一版规则删了 5,303 行（含外汇 6 对 70%+ 的正常日行情），靠 `data/epic_before_stub_cleanup.db` 备份还原 —— 清理类脚本必须先 WAL checkpoint + 备份 + 小样本验证。
- **上游历史缺口登记（新机制）**：`continuity.KNOWN_GAPS` 登记已逐条核实过、**上游确实没有且无处可补**的点：`I` 2015-02-25、`P` 2015-06-23 / 2015-10-08 / 2016-04-05 / 2017-10-09（共 5 点）。证据：大商所逐日行情页有瑞数信息（RiverSecurity）JS 反爬（GET/POST 均 412，带 cookie 无效）、上期所 `kx/{YYYYMMDD}.dat` 归档只留最近一批（2022 年及更早 404）、腾讯/同花顺/东财都不服务国内期货连续合约、新浪重拉仍是这几天缺失。检查不再重复报这批假警，但会在 detail 里如实写「另有 5 个点属上游历史缺口，无法回溯补全，已登记」。
- **停牌窗口登记**：`KNOWN_HOLDS` 记录 `NI` 2022-03-10..10（沪镍连续涨停无成交）、`NI_LME` 2022-03-08..16（LME 镍逼空停牌），这类「真实交易日但无成交」不算缺口。
- **新增周任务 `backfill_history`**（周日 09:00，`CronTrigger`）：`clean_holiday_stubs()` → `repair_outliers()` → `fill_bar_gaps()` 三层幂等执行，历史脏点/缺口可在无人值守下自愈。注意 `platform/scheduler.py` 是硬编码 add_job 列表，DB 的 jobs 行不足以让任务真正调度，两处都要注册。
- 新增 `tests/test_continuity.py`（21）、`tests/test_bars_quality.py`（14）、`tests/test_backfill.py`（8）、`tests/test_pipeline_guard.py`（10）、`tests/test_eastmoney_yield.py`（5），`pytest tests -q` → **211 passed**。
- 验证：`backfill_history` 实跑一轮 `stubs=82 / repaired=1 / filled=4`；日线 findings 从 18 → 8 → 2 → **0**，宏观 findings 0；`check_data_quality` 10 项 0 失败；`/api/system/data-quality` **9/9 通过**（含两条 continuity）；NDX 末三根 11-16=27,197.15 / 11-13=27,943.74 / 11-12=28,289.19。
- 文档：[05 数据源与接口清单](docs/05-数据源与接口清单.md) 增补 7.6（连续性检查口径、休市伪日线规则、上游已知缺口）。
### 修复（全量数据源新鲜度排查：日线停滞在 11-13、日债停 10-30、黄金 ETF 停 10-31，2026-11-16）

现象：`/market` 页大量海外资产日线停在 2026-11-13，日债停在 10-30，黄金 ETF 持仓停在 10-31。逐项直连上游核对后分成「真故障」与「正常滞后」两类，真故障 6 个全部修掉。

- **东财 K 线端点全面不可达（真故障）**：`push2his`/`push2delay` 的 8 个 secid（含 1./23./48. 分片、https/http）全部 `curl 56`。而 SPX/NDX/DJIA/DXY/USDCNH 的日线**只**依赖东财，于是永久停更，且最后一根是盘中残根（11-13：SPX DB 7520.77 vs 实际 7561.67、DJIA 52157.84 vs 52347.55、NDX 24995.65 vs 27943.74、DXY 103.19 vs 103.4109）。新增免费兜底源并改为显式优先级链（`TENCENT_KLINE_RAW` / `SINA_FX_DAILY`），见下。历史（11-12 及更早）与腾讯/新浪逐位一致，只需修正残根。
- **腾讯美股指数 K 线需走「原始」端点（新发现）**：`fqkline/get?param=usDJI,...` 只返回 1 根；`kline/kline?param=usINX,day,,,320` 返回 320 根（2025-08-08 起）。`tencent.fetch_daily_kline` 增加 `adjust=False`，`parse_kline` 容错 data 键改名（`usINX`→`us.INX`、`usNDX`→`us.NDX`）。
- **新浪外汇日线（新接入）**：`vip.stock.finance.sina.com.cn/forex/.../NewForexService.getDayKLine`，`DINIW` 10609 条（1985 起，含当日）、`fx_susdcnh` 3135 条；字段序为 `date,open,low,high,close`。DXY/USDCNH 日线改由新浪优先。
- **日本国债取错文件（真故障）**：MOF 历史汇总 `historical/jgbcme_all.csv` 只到 2026-10-30，当年文件 `jgbcme.csv` 已含 11-13。`jgb.fetch_rates` 改为「当年 + 历史」两份合并，历史文件加 24 小时缓存（因为 `collect_rates` 提到 1 小时一次）。JP2Y/JP10Y/JP30Y 由 444 点（止于 10-30）变为 698 点（2024-01-04 起，到 11-13）。
- **WGC 黄金 ETF 持仓取错频率（真故障）**：`ETF_GLOBAL_TONNES` 是周频指标（`registry.py` freq="w"），却取 WGC 回包的 `Monthly` 序列，永远滞后一个月。新增 `_wgc_etf_totals(payload, freq)`，持仓优先写 Weekly（11-13，4,268.2 吨），`ETF_FLOW_1M_TONNES` 仍用月频。
- **SQLite 并发写导致整轮采集失败（真故障）**：单写者数据库在「已有读事务再升级写锁」时不看 `busy_timeout`，直接抛 `database is locked`（日志累计 712 行）。新增 `app/platform/writelock.py`（`write_lock()` 超时 240 秒），调度器每个采集任务与黄金手动刷新都在锁内串行执行。
- **海外利率滞后一个交易日（真故障）**：SOFR 于美东 08:00、EFFR 于 09:00 才发布前一日值，而 `collect_rates` 每 6 小时一采。改为**每 1 小时**（`init_db.JOBS_DEFAULT` 与 `LEGACY_JOB_LABELS` 同步把旧标签 "every 6h" 刷新掉）。
- **NDX 报价与日线差 11%（真故障）**：东财 `100.NDX` 返回的其实是纳斯达克综合指数（盘中 24817.5 / 涨跌 −1.27% ⇒ 昨收≈25137，与腾讯 `.IXIC` 昨收 25136.27 吻合；腾讯 `.NDX` 才是纳斯达克100）。新增 `TENCENT_QUOTE_PREFERRED={"NDX": "usNDX"}`，`collect_quotes` 对该标的首选腾讯并跳过东财循环。
- **质检不再被全表最大值掩盖**：原「国内期货日线」「美债利率」两条用 `max()` 全表判断，任何单序列断更都发现不了。改为逐标的「日线行情」（阈值 5 天）与逐序列「宏观序列」（日 5 / 周 10 / 月 70 / 季 150 天，月季频留出官方发布滞后），detail 直接列出 `SYM:日期(N天)`。`/api/system/data-quality` 只展示最近一次运行的条目，已下线的检查项不再长期挂页。
- **序列频率口径**：`FR10Y`（ECB 法国 10 年，月度）原先按日频入库，质检永远判陈旧；`MACRO_SERIES_META` 声明 `freq="m"`，`store.upsert_macro` 新增 `freq` 参数并在元数据漂移时自动纠正。
- **前端「时点」语义**：Topbar「数据已同步 HH:mm」→「刷新于 HH:mm」（原来那个时间是浏览器轮询时间）；`HistoryModal` 标注「最新一点：N 天前」并说明海外标的最新点是最近成交日；利率卡片与黄金因子行显示各自 `as_of`（超频标黄）；`useFormat.freshness` 增加交易时段判断，非交易时段显示「已收盘」而不是误报「旧数据」。
- **质检口径的两个小毛病**：个别新闻源给出「未来」时间戳时 detail 会写「距今-1天」（改为负年龄按 0 天计）；`scripts/_common.ps1` 的 netstat 兜底把端口上的 `TIME_WAIT`/`ESTABLISHED` 连接当成监听者，导致 `stop.ps1` 刚停完就 `start.ps1` 会报「端口被进程 N (unknown) 占用」而拒绝启动（改为只认 `LISTENING` 行；注意该文件必须以 **UTF-8 BOM** 保存，否则 Windows PowerShell 5.1 会按 ANSI 读中文注释而整份脚本语法错误）。
- 新增 `tests/test_macro_freq.py`、`tests/test_writelock.py`、`tests/test_quote_preferred.py`，`pytest tests -q` → **153 passed**。
- 补充（2026-11-17 补交）：上列「前端语义」相关改动此前一直未提交，本次按 `web/assets` 新构建产物等价还原 6 个源文件（`useFormat.ts` / `Topbar.vue` / `HistoryModal.vue` / `MarketView.vue` / `RatesView.vue` / `GoldView.vue`）并重新构建 `web/`。**还原为语义等价重建，非逐字原文**（变量声明顺序、辅助函数写法可能与原稿不同，故 vite 产物哈希与事故前不同）；`vue-tsc --noEmit` 通过、`npm run build` 成功。
- 验证：`collect_daily_bars` 回填 55,598 根（`tencent_daily=3`、`sina_fx_daily=2`、`tencent_fallback=3`、`eastmoney_daily_failed=3`、无错误）；35 个标的实时报价 `stale_sec` 全部在 1–6 分钟内；`check_data_quality` 8 项 0 失败；`/api/system/data-quality` **7/7 通过**；`/api/market/bars` 除 ECB 6 个汇率与 USDCNH（上游当日参考汇率未发布）外全部到 2026-11-16；采集日志出现新分支 `groups: {cn_futures:12, overseas:9, fx:7, tencent_preferred:1, cn_equity:4}`；NDX 报价改为腾讯 27,512.65（昨收 27,943.74，与日线一致）。
- 文档：[05 数据源与接口清单](docs/05-数据源与接口清单.md) 增补 7.4（优先级链与上游证据）与 7.5（哪些是故障、哪些是周末/官方未发布的正常滞后）。

### 修复（总览行情「好几分钟不动」：采集 60 秒 + 未变化去重 + 保留期，2026-11-16）

- 根因：报价任务 `collect_quotes` 每 **300 秒**采集一次，而总览页每 **15 秒**轮询一次 —— 同一个数字被重复渲染 20 次，看起来像「美元指数没有实时更新」；数据链路与接口本身正常（`/api/market/snapshot` 的 DXY `stale_sec` 一直在刷新，新浪 `DINIW` 与东财分时交叉验证一致）。同时系统状态页的任务标签写着 "every 60s (trading hours)"，与实际 300 秒触发不符。
- `collect_quotes` 触发器 `IntervalTrigger(seconds=300)` → **60 秒**（东财 `trends2` 分时本身是 1 分钟粒度，60 秒即与源分辨率对齐）。
- `store.upsert_quotes` 新增**未变化去重**（`QUOTE_DEDUPE_SEC=240`）：价格/量/来源/延迟档都没变时最多每 240 秒落一行，避免 36 标的 × 1440 分钟 ≈ 5 万行/天的写放大，同时保证每个标的最新行不超过 4 分钟（`stale_sec` 不会越过「旧数据」阈值）。
- 新增行情**保留期** `EPIC_QUOTES_RETENTION_DAYS`（默认 30 天，`0`=关闭），由每日维护任务 `check_data_quality` 调 `store.prune_quotes` 清理（分钟级快照 30 天约 86 万行，不设限每年 ~1GB）。
- `init_db.JOBS_DEFAULT["collect_quotes"]` 改为 "every 60s"，`seed_jobs` 通过 `LEGACY_JOB_LABELS` 把旧标签 "every 5m" / "every 60s (trading hours)" 刷新掉（保留用户对 `enabled` 的开关）。
- 新增 `tests/test_quote_cadence.py`（去重、窗口外刷新、`prune_quotes`、保留期默认值、标签刷新、调度间隔 = 60 秒），全量 **145 passed**。
- 验证：重启后 DXY 在 `quotes` 中由每 5 分钟一行变为每分钟一行（13:54 → 13:56 → 13:58 → 13:59），`/api/market/snapshot` 的 `stale_sec` 稳定在 60–130 秒，`collect_quotes` 每轮耗时 6–9 秒、`skipped` 计数即被去重跳过的不变行情。

### 修复（东方财富数据源恢复与多通道兜底，2026-11-16）

- 根因：东财 `push2.eastmoney.com` / `push2his.eastmoney.com` 的 AAAA 边缘节点在 TLS 握手后直接断连（`RemoteProtocolError` / curl 56），且 IPv4 边缘对非 Schannel TLS 栈（httpx 的 OpenSSL）在 TLS 之后丢弃请求；`stock/get`（实时快照）与 `kline/get`（日线）被单独拦截，`trends2/get`（分时）与 `datacenter-web` 仍可用。
- `HttpClient` 统一强制 IPv4（`httpx.HTTPTransport(local_address="0.0.0.0")`）；遇 `RemoteProtocolError` 自动改用系统 `curl.exe`（Windows 走 Schannel）重试，并记住该 host 后续直连，返回仍包装成 `httpx.Response`，调用方无感。
- 东财报价：`eastmoney.fetch_quote` 在快照接口失败时回落 `trends2/get` 分时末点（`preClose` 作昨收，`delay_sec=60`），并加 5 分钟熔断避免每个标的都先去撞被拦接口；腾讯财经（`qt.gtimg.cn`）作为 A 股/指数/港股报价最后兜底。
- 东财日线被拦时用腾讯日线（`web.ifzq.gtimg.cn`，qfq，320 根）兜底 A 股与恒生；美股指数腾讯无历史，等东财 K 线恢复。
- 健康语义修正：新浪/东财/腾讯各自按自己那部分结果记录，日线任务不再覆盖东财健康（由 5 分钟一次的报价任务判定），避免健康页状态来回闪。
- 新增 `tests/test_provider_fallbacks.py`（trends 解析、熔断、腾讯报价/日线解析）与 `tests/test_http_curl_fallback.py`（curl 兜底与状态拆分），全量 **139 passed**。
- 数据：已回填 2026-11-16 沪深 300/洛阳钼业/恒生日线（腾讯），EM 系报价恢复 5 分钟级更新，「东方财富」健康恢复为正常。

### 变更（黄金原手动指标数据源接入，2026-11-15）

- 原 7 项手动指标中 5 项接入免费自动采集，黄金 provider 由 5 个增至 10 个（全部 ok）：
  - `CB_GOLD_GLOBAL_TONNES`：改接 WGC 央行仪表盘 API（`fsapi.gold.org/api/cbd/v11/charts/getPage`，按国别季度加总，最新季上报不足自动丢弃），季频、`pct_change_3m`、`scale=1.2`，34 条（2018-03 ~ 2026-06，最新完整季 32,044.8 吨）。
  - `COMEX_GOLD_INVENTORY_TONNES`：CME 官网本机不可达，改读 MetalCharts 免费周频 CSV（gold 行 `total_oz` → 吨），周频，40 条（最新 712.4 吨）；按许可需可见署名 metalcharts.org。
  - `MM_BANK_GOLD_NET`：接入 CFTC 银行参与报告月报（`CMX GOLD` 汇总行，银行多头 − 空头），月频、`percentile`，30 条（最新 −172,618 张）。
  - `SGE_GOLD_INVENTORY_TONNES` → `SHFE_GOLD_STOCK_TONNES`：上金所不公布库存，改用上期所黄金仓单日报（指定交割金库千克 → 吨），日频、`direction=-1`、`scale=3`，30 条（最新 118.404 吨）。
  - `BIS_GOLD_LEASE_RATE` → `SGE_GOLD_LEASE_3M_PCT`：BIS 无公开租赁序列，改用上金所黄金租借费率(3M) XLS 导出，日频、`level`、`scale=1.5`，1,187 条（最新 0.4236%）。
- `BIS_GOLD_SWAP_USD`、`BIS_GOLD_STORAGE_USD`：确认 BIS 无可机读季度序列（`stats.bis.org` 29 个 dataflow 与 `data.bis.org` 均无 gold），`weight` 改为 **0**（不参与评分）、保留 `manual` 手动录入。
- 新增依赖 `xlrd>=2.0`（`pyproject.toml`，解析上金所 OLE2 `.xls`）。
- 评分：参与评分指标 17 个（权重合计 139），`coverage` 由 74% 提升至 **100%**；2026-11-15 实测新增入库 1,321 条，综合评分 **−0.6「中性」**。
- 测试：`tests/test_gold.py` 新增 5 个 provider 离线解析用例（共 12 条），全库 **127 passed**。
- 文档：[17 黄金监控与综合研判](docs/17-黄金监控与综合研判.md)（指标矩阵、不可得清单、新增自动源与口径替代、验证记录）、[05 数据源与接口清单](docs/05-数据源与接口清单.md)、[07 开发进度](docs/07-开发进度.md)、README 同步。

### 新增（黄金研判图表交互，2026-11-15）

- `/gold` 走势图表新增时间范围切换：1月 / 3月 / 6月 / 1年 / 2年 / 5年 / 全部，直接复用资产历史走势弹窗的 `HISTORY_RANGES` 与 `cutByRange`，默认 1 年，选项与资产价格趋势图完全一致。
- 5 张走势图**默认不再显示黄金价格**；每张图卡新增「叠加金价」开关，可按图单独叠加伦敦金价（右侧副轴）与图中指标做趋势对比；原「黄金价格 vs 美债实际利率」改为「美债 10Y 实际利率」。
- 派生序列历史回填由约 180 天扩到 2,000 个交易日（`DERIVED_HISTORY_BARS`），`GET /api/gold/overview` 的 `series_limit` 上限由 600 提到 3,000、前端请求 2,500，长区间可用（金价 2,002 点 / 实际利率 1,218 点 / 上海溢价 1,850 点），评分与 coverage 不变（−0.6 / 100%）。

### 计划中（V1.4 候选）

- LLM 全链路实跑（断言/事件/简报编辑/论点证据）——需 `DEEPSEEK_API_KEY`。
- 港股/A 股扩展、组合级风控、PDF 服务端渲染、移动端单独设计。
- 大商所官方持仓、LME 日线、美国财政部新闻源替代方案。
- 黄金监控：BIS 半年报 PDF（Gold and gold loans / Gold deposits）解析与两项 BIS 指标权重回测；CME 官方库存源与 MetalCharts 镜像交叉校验。

## [1.3.0] - 2026-11-14

### 新增（黄金监控与综合研判）

- 新增黄金监控模块 `backend/app/gold/`：22 个指标（19 个参与评分）+ 数据源健康 + 综合评分 + 手动录入，详见 [17 黄金监控与综合研判](docs/17-黄金监控与综合研判.md)。
- 自动采集（每日 16:40 + 启动回补）：LBMA 伦敦金库（XLSX）、WGC 全球黄金 ETF（JSON）、CFTC COMEX 黄金分类持仓（年度 ZIP）、东方财富中国央行黄金储备（JSON）、本地派生（上海金溢价、COMEX 期现基差、租赁紧张度代理、实际利率、美元、20 日动量）。
- 新增 API：`GET /api/gold/overview`、`/api/gold/series`、`/api/gold/providers`、`POST /api/gold/refresh`、`POST /api/gold/metrics`（手动录入 BIS/COMEX/SGE/银行净合约等不可自动获取指标）。
- 综合评分：权重 × 标准化因子 × 方向，按可得数据重新归一；中国黄金储备剔除金价重估后作为“购金代理”；输出 `coverage` 体现置信度。
- 前端：新页面 `/gold`「黄金研判」（评分环、5 组因子卡、5 个 ECharts、因子明细、数据源监控、手动录入、方法论）；侧边栏/命令面板/路由；分析引擎页新增黄金评分卡。
- 调度：`collect_gold` 加入 `JOBS_DEFAULT`（16:40）与 APScheduler（启动回补 + 每日 16:40）。
- 测试：`tests/test_gold.py` 7 条（provider 离线解析、评分、API 契约、手动录入），全库 122 passed。

### 修复

- 首页右上角「查看简报」与 Hero「查看日报」指向同一页面的重复入口：移除页头按钮，仅保留 Hero 主 CTA。
- 按钮统一：`.btn` 对 `<a>`/`<button>` 统一 `font: inherit`、`appearance: none`、`text-align`、`user-select`、焦点环与下划线；按钮式链接与原生按钮视觉一致。

## [1.2.0] - 2026-11-14

### 新增（后端接口补齐，满足前端全部数据需求）

- `GET /api/overview`：总览页聚合接口（health + 最新简报 + 快照 + 自选含 sparkline + 宏观利率与迷你走势 + 告警 + 日历 + 任务健康），前端首屏请求由 20+ 降为 1。
- 行情单位：`instruments.extra.unit` 落库（`app/platform/instrument_units.py`），`/api/market/snapshot`、`/api/watchlist` 返回 `unit` 与 `contract_size`；前端不再硬编码单位映射。
- 简报：`/api/briefs/latest?kind=daily` 聚合 manual/premarket/postmarket 并返回 `neighbors`（上一期/下一期 id）；`/api/briefs` 支持 `kind` 分组历史 + `offset` + `total/kinds`；新增 `/api/briefs/kinds`。
- 事件：`/api/events` 支持 `q` / `instrument` / `offset` / `total`；每条事件返回 `document_id` / `document_ids`（证据链）与 `impact`。
- 新闻：`/api/news` 支持 `source` / `tier` / `since_days` / `offset` 与 `meta.total`，返回 `source_id`。
- 日历：`/api/calendar` 支持 `country` / `category` / `importance_min` / `offset` 与 `meta.total`。
- 持仓：新增 `/api/positions/products`（会员持仓品种列表）。
- 自选：新增 `PATCH /api/watchlist/{symbol}`（分组 / 优先级 / 备注），供自选管理内联编辑。
- 测试：`tests/test_api_contracts.py`（9 条契约测试）+ `test_api_smoke.py` 覆盖新端点，共 115 条测试通过。

### 修复

- 前端全局 `<a>` 下划线/默认链接色泄漏到按钮式链接（「查看日报」「查看简报」「打印」「API 文档」等）的问题：`a.btn/a.link-btn/a.nav-item` 统一 `text-decoration: none`，`.btn` 显式声明字体/颜色继承。
- `tests/test_release.py` 子进程输出按 UTF-8 解码，消除 Windows GBK 警告。

### 前端联调

- 总览页改用 `/api/overview` 单请求（自选迷你走势由后端返回）。
- 简报页接入真实历史期次（上一期/下一期）与日报/周报/月报数量徽标。
- 论点与证据页：新闻关键词搜索、事件类型筛选与证据链接、日历国家/高重要性筛选。
- 市场页单位改为后端字段、会员持仓下拉改用 `/api/positions/products`；自选管理支持内联编辑分组/优先级/备注。

## [1.1.0] - 2026-11-14

### 新增（Vue 前端重构）

- 新增 `frontend/`：Vue 3.5 + TypeScript + Vite 6 + Pinia + vue-router + ECharts 5 + Tailwind；构建产物输出到 `web/`，由 FastAPI 托管（SPA 回退，深链可直接访问）。
- 8 个页面：总览 / 市场行情 / 利率与流动性 / 分析引擎 / 交易信号 / 论点与证据 / 简报与日志 / 系统状态；信号轮询、骨架屏、错误态与空态统一。
- 设计系统：`frontend/src/styles/app.css`（深色默认 + 浅色/护眼/跟随系统；红涨绿跌可切换；标准/紧凑密度）；46 个内联 SVG 图标；自建 15+ 组件（表格/卡片/抽屉/证据/历史走势等）。
- 交互：Ctrl+K 命令面板、证据抽屉（原文 + 断言高亮）、ECharts 历史走势（区间切换/缩放）、自选管理（拖拽排序/增删/分组）、设置抽屉、告警中心、全局 Toast、打印样式。
- 深链兼容：`?doc=`、`?history=kind:key`、`?brief=`、`?theme=`、`?updown=`、`?palette=1`、`?settings=1`、`?alerts=1`、`?watch=1`。
- 旧版零构建看板迁移到 `web-legacy/index.html`，过渡期通过 `/legacy` 访问（V1.2 删除）。
- 工程：`scripts/build.ps1`（npm 构建 -> `web/`）、`scripts/dev.ps1`（Vite dev + `/api` 代理）；`setup.ps1` 自动构建前端；`ci.ps1` 增加构建门禁；CI 增加 Node 22 + `npm ci` + `npm run build`。
- 测试：`tests/test_frontend_build.py`（源码结构/无外部 CDN/构建产物/SPA 回退/旧版入口）；移除失效的 `test_theme.py` / `test_ui_static.py`。

### 新增（工作区整理）

- `scripts/maintain.ps1`：`-DryRun`（默认）/ `-Apply` / `-Verify` / `-IncludeRaw` / `-IncludeLogs`，清理可再生临时产物；本次安全清理释放 **300.6 MB / 9,429 个文件**（`data/` 577 MB → 277 MB）。
- `docs/15-前端改造方案.md`、`docs/design/mockup/`（UI 原型与 6 张预览图）。

### 变更

- `/api/*` 契约不变；新增 SPA 回退路由与 `/legacy`。
- 版本单一来源升为 `1.1.0`（`backend/app/__init__.py` / `pyproject.toml` 同步）。


## [1.0.0-rc1] - 2026-11-13

### 新增（Windows 一键启停）

- `scripts/start.ps1` / `stop.ps1` / `restart.ps1` / `_common.ps1`：后台启动（WMI 脱离控制台、日志落盘、就绪校验、PID 文件、自动开浏览器）、一键停止（进程树 + 归属校验，避免误杀）、一键重启。
- `backend/app/serve.py`：后台启动器（`-m app.serve`），日志写入 `data/logs/server.{out,err}.log`。
- `scripts/start.ps1` 支持 `-Foreground` / `-Reload` / `-NoBrowser` / `-Port`。

### 修复（Windows 脚本）

- **`setup.ps1` 在 PowerShell 5.1 无法解析**：缺 UTF-8 BOM 导致中文按 ANSI 解码、引号错配；全部 `.ps1` 已加 BOM。
- **一键启动假成功/假失败**：venv `python.exe` 是启动器，真实监听在子进程；改为进程树判定并记录 `server_pid`。
- **启动脚本在捕获输出场景不返回**：服务继承父进程 stdout 管道；改用 WMI 创建进程。
- **健康检查在 5.1 恒失败**：`System.Net.Http` 未加载 + IE 代理；改为 TcpClient 最小 HTTP 请求。
- `lint.py` 新增 PowerShell 检查：BOM 缺失与非 ASCII 文本、全脚本语法解析（`scripts/_lint_ps.ps1`）。

### 新增（工程与质量）

- `scripts/lint.py`：离线静态检查（语法、AST 异味、未用导入、编码、前端 id/handler 接线、JS 语法、文档链接、版本一致性、`.env.example` 完整性）。
- `scripts/ci.ps1`：单一发布门禁（lint → 测试 → 运行时 health/acceptance/quality）。
- `.github/workflows/ci.yml`：Python 3.11/3.12 双版本 CI（lint、pytest、安装导入冒烟）。
- `CHANGELOG.md`、`docs/14-全量核验与缺陷修复.md`。
- 版本单一来源：`app.__version__` → `settings.app_version` → `pyproject.toml`。
- 测试：`tests/test_devops.py`（JobRun 自愈、任务注册表、备份保留）与 `tests/test_release.py`（版本/lint/CI 工作流）。

### 修复（缺陷）

- **任务审计挂起**：进程重启后被中断的 `job_runs` 永远停留在 `running`；启动时与每次任务前自动改写为 `interrupted`。
- **任务开关失真**：调度器忽略 `Job.enabled`，面板显示"停用"却照常执行；改为调度前校验，且 `seed_jobs` 覆盖完整任务注册表、保留运维手工开关。
- **备份无上限**：每日备份无限增长；新增保留策略（默认 14 份，`--keep` 可调）。
- **时区不一致**：证据导出时间、ECB/JGB/东财利率起始年份使用本地时间；统一为 UTC。
- **无用导入**：清理 8 处真实未使用导入（`numpy`×2、`re`、`Path`×2、`timedelta`、`Prediction`、`MacroPoint`）。

### 新增（产品功能，本周期内）

- 可配置「重点关注」自选池：分组/优先级/备注、↑↓ 微调、拖拽排序（锁定模式默认）。
- 顶部区块导航（sticky、滚动高亮）、四套主题 + 红涨绿跌/绿涨红跌设置面板。
- 历史趋势弹框（自选/快照/利率，1M–5Y/全部）。
- 会员持仓 Top20 多空明细列表（上期所/郑商所/大商所）。
- SOFR/EFFR 与利差监控；法国 10Y；利率按国家/期限排序。
- 简报：日报/周报/月报弹框、主次动力与重点关注表格化、主线强调、涨跌幅着色、品种高亮。
- 市场快照：按 TradingEconomics 类别排序，外盘/国内分表。

### 修复（数据）

- 外盘期货/现货与 6 个外汇对缺少日线历史：接入新浪 GlobalFuturesService 与 Frankfurter，覆盖率 20/35 → **35/35**；宏观序列 21/21 → **22/22**。
- 新增两条数据覆盖质检（标的日线、宏观序列），缺失会显式失败而非静默。

## [1.0.0-rc0] - 2026-11-09

### 新增

- M0 骨架：FastAPI + SQLite(WAL) + APScheduler + 零构建看板 + 脚本 + 文档。
- M1 数据地基：国内期货/A股/外盘/汇率/美债/官方新闻采集与降级、数据源健康、数据质检。
- M2 证据链与简报：原文快照、正文抽取、规则断言（精确 span）、证据弹框、盘前/盘后简报。
- M3 分析引擎：指标、市场隐含周期、定价归因、相关性、风向、历史类比、领先滞后、事件研究、日历研究。
- M4 决策系统：规则信号、风控校验的草稿计划、含成本 walk-forward 回测、预测账本与 Brier、论点/情景/复核。
- M5 打磨验收：告警中心（价格/陈旧/质检/风控/日历/持仓背离/事件）、导出与打印、验收 API 与脚本、使用手册。
- M6 支持：日/周/月报、交易日志、会员持仓、事件库、SOFR、多主题、导航等。

---

### 约定

- 提交信息使用 `type(scope): summary`（feat/fix/docs/test/chore/refactor/perf/ops）。
- 每次合并前必须 `scripts\ci.ps1` 全绿；版本号改动需同步 `docs/10-发布说明与验收.md` 与本文档。
