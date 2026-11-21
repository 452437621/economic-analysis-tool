"""Greenspan-lineage Fed lens.

The lens is deliberately *not* a Taylor-rule replica.  It encodes the three
things the Greenspan/Bernanke/Yellen/Powell lineage actually reacts to:

1. the real cost of money (real policy rate + real long yield),
2. the financial-conditions loop (the "Greenspan put"),
3. the growth/inflation quadrant that decides whether the Fed can look through
   an inflation print or has to defend credibility.

Readings are levels/ratios computed from the local panel; the interpretive layer
(stance score, regime, put proximity, asset tilts) is a transparent weighted
average whose weights are printed in ``config/lens.yaml``.

This module is a facade: implementations live in :mod:`app.lens.fed_catalog`,
:mod:`app.lens.fed_readings` and :mod:`app.lens.fed_state`.
"""

from __future__ import annotations

from app.lens.fed_catalog import CATALOG, _META, _missing, _reading
from app.lens.fed_readings import _composite, _low_freq, build_readings
from app.lens.fed_state import (
    _asset_scores,
    _mean,
    _pct,
    _put_state,
    _quadrant,
    _stance_components,
    _stance_label,
    build_fed,
    build_state,
)

__all__ = [
    "CATALOG",
    "_META",
    "_asset_scores",
    "_composite",
    "_low_freq",
    "_mean",
    "_missing",
    "_pct",
    "_put_state",
    "_quadrant",
    "_reading",
    "_stance_components",
    "_stance_label",
    "build_fed",
    "build_readings",
    "build_state",
]
