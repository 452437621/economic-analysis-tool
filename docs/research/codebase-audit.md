# EPIC 代码库现状审计（V1.3.0）

> 审计方式：只读检查源码、配置、测试与 SQLite 实际数据；未启动服务、未安装依赖、未修改其它文件。
> 行号以当前工作区为准；数据库行数为 2026-11-17 通过 `sqlite3` 只读 `count(*)` 实测。
> 目的：为 V2.0（参考 TradingEconomics + 达利欧周期框架）区分「已实现 / 部分实现 / 仅文档」。
> 时间戳：行号与行数为 2026-11-17 15:05 前后读取快照；审计期间仓库已有并行改动（如 `scheduler.py`、`gold/providers.py` 行数已变），结构与语义结论稳定，个别行号可能漂移。

---

## 1. 技术栈与版本

| 项 | 实际值 | 证据 |
|---|---|---|
| Python 包 | `epic-market-analysis` 1.3.0 | `pyproject.toml:2-3` |
| Python 版本约束 | `requires-python = ">=3.11"`（不是硬性 3.12；CI 跑 3.11/3.12） | `pyproject.toml:5`，`.github/workflows/ci.yml:20` |
| 后端运行时版本 | `__version__ = "1.3.0"`，`settings.app_version` 取此值 | `backend/app/__init__.py:3` |
| Web 框架 | FastAPI + uvicorn；`/assets` 挂 `web/`，`/legacy` 回退 `web-legacy/` | `backend/app/main.py:57-78`, `:81-122` |
| 后端依赖 | fastapi>=0.110、uvicorn[standard]>=0.29、pydantic-settings>=2.2、sqlalchemy>=2.0、alembic>=1.13、apscheduler>=3.10,<4、httpx>=0.27、pandas>=2.2、duckdb>=1.0、pyyaml>=6.0、beautifulsoup4>=4.12、openpyxl>=3.1、xlrd>=2.0、python-dotenv>=1.0 | `pyproject.toml:6-21` |
| 开发依赖 | pytest>=8.0、pytest-asyncio>=0.23、ruff>=0.4 | `pyproject.toml:24-28` |
| 数据库 | SQLite 默认 `sqlite:///data/epic.db`；WAL、`foreign_keys=ON`、`busy_timeout=20000`、`temp_store=MEMORY` | `backend/app/platform/config.py:58`；`platform/db.py:24-35` |
| 调度 | APScheduler 3.x `AsyncIOScheduler`，时区 Asia/Shanghai；任务在线程中执行并加写锁 | `backend/app/platform/scheduler.py:23-24`, `:53-72` |
| LLM | DeepSeek 兼容客户端，`deepseek-chat`/`deepseek-reasoner`，文件缓存 + 日预算 5 USD | `backend/app/llm/client.py:22-25`；`platform/config.py:13-58` |
| 前端包 | `epic-web` 1.1.0（**与后端 1.3.0 不一致**） | `frontend/package.json` |
| 前端依赖 | vue ^3.5.13、vue-router ^4.5.0、pinia ^2.3.0、echarts ^5.6.0、vue-echarts ^7.0.3、@vueuse/core ^12.0.0、dayjs、dompurify、lucide-vue-next、markdown-it、sortablejs | `frontend/package.json` |
| 前端工具链 | Vite ^6.0.7 + Tailwind ^3.4.17 + TS ~5.6.3 + vue-tsc ^2.2.0 + @vitejs/plugin-vue ^5.2.1 | `frontend/package.json` |
| 前端构建 | 产物输出到仓库根 `web/`；`/api`、`/healthz` 代理到 127.0.0.1:8765 | `frontend/vite.config.ts:12-30` |
| 测试配置 | `testpaths=["tests"]`、`pythonpath=["backend"]`、`--basetemp=data/test/tmp`、`-p no:cacheprovider` | `pyproject.toml:38-44` |
| 环境变量 | `EPIC_` 前缀，`.env`；默认 127.0.0.1:8765，数据目录 `data/` | `backend/app/platform/config.py:13-58` |
| Ruff | line-length=110，target py311（CI 未实际执行 ruff） | `pyproject.toml:46-48` |

未找到项：
- `numpy` 的直接声明（`analytics/attribution.py` 用 `np.linalg.lstsq`，靠 pandas 传递依赖）。
- 前端测试框架（vitest/jest/playwright 均不在 `frontend/package.json`）。
- `alembic/` 迁移目录（依赖里有 alembic，但仓库无 migrations）。

---

## 2. 后端模块职责表

代码包实际位于 `backend/app/`（根目录没有 `app/`；`pyproject.toml:34-36` 设 `package-dir={"":"backend"}`）。

| 模块 | 职责 | 关键文件 |
|---|---|---|
| `api/` | 12 个 router + 序列化助手，共 63 个端点；读多写少 | `market.py`、`knowledge.py`、`decisions.py`、`serializers.py`、`system.py`、`watchlist.py`、`analytics.py`、`overview.py`、`gold.py`、`theses.py`、`events.py`、`alerts.py`、`journal.py` |
| `analytics/` | 13 个 py，纯 pandas/规则计算，结果以快照写 `analytics_results` | `runner.py`(144)、`regime.py`(105)、`drivers.py`(119)、`calendar_study.py`(101)、`data.py`(92)、`analogs.py`(73)、`events.py`(75)、`indicators.py`(61)、`leadlag.py`(53)、`attribution.py`(53)、`wind.py`(53)、`correlation.py`(36) |
| `decision/` | 信号、仓位计划、回测、论点、预测结算 | `theses.py`(287)、`runner.py`(186)、`signals.py`(128)、`plans.py`(115)、`backtest.py`(95)、`scoring.py`(89)、`review.py`(63)、`thesis_review.py`(70) |
| `gold/` | 黄金 22 指标注册、评分、采集、provider | `providers.py`(750)、`scoring.py`(249)、`runner.py`(135)、`registry.py`(89) |
| `ingest/` | 采集管道、降级链、质检、历史回补 | `pipeline.py`(1244)、`store.py`(408)、`continuity.py`(379)、`backfill.py`(242)、`symbols.py`(142)、`contracts.py`(62)、`http.py`(170)、`bars_quality.py`(130)、`providers/` 17 个文件 |
| `knowledge/` | 文档正文、规则/LLM 断言抽取、事件抽取 | `extract.py`(129)、`events.py`(176)、`llm_extract.py`(62)、`store.py`(50) |
| `narrative/` | 简报/周报/月报确定性生成、Markdown→HTML | `brief.py`(433)、`weekly.py`(147)、`monthly.py`(146)、`render.py`(72)、`llm_edit.py`(39) |
| `jobs/` | 25 个任务的注册表、`JobRun` 审计、CLI 入口、僵尸任务修复 | `runner.py`(172) |
| `platform/` | 配置、DB 会话/PRAGMA/轻迁移、调度器、写锁、日志、单位换算 | `scheduler.py`(366)、`db.py`(120)、`config.py`(72)、`instrument_units.py`(59)、`writelock.py`(25)、`logging.py`(38) |
| `models/` | 39 个 ORM 表 + Base | `core.py`(564)、`base.py`(30)、`__init__.py`(85) |
| `llm/` | 缓存、预算守卫、`llm_calls` 审计 | `client.py`(203)、`prompts.py`(14) |

顶层散件：
- `backend/app/main.py`(123)：lifespan 做 `init_db`→`seed_instruments`→`seed_jobs`→`reconcile_stale_runs`→`start_scheduler`（`main.py:36-54`），再注册 12 个 router（`:62-73`）。
- `backend/app/init_db.py`(204)：合约规格表 `CONTRACT_SPECS`（22-43）、`JOBS_DEFAULT`（92-118，25 条）、`seed_instruments`/`seed_jobs`/`seed_watchlist`。
- `backend/app/alerts.py`(373)：事件/持仓背离/日历三类告警 + 退避式去重；`notify.py`(89)：Server 酱/企业微信通道。
- `backend/app/serve.py`(62)：uvicorn 入口；`backup.py`(79)：SQLite 备份保留策略。

---

## 3. API 端点全量清单（63 个）

12 个 router 由 `main.py:62-73` 注册。以下按文件归类，路径为完整路径。

### market.py（10，prefix `/api`）
- `GET /market/snapshot` —— 自选 + 全市场快照分组
- `GET /market/bars?symbol&timeframe&limit(≤3000)` —— 日线/历史（与采集上限 3000 对齐）
- `GET /macro/latest` —— 22 条宏观序列最新值
- `GET /macro/series?code&limit(≤5000)` —— 单序列历史
- `GET /positions` —— 最新交易日的持仓快照
- `GET /positions/products` —— 品种聚合
- `GET /positions/members?product&limit(≤20)` —— 会员持仓
- `GET /calendar?days(1-60)&country&category&importance_min` —— 经济日历，返回 total
- `GET /news?q&source&tier&since_days` —— 新闻分页（join `sources`，返回 total）
- `GET /system/sources` —— 数据源健康（last_ok/last_check/last_error/documents 计数）

### analytics.py（10，prefix `/api/analytics`）
- `GET /overview` —— 一次聚合 wind/regimes/correlation/analogs/attribution/indicators/calendar_study/movers(top8)
- `GET /indicators` —— 各标的技术指标
- `GET /regimes` —— 四象限
- `GET /attribution` —— 因子归因
- `GET /correlation` —— 相关矩阵
- `GET /analogs` —— 历史类比
- `GET /wind` —— 风险风向
- `GET /leadlag` —— 领先滞后
- `GET /events`（`kind=event_study`）—— 事件研究
- `GET /calendar`（`kind=calendar_study`）—— 日历事件研究

读法：以上 10 个都通过 `_latest(kind, subject)` 读 `analytics_results` 最新 asof。

### overview.py（1）
- `GET /overview` —— 总览单请求聚合：快照、自选（含 sparkline）、最新简报、未读告警、14 天日历、任务统计、健康；宏观 sparkline 代码表见 `overview.py:32-43`

### gold.py（5，prefix `/api/gold`）
- `GET /overview?series_limit` —— 评分 + 序列 + provider 状态 + 手工指标 + 分类
- `GET /series?code&limit` —— 单指标历史
- `GET /providers` —— 各 provider 最近一次运行结果
- `POST /metrics` —— 仅 `manual=True` 指标可写，upsert `gold_metrics`
- `POST /refresh` —— 后台任务内加写锁跑 `collect_gold`，返回 `{accepted:true}`

### knowledge.py（9，prefix `/api`）
- `GET /documents/{id}` —— 正文 + claims + span
- `GET /documents/{id}/evidence` —— JSON 导出（sha256 + claims）
- `GET /claims?min_confidence&subject` —— 断言查询
- `GET /briefs` —— 按 kind 分组、分页、total、kinds 计数
- `GET /briefs/kinds` —— 各类型数量
- `GET /briefs/latest` —— 最新简报（含 previous/next 邻居）
- `GET /briefs/{id}` —— 单篇
- `GET /briefs/{id}/print` —— HTMLResponse 内联打印样式
- `GET /briefs/{id}/markdown` —— 附件下载

### decisions.py（6，prefix `/api/decisions`）
- `GET /summary` —— signals top12 + plans + checks + backtest + signal_types + open_predictions
- `GET /signals` —— 当日信号
- `GET /plans` —— 交易计划
- `GET /backtest` —— `signal_backtest` 每个 subject 的最新一条
- `GET /predictions` —— 预测列表
- `GET /review` —— Brier / hit_rate / calibration

### system.py（6，prefix `/api/system`）
- `GET /health` —— DB `SELECT 1` + 行数 + 调度器快照 + llm_enabled
- `GET /jobs` —— 任务注册表 + 最近状态
- `GET /job-runs?limit(≤200)` —— 运行审计
- `GET /meta` —— 版本/配置（不回密钥）
- `GET /data-quality` —— 最近 5 分钟窗口内 latest per kind:dataset
- `GET /acceptance` —— 14 条 DoD 阈值（日线≥10000、宏观≥1000、claims≥50、analytics≥10、plans≥1、theses≥1 等）

### 其余 4 个 router（15）
- `theses.py`（4）：`GET /theses`、`GET /theses/{id}`（evidence join Claim）、`GET /theses/review`、`PATCH /theses/{id}`（status 白名单 active/watch/closed/invalidated）
- `watchlist.py`（7）：`GET/POST /watchlist`、`GET /watchlist/candidates`、`POST /watchlist/reorder`、`POST /watchlist/{symbol}/move`、`PATCH /watchlist/{symbol}`、`DELETE /watchlist/{symbol}`
- `alerts.py`（2）：`GET /alerts?limit&include_acked&unread`、`POST /alerts/{id}/ack`
- `journal.py`（2）：`GET /journal`、`POST /journal`（按 entry_date upsert）
- `events.py`（1）：`GET /events?type&q&instrument`（返回 document_ids）

端点总数核对：`Select-String '@router\.(get|post|patch|delete|put)'` = 63（无 put）。
安全/运维缺口：全站无认证、无速率限制（仅绑定 127.0.0.1）；没有触发 analyze/decide 的 HTTP 入口（只能等 cron 或 `python -m app.jobs.runner`）。

---

## 4. 数据模型

`backend/app/models/core.py` 共 39 个 ORM 表（39 条 `__tablename__`，40 个类含 Base）。

| 域 | 表（关键字段/约束） |
|---|---|
| 来源与健康 | `sources`(tier S1..S6, reliability 0.6)、`source_health`(source_id, ok, latency_ms, error)、`gold_provider_runs`(provider, ok, records, error) |
| 标的与行情 | `instruments`(symbol, asset_class, contract_size, tick_value, margin_pct, domestic_proxy_of, extra JSON)、`market_bars`(unique instrument+timeframe+ts；OHLCV/open_interest/delay_sec)、`quotes`(unique instrument+ts；price/prev_close/change_pct/bid/ask) |
| 宏观 | `macro_series`(code unique, unit, freq, country)、`macro_obs`(unique series+ts+revision；value/fetched_at) |
| 内容/知识 | `documents`(url_hash unique, body_status)、`document_bodies`、`document_spans`(start/end/quote/claim_id)、`claims`(type fact/data/forecast/opinion/rumor, subject/predicate/object JSON, confidence 0.5)、`entities`、`events`、`event_instruments` |
| 研判 | `theses`(asset_ids, direction, prior, posterior, horizon_days, status, invalidation)、`thesis_evidence`(weight 0.5)、`scenarios`(probability/triggers/impacts)、`graph_edges`(src/dst, mechanism, sign, lag_days, strength, regime, confidence) |
| 决策 | `signals`(breakout/momentum/reversion/spread/event)、`trade_plans`(entry_low/high, stop, targets JSON, size, risk_pct, time_stop_days, status)、`plan_details`、`plan_checks`、`predictions`(probability, horizon, brier)、`outcomes`(prediction_id, actual, score) |
| 内容产出 | `briefs`(kind, unique kind+trade_date, markdown, meta)、`journal_entries`、`alerts` |
| 运营 | `jobs`(name unique, cron, enabled, last_status)、`job_runs`(job_name, status, detail)、`llm_calls`(task/model/tokens/cost/cached)、`audit_log`、`data_checks`(kind reconcile/freshness/coverage/continuity, dataset, expected/actual/deviation, passed)、`analytics_results`(kind+subject+asof unique, payload JSON, code_version) |
| 黄金/持仓/自选 | `gold_metrics`(unique code+as_of)、`member_positions`、`position_snapshots`、`watchlist`(sort_order)、`economic_events`(unique ts+name, importance 1-3) |

实测行数（只读 `count(*)`，2026-11-17）：

| 表 | 行数 | 表 | 行数 |
|---|---|---|---|
| market_bars | 84,155 | quotes | 22,834 |
| macro_obs | 25,672 | economic_events | 2,593 |
| claims | 3,996 | documents | 290 |
| gold_metrics | 12,483 | member_positions | 1,560 |
| job_runs | 4,360 | analytics_results | 69 |
| data_checks | 111 | signals | 50 |
| trade_plans | 6 | predictions | 6 |
| **outcomes** | **0** | theses / scenarios | 8 / 16 |
| briefs | 11 | alerts | 393 |
| watchlist | 10 | instruments / macro_series | 35 / 22 |
| **graph_edges** | **0** | | |

**缺失/不足的表**（V2.0 必补）：
1. **分析运行/步骤溯源**：`analytics_results` 只有 `kind+subject+asof` 最新快照（unique），没有 `analytics_runs`（耗时、输入行数、异常）与 `analytics_steps`（算法/参数/中间产物）；`code_version` 只是 `m3.0`/`m4.0` 字符串。
2. **预测对账明细**：`outcomes` 0 行；没有逐笔结算记录（用哪根 bar、命中/未命中原因）与 calibration 持久化。
3. **国家/指标元数据**：没有 `countries`/`indicators` 表；宏观元数据散在 `pipeline.MACRO_SERIES_META`（`pipeline.py:112-135`），黄金指标是 Python dict（`gold/registry.py:29-59`）。
4. **参与者/立场卡**：无 players/stances/statements 表（政策三角无落点）。
5. **传导图机制模板**：`graph_edges` 有结构无数据，缺 mechanism 模板表与估计版本。
6. **情景树/贝叶斯**：`scenarios` 只有 probability/triggers/impacts，无节点依赖、先验/似然、更新日志。
7. **事件研究库**：`economic_events` 只是日历；历史事件研究是硬编码 14 条（`analytics/events.py`），无分类法与样本表。
8. **数据修订/回放**：`macro_obs` 有 `revision`（部分实现），行情无 revision/原始载荷快照表；仅 `source_health` 与 `documents.raw_path`。
9. **任务依赖**：`jobs` 无 depends_on/timeout 字段，顺序靠 cron 时间。

---

## 5. 现有分析算法逐个说明

> 每条给出：输入 → 输出 / 公式或权重 → 局限；均为读代码核实。

