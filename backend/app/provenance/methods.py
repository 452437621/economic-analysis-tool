"""方法登记表：每个推导都能追到「谁算的、哪版代码、什么参数」。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.v2 import MethodRegistry
from app.provenance.engine import module_sha

# method_id -> 展示与归属。module 用于计算代码摘要（文件前 16 位 sha256）。
METHOD_SPECS: tuple[dict, ...] = (
    {
        "method_id": "analytics.run.v1",
        "name": "分析引擎批处理",
        "version": "1.0",
        "kind": "pipeline",
        "module": "app.analytics.runner",
        "description": "M3 分析批处理：行情指标、周期象限、风向、相关性、归因、类比、领先滞后、事件研究。",
    },
    {
        "method_id": "analytics.regime.v1",
        "name": "市场隐含周期象限",
        "version": "1.0",
        "kind": "model",
        "module": "app.analytics.regime",
        "description": "用收益率曲线、铜金比、盈亏平衡通胀、油价、实际利率的 z-score 映射增长/通胀象限。",
    },
    {
        "method_id": "analytics.wind.v1",
        "name": "市场风向合成",
        "version": "1.0",
        "kind": "model",
        "module": "app.analytics.wind",
        "description": "风险资产广度 40% + 20 日动量 35% + 10Y 利率变化 25%，合成 −100..100 风向分。",
    },
    {
        "method_id": "analytics.indicators.v1",
        "name": "标的行情指标",
        "version": "1.0",
        "kind": "model",
        "module": "app.analytics.indicators",
        "description": "收盘、20 日涨跌、趋势、252 日分位、年化波动率。",
    },
    {
        "method_id": "gold.composite.v1",
        "name": "黄金综合评分",
        "version": "1.0",
        "kind": "model",
        "module": "app.gold.scoring",
        "description": "22 项黄金指标按类别归一化、加权合成 0–100 评分与标签，附覆盖率与因子明细。",
    },
    {
        "method_id": "gold.providers.v1",
        "name": "黄金指标采集",
        "version": "1.0",
        "kind": "ingest",
        "module": "app.gold.providers",
        "description": "央行购金、ETF、租赁利率、三地库存、COT、做市商等指标源采集。",
    },
    {
        "method_id": "cycle.engine.v1",
        "name": "EPIC-C 2.0 周期引擎",
        "version": "1.0",
        "kind": "model",
        "module": "app.cycle.engine",
        "description": "DMI/ICI/ECI 分量合成、长债务与短债务周期定位、债务可持续性、世界秩序、历史类比与四情景。",
    },
    {
        "method_id": "timeline.catalog.v1",
        "name": "世界长河 1500–2026",
        "version": "1.0",
        "kind": "dataset",
        "module": "app.timeline.engine",
        "description": "1500–2026 事件年表入库、霸权周期与实力/储备份额、当下五维坐标与历史类比。",
    },
)


def ensure_methods(session: Session) -> int:
    """幂等登记内置方法；代码变更时更新 code_sha，便于版本影响分析。"""
    existing = {
        row.method_id: row for row in session.scalars(select(MethodRegistry)).all()
    }
    changed = 0
    for spec in METHOD_SPECS:
        sha = module_sha(spec["module"])
        row = existing.get(spec["method_id"])
        if row is None:
            row = MethodRegistry(method_id=spec["method_id"])
            session.add(row)
            changed += 1
        row.name = spec["name"]
        row.version = spec["version"]
        row.kind = spec["kind"]
        row.description = spec["description"]
        row.code_sha = sha
        row.params_schema = spec.get("params_schema")
    return changed


def method_map(session: Session) -> dict[str, MethodRegistry]:
    return {row.method_id: row for row in session.scalars(select(MethodRegistry)).all()}
