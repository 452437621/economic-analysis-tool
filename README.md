# EPIC · 个人市场分析工具

> **Economic Positioning, Intelligence & Cycles** —— 本地运行、以证据为中心的个人宏观—市场—交易决策工作台。
>
> 状态：**V1.1.0 — 前端已重构为 Vue 3 + Vite（2026-11-14）**；M6 试运行待真实使用与校准。35 标的、6.5 万根日线、2.2 万条宏观观测、2,500+ 财经日历、13 品种会员持仓（**Top20 多空明细**）、267 篇官方新闻/3,689 条断言；**8 个路由页面**（总览 / 市场 / 利率 / 分析 / 交易信号 / 论点与证据 / 简报与日志 / 系统）；**深色终端风 + 浅色/护眼/跟随系统**、红涨绿跌可切；**证据抽屉、ECharts 历史走势、Ctrl+K 命令面板、自选拖拽排序、打印/导出**；后端 API 契约不变；旧版看板保留在 `/legacy`；LLM 待 Key。

![V1.1 总览](docs/assets/vue/vue-overview.png)

---

## 快速开始

```powershell
# 1) 初始化（引导 Python 3.12、创建 .venv、安装依赖、建库、写入种子数据、构建前端）
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1

# 2) 启动（后台运行，自动打开浏览器）
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

浏览器打开 **http://127.0.0.1:8765**（Vue 前端）；旧版零构建看板在 **http://127.0.0.1:8765/legacy**。

### 前端开发 / 构建

| 操作 | 命令 | 说明 |
|---|---|---|
| 构建前端 | `.\scripts\build.ps1` | `vue-tsc` + `vite build` → `web/`（FastAPI 直接托管） |
| 前端开发模式 | `.\scripts\dev.ps1` | 后端未跑会先拉起；Vite `:5173`，`/api` 代理到 8765 |
| 类型检查 | `cd frontend; npm.cmd run typecheck` | vue-tsc |
| 依赖安装 | `cd frontend; npm.cmd install` | registry 已固定为 npmmirror（`frontend/.npmrc`） |

> 本机 `npm.ps1` 被执行策略拦截，请使用 `npm.cmd`；首次构建前如无 `frontend/node_modules`，`build.ps1` 会自动安装。

### Windows 一键启动 / 停止

| 操作 | 命令 | 说明 |
|---|---|---|
| 启动 | `.\scripts\start.ps1` | 后台运行，写 `data\run\epic.pid`，就绪后自动打开浏览器 |
| 停止 | `.\scripts\stop.ps1` | 停止并释放端口，清理 PID 文件 |
| 重启 | `.\scripts\restart.ps1` | 停止（若在运行）后重新启动 |
| 前台运行 | `.\scripts\start.ps1 -Foreground` | 占用当前终端，Ctrl+C 停止 |
| 调试热重载 | `.\scripts\start.ps1 -Reload` | 改代码自动重载（前台） |
| 换端口 | `.\scripts\start.ps1 -Port 8766` | 也可在 `.env` 设 `EPIC_PORT` |
| 不弹浏览器 | `.\scripts\start.ps1 -NoBrowser` | CI / 远程场景 |
| 强制停止 | `.\scripts\stop.ps1 -Force` | 仅当确认占用端口的是本项目服务 |

脚本行为要点：

- 已在运行时再次 `start` 会直接提示并退出（幂等），不会起第二个实例。
- 端口被其他程序占用时**拒绝启动**并打印占用进程，不会误杀。
- 启动就绪判定 = `/healthz` 200 **且** 端口归属在本次进程树内，避免"假成功"。
- 后台模式通过 WMI 脱离控制台/管道，脚本立即返回；日志写入 `data\logs\server.{out,err}.log`。
- `stop` 优先杀真实服务进程（`server_pid`），失败再兜底 `taskkill /T /F`，并校验是本项目进程。
- 所有 `.ps1` 均为 UTF-8 BOM，兼容 Windows PowerShell 5.1（中文不会乱码/解析失败）。

- 首次启动 30 秒内完成行情/利率/新闻的自动回补与入库（约 4 万根日线、1.8 万条宏观观测、13 品种会员持仓）。
- 手动跑任务：`.\.venv\Scripts\python.exe -m app.jobs.runner --list` / `--job collect_quotes` / `--job brief_manual` / `--all`
- 生成简报：`--job brief_manual`，然后打开看板「简报 → 日报」
- 证据链：点击任意新闻 → 正文弹窗 + 数字断言高亮；也可用 `http://127.0.0.1:8765/?doc=<document_id>` 深链
- 自检：`powershell -ExecutionPolicy Bypass -File .\scripts\selfcheck.ps1`（lint + 测试 + 健康 + 验收 + 质检）
- 验收：`powershell -ExecutionPolicy Bypass -File .\scripts\check_acceptance.ps1`（跑测试 + 14 项 DoD）
- 备份：`.\scripts\backup.ps1` → `data/backup/<时间戳>/`
- 测试：`.\.venv\Scripts\python.exe -m pytest -q`

