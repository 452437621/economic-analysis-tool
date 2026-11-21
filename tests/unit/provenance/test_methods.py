"""Method registry idempotency and code hashes."""

from __future__ import annotations

import pytest

from app.provenance.methods import METHOD_SPECS, ensure_methods, method_map
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def test_ensure_methods_is_idempotent_and_hashes_modules(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            first = ensure_methods(session)
            session.commit()
            second = ensure_methods(session)
            session.commit()
            mapping = method_map(session)
        assert first == len(METHOD_SPECS)
        assert second == 0
        assert set(mapping) == {spec["method_id"] for spec in METHOD_SPECS}
        assert all(len(row.code_sha) == 16 for row in mapping.values())
        assert "lens.synthesis.v1" in mapping
    finally:
        engine.dispose()
