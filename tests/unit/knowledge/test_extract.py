"""Numeric claim extraction from document text."""

from __future__ import annotations

import pytest

from app.knowledge.extract import extract_numeric_claims

pytestmark = pytest.mark.unit


def test_claim_extraction_with_default_subject():
    text = "The ECB said inflation was 2.5% in October. Unemployment at 4.1%."
    claims = extract_numeric_claims(text, default_subject="欧洲央行")
    assert len(claims) >= 2
    assert claims[0].subject == "欧洲央行"
    assert claims[0].value == 2.5
    assert claims[0].unit == "%"
    assert claims[1].subject == "欧洲央行"
    assert text[claims[0].start : claims[0].end].strip().startswith("The ECB")


def test_claim_spans_are_exact():
    text = "The Federal Reserve kept the rate at 4.25% and said inflation was 2.8%."
    claims = extract_numeric_claims(text)
    assert claims
    for claim in claims:
        assert text[claim.start : claim.end].strip() == claim.quote