> 环境说明：系统 Python 为 3.8（过旧）。`setup.ps1` 会用 uv 在工作区内安装 **Python 3.12.16**（`.python/`），不修改系统环境。

---

## 已接入的数据（2026-11-13 实测）

| 数据 | 来源 | 覆盖 |
|---|---|---|
| 国内期货日线 | 新浪 | 黄金/白银/铜/铝/锌/镍/原油/豆粕/铁矿/白糖/棉花/棕榈油，各约 2000 根 |
| 国内期货实时 | 新浪 | 主力连续（价、涨跌、成交、持仓），约 3–60 秒 |
| A 股/指数 | 东方财富 | 沪深 300、洛阳钼业（日线 + 快照） |
| 外盘金银油铜 | 新浪 | 伦敦金银、COMEX 金银、WTI、Brent、LME 铜（约 15 分钟延迟，界面标注） |
| 汇率 | 新浪 | USDCNH/USDJPY/EURUSD/GBPUSD/USDCAD/USDSEK/USDCHF + 自算 DXY 代理 |
| 美元/人民币日线 | 东方财富 | DXY、USDCNH 各 2000 根（2019–2026），DXY 实时报价 |
| 全球股指 | 东方财富 | 标普500、纳指100、道琼斯、恒生（日线约 2000 根 + 实时） |
| LME 金属 | 新浪 | 伦铝/伦锌/伦镍实时（约 15 分钟延迟；无免费日线） |
| 美债利率 | 美国财政部 CSV | 2/5/10/30Y、5/10Y 实际利率、盈亏平衡通胀，近 5 年日频 |
| 日/德国债 | 日本财务省 / 欧洲央行 | JP2Y/10Y/30Y、DE2Y/10Y，近 4 年日频 |
| 中国国债 | 东方财富 | CN2Y/5Y/10Y/30Y、10Y-2Y 利差，近 4 年日频 |
| 财经日历 | 东方财富 | 过去 180 天 + 未来 14 天经济数据（中/美/欧/日等），每 6 小时更新 |
| 会员持仓 | 上期所 / 郑商所 / 新浪 | 铜铝锌镍金银铅锡 + 棉花白糖 + 豆粕棕榈铁矿 Top20 多空持仓（日频） |
| 新闻政策 | 官方 RSS/HTML | 美联储、欧洲央行、日本央行、美国贸易代表办公室（USTR）、美国能源信息署、国家统计局 |
| 事件驱动 | 规则抽取 | 贸易/地缘/货币/供给/数据五类事件，自动关联标的（每 30 分钟） |

> 限制：Yahoo/CFTC/LME 国内直连 403；FRED 超时；BLS 403。对应替代与后续方案见 [05 数据源](docs/05-数据源与接口清单.md)、[07 开发进度](docs/07-开发进度.md)。

---

## 它要解决什么

