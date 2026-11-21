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
    {
        "method_id": "ledger.review.v1",
        "name": "台账：原则库核对与预测校准",
        "version": "1.0",
        "kind": "model",
        "module": "app.ledger.engine",
        "description": "26 条原则按当前读数核对命中/接近/不成立，预测登记、到期对账与 Brier 校准。",
    },
    {
        "method_id": "lens.engine.v1",
        "name": "多透镜引擎",
        "version": "1.0",
        "kind": "pipeline",
        "module": "app.lens.engine",
        "description": (
            "加载本地面板，计算美联储、宋鸿兵、宏观层、微观层与人物透镜共 13 套读数，"
            "评估规则、按权重合成七类资产评分并给出仓位与组合约束。"
        ),
    },
    {
        "method_id": "lens.fed.v1",
        "name": "美联储主席透镜",
        "version": "1.0",
        "kind": "model",
        "module": "app.lens.fed_state",
        "description": "格林斯潘—伯南克—耶伦—鲍威尔反应函数：实际利率、金融条件、看跌期权与增长/通胀象限。",
    },
    {
        "method_id": "lens.song.v1",
        "name": "宋鸿兵透镜",
        "version": "1.0",
        "kind": "model",
        "module": "app.lens.song_state",
        "description": "美元环流温度、美元心脏三态、债务货币化、黄金熵值与资产映射。",
    },
    {
        "method_id": "lens.macro.v1",
        "name": "宏观层",
        "version": "1.0",
        "kind": "model",
        "module": "app.lens.layers_macro",
        "description": "增长/通胀四象限、净流动性、财政主导与融资压力，输出宏观状态与七类资产评分。",
    },
    {
        "method_id": "lens.micro.v1",
        "name": "微观层",
        "version": "1.0",
        "kind": "model",
        "module": "app.lens.layers_micro",
        "description": "风险偏好、黄金实物紧张度与拥挤度（基差/溢价/租借/ETF/持仓/金银比）。",
    },
    {
        "method_id": "lens.persona.v1",
        "name": "人物透镜引擎",
        "version": "1.0",
        "kind": "model",
        "module": "app.lens.persona_engine",
        "description": "读取 config/personas/*.yaml，在 AST 沙箱内求值读数与规则，输出九位思想者各自的倾向与评分。",
    },
    {
        "method_id": "lens.synthesis.v1",
        "name": "多透镜合成与研判",
        "version": "1.0",
        "kind": "model",
        "module": "app.lens.synthesis",
        "description": "13 套透镜按权重合成共识分、一致度、分歧/共振清单、七类资产评分、情景推演与组合仓位约束。",
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
