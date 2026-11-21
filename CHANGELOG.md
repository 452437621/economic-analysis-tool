# 变更记录（CHANGELOG）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，版本号使用 [语义化版本](https://semver.org/lang/zh-CN/) 的预发布形式（`1.0.0-rc1`）。

> 运行时版本以 `backend/app/__init__.py` 为唯一来源，`pyproject.toml` 与 `/api/system/health` 必须一致（`tests/test_release.py` 会校验）。

## [Unreleased]

### 新增（专题研判：黄金 + 洛阳钼业，2026-11-21）
- **专题框架**：新增 `config/topics.yaml` 注册表与 `app/topics/{config,scoring,storage}`；`/api/topics` 提供列表、overview、refresh、持仓读写；`config/topics/luoyang.yaml` 承载标的/情景/持仓/评分参数。新增专题只需改配置并登记 adapter。
- **黄金评分合并**：`app/gold/signals.py` 移植 golden_analysis 的估值缺口、趋势、波动率、金银比、通胀预期、季节性 6 项正交信号；`compute_gold_score` 与 17 项指标统一走 `combine_factors`，新增 `signals/signal_details/combined/analytics`，重叠维度不重复计权；动量因子升级为 3 个月收益 + RSI14 复合口径。旧 `/api/gold/*` 键保持兼容。
- **洛阳钼业**：新增东财采集器（行情/估值/财务/三表/分部/两融/资金流/分红/公告/研报/同业）与 `collect_luoyang`（每日 16:50）；移植单因子/多因子/滚动 beta/领先滞后/收益分解/估值分位/四法情景/持仓补仓/事件反应等纯函数；`topic_datasets/topic_dataset_rows/topic_source_runs/topic_settings` 通用长表存储。
- **前端**：新增 `TopicsView` + `components/topics/*`（13 种分区渲染器、tab、吸顶锚点导航、图表范围、持仓/手动指标抽屉）；`/topics/:topicId?` 路由，`/gold` 重定向到 `/topics/gold`；侧栏、命令面板、分析页黄金卡同步；删除旧 `GoldView` 与 gold 页面专属组件。
- **质检**：`check_data_quality` 增加洛阳关键数据集新鲜度检查（`action_job=collect_luoyang`）。

### 修复
- 洛阳 overview 在 `total_market_cap=NaN`、缺 `pb_mrq/ps_ttm`、PE 跨 0 时不再 500；事件表次日/5 日反应列已对齐。
- 黄金覆盖率在信号缺失时不再高估（unavailable 信号保留权重）；KPI「伦敦金现」与 ETF 资金流/COMEX 库存/上金所租借费率图表序列恢复。
- 配置参数缓存纳入 `config/topics/*.yaml`；topic 数据版本在刷新已有行时前进；`load_rows(limit)` 改为返回最新 N 条；批内重复键 upsert 去重。
- `PositionIn` 支持 `add_prices/add_ratios`；`tests/helpers` 注册 topic 模型；0 分位、HAC 标准误、单调上涨 RSI 等边界修正。

### 验证
- 后端 `pytest -q` **540 passed / 1 skipped**；`scripts/lint.py` PASSED；前端 `vue-tsc` 0 error、vitest **55 passed**、`vite build` 成功。

## [3.0.0] - 2026-11-21

### 结构整理（V3.0.0）

- **打包**：`pyproject.toml` 改用 `[tool.setuptools.packages.find]` 打包 `app` 全部子包；补齐 `app/cycle/__init__.py`；新增 wheel 内容与全模块导入回归测试。
- **死代码**：删除无引用的 `app/jobs/catchup.py` 兼容包装（实现早已在 `app/jobs/supervisor.py`）。
- **ingest 拆分**：新增 `ingest/sources.py`（单一数据源注册表）与 `ingest/macro_meta.py`；`ingest/pipeline.py` 拆为 `ingest/collectors/*`，原模块保留为 facade，旧导入路径不变。
- **lens 拆分**：`fed`/`song`/`layers`/`persona`/`engine` 拆为 catalog/readings/state 等实现模块，原模块保留 facade。
- **前端**：`api/types.ts` 按域拆分并保留 barrel；`Cycle`/`Gold`/`Analysis`/`Lenses`/`Pipeline`/`System`/`History` 大视图提取组件、composable 与纯函数工具；新增 vitest 测试。
- **脚本**：新增标准库实现的 `scripts/epic.py` 统一核心，16 个动作各配 `.ps1`/`.cmd`/`.sh` 三套包装，支持 Windows PowerShell 5.1/7、cmd.exe 与 Linux bash；移除 `_common.ps1`。
- **测试**：按领域重组 `tests/`（unit/integration/release），重命名并拆分 `test_m2`–`test_m21`，共享 fixtures/helpers，接入 marker 与 `pytest-cov`，补齐未覆盖模块和管理端点。
- **验证**：后端 `495 passed / 1 skipped`；前端 `36 passed`；`vue-tsc` 0 error；`vite build` 成功；`scripts/lint.py` PASSED；本地行覆盖率估算 **76.3%**；Windows PowerShell/CMD 启停冒烟通过（8877/8878 隔离端口）。
- **CI/文档**：新增 Windows 生命周期与 Linux Shell 检查；README/使用手册/交付清单更新为三平台命令表。

### 新增（系统状态四项加固：调度自检、数据源备用、质检处置、验收说明，2026-11-21）

- **调度自检**：新增 `backend/app/jobs/plan.py`（作业计划单一事实源）与 `backend/app/jobs/supervisor.py`（启动/周期自检）。按「定点作业取最近应执行时点、间隔作业取 last_run + 周期」判断逾期；启动后先补采集，再评估数据就绪，随后按依赖补质检、分析、周期、透镜、决策、论点、台账、简报；数据不可用时下游写 `skipped` + `blocked_by`，不再硬跑。删除 `analyze/decide/theses` 等启动 bootstrap，避免与补跑重复；注册 `backfill_history`（周日 09:00）与 `repair_data`（15:55）。新增 `schedule_checks` 表与 `GET/POST /api/system/schedule-check`、`GET /api/system/schedule`、`POST /api/system/jobs/{name}/run`。
- **数据源备用**：新增 `backend/app/ingest/failover.py`（有序备用链、基于 `source_health` 的熔断/冷却、最近可用数据）、`chains.py`（按数据域的主源→备源注册表）与 FRED CSV provider（美债、SOFR/EFFR、H.4.1、H.6 备用；国债/资产负债表百万美元、TGA/M2 十亿美元按单位缩放）。`collect_rates` / `collect_macro` 在主源缺失或滞后时自动补 FRED；`/api/system/sources` 增加角色/数据域、24h 成功率、连续失败、冷却至与链摘要。质检批次对 `US10Y/US2Y/US_M2` 做 FRED 抽样对账（`backend/app/ingest/reconcile.py`），偏差写 `DataCheck(kind="reconcile")`，不静默覆盖。
- **质检处置**：`DataCheck` 增加 `batch_id/severity/cause/impact/remediation/action_job`（轻量迁移），`check_data_quality` 每轮写同一批次并统一走 `backend/app/ingest/quality.py` 的 playbook；对账异常不再被吞掉，源连续失败进入质检批次；修复 `kind:dataset` 漏 `symbol`。新增 `repair_data` 自动修复（冷却 30 分钟、单轮最多 3 个、修复后复核一次）与 `POST /api/system/data-quality/repair`。新增 `backend/app/platform/quality_gate.py`：按最新批次 + 直接新鲜度 + 覆盖给出 `ok/degraded/blocked/unknown`，透镜置信度乘门控系数（夹 0.3–0.85）、组合标 `actionable=false`；决策在 blocked 时不再删除旧计划并返回跳过原因；周期/分析/黄金写入降级原因；修复周期综合分降级原因为不可达的问题，并取消缺失输入默认 50 的静默中性化。
- **验收说明**：新增 `backend/app/platform/acceptance.py`，每个检查输出 `actual/required/reason/impact/remediation/action_job`；无质检批次/批次超过 36h 不再假通过；新增调度逾期、调度自检时效、关键源链、数据就绪、序列覆盖检查；`failed_summary` 汇总失败项与作业/源线索。`/api/system/acceptance` 保留 `name/passed/detail` 兼容。
- **前端**：`SystemView` 新增「调度自检」卡（逾期/就绪/最近自检/质量门、立即补跑）、任务表逾期徽标、数据源角色/域/成功率/连续失败与备用链、质检严重度/期望实际偏差/处置与一键修复、验收失败摘要与详细说明；`OverviewView` 覆盖接口缺失不再回退 100%。
- **验证**：`scripts/lint.py` PASSED；全量 `pytest -q` **388 passed**（含 `test_frontend_build.py`）；`npm run build` 成功；新增 `test_schedule_plan/test_failover/test_fred_provider/test_quality_playbook/test_quality_gate/test_acceptance_details` 等离线测试。

### 修复与文档（README 对齐、自托管 /docs、全页截图，2026-11-19）

- **`/docs` 白屏修复**：FastAPI 默认文档页从 `cdn.jsdelivr.net` 加载 swagger-ui，本机网络下不可达导致空白。新增 `backend/app/platform/api_docs.py`（零依赖自托管文档页：读取 `/openapi.json` 按 tag 分组渲染端点、搜索、参数/请求体/响应表与 curl 片段），`main.py` 改为 `FastAPI(docs_url=None, redoc_url=None)` 并显式挂 `/docs`，离线可用。
- **README 重写为实测口径**：状态行、数据表、架构图、目录树、质量表与历史区块全部改为 2026-11-19 真值——17 个页面（19 条路由）、API 端点 114 个（`/api/v2` 38 个）、361 条 pytest、35 标的、84,237 根日线、35,624 条宏观观测（57 序列）、2,645 条日历、299 篇新闻、3,790 条断言、13 品种 3,120 行持仓；新增「界面一览」19 张 1600×1150 截图与 `scripts/screenshots.ps1` 生成脚本；`/docs` 说明改为自托管。
- **截图重拍**：新增 `scripts/screenshots.ps1`（本机 Chrome 无头模式逐页截图，自动探测 Chrome/Edge，参数 `-BaseUrl/-OutDir/-Width/-Height/-BudgetMs`）；`docs/assets/vue/` 19 张全部为 2026-11-19 实拍（含新增 `/lenses` 与 `/docs`），删除已无对应页面的 `vue-evidence.png`、`vue-settings.png`、`vue-watchlist.png`。
- **文档一致性**：`docs/05` 新增「2.9 宏观与流动性补全」并把「宏观 22 条序列」改为 57 条；`docs/08` 重写页面说明（17 页）与定时任务表（30 个作业的真实时间）；`docs/26` 补多透镜权威页；`docs/07` 新增 2026-11-19 进度节；`docs/15`、`docs/27`、`docs/28`、`docs/16` 修正页签数、截张数与 `/docs` 说明。
- **验证**：`scripts/lint.py` PASSED；全量 `pytest -q` **361 passed**；`vue-tsc --noEmit` 0 error；`vite build` 成功；线上 `/docs` 与 `/api/v2/lenses/state` 均 200。

### 新增（仓位/止损/组合权重与资金解耦，2026-11-19）

- **决策要素**：新增 `backend/app/lens/position.py`——把资产方向翻译成可执行的下注：止损距离 `2×ATR(14)`（夹 1.5%–8%）、单笔风险预算 `1%×|共识分|`（夹 0.3%–2%）、权重 `风险预算/止损距离`（单资产 ≤30%），组合层强制总敞口 ≤80%、组合风险 ≤6%（超限等比缩放，权重向下取整到 0.1% 避免越界）。长债用收益率 bp 表达止损，其余资产用价格；每项都带 `stop_note` / `rationale` 可供复核。
- **合成与取证**：`engine._synthesis` 为每个资产挂 `plan`，并输出 `portfolio`（`gross/long/short/net/cash`、`portfolio_risk_pct`、`positions`、五条规则、`note`）；`lens.synthesis` 的 claim 增加「组合建议总敞口/组合风险」，caveat 声明权重基准与账户余额无关，`persist` 步骤记录这两项输出。
- **API**：`/api/v2/lenses/state` 与 `POST /run` 顶层新增 `portfolio`（同 `synthesis.portfolio`）；只读取到旧版推导（无 `portfolio`）时自动补算一次。
- **前端**：`/lenses` 合成表新增「仓位 / 止损 / 权重」三列（带止损说明 tooltip），并新增「组合层 · 仓位 / 止损 / 权重」卡（总敞口、多空、净敞口、现金、组合风险、逐仓位表、规则与说明）。`LensAsset` 增 `plan`、`LensSynthesis` 与 `LensStateResponse` 增 `portfolio`。
- **交易信号与资金解耦**（`backend/app/decision/plans.py`）：手数改按标准基准权益 10 万元计算并保留小数手，删除「手数 ≥ 1」「保证金占用 ≤ 50% 权益」两条拦截，改用 5 条与资金规模无关的检查（单笔风险 ≤0.3%、止损距离 ≤5%、组合权重 ≤25%、名义杠杆 ≤5×、手续费 ≤风险金额 20%）；新增 `weight_pct`/`stop_distance_pct`/`risk_amount`/`leverage`/`risk_reward`/`sizing_note`/`lots_int`/`base_equity`，`PlanDetail.payload` 同步。`/signals` 页去掉「资金不足」标签与页脚说明，改为展示标准手数、止损距离、权重、杠杆、风险金额与盈亏比。
- **文档**：`docs/27` 新增 §12.6（止损/风险预算/权重/组合约束四项规则表与口径说明）；`docs/28` 的 E2「构建投资决策」由「部分达成」改为「达成」，弱项改为「仓位只到建议不到执行」。
- **验证**：`tests/test_v2_lenses.py` 扩为 10 条（新增组合缩放与 claim 用例）；`tests/test_m5.py` 改写「昂贵合约手数 ≥1」旧断言，新增资金无关用例；`scripts/lint.py` PASSED；全量 `pytest -q` 通过。

### 新增（多透镜扩展与数据补全，2026-11-19）

- **人物研究**：新增 9 份研究笔记 [`docs/research/persona-*.md`](docs/research)——达里奥（DL1–DL11）、德鲁肯米勒（SD1–SD11）、马克斯（HM1–HM12）、冈拉克（JG1–JG12）、埃里安（EE1–EE12）、波萨（ZP1–ZP10）、佩蒂斯（MP1–MP12）、辜朝明（RK1–RK11）、政策四人体（PA1–PA12，拉加德/植田和男/贝森特/潘功胜）；每份 300–400 行，含 14 条指标、可证伪规则（阈值 + 失效条件 + 资产映射）、2023–2026 观点验证、出处分级与数据缺口。
- **通用人物引擎**：新增 `backend/app/lens/persona.py`——YAML 驱动的透镜加载与校验（`load_specs`/`validate_spec`）、AST 白名单表达式沙箱（`z`/`pctile`/`chg`/`pct`/`yoy`/`ma`/`shift`/`sum12`/`ttm`，支持数字开头列名占位符与关键字参数）、读数/规则/七资产评分/lean 与覆盖率。新增 `config/personas/*.yaml` 9 份规格（合计 93 条规则）。
- **宏观层与微观层**：新增 `backend/app/lens/layers.py`——宏观层 14 条读数（增长/通胀 z、实际利率、净流动性 `(FED_ASSETS−TGA−RRP)/1e12`、财政脉冲 TTM、利息/收入、融资压力、M2 同比、中美曲线）与 M1–M6 规则；微观层 14 条读数（SPX 偏离 200 日线、NDX/SPX、铜金比、油金比、金银比、COMEX 基差、中金价差、SGE 租借、ETF 流向、COT z、汇率与 A 股动量）与 P1–P6 规则。
- **合成升级**：`backend/app/lens/engine.py` 从 2 套透镜扩到 13 套（美联储、宋鸿兵、宏观、微观 + 9 人物），`_synthesis` 改为加权合成（权重取 `config/lens.yaml`，合计 1.000；缺失透镜不计 0），一致度升级为多镜共振（≥2 套同向 min≥0.25）/共振强信号（≥3 套且 |consensus|≥0.6）/分歧（正负各≥0.35）/单一透镜；分歧按「最强多 vs 最强空」成对输出；推导从 3 条增至 14 条（`lens.macro.state`、`lens.micro.state`、9 条 `lens.persona.<id>.state`），方法注册新增 `lens.macro.v1`/`lens.micro.v1`/`lens.persona.v1`。
- **数据源补全**：新增 `backend/app/ingest/providers/fed_h41.py`（美联储 H.4.1 资产负债表 6 条周频序列）、`fed_h6.py`（M1/M2/货币基础）、`nyfed_money.py`（TGCR/BGCR/OBFR 与隔夜逆回购余额）；`pipeline.py` 新增 `SOURCE_FED_RESEARCH`、`MACRO_SERIES_META` 19 个 code、世界银行 5 个结构性指标（经常账户、储蓄率、M2/GDP、资本形成、实际增长），并把联邦债务回补到 1800 天、财政部月度收支回补到 109 个月。`macro_series` 34 → **57 条**。
- **API**：`/api/v2/lenses/*` 暴露 `macro`/`micro`/`personas` 与 `rules.{macro,micro,personas}`，人物条目补 `name/title/school/key_question/thesis`；`lenses` 新增每日 16:25 作业（`runner.py`、`scheduler.py`、`catchup.py`、`init_db.py` 种子同步）。
- **前端**：`/lenses` 页签扩为 6 个（合成研判 / 美联储 / 宋鸿兵 / 宏观·微观 / 人物透镜 / 规则与证据），新增宏观象限卡、微观结构卡、两层读数网格、人物卡与人物评分矩阵，资产表增透镜数与逐镜分数。
- **文档**：新增 [`docs/28-原始需求达成度审计.md`](docs/28-原始需求达成度审计.md)（原始需求逐条判定与证据、未达成清单、P0–P2 路线）与 [`docs/29-数据源与数据完整性.md`](docs/29-数据源与数据完整性.md)（provider→序列→覆盖、缺口与替代、完整性机制、新增数据源做法）；更新 `docs/27` 缺口表、README 状态与页面表。
- **验证**：`tests/test_v2_lenses.py` 扩为 8 条（含人物规格校验）；`tests/test_macro_sources.py` 补 H.4.1/H.6 离线 stub；`scripts/lint.py` PASSED；`vue-tsc --noEmit` 0 error；`vite build` 成功；全量 `pytest -q` **358 passed**。

### 新增（双透镜：美联储一脉与宋鸿兵框架，2026-11-18）

- **研究笔记**：新增 `docs/research/fed-chair-framework.md`（格林斯潘/伯南克/耶伦/鲍威尔：哲学演变、反应函数、26 指标、R1–R15、8 案例、2025–26 预警、S1–S27 出处与 20 处【未核实】）与 `docs/research/song-hongbing-framework.md`（《货币战争》理论骨架、资产映射、25 指标可得性、S1–S14、T1–T8、2023–2026 研判验证、N01–N50 出处）。新增设计说明 [`docs/27-多透镜研判-美联储宋鸿兵与九位思想者.md`](docs/27-多透镜研判-美联储宋鸿兵与九位思想者.md)。
- **后端引擎**：新增 `backend/app/lens/`——`common.py`（读数/规则求值/分位/z/相关）、`fed.py`（21 条读数、stance 加权分位、增长×通胀四象限、Fed Put 行权距离、7 类资产评分）、`song.py`（31 条读数、SOFR−EFFR「美元心脏」三态、热/冷环流相位、收割与债务风险、黄金状态）、`engine.py`（`run_lenses` 六步编排、三条推导、observations 幂等、透镜预测直写 Forecast）。新增 `config/lens.yaml`（F1–F12、12 条 S 规则、权重、数据缺口与免责声明；S6/S14 因缺可计算指标未纳入）。
- **API**：新增 `/api/v2/lenses`——`GET /state`、`POST /run`、`GET /forecast-codes`、`GET/POST /forecasts`、`GET /ping`、`POST /commentary`；`/state` 无落库数据时懒运行一次，并支持从落库推导的 `rule_metrics` 重建全部规则状态（含 miss/unknown）。方法注册新增 `lens.engine.v1`、`lens.fed.v1`、`lens.song.v1`、`lens.synthesis.v1`；`RunRecorder` 的 kind 白名单加入 `lens`。
- **前端**：新增 `/lenses`「双透镜」页（合成研判 / 美联储透镜 / 宋鸿兵透镜 / 规则与证据四页签，7 类资产共识表、预警与分歧、90 天三情景、21+31 条读数网格、F/S 规则 trace、预测登记、AI 解读），路由与侧栏「专题」组接入；`api/types.ts` 与 `endpoints.ts` 同步。
- **验证**：新增 `tests/test_v2_lenses.py` 7 条（配置、端到端、幂等、只读状态、预测与运行、预测结算、LLM ping）；`scripts/lint.py` PASSED；`vue-tsc --noEmit` 0 error；`vite build` 成功（`LensesView-*.js` 29.3KB）；全量 `pytest -q --ignore=tests/test_frontend_build.py` **352 passed**。
- **已知边界**：COMEX 白银库存、IMF COFER、CIPS/人民币跨境、HY OAS、M2、财政脉冲（payload）6 项未接入，对应规则显示 `unknown`；合成概率为启发式映射，尚未校准。

### 修复（双透镜审核意见，2026-11-19）

- **血缘**：`lens.fed.state` 的 `subject` 由拼写错误的 `lens:feded` 改为 `lens.fed`；运行返回补齐 `kind/subject/started_at/duration_ms/error`，与只读路径同形。
- **契约**：`/api/v2/lenses/synthesis.divergences` 补齐 `spread` 与 `reading`，前端按 `asset` 作 key；`LensDivergence` 类型与后端一致；`gold_regime` 颜色映射改为实际枚举（`strategic/accumulate/avoid`）。
- **结算**：`ledger.engine.actual_value` 增加 `lens.<asset>` → 标的收盘价（长债 → US30Y 收益率）映射，透镜预测到期可真正结算，不再永久 `pending`。
- **API**：`GET /state` 无落库数据时懒运行；`GET /forecasts` 的 `status` 下推 SQL 并限定 `open/resolved`；`commentary` 的时间窗改读 `outlook.horizon_days`；`POST /run` 不再把内部异常明文回传；`_payload_from_persisted` 与 `_payload_from_result` 合并为同一 `_payload`，规则分组直接按配置，不再用编号前缀猜测。
- **文档/配置**：修正 `docs/27` 的评分区间（−2…+2）、agreement 阈值、gold_regime 命名、`app.platform.db` 复现命令、财政脉冲口径与 S6/S14 未纳入原因；删除 `config/lens.yaml` 中未被消费的 `forecast_horizons`/`asset_order` 与不存在的 `lens-methodology.md` 引用；README/CHANGELOG 的规则数、测试数与未核实数改为可复现实测。
- **测试**：`tests/test_m7.py` 日志列表改为按日期过滤，消除共享测试库导致的偶发失败；新增透镜预测结算用例。