把「信息汇聚 → 证据固化 → 因果分析 → 情景推演 → 交易计划 → 复盘校准」做成可重复的流水线：

- **信息**：多源汇聚、事件聚类、原文快照与可信度评分；
- **分析**：经济周期定位、资产定价分解、跨市场传导、参与者行为、历史类比；
- **取证**：每条结论可溯源到原文片段、时间与来源，矛盾并列不隐藏；
- **决策**：面向国内期货与 A 股的交易计划（方向、价位、仓位、止损、时间止损、失效条件）；
- **复盘**：预测登记、Brier 校准、信号回测、交易日志与纪律分。

覆盖重点：黄金/白银、原油、铜铝锌镍、内外盘同品种、美元与日元/人民币、美债与中日欧利率、美股与 A 股（有色金属，洛阳钼业为个股模板）。**不覆盖国内独有品种**，V1 不接自动下单。

---

## 文档索引

| 文档 | 内容 |
|---|---|
| [01 需求分析与产品定义](docs/01-需求分析与产品定义.md) | 背景、痛点、范围、功能/非功能需求、验收标准 |
| [02 系统架构设计](docs/02-系统架构设计.md) | 分层架构、数据模型、采集适配、LLM 编排、前端、部署 |
| [03 分析框架与模型设计](docs/03-分析框架与模型设计.md) | 周期/定价/传导/参与者/历史类比/证据可信度/交易系统 |
| [04 实施方案与里程碑](docs/04-实施方案与里程碑.md) | M0–M6 里程碑、WBS、关键路径、测试、风险 |
| [05 数据源与接口清单](docs/05-数据源与接口清单.md) | 免费/付费数据源、实测可用性、降级链、合规 |
| [06 示例输出：黄金分析](docs/06-示例输出-黄金分析.md) | 简报/计划卡/证据链样例 |
| [07 开发进度](docs/07-开发进度.md) | 已完成、问题与修复、下一步 |
| [08 使用手册](docs/08-使用手册.md) | 安装、每日流程、任务表、配置、API、排障、验收 |
| [09 试运行与验收](docs/09-试运行与验收.md) | DoD 对照、M6 计划、安全合规、容量、V1.1 清单 |
| [10 发布说明与验收](docs/10-发布说明与验收.md) | V1.0-rc 功能矩阵、数据限制、验收证据、用户待办 |
| [11 M6 试运行清单](docs/11-M6试运行清单.md) | 每日/每周清单、周度校准表、两周出口标准 |
| [12 异常恢复演练](docs/12-异常恢复演练.md) | 降级场景、恢复手册、演练证据与待补项 |
| [13 交付清单](docs/13-交付清单.md) | 交付内容、验证证据、待用户事项、已知限制 |
| [14 全量核验与缺陷修复](docs/14-全量核验与缺陷修复.md) | 目标完成度核验、代码扫描结论、缺陷修复、DevOps 流程 |
| [15 项目整理与前端改造方案](docs/15-前端改造方案.md) | 扫描结论、文件整理、UI 规范、Vue 技术方案、实施与验收 |
| [CHANGELOG](CHANGELOG.md) | 版本变更记录与发布约定 |

---

## 质量与 DevOps

| 环节 | 命令 / 文件 | 内容 |
|---|---|---|
| 静态检查 | `scripts/lint.py` | 语法、AST 异味、未用导入、编码、Vue 源码结构/外部 CDN/构建产物、PowerShell BOM、文档链接、版本一致性 |
| 前端类型 | `cd frontend; npm.cmd run typecheck` | vue-tsc（构建时也会执行） |
| 构建 | `scripts/build.ps1` | vue-tsc + vite build → `web/`；`ci.ps1` 与 CI 都会先构建 |
| 测试 | `pytest -q` | 105 条：解析器、数据管道、分析、决策、API 冒烟（含写接口与 404）、降级、DevOps、前端源码/产物 |
| 本地门禁 | `scripts/ci.ps1` | 前端构建 → lint → pytest → 运行时 health/acceptance/quality，非 0 即失败 |
| CI | `.github/workflows/ci.yml` | Python 3.11/3.12 矩阵 + Node 22 构建 + 安装导入冒烟 |
| 版本 | `backend/app/__init__.py` | 单一来源，`pyproject.toml` 与 `/api/system/health` 必须一致 |
| 运维 | `backup.ps1` / `restore.ps1` | 完整性校验、保留 14 份、恢复前安全副本 + DryRun |
| 清理 | `scripts/maintain.ps1` | `-DryRun`（默认）/`-Apply`/`-Verify`，清理可再生临时产物 |
| 自愈 | 启动时 `reconcile_stale_runs()` | 中断任务自动标记 `interrupted`，任务开关真正生效 |

