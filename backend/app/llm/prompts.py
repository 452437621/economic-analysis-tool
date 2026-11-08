"""Versioned prompt loading."""

from __future__ import annotations

from app.platform.config import ROOT_DIR

PROMPT_DIR = ROOT_DIR / "prompts"


def load_prompt(name: str, version: str = "v1") -> str:
    path = PROMPT_DIR / f"{name}.{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")
