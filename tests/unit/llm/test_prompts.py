"""Versioned prompt loading."""

from __future__ import annotations

import pytest


from app.llm.prompts import load_prompt

pytestmark = pytest.mark.unit


def test_loads_versioned_prompt() -> None:
    text = load_prompt("brief_editor", "v1")
    assert len(text.strip()) > 100


def test_missing_prompt_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist", "v1")
