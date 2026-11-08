"""LLM client (DeepSeek-compatible) with caching, budget guard and audit trail."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import func, select

from app.models.core import LlmCall
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

# USD per 1M tokens (approximate DeepSeek public pricing, used for budget guard)
PRICE_INPUT_PER_M = 0.27
PRICE_OUTPUT_PER_M = 1.10
CACHE_DIR = settings.data_dir / "cache" / "llm"


class LLMUnavailable(RuntimeError):
    pass


class LLMBudgetExceeded(RuntimeError):
    pass


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    latency_ms: int = 0


def estimate_cost(tokens_in: int, tokens_out: int) -> float:
    return round(
        tokens_in / 1_000_000 * PRICE_INPUT_PER_M + tokens_out / 1_000_000 * PRICE_OUTPUT_PER_M,
        6,
    )


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        budget_usd: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.budget_usd = budget_usd if budget_usd is not None else settings.llm_daily_budget_usd
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def _spent_today(self) -> float:
        with SessionLocal() as session:
            value = session.scalar(
                select(func.sum(LlmCall.cost_usd)).where(
                    LlmCall.ts >= _today_start(), LlmCall.cached.is_(False)
                )
            )
        return float(value or 0.0)

    def chat(
        self,
        messages: list[dict],
        *,
        task: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        json_mode: bool = False,
        model: str | None = None,
    ) -> LLMResult:
        if not self.available:
            raise LLMUnavailable("DEEPSEEK_API_KEY is not configured")
        model = model or self.model
        key = hashlib.sha256(
            json.dumps([model, task, messages, temperature], ensure_ascii=False).encode()
        ).hexdigest()
        cache_path = self._cache_path(key)
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                return LLMResult(
                    text=payload["text"],
                    model=payload.get("model", model),
                    tokens_in=payload.get("tokens_in", 0),
                    tokens_out=payload.get("tokens_out", 0),
                    cost_usd=payload.get("cost_usd", 0.0),
                    cached=True,
                )
            except (KeyError, json.JSONDecodeError):
                cache_path.unlink(missing_ok=True)

        if self._spent_today() >= self.budget_usd:
            raise LLMBudgetExceeded(f"daily LLM budget exceeded: {self.budget_usd} USD")

        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        started = time.monotonic()
        with httpx.Client(timeout=90) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
        latency_ms = int((time.monotonic() - started) * 1000)
        resp.raise_for_status()
        payload = resp.json()
        text = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        cost = estimate_cost(tokens_in, tokens_out)

        cache_path.write_text(
            json.dumps(
                {
                    "text": text,
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": cost,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with SessionLocal() as session:
            session.add(
                LlmCall(
                    task=task,
                    model=model,
                    prompt_hash=key,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    cached=False,
                )
            )
            session.commit()
        return LLMResult(
            text=text,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    def chat_json(self, messages: list[dict], *, task: str, model: str | None = None) -> dict:
        result = self.chat(
            messages,
            task=task,
            temperature=0.1,
            max_tokens=3000,
            json_mode=True,
            model=model,
        )
        text = result.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[-1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise
