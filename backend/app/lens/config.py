"""Lens config loading (``config/lens.yaml``)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "lens.yaml"


@lru_cache(maxsize=4)
def _load_config_cached(path: str, mtime: float) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config() -> dict[str, Any]:
    stat = CONFIG_PATH.stat()
    return _load_config_cached(str(CONFIG_PATH), stat.st_mtime)
