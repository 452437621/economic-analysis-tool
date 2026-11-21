"""Persona spec loading, validation and expression behavior must not change."""

from __future__ import annotations

import pytest

import pandas as pd

from app.lens import persona
from app.lens.persona_spec import PersonaSpec

pytestmark = pytest.mark.unit

EXPECTED_SPECS = {
    "dalio",
    "druckenmiller",
    "marks",
    "gundlach",
    "el_erian",
    "pozsar",
    "pettis",
    "koo",
    "policy_actors",
}


def test_load_specs_is_cached_and_unchanged():
    first = persona.load_specs()
    second = persona.load_specs()
    assert {spec.id for spec in first} == EXPECTED_SPECS
    assert [spec.id for spec in first] == [spec.id for spec in second]
    assert second is not first
    assert second[0] is first[0]


def test_validate_spec_accepts_shipped_specs():
    for spec in persona.load_specs():
        assert persona.validate_spec(spec) == [], spec.id


def test_validate_spec_reports_missing_scores():
    problems = persona.validate_spec(PersonaSpec(id="broken", name="Broken"))
    assert problems == [
        "scores 缺少：us_equity, gold, silver, usd, cn_equity, long_bond, commodities"
    ]


def test_validate_spec_reports_duplicate_and_missing_expr():
    spec = PersonaSpec(
        id="broken",
        name="Broken",
        readings=[
            {"id": "a", "label": "A", "expr": "US10Y"},
            {"id": "a", "label": "B", "expr": ""},
        ],
        scores={asset: "0" for asset in persona.ASSET_IDS},
    )
    problems = persona.validate_spec(spec)
    assert problems == ["readings 存在重复 id", "a 缺少 expr"]


def test_validate_spec_checks_columns_when_supplied():
    spec = PersonaSpec(
        id="broken",
        name="Broken",
        readings=[{"id": "a", "label": "A", "expr": "MISSING_COL"}],
        scores={asset: "0" for asset in persona.ASSET_IDS},
    )
    assert "a 引用未知列 MISSING_COL" in persona.validate_spec(spec, columns=["US10Y"])


def test_normalize_expression_rewrites_numeric_columns():
    assert persona.normalize_expression("pct(000300, 20)") == "pct(SYM_000300, 20)"


def test_evaluate_expression_is_unchanged():
    frame = pd.DataFrame({"US10Y_REAL": [1.0, 2.0, 3.0]})
    out = persona.evaluate_expression("chg(US10Y_REAL, 1)", frame)
    assert out.tolist()[1:] == [1.0, 1.0]
    with pytest.raises(persona.ExpressionError):
        persona.evaluate_expression("nope(US10Y_REAL)", frame)