- **`analytics/regime.py`（四象限，部分实现）** 输入：14 标的日线 `closes` + `macro`；输出按国家 `{growth, inflation, liquidity, quadrant, confidence, method}`。算法：250 日 z-score（`:14-23`）→ `_score = 50 + 50*tanh(z/1.5)`（`:26-27`）→ 阈值 ±0.15 分五态（`:30-39`）。US：增长 `0.6*(US10Y-US2Y)+0.4*铜金比 60d`、通胀 `0.6*US10Y_BE+0.4*SC 60d`、流动性 `-US10Y_REAL`、confidence 0.4；CN：增长 `0.4*CU+0.3*I+0.3*000300`、通胀 `0.5*SC+0.3*M+0.2*P`、流动性 `000300 20d`、confidence 0.35。局限：全部为**市场隐含**代理，注释承认官方增长/通胀未接入（BLS 403），只有短周期一层。
- **`analytics/wind.py`（风险风向）** 输入 7 个风险资产（CU/AL/ZN/NI/SC/000300/603993）；`breadth`=站上 MA60 比例、`momentum`=20d 均值经 `tanh(mom/0.05)`、`rate`=`-tanh(ΔUS10Y_20d/0.5)`；`score = 100*(0.4*(2*breadth-1)+0.35*momentum+0.25*rate)` clamp ±100，±25 判进攻/避险。局限：等权、固定权重、无波动率/相关性调整。
- **`analytics/attribution.py`（因子归因）** 输入资产收益 + 3 驱动（`real_yield_chg`/`breakeven_chg`/`curve_chg`，需 4 条序列齐全才构造，`:49-52`）；带截距 OLS（`np.linalg.lstsq`）、窗口 120 日、近 20 日贡献，输出 betas/contributions_pct/actual_pct/residual_pct/r2，样本 <40 返回 `{}`。局限：线性平稳假设、多重共线性未处理、残差常大。
- **`analytics/correlation.py`** 120 日日收益相关，仅保留有效样本 ≥60 的列（≥3 列），输出 symbols/matrix/top_pairs(10)/avg_abs_corr。
- **`analytics/analogs.py`（历史类比）** 周频（W-FRI）状态向量 US10Y/US10Y_REAL/US10Y_BE/slope/4 周动量等，macro ffill 后 `dropna().tail(320)` 周；z-score 欧氏距离取 5 近邻、`min_gap_days=180`，输出 4/12 周（20d/60d）前瞻收益。局限：样本约 6 年、周频、等权距离、无显著性检验。
- **`analytics/leadlag.py`（领先滞后）** 两两比较同日与 ±1..5 日 shift 相关取绝对值最大者，`min_obs=120`/`top_n=12`，输出 same_day_corr/best_corr/lag_days/interpretation。局限：相关非因果，未做 Granger/转移熵（`docs/07-开发进度.md:1053` 亦承认）。
- **`analytics/calendar_study.py`（日历事件研究）** 6 资产 × 1/3/5 日前瞻收益；中文关键词分就业/通胀/增长/景气/消费/工业/贸易，按 (country, category) 统计均值/上涨概率/样本数，最多 400 事件，事件对齐「事件日之后首个交易日」。局限：关键词硬编码、未区分预期差。
- **`analytics/drivers.py`（驱动排序）** 规则打分：风向 |score|≥10、US10Y 20 日变动≥0.1pp、DXY 20 日 |chg|≥1%、会员持仓 `net_ratio` 与 20 日趋势背离（|ratio|≥0.05 且 |trend|≥1%）、近 7 天高影响事件数/5、regime 置信度≥0.35；按 strength 降序取前 6。局限：阈值人工拍定、无学习/校准。
- **`analytics/indicators.py`** 需 ≥30 点；输出 1/5/20/60 日变动、MA20/60 与偏离度、年化波动 `std20*sqrt(252)*100`、252 日分位、trend、OI 5 日变化。
- **`analytics/events.py`** 硬编码 14 条历史事件（2019-07-31…2025-04-02）、5 资产 × 20/60 日，按类型聚合 mean/median/hit_rate/n。局限：样本与分类写死，不可增量扩展。
- **`analytics/runner.py`（编排）** 载入→对齐→逐标的指标→regime→wind→correlation→attribution（6 标的）→analogs→leadlag→event_study→calendar_study（近 365 天 importance≥3）；`_save` 对每个 `kind+subject` **先 delete 再 insert** 只留最新（`runner.py:35-44`），`code_version="m3.0"`，数据空则 `RuntimeError`。
- **`decision/scoring.py`（预测结算）** 遍历 open 预测→关联 `TradePlan`→取 made_at 后 `horizon+1` 根日线；先判止损（outcome 0）再判 T1（outcome 1），否则到期收盘符号；`brier=(p-outcome)^2`，写 `Outcome` 并置 resolved，无 plan/bar 不足则 skipped。
- **`decision/signals.py`** 13 标的（12 期货 + 603993）、需 ≥80 点、ATR-like=14 日 |close diff| 均值；突破（破 20 日区间，strength=幅度/ATR 上限 1）、动量（60d>5% 且 >MA20，反向 <-5% 且 <MA20，strength=|ret60|/0.15）、均值回归（`z=(price-MA20)/std20`，|z|>2，strength=超出部分/2+0.3）。局限：无参数寻优、未区分品种波动率与交易时段。
- **`decision/backtest.py`** 3 规则、forward 10 日、成本 0.06%（往返）、2024-01-01 切 train/test；输出 count/hit_rate/avg_return/median/avg_win/avg_loss/profit_factor + by_symbol。局限：无滑点/流动性模型、多空不对称未处理、样本内参数。
- **`decision/plans.py`（仓位）** `size = equity*risk_pct/100/(|price-stop|*multiplier)`；止损 ±1.5ATR、T1=2ATR、T2=3ATR、entry ±0.3%，手数 floor，`time_stop_days=3`；5 条校验：单笔风险≤0.3%、止损距离≤5%、手数≥1、保证金≤50%权益、手续费≤风险额 20%。
- **`decision/runner.py`（决策编排）** 清理当日 Signal/draft 计划/同日回测后重建；取 strength 前 6 且≥0.5 生成计划 + 5 条检查 + `Prediction(probability=0.55, horizon=time_stop_days)`；回测写 `AnalyticsResult(kind="signal_backtest", code_version="m4.0")`。
- **`gold/scoring.py`（黄金综合分，V1.3 最完整的算法块）** 22 指标（`gold/registry.py:29-83`），权重合计 `WEIGHT_TOTAL=139`（`scoring.py:14`）；归一 `pct_change_1m`(30d)/`pct_change_3m`(90d)/`percentile`(近 104 期、≥8 期)/`level`(value/scale)/`level_and_change`（实际利率：水平 6 : 30 日变动 4）；`score = Σ(w*factor)/Σw*100`，coverage=已获取权重/139（缺失不进分母）；标签 ±18/±50、因子信号 ±0.15；特例：中国黄金储备用「储备变动% − 金价涨幅%」近似净购金（`:125-132`）、`GOLD_MOM_20D_PCT` 用 AU 日线 20 日动量覆盖样本不足（`:162-183`）；手工指标（weight 0）：`BIS_GOLD_SWAP_USD`、`BIS_GOLD_STORAGE_USD`。局限：权重人工设定、未校准、`level` 的 scale 靠经验、无置信区间与失效条件。

