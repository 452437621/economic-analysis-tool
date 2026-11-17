"""Monthly score history (for charts, momentum and analog matching).

History is computed on the market indicators only: manual structural readings
are point-in-time expert values and are intentionally kept out of the
historical series (otherwise they would create a false flat line).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.cycle.config import load_config
from app.cycle.indicators import phi_series
from app.cycle.market import Panel, indicator_series, zscore


@dataclass
class History:
    scores: pd.DataFrame
    zscores: pd.DataFrame
    coverage: pd.DataFrame

    @property
    def months(self) -> int:
        return len(self.scores)


def build_history(panel: Panel, config: dict | None = None) -> History:
    cfg = config or load_config()
    norm = cfg.get("normalization") or {}
    window = int(norm.get("window_days", 2520))
    min_obs = int(norm.get("min_obs", 250))
    clip = float(norm.get("clip_z", 3.5))

    z_monthly: dict[str, pd.Series] = {}
    weight_by_score: dict[str, dict[str, float]] = {}
    for spec in cfg.get("indicators") or []:
        series = indicator_series(panel, spec)
        clean = series.dropna()
        if clean.empty:
            continue
        z = zscore(clean, window_days=window, min_obs=min_obs, clip=clip)
        z_monthly[spec["id"]] = z.resample("ME").last()
        weight_by_score.setdefault(spec["score"], {})[spec["id"]] = float(spec.get("weight", 0))

    if not z_monthly:
        return History(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    z_frame = pd.DataFrame(z_monthly).sort_index()
    scores = pd.DataFrame(index=z_frame.index)
    coverage = pd.DataFrame(index=z_frame.index)
    for score_id, weights in weight_by_score.items():
        cols = [column for column in weights if column in z_frame.columns]
        if not cols:
            continue
        matrix = pd.DataFrame({column: z_frame[column] for column in cols})
        scores_matrix = 100.0 * matrix.apply(phi_series)
        w = pd.Series({column: weights[column] for column in cols})
        available = matrix.notna().mul(w, axis=1).sum(axis=1)
        total = float(w.sum())
        weighted = scores_matrix.fillna(0.0).mul(w, axis=1).sum(axis=1)
        scores[score_id] = (
            weighted / available.replace(0.0, np.nan)
        ).where(available >= total * 0.6).astype("float64")
        coverage[score_id] = (available / total).round(3)
    return History(scores=scores, zscores=z_frame, coverage=coverage)


def momentum_12m(scores: pd.DataFrame, score_id: str = "GROWTH") -> float | None:
    if score_id not in scores.columns:
        return None
    series = scores[score_id].dropna()
    if len(series) < 13:
        return None
    return float(series.iloc[-1] - series.iloc[-13])