### 重构（去重与可读性，2026-11-19）

- **API 序列化统一**：`backend/app/api/serializers.py` 的 `iso()` 支持 `datetime | str`，并新增 `run_payload()`、`derivation_payload()`；`cycle/glassbox/knowledge/ledger/market/timeline/trades/lenses` 八个路由删除各自的 `_iso` 与运行/推导字典构造，统一复用，时间戳统一为带 UTC 偏移的 ISO（naive 值补 `+00:00`）。
- **透镜读数的目录元数据收口**：`backend/app/lens/common.py` 新增 `reading_from_catalog()` / `missing_from_catalog()` / `low_freq_column()` / `format_reading()` / `round_opt()`；`fed.py` 与 `song.py` 删除各自重复的 `_reading`、`_missing`、`_low_freq`、`_fmt` 实现（约 60 行重复），`engine.py` 复用 `round_opt`。
- **前端格式化复用**：`useFormat.ts` 新增 `fmtRatioPct()`，`LensesView.vue` 删除本地 `pct()`。
- **验证**：`scripts/lint.py` PASSED；`vue-tsc --noEmit` 0 error；`vite build` 成功；全量 `pytest -q --ignore=tests/test_frontend_build.py` **352 passed**，`tests/test_frontend_build.py` 5 passed。

### 改进（系统状态 · 数据质检列宽，2026-11-18）

- `frontend/src/views/SystemView.vue`：「数据质检」表改为固定布局并加 `colgroup`——数据集列 132px 且 `white-space: nowrap`（超长省略并带 `title`），类型 / 状态列 84 / 72px 固定，明细列占剩余宽度并自动换行，长明细不再挤压数据集列。

### 修复（证据抽屉 PDF 正文乱码，2026-11-18）

- **症状**：日报「新闻与政策（官方来源）」的证据按钮点开后，抽屉正文与断言是 `%PDF-1.6` 开头的二进制乱码（如 ECB 演讲 PDF、日本央行统计 PDF）。
- **根因**：`backend/app/ingest/pipeline.py` 的 `collect_bodies()` 把 `resp.text`（PDF 字节被当文本解码）直接交给 `extract_main_text()` 抽正文，没有 content-type / 二进制判断；乱码长度超过 80 字符即写入 `document_bodies`，`extract_claims()` 又从乱码里抽出断言。
- **修复**：`ingest/providers/html_extract.py` 新增 `looks_like_binary()`（`%PDF` 开头、U+FFFD 或控制字符占比过高）并在 `extract_main_text()` 入口短路返回空串；`collect_bodies()` 对 `.pdf` URL / `content-type` 含 pdf 或 octet-stream / 疑似二进制的响应标记 `body_status="unsupported"`，不写正文（stats 增加 `unsupported`）；新增 `purge_binary_bodies()` 清理存量坏正文及其派生 `Claim` / `DocumentSpan`（实测清理 **77 条正文 / 219 条断言 / 219 条片段**，292 → 215 条正文）。
- **前端兜底**：`components/domain/EvidenceDrawer.vue` 增加 `binaryDoc` 判断（`status=="unsupported"`、URL 以 `.pdf` 结尾、正文疑似二进制），命中时只显示「原文为 PDF / 二进制文件」提示与「打开原文」，不再渲染乱码正文与断言。
- **验证**：新增 `tests/test_binary_body_guard.py` 3 条（二进制识别、抽正文短路、存量清理级联）；`pytest -q` → **350 passed**；`vue-tsc --noEmit` 0 error；`scripts/build.ps1` → 44 个资源；重启后实测 `/api/documents/0df7a6a1…` 返回 `status=unsupported`、`body=null`、`claims=0`。

### 改进（可用性九项：菜单归类、页面去重、预警台账重排、任务可观测、表格禁横滚、中英对照，2026-11-18）

- **菜单归类（需求 1）**：`frontend/src/layouts/Sidebar.vue` 的「证据」组（分析引擎 / 分析过程 / 分析依据）下移到「预警」组之后、系统之前，与信息架构文档一致。
- **页面去重（需求 2）**：`AnalysisView.vue` 四块整表改为「摘要 + 下钻」——方法注册表 → 方法构成 / 代码指纹 / 最近运行三项摘要；最新运行 → 只展示最近一次 + 「查看全部运行与步骤链」；证据等级 → 只留分布 + 推导明细链接；数据质量 → 通过率 / 未通过 / 检查时点一行 + `/system` 链接；`ThesesView.vue` 的「论点复核」统计并入 KPI，只留最近 6 条记录；改名消歧「周期状态 → 市场隐含周期象限」「历史类比 → 相似交易日」。权威页与摘要页对照见新增的 `docs/26-页面交互与信息架构.md`。
- **预警台与预测台账（需求 3）**：`components/alerts/AlertTable.vue` 重写为 9 列固定布局（状态 / 严重度 / 规则 / 指标 / 当前值 / 阈值输入 / 距离 / 观测日 / 展开），阈值可直接在行内编辑并保存（`PATCH /api/v2/cycle/config`），删除恒为空值的「胜率 / 置信度」列，触发行展开给出复核说明；`AlertsView.vue` 删除与表内重复的 `ThresholdEditor` 区块、页脚补 `/ledger` 与 `/pipeline` 跳转并渲染降级原因；`LedgerView.vue` 未结 / 已结合并为 7 列单表、按到期日升序、逾期高亮、表内滚动，重算失败给 toast，口径说明折叠，原则核对只留计数与链接。
- **交互与业务梳理（需求 4）**：`PipelineView` / `CycleView` / `AnalysisView` 页头互链（分析结论、分析依据、市场隐含象限、世界长河、周期规则预警），`router/index.ts` 的 `scrollBehavior` 支持 `#anchor` 平滑定位；页面职责边界、业务数据流、交互惯例写入 `docs/26-页面交互与信息架构.md`。
- **任务调度可观测（需求 5）**：`models/core.py` 的 `Job` 新增 `description` 列并配 light migration；`init_db.py` 新增 `JOB_DESCRIPTIONS`（29 个任务的用途说明）在 `seed_jobs()` 时回填；`/api/system/jobs` 新增 `description` 与 `run_count`，`/api/system/job-runs` 支持 `job_name` 过滤并返回 `id` / `duration_ms`；`scheduler.py` 心跳写 `JobRun` 且每小时 `prune_job_runs()` 保留每任务最近 200 条；`SystemView.vue` 任务表改为 7 列（任务 / 任务描述 / 计划 / 启用 / 最近状态 / 最近运行 + 时效 / 调度次数），点「调度次数」抽屉展示执行历史（开始时间 / 状态 / 耗时 / 摘要）。
- **数据健康·序列覆盖（需求 6）**：`SystemView.vue` 由长文本段落改为四个指标块（序列覆盖 / 作业健康 / 最近同步 / 数据时点）+ 健康度进度条与图例 + 分行的计算口径列表（按 `；|;|\n` 拆分 `coverage.method`）。
- **表格不再横向滚动（需求 7）**：`styles/app.css` 移除 `tbody td` 的全局 `white-space: nowrap`，`.table-wrap` 改为 `overflow-x: hidden`，新增 `td.cell-wrap` / `td.cell-clip`（仅数值、时间、代码、徽标保留 nowrap）；清理各页硬 `min-width`（Trades 12 → 11 列并合并类型/方向、History 周期表删两列重复、Ledger 7 列、AlertTable 9 列、Cycle/Pipeline/HistoryTimeline 去硬宽、MarketCalendar 网格改 `minmax(0, Npx)`）。
- **简报（需求 8）**：`narrative/brief.py` 日报「会员持仓」改为 pipe 表格（品种 / 多头 / 空头 / 净持仓 / 净占比，头尾各 3），事件与新闻的英文标题后追加「（中文：…）」且中文在 `enhance_brief` 之前写入、`[D:xxx]` 证据标记保持完整；`weekly.py` / `monthly.py` 复用 `position_rows` / `recent_event_rows` / `news_lines`，补「会员持仓」「事件驱动」「新闻与政策」三节（周月报翻译 `allow_llm=False`，不阻塞定时任务）；新增 `narrative/zh.py`（`zh_pairs` 批量翻译）与 `prompts/brief_editor.v1.md` 的两条硬约束（保留中文对照括号、保持 pipe 表格）。
- **全站中英对照（需求 9）**：新增 `composables/useZhTranslate.ts`（单例缓存、批量 ≤30、失败冷却静默重试）与 `components/ui/ZhText.vue`（中文为主、英文原文弱化、缺译提示），统一 `ThesesView` / `OverviewView` 两处重复的翻译逻辑，并接入财经日历、告警抽屉标题与正文、政治窗口、证据抽屉文档标题。
- **验证**：`pytest` → **347 passed**；`vue-tsc --noEmit` 0 error；`scripts/build.ps1` → 44 个资源、1,623 KB；重启服务后实测 `/api/system/jobs` 29 条全部带 `description` 与 `run_count`、`/api/system/job-runs?job_name=collect_quotes` 返回 `duration_ms`、`/api/briefs/latest?kind=daily` 含持仓表格与「（中文：…）」、`/api/knowledge/translate` 中文原文直返 `seed`。
- **已知边界**：当前环境未配置 `.env` / `DEEPSEEK_API_KEY`（`llm_enabled=false`），本地语料未收录的英文标题暂无中文对照，`ZhText` 会显示缺译提示；`/api/system/acceptance` 仍因世界银行年频序列（`WB_*`）滞后报 2 项失败，属数据源发布节奏问题；Windows 沙箱下 pytest 的 `tmp_path` 目录权限（`mkdir(mode=0o700)` 在沙箱内不可读）用工作区 `data/test/shim` 的 `sitecustomize` 规避，不进入仓库。

### 新增（全系统审计补齐：真实结构性数据源、流水线看门狗、预测台账自动化，2026-11-18）

- **结构性宏观数据源接入（替换硬编码）**：新增 4 个 provider——`backend/app/ingest/providers/treasury_fiscal.py`（美国财政部 Fiscal Data：`debt_to_penny` 日频联邦债务、MTS table 9 月频收支）、`worldbank.py`（世界银行年频 GDP/CPI/失业率/债务）、`imf_datamapper.py`（IMF WEO 年频 7 指标 × 中/美，带浏览器 UA 与 `Referer/Origin`）与 `errors.py`（统一 `ProviderError`）。`backend/app/ingest/pipeline.py` 的 `MACRO_SERIES_META` 由 22 条扩到 49 条，新增 `collect_macro()`（三段独立降级，返回 `{series, obs, degraded_reasons, elapsed_ms}`）与 `_store_macro_points()`；新增作业 `collect_macro`（Cron 08:05 + 启动 40 秒 bootstrap）。实测 `collect_macro()` 写入 `{"series":12,"obs":505}`，`macro_series` 22 → 34 条（含 7 条年频），重复执行不产生重复观测。
- **周期引擎结构性读数改为「数据库实时优先、YAML 人工兜底」**：新增 `backend/app/cycle/structural.py`（`resolve()` / `score_from_bands()`），`config/cycle.yaml` 的 7 条结构性人工值补 `bands` 与 `live_series`，`backend/app/cycle/{indicators,sustainability,engine}.py` 传入 `session` 并按命中情况给 E2/E3 与 caveat。实测 7 条中 3 条转为实时：美国联邦债务/GDP **132.15%**（财政部日频债务 ÷ 世界银行 GDP）、财政赤字/GDP **6.86%**（MTS 近 12 个月）、利息/财政收入 **19.82%**；其余 4 条（`us_r_minus_g`、`cn_debt_gdp`、`cn_interest_revenue`、`us_reserve_share`）显式回落并给出原因（IMF COFER 尚未接入等），不再冒充实时。
- **流水线与作业不中断**：`backend/app/provenance/engine.py` 新增 `reconcile_stale_analysis_runs()`（超时 `running` → `interrupted` + `run.interrupted` 降级原因，`RunRecorder.start()` 与启动 lifespan 各调用一次，实测收尾 2 条僵尸 gold 运行）；新增 `backend/app/jobs/catchup.py` 与 `main.py` 启动补跑（`catch_up_jobs()`，按 `jobs.last_run_at` 与当日 `JobRun` 判重），实测补跑 `brief_premarket` 成功（简报表新增 2026-11-18 premarket）。
- **预测台账自动化（Brier 不再永远无样本）**：`backend/app/ledger/engine.py` 新增 `auto_register_forecasts()`——9 个指标（六分量 + 黄金评分 + XAUUSD + US10Y）× 30/90 天期限，用 60 天斜率定方向与概率、按斜率外推目标值，幂等键 `code+subject+target_date`；`run_ledger()` 增加 `register_forecasts` 步骤，实测生成 **18 条 open 预测**（到期日 2026-12-18 / 2027-02-16）。同时修复 `_latest_market_value()` 使用了不存在的列（`Instrument.code`/`MarketBar.ts` → `Instrument.symbol`/`MarketBar.ts_utc`）与 `_latest_gold_score` 的时间列（`AnalyticsResult.ts` → `asof`）。
- **数据质检口径修正**：年频宏观序列的新鲜度窗口由 400 天放宽到 **800 天**（`backend/app/platform/coverage.py` 的 `FRESH_DAYS_BY_FREQ`、`inspect/pipeline.py` 的 `check_data_quality`、`backend/app/ingest/continuity.py` 的年频空档上限），因为世界银行/IMF 年度值本身会滞后 18~24 个月，400 天会把「上游尚未发布」误判为断更；同步更新 `QUALITY_METHOD` 的对外口径文案。重跑 `check_data_quality` → **10 项检查 0 失败**（此前 continuity 5 处缺口、freshness 2 条年频滞后均已消除）。
- **前端功能补完**：`AnalysisView.vue` 新增「引擎透明度」四区块（方法注册表 / 最新运行结论 / 证据等级分布 / 数据质量，text 4726→7542）；`LedgerView.vue` 预测清单拆未结/已结两表并补结算口径与 `n=0` 说明（text 2706→4429）；`SystemView.vue` 任务表增加「时效」列（>24h 黄、>72h 红、未运行红标）与卡头汇总（text 4859→5472）；`CycleView.vue` 新增全宽「结构性 / 人工观测」表（16 行，证据等级、来源、时效、降级原因）；空态补操作提示（`OverviewView`/`MarketView`/`DerivationDrawer`/`EvidenceDrawer`）；删除无引用的 `frontend/src/views/TokensView.vue`。
- **侧栏精简**（`frontend/src/layouts/Sidebar.vue`、`frontend/src/styles/app.css`）：去掉「市场行情」「分析依据」后面的计数徽标（`badgeFor()`/`counts`/`.nav-badge` 全删），侧栏宽度 232px → **196px**，导航内边距与分组标签同步收紧。
- **验证**：`pytest tests -q` → **341 passed**（新增 `tests/test_pipeline_gaps.py` 9 条、`tests/test_macro_sources.py` 6 条、`tests/test_cycle_structural.py` 12 条）；`scripts/lint.py` → PASSED（0 errors, 0 warnings）；`vue-tsc --noEmit` 0 error、`npm run build` ✓；真实库重跑 `cycle`（10 步 / 7 推导 / 36 类比）与 `ledger`（原则 9 命中 4 接近 6 不成立 7 缺数据）；headless Chrome 逐路由扫 16 页 **0 JS 错误、0 零高度图表**，截图复核分析引擎 / 预测台账 / 周期罗盘 / 系统状态 / 分析过程。
- **已知边界**：IMF COFER 储备货币份额、BIS/IIF 中国债务等 4 条仍需人工观测（已在 UI 标注回落原因与证据等级）；`extract_claims_llm` 需要 `DEEPSEEK_API_KEY`，未配置时保持「从未运行 / 降级」；Brier 需等 2026-12-18 首批预测到期后才有样本。

