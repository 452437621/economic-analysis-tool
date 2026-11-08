"""LLM brief editor (strict: no new facts)."""

from __future__ import annotations

import logging

from app.llm.client import LLMClient
from app.llm.prompts import load_prompt

logger = logging.getLogger(__name__)


def enhance_brief(markdown: str, *, client: LLMClient | None = None) -> tuple[str, dict]:
    client = client or LLMClient()
    if not client.available:
        return markdown, {"skipped": "no_api_key"}
    try:
        prompt = load_prompt("brief_editor")
        result = client.chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": markdown},
            ],
            task="brief_edit",
            temperature=0.25,
            max_tokens=4000,
        )
        text = result.text.strip()
        if len(text) < len(markdown) * 0.5:
            return markdown, {"skipped": "too_short"}
        return text, {
            "model": result.model,
            "cost_usd": result.cost_usd,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("brief enhancement failed: %s", exc)
        return markdown, {"skipped": f"error: {exc}"}
