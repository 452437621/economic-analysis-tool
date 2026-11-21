"""Provider chains registry and cross-source reconciliation."""

from __future__ import annotations

import pytest

from datetime import datetime, timezone


from app.ingest import chains, sources
from app.ingest.contracts import MacroPoint
from app.ingest.reconcile import compare_series

pytestmark = pytest.mark.unit

SOURCE_VALUES = {
    key: value
    for key, value in vars(sources).items()
    if key.startswith("SOURCE_") and isinstance(value, dict)
}


def test_chain_ids_are_unique_and_sources_resolve() -> None:
    ids = [chain.id for chain in chains.CHAINS.values()]
    assert len(ids) == len(set(ids))
    known = list(SOURCE_VALUES.values())
    for chain in chains.CHAINS.values():
        for source in chain.sources:
            assert any(source is candidate for candidate in known), (
                f"{chain.id} references an unregistered source: {source}"
            )


def test_source_roles_marks_primary_and_backup() -> None:
    roles = chains.source_roles()
    assert roles
    assert any("primary" in value["roles"] for value in roles.values())
    assert any("backup" in value["roles"] for value in roles.values())
    treasury = chains.chains_for_source("美国财政部")
    assert "rates.us_treasury" in treasury


def _point(day: int, value: float) -> MacroPoint:
    return MacroPoint(code="US10Y", ts=datetime(2026, 1, day, tzinfo=timezone.utc), value=value)


def test_compare_series_within_tolerance_returns_none() -> None:
    primary = [_point(1, 4.0), _point(2, 4.1)]
    secondary = [_point(2, 4.11)]
    assert compare_series(primary, secondary, tolerance=0.005) is None


def test_compare_series_flags_material_divergence() -> None:
    primary = [_point(2, 4.0)]
    secondary = [_point(2, 4.2)]
    finding = compare_series(primary, secondary, tolerance=0.005)
    assert finding is not None
    assert finding["as_of"] == "2026-01-02"
    assert finding["expected"] == 4.0
    assert finding["actual"] == 4.2
    assert finding["deviation"] == pytest.approx(0.05)


def test_compare_series_without_common_dates_returns_none() -> None:
    assert compare_series([_point(1, 4.0)], [_point(2, 4.0)]) is None