---

## 6. 调度与任务

注册分三处：`init_db.py:92-118` 的 `JOBS_DEFAULT`（25 条，含 `brief_manual` 手工项）；`platform/scheduler.py` 的 24 个业务 `add_job`（`:80-330`）+ heartbeat（`:343`）+ 7 个启动补跑 `DateTrigger`（`:106,142,202,217,224,289,305`，55s/25s/240s/300s/330s/45s/25s），共 32 次注册、24 个不同任务 id。`GET /api/system/jobs` 读 `jobs` 表。

| 任务 | 触发 | 产出/链路 |
|---|---|---|
| heartbeat | 每 60s | 只刷新 `jobs.last_status` |
| collect_quotes | 每 60s（启动 +3s） | quotes（新浪/东财/腾讯链） |
| collect_news | 每 3min | documents 列表 |
| collect_news_slow | 08:15（启动 +55s 补一次） | 官方慢源 |
| collect_rates | 每 1h（启动 +15s） | 美/日/德/法国债、SOFR/EFFR |
| collect_calendar | 每 6h | economic_events |
| collect_positions | 15:45（启动 +25s） | member_positions |
| collect_daily_bars | 15:40 / 06:30（启动 +25s） | market_bars |
| backfill_history | 周日 09:00 | 补缺口/修脏点（先于周报） |
| collect_gold | 16:40（启动 +45s） | gold_metrics + gold_provider_runs |
| collect_bodies | 每 10min | document_bodies |
| extract_claims | 每 15min | claims（规则版） |
| extract_claims_llm | 每 20min（有 Key 才注册，`scheduler.py:177-185`） | claims（LLM 版） |
| extract_events | 每 30min | events/event_instruments |
| check_data_quality | 15:50 | data_checks（reconcile/freshness/coverage/continuity） |
| analyze | 16:10（启动 +240s） | analytics_results |
| decide | 16:30（启动 +300s） | signals/plans/predictions |
| theses | 16:35（启动 +330s） | theses/scenarios |
| score_predictions | 17:00 | outcomes |
| scan_alerts | 每 5min | alerts |
| brief_premarket | 07:30 | briefs |
| brief_postmarket | 21:00 | briefs |
| weekly_review | 周日 10:00 | briefs |
| monthly_review | 每月 1 日 10:00 | briefs |

- 依赖顺序**只靠时间表**：15:40 日线 → 15:45 持仓 → 15:50 质检 → 16:10 分析 → 16:30 决策 → 16:35 论点 → 17:00 结算 → 21:00 盘后简报；没有 DAG、没有上游成功校验。
- 失败行为：`run_job` 捕获异常写 `job_runs.status="error"` + `last_error` 后继续（`jobs/runner.py:96-140`）；`_collector` 再兜一层 try（`scheduler.py:53-72`）；**不重试、不降级、不阻断下游**。
- 并发：所有任务串行在 `write_lock` 内（SQLite 单写者）。
- 僵尸任务：启动与每次 run 前把 `running` 超 90 分钟（或 `all_jobs=True` 时全部）改为 `interrupted`（`jobs/runner.py:42`, `:72-93`）。
- `env == "test"` 时**不注册业务任务**，只跑 heartbeat（`scheduler.py:351-352`）；调度器快照给 `/api/system/health`（`:363-366`）。

---

## 7. 数据采集与降级

**HTTP 层**（`ingest/http.py`）
- 统一 UA、30s 超时、每 host 最小间隔（默认 0.35s）、3 次重试、429/5xx 重试（`:20`, `:124-167`）；强制 IPv4（`local_address="0.0.0.0"`，`:56`）。
- 东财 push2 边缘在 TLS 后断连时自动切系统 `curl`（Schannel）并把 host 记入 `CURL_ONLY_HOSTS`，下次直接走 curl（`:26`, `:80-122`）。

**来源分级**
- `sources` 表存 `tier` 与 `reliability`：S1 官方 0.95（Treasury/JGB/ECB/SHFE/CZCE/NYFed）、S2 市场 0.8–0.9（新浪/东财/腾讯/Frankfurter）（`pipeline.py:68-97`）。
- 每次抓取写 `source_health`（ok/latency_ms/error），`/api/system/sources` 展示。

**报价降级链**（`pipeline.py:206-365`）
- 新浪国内期货/外盘/FX → 东财 A 股/指数/DXY/USDCNH（个别标的先走腾讯，`TENCENT_QUOTE_PREFERRED`）→ 腾讯兜底 → FX 篮子合成 DXY 代理。
- 单组失败只记错不拖垮整轮；未变化报价按时间窗去重落库（`store.upsert_quotes`）；快照保留 14 天（`:358-361`）。

**日线降级链**（`pipeline.py:368-534`）
- 国内期货/外盘走新浪连续合约；美股指数优先腾讯原始 K 线（避免东财盘中残根）；DXY/USDCNH 优先新浪外汇日线；A 股/恒生东财优先、腾讯前复权兜底。
- 入库上限 `DAILY_BAR_LIMIT=3000`（`:148`）。

**脏数据护栏**
- `_guard_tail_bar`：末根偏离前收 >25%（`MAX_TAIL_MOVE_PCT`）先尝试单根接口订正，失败则丢弃该根（宁可缺口，`:154-198`）。
- `bars_quality.py`：识别休市伪日线（整根 OHLC 复制、开高相同+成交量≈相同、单点+零量+收盘 5bp 内不动），对「天然单点序列」（新浪外汇日线）整体豁免（`:38-45`, `:65-116`）。