### 修复（「分析依据」更名、原则库抽屉排版，2026-11-18）

- **「论点与证据」更名为「分析依据」**：`frontend/src/layouts/Sidebar.vue`、`frontend/src/router/index.ts`（`meta.title`）、`frontend/src/views/ThesesView.vue`（页头标题、eyebrow 与刷新提示）、`frontend/src/components/domain/CommandPalette.vue` 同步；面包屑随之显示「EPIC V2 / 证据 / 分析依据」。
- **原则库详情抽屉排版修复**（`frontend/src/views/PrinciplesView.vue`）：「如何核对」四步列表原先用两列 grid，序号伪元素、标题 `b` 与正文 `span` 共三个网格项只占两列，导致正文被挤进 20px 序号列、逐字竖排。改为序号 `grid-column:1; grid-row:1 / span 2`，标题与正文都落在第二列（`grid-column:2`）并允许 `overflow-wrap: anywhere`；实测步骤正文宽度由 20px 恢复为 419px（抽屉内容宽）。
- **抽屉标题栏抗溢出**（`frontend/src/styles/app.css`）：`.drawer-title` / `.drawer-sub` 增加 `min-width: 0` + 省略号截断，长原则名与副标题不再挤压关闭按钮。
- 验证：`vue-tsc --noEmit` 0 error、`npm run build` ✓、CDP 复扫 10 条路由 0 JS 错误、原则库 26 张卡片抽屉实测无横向溢出。

### 变更（菜单扁平化为两级、数据健康并入顶栏，2026-11-18）
- **侧栏只保留两级菜单**（`frontend/src/layouts/Sidebar.vue`）：今日（总览 / 简报 / 交易）、市场（市场行情 / 利率与流动性）、专题（黄金研判 / 交易信号）、证据（分析引擎 / 分析过程 / 论点与证据）、周期（周期罗盘 / 世界长河 / 原则库）、预警（预警台 / 预测台账）、系统（系统状态）；取消「研判」一级与全部三级小标题，`NavSection` / `sectionsOf()` 与 `.nav-sub` 一并删除。
- **页面与分组更名**（`frontend/src/router/index.ts`）：「透明管线」改为「分析过程」，面包屑分组按新结构标注（证据 / 周期 / 预警 / 专题），「简报与日志」统一为「简报」；`PipelineView.vue` 页头与 `AlertsView.vue`、`LedgerView.vue` 的跳转文案同步改为「分析过程」。
- **数据健康并入右上角**（`frontend/src/layouts/Topbar.vue`）：「数据采集」pill 改为可点击展开面板，内含数据健康百分比与进度条、序列覆盖、最近同步、后端 API、行情标的、调度器与版本；右侧 pill 仍显示系统当前时间 `yyyy-MM-dd HH:mm:ss`。侧栏底部只保留版本行（`EPIC v2.0.0 · 本地实例`），删除重复的健康卡与 `.sf-status / .sf-rows / .sf-row` 样式（`frontend/src/styles/app.css`）。
- **验证**：`vue-tsc --noEmit` 0 error；`npm run build` 成功；`scripts/lint.py` PASSED（0 errors, 0 warnings）；headless Chrome 逐路由核对面包屑（今日 / 市场 / 专题 / 证据 / 周期 / 预警 / 系统）与页面名，侧栏三级小标题数量为 0，数据面板输出「健康 95.8% · 序列覆盖 21/22 · 行情标的 35 个 · 调度器 运行中」。

### 新增（交易模块、世界长河按原型 1:1 重绘、顶栏双 pill，2026-11-17）

- **「交易日志」升级为独立「交易」模块**：新增 `trade_records` 表（`backend/app/models/v2.py`）与 `backend/app/api/trades.py` 七个端点——`GET /api/trades`（关键词 / 品种类型 / 方向 / 状态 / 日期区间筛选 + 分页）、`GET /api/trades/{id}`、`POST /api/trades`、`PATCH /api/trades/{id}`、`DELETE /api/trades/{id}`、`GET /api/trades/summary`（笔数/胜率/累计盈亏/盈亏比/手续费/平均盈亏）、`GET /api/trades/stats`（按品种类型与按月分组）。字段覆盖参考表 `商品期货交易计划与执行分析系统.xlsx` 的计划与复盘链路：品种/名称/类型（期货·股票·期权·外汇·加密）/方向/状态（计划·挂单·持仓·已平仓·已取消）/策略/计划数量/实际数量/开仓价/平仓价/止损价/止盈价/保证金/杠杆/手续费/盈亏/收益率/风险金额/盈亏比/预计胜率/盈亏归因/计划说明/复盘结论/标签；盈亏、收益率、盈亏比由服务端按开平仓价与数量计算，避免前后端口径漂移（预计胜率表单按 `%` 录入、库内统一存 0–1 小数）。
- **新增 `/trades` 页面**（`frontend/src/views/TradesView.vue` + `components/trades/{TradeTable,TradeFormDrawer,TradeKpi}.vue`）：5 张 KPI（总笔数/胜率/累计盈亏/盈亏比/手续费）、搜索与四组筛选、按交易日倒序表格（盈亏红绿）、新建与编辑抽屉（基本信息 / 价格与仓位 / 风险与复盘 / 标签 四组，前端实时预估盈亏与收益率、品种代码 datalist 速选）、删除二次确认、空态与错误态；`/journal` 改为重定向到 `/trades`，侧栏「交易日志」更名为「交易」，简报页的内嵌日志块改为跳转链接卡；下线未再使用的 `views/JournalView.vue` 与其样式，`/api/journal` 接口保留（作为按日笔记能力，未被页面引用）。
- **世界长河按合并原型 1:1 重绘**（新增 `frontend/src/components/history/HistoryTimelineChart.vue`，替换原 ECharts 双折线与旧四泳道）：储备货币份额带（荷兰盾/英镑/美元/人民币四条曲线 + 峰值标注 + 2026 后推演区）、每 50 年网格与年份刻度、荷兰/英国/美国/中国四条帝国泳道与崛起·顶峰·衰落三色带、22 类事件按图层换形状（债务危机菱形、战争三角、技术革命圆点、帝国兴衰圆环）并带引线与年份上下交替标注、图例、缩放（100/130/170/220%）与三档时间窗、五类图层 chips；画布宽度与原型一致按容器自适应（`W = (可视宽 - 8) × zoom`，100% 时不产生横向滚动）；数据优先取 `/api/v2/timeline/{overview,events,eras,powers}`，接口不可用时回落原型静态数据并标注「示意数据」；点击事件联动右侧详情卡。
- **顶栏时间口径重构**（`frontend/src/layouts/Topbar.vue`）：拆成两个 pill——① 绿色状态点 + 「数据采集」+ 采集时间（`yyyy-MM-dd HH:mm`）+ 健康百分比；② 系统当前时间 `yyyy-MM-dd HH:mm:ss`（每秒刷新）。数据生成时间不再进顶栏，统一为各页标题旁的 `.gen-at`「（生成于 …）」。
- **修复**：全局 `.ic` 补 `width/height: 14px`（此前 `svg { display:block }` 使世界长河页头 16px 时钟图标被撑成 300×150）；`backend/app/api/cycle.py` 新增 `_normalize_state()` 兼容旧推导（见下）；`backend/app/alerts.py` 事件标题上限由 60 改 200 并新增 `_supersede_truncated()` 清理历史截断告警。
- **验证**：`pytest tests -q` → **314 passed**（新增 `tests/test_trades.py` 与 `tests/test_zh_translate.py`、`tests/test_journal.py`）；`scripts/lint.py` → PASSED（0 errors, 0 warnings）；`npm run build` 成功、`vue-tsc --noEmit` 0 error；headless Chrome 逐路由扫 16 页 **0 JS 错误**，截图复核总览/交易/周期/长河/管线/预警台/台账/原则库/信号。
- **已知边界**：交易模块未接券商/期货公司成交单（纯手工台账）；`/trades` 当前为空库，示例数据仅在验证时插入并已清除；世界长河的储备份额与事件年份为示意数据（E0 叙事级），不是精确历史统计。

