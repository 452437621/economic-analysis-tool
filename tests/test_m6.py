"""M6 tests: LLM extraction (fake client), notifications, review, renderer."""

from __future__ import annotations

from app.decision.review import summarize
from app.knowledge.llm_extract import extract_claims_with_llm
from app.llm.client import LLMClient, estimate_cost
from app.narrative.render import markdown_to_html
from app.notify import build_serverchan_payload, build_wechat_payload, format_alert

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


def test_notify_payloads():
    alert = {"level": "critical", "title": "沪金 下跌 6%", "message": "最新 900"}
    text = format_alert(alert)
    assert "CRITICAL" in text
    assert "沪金" in text
    url, payload = build_serverchan_payload("KEY", text)
    assert url.endswith("/KEY.send")
    assert payload["desp"] == text
    url, payload = build_wechat_payload("https://example.com/hook", text)
    assert payload["text"]["content"] == text


def test_review_summary():
    records = [
        {"probability": 0.55, "actual": 1.0, "brier": 0.2025},
        {"probability": 0.55, "actual": 0.0, "brier": 0.3025},
        {"probability": 0.65, "actual": 1.0, "brier": 0.1225},
    ]
    summary = summarize(records)
    assert summary["count"] == 3
    assert summary["hit_rate"] == round(2 / 3, 3)
    assert summary["brier"] > 0
    assert summary["calibration"]


def test_markdown_render_escapes_html():
    html = markdown_to_html("## 标题\n\n<script>alert(1)</script>\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<h3>标题</h3>" in html
    assert "&lt;script&gt;" in html
    assert "<table>" in html
    assert 'class="mainline"' in markdown_to_html("> **一句话主线：** 测试")