**回补与连续性**
- `ingest/backfill.py` 周日 09:00 跑 `fill_bar_gaps`（每标的 ≤60 天）+`repair_outliers`+`clean_holiday_stubs`。
- `continuity.py` 用「同业共识交易日」判缺口（不预置交易日历），输出 `Finding` 并写 `data_checks(kind="continuity")`。

**数据质检**（`check_data_quality`，`pipeline.py:995-1244`）
- CZCE 官方日行情对账（SR/CF，偏差 ≤0.2%）。
- 日线新鲜度 5 天（逐标的，避免单序列停更被全表最大值掩盖）；宏观按频率（日 5/周 10/月 70/季 150 天）。
- 行情快照 1 天、新闻 3 天；启用标的日线覆盖、宏观序列覆盖。
- 连续性检查；全部落 `data_checks`，由 `/api/system/data-quality` 取最近窗口。

**文档与知识**
- `documents` 保存 url_hash/sha256/raw_path（快照已落盘）、`body_status` 状态机（pending→extracted→stored/skipped）、`document_bodies` 正文。
- 规则版断言 confidence 固定 0.45（`knowledge/extract.py:125`）；LLM 版需 Key。
- 5 个官方 RSS + 1 个慢源（`pipeline.py:99-110`）。

**缺口**
- 无采集重试预算/熔断策略；多源交叉校验仅 CZCE 2 个品种；`data_checks` 仅 111 行（每天一轮），无法回溯质检趋势。

---

## 8. 前端

路由 9 个页面 + 兜底重定向（`frontend/src/router/index.ts:3-62`）；分组：工作台（总览/市场）、研究分析（利率/分析/信号/黄金/论点）、内容（简报）、系统（状态）。

| 路由 | 页面 | 主要职责/组件 | 文件行数 |
|---|---|---|---|
| `/` | OverviewView | `GET /api/overview` 单请求：自选卡+sparkline、宏观利率、最新简报、告警、14 天日历、任务与健康 | 597 |
| `/market` | MarketView | snapshot 分组表 + 持仓/品种/会员持仓弹窗 | 686 |
| `/rates` | RatesView | `macro/latest`+`macro/series`，按 MACRO_GROUPS 分组 | 563 |
| `/analysis` | AnalysisView | `analytics/overview`+`gold/overview`，regime/风/归因/相关/类比/领先滞后卡片 | 1214 |
| `/signals` | SignalsView | `decisions/summary`+`review`，信号/计划/回测/Brier | 824 |
| `/gold` | GoldView | `gold/overview`，22 指标卡、coverage、分类、序列图（唯一 ECharts 页面） | 1854 |
| `/theses` | ThesesView | 论点+证据+情景，叠加事件/新闻/日历上下文 | 929 |
| `/briefs` | BriefsView | 简报列表/最新/打印/Markdown 下载、日志 | 1020 |
| `/system` | SystemView | health/jobs/sources/data-quality/acceptance | 370 |

**设计系统**
- 纯 CSS 变量 tokens（`styles/app.css:9-41` 深色、`:44-68` 浅色、`:862+` sepia）；Tailwind 只做 token 映射（`tailwind.config.cjs:6-29`）。
- 主题 dark/light/sepia/auto（`stores/prefs.ts:4-6,47-69`）；偏好写 localStorage（`prefs.ts:8-10`）。
- **红涨绿跌可切换**：`--up:#F0544F`、`--down:#2FBF71`（深色），浅色 `#D64541/#1B8A55`；`html[data-updown="green"]` 交换 `--up-color/--down-color`（`app.css:22-29,70-74`）。
- 密度 standard/compact（`app.css:120-125` + `AppShell.vue:85` 给 body 加 `is-compact`）。
- 排版：13px、`tabular-nums`、行高变量 `--row-h`、侧栏 232px、顶栏 56px。

**ECharts**
- `vue-echarts` + 按需 `use([...])`：Line/Bar/Candlestick/Treemap、Grid/Tooltip/Legend/DataZoom/MarkLine/VisualMap/Title（`components/charts/EChart.vue:11-38`）。
- 构建单独拆包（`vite.config.ts:22-29`），产物 `web/assets/echarts-*.js` 621KB。

**API 客户端与状态**
- 自写 fetch（无 axios）：同源、15s 超时、`ApiError`、非 JSON 回文本（`api/client.ts:33-70`）；端点集中在 `api/endpoints.ts`(182)，类型 `api/types.ts`(690)。
- 轮询 `composables/usePolling.ts`(92)，默认 15s（`prefs.ts:56`）。
- Pinia stores：prefs/toast/evidence/health/alerts/history。
- `components/domain/`：CommandPalette（Ctrl+K）、SettingsDrawer、EvidenceDrawer、AlertsDrawer、HistoryModal、WatchlistManager（拖拽排序）。
- `layouts/`：AppShell/Sidebar/Topbar。

**构建产物（web/）**
- Vite 产物：`index.html` 2KB + assets（echarts 621KB、vendor 114KB、BriefsView 155KB、OverviewView 63KB 等）。
- `web-legacy/index.html` 87KB 保留为 `/legacy` 回退（`main.py:81-122`）。

**mockup 与新前端差异**
- `docs/design/mockup/index.html` 172KB 单页静态原型：内联 SVG 图表、URL 参数切 overview/market/brief/tokens 四个视图、示例数据；README 记录 9 节设计规范与已知限制。
- 新前端：9 路由 SPA + ECharts + Pinia + Tailwind/CSS tokens + 真实 API + localStorage 偏好；视觉 token 基本沿用（`app.css:1` 注释「由 docs/design/mockup 原型提炼」）。
- 主要差异：页面数量（4→9）、图表库（内联 SVG→ECharts）、数据源（示例→API）、新增命令面板/证据抽屉/历史弹窗；mockup 的 `tokens` 视图在新前端没有对应路由（由设置抽屉承担）。

---

## 9. 测试与门禁

**pytest**：40 个 `test_*.py` + `tests/conftest.py`（数据目录指向 `data/test/m0`，`EPIC_ENV=test`，`conftest.py:5-9`），约 208 个测试函数。

