"""LLM claim extraction with a fake client."""

from __future__ import annotations

import pytest

from app.knowledge.llm_extract import extract_claims_with_llm

pytestmark = pytest.mark.unit

TEXT = "The Federal Reserve kept the policy rate at 4.25% on November 5, 2026. Inflation was 2.8%."


class FakeLLM:
    available = True

    def chat_json(self, messages, *, task, model=None):
        return {
            "claims": [
                {
                    "type": "data",
                    "subject": "美联储",
                    "predicate": "维持利率不变",
                    "value": 4.25,
                    "unit": "%",
                    "quote": "The Federal Reserve kept the policy rate at 4.25%",
                    "confidence": 0.9,
                },
                {
                    "type": "data",
                    "subject": "美国通胀",
                    "predicate": "CPI同比",
                    "value": 2.8,
                    "unit": "%",
                    "quote": "Inflation was 2.8%",
                    "confidence": 0.85,
                },
                {
                    "type": "fact",
                    "subject": "假引用",
                    "predicate": "不应入库",
                    "value": None,
                    "unit": None,
                    "quote": "这句话不在原文里",
                    "confidence": 0.9,
                },
            ]
        }


def test_llm_claim_extraction_keeps_exact_spans_and_drops_bad_quotes():
    claims = extract_claims_with_llm(FakeLLM(), TEXT, default_subject="美联储")
    assert len(claims) == 2  # fabricated quote dropped
    for claim in claims:
        assert TEXT[claim.start : claim.end] == claim.quote
    assert claims[0].subject == "美联储"
    assert claims[0].value == 4.25
    assert claims[0].unit == "%"
