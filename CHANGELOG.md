# 变更记录（CHANGELOG）

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，版本号使用 [语义化版本](https://semver.org/lang/zh-CN/) 的预发布形式（`1.0.0-rc1`）。

> 运行时版本以 `backend/app/__init__.py` 为唯一来源，`pyproject.toml` 与 `/api/system/health` 必须一致（`tests/test_release.py` 会校验）。

## [Unreleased]

### 计划中（V1.4 候选）

- LLM 全链路实跑（断言/事件/简报编辑/论点证据）——需 `DEEPSEEK_API_KEY`。
- 港股/A 股扩展、组合级风控、PDF 服务端渲染、移动端单独设计。
- 大商所官方持仓、LME 日线、美国财政部新闻源替代方案。
- 黄金监控：WGC 央行购金官方下载（Cloudflare）绕行、CME COMEX 库存镜像、SGE 库存数据源、BIS 报告解析。

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