- 纯函数/解析器：`test_m2`(HTML/CZCE/claim)、`test_m3`(analytics)、`test_m4`(signals/sizing/plans/backtest)、`test_parsers`(录制的上游样本)、`test_bars_quality`(14 例休市伪日线)、`test_continuity`(21 例共识交易日)、`test_macro_freq`、`test_m8/m9/m19/m20`(JGB/ECB/CN 收益率/日历/SOFR/新浪全球)。
- 里程碑：`test_m5`(告警/合约乘数)、`test_m6`(LLM fake/通知/复盘/渲染)、`test_m7`(周报/日志/验收/DXY)、`test_m10`~`test_m21`（日历告警、论点、月报、会员持仓、官方源、事件抽取、DCE 持仓、驱动排序、自选、美股日线、简报主线）。
- 降级与护栏：`test_degraded`、`test_provider_fallbacks`、`test_http_curl_fallback`、`test_pipeline_guard`(10 例末根护栏/脏点订正)、`test_quote_cadence`、`test_quote_preferred`、`test_writelock`、`test_backfill`(5 例)。
- 契约/运维：`test_api_contracts`(10)、`test_api_smoke`、`test_smoke`、`test_devops`(僵尸任务自愈/任务注册/备份保留)、`test_frontend_build`(6 例)、`test_release`(版本单一来源+lint 门禁+CI 存在)、`test_gold`(13 例)。

**静态门禁 `scripts/lint.py`**（292 行，9 项，`CHECKS` 在 `:251-261`）：
- `syntax`：`compile()` 全后端 py。
- `ast`：裸 except、可变默认值、naive datetime、后端 print。
- `imports`：启发式未使用 import。
- `encoding`：UTF-8 与 U+FFFD。
- `frontend`：依赖齐全、必要文件、禁止外部 CDN、`web/` 产物校验。
- `powershell`：BOM + 语法。
- `docs`：markdown 相对链接。
- `version`：pyproject vs `app.__version__`（`:184-202`）。
- `env`：`.env.example` 关键键。

**CI**（`.github/workflows/ci.yml`）：
- ubuntu-latest × Python 3.11/3.12；`npm ci`→`npm run build`→`python scripts/lint.py`→`pytest -q --maxfail=1`；失败也上传 `data/test/`。
- 另有 `package` job 只做 `import app` 冒烟（`:66-80`）。

**验收**：
- `GET /api/system/acceptance` 14 条 DoD 阈值（`api/system.py:178`）。
- 脚本：`scripts/check_acceptance.ps1`、`selfcheck.ps1`、`ci.ps1`、`build.ps1`、`dev.ps1`、`start/stop/restart/setup/backup/restore/maintain.ps1`（共 14 个）。

**缺口**：
- 无覆盖率统计；无前端单测/E2E（`vue-tsc --noEmit` 只在 build 时跑）。
- CI 只跑 Linux：Windows 的 curl/Schannel 兜底、计划任务、PowerShell 运行行为未覆盖。
- 无性能/长稳测试；调度器本身无集成测试。

---

## 10. 设计与实现的差距

对照 `docs/03-分析框架与模型设计.md` 的 EPIC-C（§2 周期引擎、§3 政策、§5 传导图、§6 参与者、§8 类比、§9 贝叶斯）：

| EPIC-C 要素 | 状态 | 证据 |
|---|---|---|
| 五层周期嵌套（长债/短债/库存/信用/政治） | **仅文档** | `docs/03:59-67` 定义五层；代码只有短周期四象限代理 `analytics/regime.py`；backend 无 debt/credit/inventory/political 序列或打分（`grep debt` 零命中） |
| 四象限 + 过渡态 | **部分实现** | `regime.py:30-39` 阈值 ±0.15 输出五态；仅 US/CN，输入是市场代理（铜金比/盈亏平衡/SC 动量），官方增长通胀未接入（注释 BLS 403），confidence 固定 0.4/0.35 |
| 政策三角（沃什—贝森特—特朗普）/ 立场卡 / 美联储反应函数 | **仅文档** | `docs/03:45-56`, `:121-162`；无 players/stances/statements 表，`grep "Player"` 零命中；`entities` 只是抽取别名表（`knowledge/extract.py:13-22`） |
| 债务可持续性 / 化债模式 | **仅文档** | `docs/03:89-105`；无债务/GDP、r-g、利息支出数据与模型 |
| 传导图（机制/符号/滞后/置信度） | **仅文档 + 空表** | `graph_edges` 表已建（`models/core.py:363`）但 0 行；`leadlag.py` 只是 ±5 日两两相关，不是 Granger/转移熵；`docs/07:1053` 自述未实现 |
| 参与者模型（九类画像/影响力） | **部分实现** | 无参与者画像；有 `member_positions` 1,560 行（会员持仓）与 `drivers.py` 净持仓背离规则；黄金用 COT 做市商/管理基金指标（`gold/registry.py:53-56`） |
| 情景树 / 贝叶斯更新 | **部分实现** | `scenarios` 16 行但概率是模板写死 0.55/0.45 或 0.5/0.5（`decision/theses.py:87-100`, `:128-141`）；`posterior = min(0.9, strength*0.7 + evidence_weight*0.3)`（`:66`），无似然/先验更新、无概率校准 |
| 历史类比库（事件分类法 + ≥30 事件） | **部分实现** | `analogs.py` 周频状态向量欧氏近邻（k=5、180 天间隔、320 周）；`analytics/events.py` 硬编码 14 条事件（文档要求 ≥30），无分类法/事件样本表 |
| 统一资产定价分解（§4） | **部分实现** | `attribution.py` 对 6 标的做 3 驱动 OLS；黄金有 22 因子加权；其余资产无结构化定价模型 |
| 证据/断言/防幻觉（§9） | **部分实现** | `claims` 3,996 行 + `document_spans` 定位 + `sources.tier`；但 confidence 固定 0.45/0.5，无事实校验/交叉验证，LLM 链路未用真实 Key 跑过（`docs/07:938`） |
| 交易闭环（EPIC-T，§10） | **部分实现** | signals/plans/backtest/predictions 有实现；`outcomes` 0 行、`predictions` 6 行 → 结算闭环从未真正跑出结果；`trade_plans` 仅 6 条 draft |
| 每日 SOP（§11） | **部分实现** | 盘前/盘后/周/月简报与日志有；缺事件前 T-7/T-1「预期 vs 意外」清单 |

