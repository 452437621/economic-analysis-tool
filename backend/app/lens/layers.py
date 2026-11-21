"""宏观层与微观层：把「人物透镜」下沉到可复用的两层结构。

用户要求「构建宏观、微观的经济分析逻辑」。这里的两层不是新的人，而是
所有透镜共用的**共同底座**：

* **宏观层（macro）**：增长、通胀、流动性、财政、融资压力、美元与曲线。
  它回答「这个经济体处在什么状态」，是每个透镜的输入。
* **微观层（micro）**：估值与趋势、跨资产比价、黄金微观结构（基差/溢价/
  租借/ETF）、持仓与汇率动量。它回答「价格已经定价到哪里」。

两层都产出与人物透镜同构的 ``readings / rules / scores``，于是合成器可以
对「宏观 × 微观 × 人物」做统一加权，而前端只需要一套渲染逻辑。

This module is a facade: implementations live in :mod:`app.lens.layers_catalog`,
:mod:`app.lens.layers_frame`, :mod:`app.lens.layers_macro` and
:mod:`app.lens.layers_micro`.
"""

from __future__ import annotations

from app.lens.layers_catalog import MACRO_READINGS, MICRO_READINGS, log
from app.lens.layers_frame import _direction, _metric, build_frame
from app.lens.layers_macro import _REGIMES, build_macro_layer
from app.lens.layers_micro import build_micro_layer

__all__ = [
    "MACRO_READINGS",
    "MICRO_READINGS",
    "_REGIMES",
    "_direction",
    "_metric",
    "build_frame",
    "build_macro_layer",
    "build_micro_layer",
    "log",
]
