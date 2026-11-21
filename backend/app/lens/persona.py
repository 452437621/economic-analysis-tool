"""通用人物透镜：由 ``config/personas/*.yaml`` 驱动，无需为每位人物写 Python。

设计目标与其余透镜（美联储、宋鸿兵、宏观层、微观层）保持一致：把一个人
（或一组政策制定者）的框架压缩成可复算的**读数 → 规则 → 资产评分**三层，
落成 provenance 推导。差别只在于：

* 读数、规则、评分全部是 YAML 里的表达式，新增人物 = 新增一个 YAML 文件；
* 表达式只允许调用下面 ``FUNCTIONS`` 里声明的纯函数与面板列名，不接受任意代码。

表达式语言（与 ``docs/27`` §12.2 一致）::

    z(US10Y_REAL, 250)          滚动 z 分数
    pctile(DXY, 2500)           N 日分位（0–1）
    chg(US10Y, 63)              63 日变化
    pct(XAUUSD, 63)             63 日涨跌幅（%）
    yoy(WB_US_CPI)              同比（%）
    ma(SPX, 200)                移动平均
    shift(SOFR_EFFR, 1)         滞后一期
    sum12(US_MTS_DEFICIT)       近 12 个月求和（TTM，回填到日频）

求值上下文内的列就是面板列（宏观 code / 行情 symbol / 黄金指标 code），
缺失列会以全 NaN 序列出现，于是读数落到 ``missing_reason``，规则落到
``unknown``，不会抛异常中断整次运行。

This module is a facade: implementations live in
:mod:`app.lens.persona_expression`, :mod:`app.lens.persona_spec` and
:mod:`app.lens.persona_engine`.
"""

from __future__ import annotations

from app.lens.persona_engine import (
    _last,
    build_persona,
    build_personas,
    build_readings,
    build_scores,
    build_state,
)
from app.lens.persona_expression import (
    FUNCTIONS,
    ExpressionError,
    _ALLOWED_NODES,
    _NUMERIC_COLUMN_RE,
    _as_series,
    _chg,
    _last_rank,
    _ma,
    _pct,
    _pctile,
    _shift,
    _sum12,
    _yoy,
    _z,
    evaluate_expression,
    normalize_expression,
)
from app.lens.persona_spec import (
    ASSET_IDS,
    PERSONA_DIR,
    RULE_FIELDS,
    RULE_OPS,
    SEVERITIES,
    TAIL_ROWS,
    PersonaSpec,
    _cache,
    _load_spec,
    load_specs,
    log,
    validate_spec,
)

__all__ = [
    "ASSET_IDS",
    "FUNCTIONS",
    "PERSONA_DIR",
    "RULE_FIELDS",
    "RULE_OPS",
    "SEVERITIES",
    "TAIL_ROWS",
    "ExpressionError",
    "PersonaSpec",
    "_ALLOWED_NODES",
    "_NUMERIC_COLUMN_RE",
    "_as_series",
    "_cache",
    "_chg",
    "_last",
    "_last_rank",
    "_load_spec",
    "_ma",
    "_pct",
    "_pctile",
    "_shift",
    "_sum12",
    "_yoy",
    "_z",
    "build_persona",
    "build_personas",
    "build_readings",
    "build_scores",
    "build_state",
    "evaluate_expression",
    "load_specs",
    "log",
    "normalize_expression",
    "validate_spec",
]
