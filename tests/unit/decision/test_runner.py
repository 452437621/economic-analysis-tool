"""Decision runner quality-gate short circuit."""

from __future__ import annotations

import pytest

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.analytics.data import MarketFrames
from app.decision import runner
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def test_run_decision_blocks_when_quality_gate_blocks(tmp_path, monkeypatch) -> None:
    engine, factory = make_db(tmp_path)
    try:
        index = pd.date_range(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            periods=30,
            freq="D",
        )
        frames = MarketFrames(
            closes=pd.DataFrame({"AU": [100.0 + step for step in range(30)]}, index=index),
            macro=pd.DataFrame(index=index),
            open_interest=pd.DataFrame(),
        )
        monkeypatch.setattr(runner, "load_frames", lambda: frames)
        monkeypatch.setattr(
            runner,
            "assess_quality",
            lambda session: {"status": "blocked", "caveat": "data stale"},
        )
        monkeypatch.setattr(runner, "SessionLocal", factory)

        result = runner.run_decision()
        assert result["status"] == "blocked"
        assert result["skipped"] == "quality_gate"
        assert result["signals"] == 0
        assert result["reason"] == "data stale"
    finally:
        engine.dispose()


def test_run_decision_raises_without_bars(monkeypatch) -> None:
    empty = MarketFrames(
        closes=pd.DataFrame(),
        macro=pd.DataFrame(),
        open_interest=pd.DataFrame(),
    )
    monkeypatch.setattr(runner, "load_frames", lambda: empty)
    try:
        runner.run_decision()
    except RuntimeError as exc:
        assert "no daily bars" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")
