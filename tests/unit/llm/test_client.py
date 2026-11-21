"""LLM client availability and cost estimation."""

from __future__ import annotations

import pytest

from app.llm.client import LLMClient, estimate_cost

pytestmark = pytest.mark.unit


def test_llm_unavailable_falls_back():
    client = LLMClient(api_key="")
    assert client.available is False
    from app.narrative.llm_edit import enhance_brief

    text = "# 测试\n内容"
    enhanced, meta = enhance_brief(text, client=client)
    assert enhanced == text
    assert meta["skipped"] == "no_api_key"


def test_estimate_cost():
    assert estimate_cost(1_000_000, 0) == 0.27
    assert abs(estimate_cost(0, 1_000_000) - 1.10) < 1e-9
