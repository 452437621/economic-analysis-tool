"""M3 analytics unit tests: return attribution."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analytics.attribution import decompose

pytestmark = pytest.mark.unit


def test_decompose_recovers_betas():
    rng = np.random.default_rng(11)
    n = 200
    d1 = rng.normal(0, 0.01, n)
    d2 = rng.normal(0, 0.01, n)
    y = 2.0 * d1 - 1.0 * d2 + rng.normal(0, 0.0001, n)
    result = decompose(
        pd.Series(y),
        pd.DataFrame({"d1": d1, "d2": d2}),
        window=180,
        contrib_days=20,
    )
    assert abs(result["betas"]["d1"] - 2.0) < 0.05
    assert abs(result["betas"]["d2"] + 1.0) < 0.05
    assert result["r2"] > 0.99