**10 条技术债/风险**

1. **分析结果覆盖式写入**：`runner._save` 先 delete 再 insert 只留最新（`analytics/runner.py:35-44`），69 行快照无历史 → 无法回测分析结论、无法审计算法漂移。
2. **版本漂移**：后端/pyproject 1.3.0 vs 前端 `package.json` 1.1.0；`lint.py:184-202` 只校验 pyproject/README/docs10，不查前端版本。
3. **无真实迁移框架**：`alembic` 在依赖里但无迁移目录，schema 演进靠 `platform/db.py:95-110` 手写轻迁移 + `create_all`，改列/删列无路径。
4. **调度无 DAG/门禁**：顺序靠壁钟、失败仅记录，下游照跑旧数据（`jobs/runner.py:117-140`）；bootstrap 任务散落 7 个 DateTrigger，易与 cron 重复。
5. **全任务串行写锁**：`_collector` 内所有任务（含分析/决策/简报）都进 `write_lock`（`scheduler.py:65-72`），长任务挤占采集，SQLite 单写者被放大成全局吞吐瓶颈。
6. **大量硬编码配置**：`MACRO_SERIES_META`（`pipeline.py:112-135`）、`NEWS_FEEDS`、`analytics/events.py` 14 事件、`calendar_study.KEYWORDS`、`decision/theses.KEYWORDS/EVENT_DIRECTION`、前端 `utils/market.ts` 分类；改口径必须改代码。
7. **JSON 列无 schema**：`asset_ids/impacts/params/targets/evidence_claim_ids` 无校验、无外键，跨表 join 靠应用层；`graph_edges` 建了空表。
8. **前端缺测试且单文件过大**：无 vitest/Playwright；`GoldView.vue` 1854、`AnalysisView.vue` 1214、`BriefsView.vue` 1020、`types.ts` 690。
9. **数据保留期口径冲突**：`collect_quotes` 硬编码删 14 天前快照（`pipeline.py:358-361`），而配置 `quotes_retention_days` 默认 30（`platform/config.py`），两处不一致。
10. **LLM 链路不可验证 + 单文件过重**：无真实 Key，`llm_calls` 与预算守卫就绪但未跑通；`extract_claims_llm` 无 Key 时不注册（`scheduler.py:177-185`）；`pipeline.py` 1244 行、`gold/providers.py` 750 行、`narrative/brief.py` 433 行职责过重。

---

## 11. 对 V2.0 的 10 条工程建议

1. **先补溯源，再上新模型**：新建 `analytics_runs`（run_id、kind、asof、耗时、输入行数、状态、error）与 `analytics_steps`（run_id、算法、参数 JSON、中间产物），`analytics_results` 加 `run_id` 并**改为追加**（保留历史）；`code_version` 换成构建号。这是周期/情景版本对比的地基。
2. **建指标/国家元数据表**：`indicators`（code/名称/单位/频率/方向/权重/来源/发布滞后/口径/是否手工）+ `countries`，把 `gold/registry.py`、`MACRO_SERIES_META`、`instrument_units.py` 迁进去，前端与评分都从 DB 读；一次迁移解决技术债 6。
3. **政策三角用现有知识流水线落地**：新建 `players`/`stance_cards`/`statements`（复用 `documents`/`claims`/`entities`，不必新采集）；先做 10 个对象的立场卡 + 言行差规则，再谈反应函数参数估计。
4. **周期引擎分两步**：先把五层各做「一层一个打分卡」（数据可得就给分、缺就给 `null` + 原因），复用 `regime.py` 的 z-score/象限框架并扩到官方 CPI/PMI/失业率/信用脉冲（`macro_series` 现有 22 条，需扩采集，不动 analytics 主体）；HMM/马尔可夫切换留到有 2–3 年一致序列后。
5. **激活传导图**：用 `graph_edges` 存 20–30 条人工机制模板（src/dst/mechanism/sign/lag），再用 `leadlag`+`attribution` 的估计回填 lag/strength/confidence，形成「模板 vs 实测」对照；不要先上 Granger 全图搜索（样本不足、易过拟合）。
6. **情景/贝叶斯最小闭环**：`scenarios` 加 `prior/likelihood/posterior/updated_at` 与节点依赖；每次证据（claim/event）到达时按固定似然表更新一次，并把概率写入 `predictions` 参与 Brier 校核——没有第 6 条，先别上没校准的情景概率。
7. **修预测对账闭环**：`predictions` 6 / `outcomes` 0 说明结算链从未跑通；先修 `decision/scoring.py` 的触发与 Signals 页呈现（`review` 已有），再加每周对账任务与 calibration 持久化表；这是 V2 可信度的门票。
8. **数据层分治而非换库**：SQLite 继续做 OLTP（WAL 已开），月度/周度分析快照与回测用 DuckDB（依赖已在 `pyproject.toml:15`，目前未用）做只读计算；若要换 PG，先等 `analytics_runs` 迁移完成，避免一次双改。
9. **前端重构有边界**：抽 `packages/design-system`（tokens + 表格/卡片/Drawer），拆 `GoldView`/`AnalysisView`/`BriefsView` 为子组件，加 vitest；新增「周期定位」「情景树」两个路由，复用现有卡片与 `EChart` 封装，不重做布局。
10. **运维补齐**：`jobs` 加 `depends_on` + `timeout` 与失败门禁（analyze 前校验质检通过）、把 `JOBS_DEFAULT` 与 scheduler 注册统一为单一来源、加受控的 `POST /api/system/jobs/{name}/run`（带写锁）。
    **先别动**：`ingest/providers` 契约、`bars_quality`/`continuity` 判定规则、`sources` 分级与 `source_health` 结构、`gold/scoring` 的 coverage 机制——这几块是已验证资产，V2 应在其上加层而不是改写。

---

审计结论：V1.3 已经是**能自采集、自质检、自分析、自出简报**的单机闭环，强项在采集降级/数据质量/黄金因子监控；EPIC-C 的「周期嵌套、政策三角、传导图、参与者、贝叶斯情景」基本停在 `docs/03`，代码只有四象限代理、简单类比与模板情景。V2.0 的重点应是**元数据 + 溯源 + 闭环校核**三件基础设施，而不是继续加指标。