### 修复（可用性九项：白屏、菜单归类、中文对照与时间口径，2026-11-17）

- **修复 `/cycle` 点击重算白屏**：根因是数据库里的旧版 `cycle.state.world` 推导缺少 `band/phase_id/confidence/next_phase`，前端模板直接下标 `long_cycle.band[0]` 抛 `TypeError: Cannot read properties of undefined (reading '0')`。后端 `backend/app/api/cycle.py` 新增 `_normalize_state()`，按 `config/cycle.yaml` 的相位区间补齐 `band/phase_id/phase/meaning/asset/position/next_phase`、`short_cycle` 六键、六分量 `composites` 与 `readings` 结构，`generated_at` 改用该次运行的 `finished_at`；前端 `CycleView.vue` 与 `components/cycle/*` 同步加防守（`asNumber/asText` 兜底、空数组/缺字段降级、接口失败提示不白屏）。
- **删除「设计规范」菜单与 `/tokens` 页面**：设计 token 属于内部约束，不再出现在使用系统中（规范文本仍在 `docs/21-UI设计规范.md`）。
- **研判二级菜单归类**（`frontend/src/layouts/Sidebar.vue`）：新增二级小标题——周期与位置（周期罗盘/世界长河）、透明与证据（透明管线/分析引擎）、预警与台账（预警台/预测台账/原则库）、专题（黄金研判/交易信号/论点与证据）。
- **事件与新闻中英对照**（`backend/app/knowledge/translate.py`、`config/translations.zh.json`、`POST /api/knowledge/translate`）：本地种子 + 缓存（`sha1` 文本哈希）双层，未命中且配置 `DEEPSEEK_API_KEY` 时走 LLM 兜底；`ThesesView.vue` 事件/新闻改为中文在上、英文原文弱化，缺失时提示配置 Key；总览告警同样双语（前端 `utils/labelMap.ts` 提供 kind/level/category 中文标签，翻译前剥离「事件：」前缀）。
- **判研六页内容补全**（`History/Pipeline/Alerts/Ledger/Principles/Cycle` 及其子组件）：周期罗盘新增页面状态机（骨架/错误/空态「暂无周期状态」/字段缺失）；世界长河事件详情可放大抽屉；透明管线 `?code=` 自动展开溯源、契约外步骤显式提示；预警台左表右阈值、未知指标三处提示；预测台账增加未结/已结标记、备注列与 Brier 分桶柱图；原则库按类别分组并附「如何核对」抽屉。
- **全站时间口径与样式统一**：删除各页「更新于」徽标，数据生成时间统一为标题旁 `.gen-at`；`AlertsView/HistoryView/PipelineView/SignalsView/LedgerView/PrinciplesView` 六处改造完成；清理 `BriefsView` 残留日志样式与全局未用 `.clock`、`.pipe-generated-badge`。
- **验证**：CDP 复扫 `/trades /alerts /history /pipeline /signals /ledger /principles /overview` 全部 0 JS 错误；`vue-tsc` 0 error；`pytest` 314 passed；`lint` PASSED。

### 新增（UI 对齐：壳层重构、设计规范页、四个研究页重做与 8 项后端接口，2026-11-17）

