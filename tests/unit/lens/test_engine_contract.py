"""The engine orchestrator must keep its top-level payload contract after the split."""

from __future__ import annotations

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.lens import engine as lens_engine
from app.models import core as _core  # noqa: F401 - register metadata
from app.models import v2 as _v2  # noqa: F401 - register metadata
from app.models.base import Base

pytestmark = pytest.mark.unit

TOP_LEVEL_KEYS = {
    "run",
    "panel",
    "quality",
    "fed",
    "song",
    "macro",
    "micro",
    "personas",
    "synthesis",
    "rules",
    "data_gaps",
    "derivations",
    "config_version",
}

ASSET_IDS = (
    "us_equity",
    "gold",
    "silver",
    "usd",
    "cn_equity",
    "long_bond",
    "commodities",
)


def test_run_lenses_contract_on_empty_panel():
    sqlite = create_engine("sqlite://")
    Base.metadata.create_all(sqlite)
    factory = sessionmaker(bind=sqlite)
    with factory() as session:
        result = lens_engine.run_lenses(session)

    assert set(result) == TOP_LEVEL_KEYS
    assert [row["id"] for row in result["synthesis"]["assets"]] == list(ASSET_IDS)
    assert [row["id"] for row in lens_engine.ASSETS] == list(ASSET_IDS)
    assert result["synthesis"]["lens_count"] == 13
    assert result["config_version"]
    assert result["fed"]["catalog"] is lens_engine.fed_lens.CATALOG
    assert result["song"]["catalog"] is lens_engine.song_lens.CATALOG
