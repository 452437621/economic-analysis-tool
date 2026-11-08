"""LLM-based claim extraction with exact-quote enforcement."""

from __future__ import annotations

import logging

from app.knowledge.extract import ExtractedClaim
from app.llm.client import LLMClient
from app.llm.prompts import load_prompt

logger = logging.getLogger(__name__)


def extract_claims_with_llm(
    client: LLMClient,
    text: str,
    *,
    default_subject: str | None = None,
    max_chars: int = 8000,
) -> list[ExtractedClaim]:
    if not client.available:
        return []
    prompt = load_prompt("extract_claims")
    user = f"来源：{default_subject or '未知'}\n\n文本：\n{text[:max_chars]}"
    payload = client.chat_json(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user},
        ],
        task="extract_claims",
    )
    claims: list[ExtractedClaim] = []
    for item in (payload.get("claims") or [])[:20]:
        quote = str(item.get("quote") or "").strip()
        if not quote:
            continue
        start = text.find(quote)
        if start < 0:
            logger.debug("llm claim quote not found verbatim, skipped: %s", quote[:60])
            continue
        value = item.get("value")
        try:
            value = float(value) if value is not None else None
        except (TypeError, ValueError):
            value = None
        try:
            confidence = float(item.get("confidence") or 0.6)
        except (TypeError, ValueError):
            confidence = 0.6
        claims.append(
            ExtractedClaim(
                subject=str(item.get("subject") or default_subject or "市场"),
                predicate=str(item.get("predicate") or "陈述"),
                value=value,
                unit=item.get("unit"),
                quote=quote[:500],
                start=start,
                end=start + len(quote),
                confidence=max(0.0, min(1.0, confidence)),
            )
        )
    return claims