- **壳层按合并原型重构**：`router/index.ts` 分组改为「今日 / 市场 / 研判 / 系统」并保留全部 15 个既有页面；`Sidebar.vue` brand 改为 `E2 / EPIC V2 / 周期研判 · 宏观工作台`，底部新增数据健康进度条（`/api/system/coverage`，序列覆盖与最近同步）；`Topbar.vue` 面包屑改为 `EPIC V2 / 组 / 页`，右侧 pill 改为「数据时点 · 健康度 %」；新增 `styles/app.css` 的 `.crumb-group`。
- **新增 `/tokens` 设计规范页**（`frontend/src/views/TokensView.vue`）：色板 14 个 token、字阶 8 档、按钮与 badge、间距、表单控件、示例数据表、骨架/空态/状态点与口径说明，作为后续页面自检基准。
- **`/cycle` 周期罗盘按原型重做**（`CycleView.vue` + `components/cycle/{CycleCompass,CycleForces}.vue`）：hero（长债务阶段 + 短周期 + 综合置信度 + 数据覆盖/规则版本/下次校准）、四象限相位罗盘、五力仪表、8 张关键读数（真实值 + z + 日变动 + spark + E2 证据）、今日预警、历史类比 Top3；**保留**原六分量罗盘、五层周期、60 月轨迹、四情景、债务可持续性、世界秩序、降级原因框与全部轮询/重算能力。
- **新增 8 张读数的真实数据源**（`backend/app/cycle/readings.py` + `GET /api/v2/cycle/readings`）：直接取本地 `macro_obs` / `market_bars`，计算 z（约 5 年窗口）与日变动并附 30 点 spark；缺失时返回 `missing=true` 与原因，不填占位值。实测 8/8 有值：美债 10Y 5.12%、实际利率 2.92%、10Y–2Y +29bp、黄金 3,856、金银比 81.4、LME 铜 13,237、美元指数 103.55、中美利差 −349bp。
- **`/alerts` 预警台按原型重做**（`AlertsView.vue` + `components/alerts/{AlertTable,ThresholdEditor,MarketCalendar}.vue`）：严重度筛选、10 列表格与 10 列可编辑阈值表（保存走 `PATCH /api/v2/cycle/config`，带审计）、财经日历显示预期/前值/实际，缺失字段显示「—」；保留轮询、立即重算、unknown 显式提示与行展开三列。
- **`/pipeline` 透明管线按原型重做**（`PipelineView.vue` + `components/pipeline/{PipelineDag,NodeDetail,PipelineTrace,ScenarioSandbox,ModelCard}.vue`）：run-strip、6 节点 DAG（采集/质检/特征/周期引擎/情景/输出，按步骤名与关键词归并）、L1–L5 溯源树、反事实沙盘（`POST /api/v2/cycle/scenario`，六分量滑杆 + 阶段/短周期/情景概率增量）、模型卡与校准摘要；`?code=` 深链与溯源抽屉全保留。
- **`/history` 世界长河按原型重做**（`HistoryView.vue` + `components/history/{HistoryTimeline,HistoryEventDetail}.vue`）：纯前端时间窗缩放、四层泳道去重叠、霸权时期色带、储备份额曲线（SVG）、GDP/储备两张折线、周期对照表新增黄金期/转折/当前阶段三列、事件全屏详情；`?event=` 深链保留。
- **后端同步扩展 8 项接口**：`GET /api/system/coverage`（健康度 = 60% 序列覆盖 + 40% 作业健康，含最近同步）、`GET /api/v2/cycle/meta`（规则版本/下次校准/Brier/覆盖）、`PATCH /api/v2/cycle/config`（阈值写入 `config/cycle.overrides.yaml` + `data/audit/cycle-config.jsonl` 审计）、`POST /api/v2/cycle/scenario`（纯内存重算，不写库）、`GET /api/market/calendar` 扩展预期/前值/实际与详情、`GET /api/v2/timeline/eras` 扩展黄金期/转折/当前阶段、`GET /api/briefs/{id}` 扩展 `evidence_ids` / `main_thesis`、`GET /api/v2/cycle/readings`；新增 `backend/app/platform/coverage.py` 与轻量迁移（`economic_events` 增可空 forecast/previous/actual/unit）；旧 `/api/*` 与 `/api/calendar` 全部保留。
- **页面功能补全**：市场页表头新增「导出 CSV」（UTF-8 BOM）、品种证据列由固定「—」改为 E0 来源按钮；简报右栏新增「关联证据 · 本期引用」卡（优先接口 `evidence_ids`，回退解析正文证据链接）；总览页新增「近期事件」（政治日历）并把 4 个 KPI 进度条改为真实数据（健康度、行情覆盖、日线回补、作业健康）。
- **验证**：`pytest tests -q` → **280 passed**（新增 `tests/test_v2_ui_align.py` 14 条含读数契约）；`scripts/lint.py` → PASSED（0 errors, 0 warnings）；`npm run build` 成功（`vue-tsc --noEmit` 0 error）；headless Chrome 逐页截图复核（总览/简报/行情/周期/长河/管线/预警台/设计规范/系统，1440 宽），修复两处截图发现的问题（周期概览卡图标尺寸、侧栏版本文案）。
- **已知边界**：五力中「自然冲击」用原油 60 日动量代理、「技术革命」因本地无 NDX/SPX 序列保持「数据缺失」并标 E1 代理口径；财经日历的预期/前值取决于采集源，缺则为「—」；预警的胜率/置信度尚无已结算样本，显示「—」；A2 沙盘不持久化，且 `growth_12m_change` 未入推导快照，短周期判定只用水平值。

### 新增（设计原型合并：V1 布局 + V2 研究视图，2026-11-17）

- **新增 `docs/design/mockup-merged/index.html`**（单文件 355 KB）：以 V2 为壳（导航、顶栏、主题、命令面板、路由），把 V1 原型的总览、市场、简报、设计规范四页并入，合并后共 8 个真实视图——总览 / 简报 / 行情 / 周期罗盘 / 世界长河 / 透明管线 / 预警台 / 设计规范。原两版文件保持不变。
- **合并方式可复现**（同目录 `build.py`）：用 Chrome headless `--dump-dom` 抓取 V1 渲染后的 DOM → 提取 `#view-{overview,market,brief,tokens}` 四个 section 存为 `<template>` → V1 的 CSS 加 `.v1-page` 作用域与浅色主题前缀后存入 `<script type="text/plain">` → 首次切换到 V1 视图时用 `attachShadow({mode:"open"})` 注入，`MutationObserver` 同步深浅主题；V2 原有四视图、为什么抽屉与命令面板逻辑未改。
- **导航与路由改写**：今日（总览/简报）、市场（行情；利率与日历保留「待接入」）、研判（周期罗盘/世界长河/透明管线/预警台）、系统（设计规范）；`VIEWS` 扩为 8 项、默认视图改为 `overview`、URL 同步与偏好存储沿用 V2 机制；无新增依赖（无外链字体、无外部脚本）。
- **详细检查**：8 个视图 × 深色/浅色共 13 张 1440 宽截图逐页复核（`docs/design/mockup-merged/preview-*.png`）；修掉两处合并缺陷——① 正则按嵌套 `<section>` 切分会残留标签文本，改为按视图起点切分；② 浅色主题下 V1 内容仍为深色，原因是独立的 `html[data-theme="light"]` token 块被误删，改为映射到 `.v1-page[data-theme="light"]`。
- **已知差异**（也写入原型 README）：V1 三页内容冻结在 2026-11-13 设计快照，页内按钮为静态展示（`data-go` 跳转除外）；利率与日历仍是「待接入」占位；V1 内容的数据是示意值，不是实时接口。
- 验证：`scripts/lint.py` PASSED；合并文件无外链、无 `@import`、无外部 `script src`；相对链接检查通过。

### 新增（V2.0 M5 打磨：总览定位条、调度接入与版本 2.0.0，2026-11-17）

- **总览页新增周期定位条**（`frontend/src/views/OverviewView.vue`）：Hero 下方一行显示「长债务周期 → 短周期 → 预警已触发/总数」，数据来自 `/api/v2/cycle/state`（2 分钟轮询），并提供 `/cycle`、`/alerts`、`/history` 三个入口，让「今天在周期里的位置」在首页即可见。
- **调度器接入三个 V2.0 作业**（`backend/app/platform/scheduler.py`、`backend/app/jobs/runner.py`、`backend/app/init_db.py`）：`cycle` 每日 16:20（在 analyze 16:10 之后、decide 16:30 之前）、`ledger` 每日 16:45（周期快照就绪后核对原则与到期预测）、`timeline` 每周日 09:30（数据集改动后刷新年表）。作业登记表同步新增默认 cron 标签，`JobRun` 只保存紧凑摘要（周期阶段/短周期状态/预警计数/原则四态/Brier），完整血缘仍在 `analysis_runs` 与 `derivations`。
- **版本升级到 2.0.0**：`backend/app/__init__.py`、`pyproject.toml`、`frontend/package.json` 三处同步（`/api/system/health` 与 `tests/test_release` 校验通过）。
- **文档更新**：README 状态行改为 V2.0.0、页面表补 6 个新页面、V2.0 预览段改为「已实施」并列出设计文档与原型；`docs/18` 新增「6.0 实施记录」（M0–M5 状态、实际落地、提交号、与计划的三处偏差）。
- **验证**：`pytest tests -q` → **266 passed**；`scripts/lint.py` → PASSED（0 errors, 0 warnings）；`npm run build` 成功；三个新作业用 `python -m app.jobs.runner --job cycle|timeline|ledger` 实跑均 ok（cycle：长债务顶部/短周期衰退/预警 1 条；ledger：命中 12 / 接近 2 / 不成立 5 / 缺数据 7）；headless Chrome 复核总览页定位条渲染正常。

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
