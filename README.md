# EPIC · 个人市场分析工具

> **Economic Positioning, Intelligence & Cycles** —— 本地运行、以证据为中心的个人宏观—市场—交易决策工作台。
>
> 状态：**M0 已完成**（2026-11-09）：后端可运行、数据库与调度器就绪、看板可访问；**M1 数据地基进行中**。

---

## 快速开始

```powershell
# 1) 初始化（自动引导 Python 3.12、创建 .venv、安装依赖、建库、写入种子数据）
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1

# 2) 启动
powershell -File .\scripts\start.ps1
```

浏览器打开 **http://127.0.0.1:8765** ，可见系统状态看板。

- 开发模式：`.\scripts\start.ps1 -Reload`
- 备份：`.\scripts\backup.ps1` → `data/backup/<时间戳>/`
- 测试：`.\.venv\Scripts\python.exe -m pytest -q`

> 环境说明：系统 Python 为 3.8（过旧）。`setup.ps1` 会用 uv 在工作区内安装 **Python 3.12.16**（`.python/`），不修改系统环境。

---

## 它要解决什么

把「信息汇聚 → 证据固化 → 因果分析 → 情景推演 → 交易计划 → 复盘校准」做成可重复的流水线：

- **信息**：官方/媒体/持仓/日历多源汇聚，事件聚类，原文快照与可信度评分；
- **分析**：经济周期定位、资产定价分解、跨市场传导、参与者行为、历史类比；
- **取证**：每条结论可溯源到原文片段、时间与来源，矛盾并列不隐藏；
- **决策**：面向国内期货与 A 股的交易计划（方向、价位、仓位、止损、时间止损、失效条件）；
- **复盘**：预测登记、Brier 校准、信号回测、交易日志与纪律分。

覆盖重点：黄金/白银、原油、铜铝锌镍、内外盘同品种、美元与日元/人民币、美债与中日欧利率、美股与 A 股（有色金属，洛阳钼业为个股模板）。**不覆盖国内独有品种**，V1 不接自动下单。

---

## 文档索引

| 文档 | 内容 |
|---|---|
| [01 需求分析与产品定义](./docs/01-需求分析与产品定义.md) | 背景、痛点、范围、功能/非功能需求、验收标准 |
| [02 系统架构设计](./docs/02-系统架构设计.md) | 分层架构、数据模型、采集适配、LLM 编排、前端、部署 |
| [03 分析框架与模型设计](./docs/03-分析框架与模型设计.md) | 周期/定价/传导/参与者/历史类比/证据可信度/交易系统 |
| [04 实施方案与里程碑](./docs/04-实施方案与里程碑.md) | M0–M6 里程碑、WBS、关键路径、测试、风险 |
| [05 数据源与接口清单](./docs/05-数据源与接口清单.md) | 免费/付费数据源、实测可用性、降级链、合规 |
| [06 示例输出：黄金分析](./docs/06-示例输出-黄金分析.md) | 简报/计划卡/证据链样例 |
| [07 开发进度](./docs/07-开发进度.md) | 已完成、遇到的问题、下一步任务 |

---

## 架构一览

```
浏览器 (静态看板 → M1 起 React)
   │ HTTP 127.0.0.1:8765
FastAPI (api / SSE / 导出)
   │
├─ 采集适配层  market / macro / news / positions / calendar
├─ 知识层      documents / claims / events / theses / evidence
├─ 分析层      regime / pricing / correlation / analog / sentiment
├─ 决策层      signals / plans / risk / backtest / predictions
├─ LLM 编排    DeepSeek（抽取/分析/核查/编辑）
└─ 存储        SQLite + DuckDB/Parquet + 文件快照
```

技术栈：Python 3.12 + FastAPI + SQLAlchemy + APScheduler + DuckDB；前端 React/TS/ECharts（M1 起）；数据源见 [05](./docs/05-数据源与接口清单.md)。

---

## 里程碑

| 阶段 | 交付 | 状态 |
|---|---|---|
| M0 | 环境、骨架、数据库、调度器、健康检查、看板 | ✅ 完成 |
| M1 | 行情/宏观/新闻/持仓采集 + 多源降级 + 数据看板 | 🚧 进行中 |
| M2 | 证据链、可信度、每日简报 v1 | 待开始 |
| M3 | 周期/定价/关联/类比/参与者分析 | 待开始 |
| M4 | 信号、情景、交易计划、风控、回测、预测账本 | 待开始 |
| M5 | 告警、导出、系统页、性能、文档、安全 | 待开始 |
| M6 | 两周试运行与校准 | 待开始 |

---

## 目录

```
backend/app/        FastAPI 应用（api / platform / models / ...）
web/                零构建看板（M1 换 React）
config/             默认配置（关注清单、LLM、调度）
docs/               设计与进度文档
scripts/            setup / start / backup
tests/              pytest
data/               运行时数据（gitignore）
```

---

*本系统仅供个人研究与决策辅助，不构成投资建议。*