## 架构一览

```
浏览器（Vue 3 SPA，web/ 构建产物）
   │ HTTP 127.0.0.1:8765（SPA 回退 + /api + /legacy 旧版）
FastAPI（api / 导出 / 打印）
   │
├─ 采集适配层  sina / eastmoney / treasury / rss（限速、重试、快照、健康）
├─ 知识层      documents / claims / events / theses / evidence（M2）
├─ 分析层      regime / pricing / correlation / analog / sentiment（M3）
├─ 决策层      signals / plans / risk / backtest / predictions（M4）
├─ LLM 编排    DeepSeek（M2）
└─ 存储        SQLite + DuckDB/Parquet + 文件快照
```

技术栈：Python 3.12 + FastAPI + SQLAlchemy + APScheduler + DuckDB；前端 **Vue 3.5 + TypeScript + Vite 6 + Pinia + vue-router + ECharts 5 + Tailwind**（`frontend/`）；数据源见 [05](docs/05-数据源与接口清单.md)。

---

## 里程碑

| 阶段 | 交付 | 状态 |
|---|---|---|
| M0 | 环境、骨架、数据库、调度器、健康检查、看板 | ✅ 完成 |
| M1 | 行情/宏观/新闻接入 + 多源降级 + 数据看板 | ✅ 完成（CZCE 对账、数据质量已补；经济日历待补） |
| M2 | 证据链、可信度、每日简报 v1 | ✅ 基础完成（规则抽取 + 证据链 UI + 简报 v1；LLM 抽取待 Key） |
| M3 | 周期/定价/关联/类比/参与者分析 | ✅ v0 完成（周期/归因/相关性/风向/类比；传导图与持仓待补） |
| M4 | 信号、情景、交易计划、风控、回测、预测账本 | ✅ 完成（v0.2：合约/手数/保证金、成本回测、预测对账、论点/情景管理） |
| M5 | 告警、导出、系统页、性能、文档、安全 | ✅ 完成（v0.2：通知渠道、打印/PDF、LLM 接入、复核 API、验收文档） |
| M6 | 两周试运行与校准 | 🟡 支持工具就绪（日志/周报/月报/验收/自检），待真实使用 |
| V1.1 | Vue 3 前端重构（8 页路由 / 设计系统 / 证据抽屉 / ECharts / 命令面板）+ 工作区整理 | ✅ 完成（2026-11-14；旧版保留 `/legacy`） |

---

## 目录

```
backend/app/        FastAPI 应用（api / ingest / jobs / platform / models）
frontend/           Vue 3 + TS + Vite 源码（src/{api,components,composables,layouts,router,stores,styles,views}）
web/                前端构建产物（index.html + assets/*，由 FastAPI 托管）
web-legacy/         旧版零构建看板（/legacy，V1.2 删除）
config/             默认配置（关注清单、宏观序列、新闻源、LLM）
docs/               设计与进度文档（含 Vue 版与旧版看板截图）
scripts/            setup / build / dev / start / stop / restart / backup / restore / selfcheck / maintain / lint
tests/              pytest（解析器离线测试 + smoke + 前端源码/产物）
data/               运行时数据（gitignore）
```

---

*本系统仅供个人研究与决策辅助，不构成投资建议。*
