"""Song Hongbing / 《货币战争》 lens.

The lens is built around the one variable Song keeps returning to: the
*temperature of the dollar circulation*.  Assets are functions of that
temperature, and the temperature itself is read at two places:

* the dollar's external price (DXY percentile / momentum / real yields), and
* the dollar's "heart" — the repo market (SOFR vs EFFR, SOFR spikes).

A second, independent chain (debt monetisation + gold's entropy premium) is
kept separate on purpose: Song himself treats gold as the scale of *global
disorder*, not as a risk-on/risk-off asset.

This module is a facade: implementations live in :mod:`app.lens.song_catalog`,
:mod:`app.lens.song_readings` and :mod:`app.lens.song_state`.
"""

from __future__ import annotations

from app.lens.song_catalog import CATALOG, _META, _missing, _reading
from app.lens.song_readings import _low_freq, _yoy_pct, build_readings
from app.lens.song_state import (
    _asset_scores,
    _heart,
    _phase,
    build_song,
    build_state,
)

__all__ = [
    "CATALOG",
    "_META",
    "_asset_scores",
    "_heart",
    "_low_freq",
    "_missing",
    "_phase",
    "_reading",
    "_yoy_pct",
    "build_readings",
    "build_song",
    "build_state",
]
