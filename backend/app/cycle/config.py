"""Load and validate the EPIC-C cycle configuration.

All thresholds, indicators and manual observations live in
``config/cycle.yaml`` so that tuning the engine never requires a code change.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT_DIR / "config" / "cycle.yaml"

EVIDENCE_WEIGHT = {"E0": 1.0, "E1": 0.95, "E2": 0.90, "E3": 0.75, "E4": 0.50}


class CycleConfigError(RuntimeError):
    """Raised when cycle.yaml is missing or malformed."""


def _parse_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


@lru_cache(maxsize=1)
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise CycleConfigError(f"missing cycle config: {CONFIG_PATH}")
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CycleConfigError("cycle config must be a mapping")
    for key in ("normalization", "scores", "indicators", "manual"):
        if key not in raw:
            raise CycleConfigError(f"cycle config missing section: {key}")
    raw["_meta"] = {
        "version": raw.get("version", "0"),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "path": str(CONFIG_PATH.relative_to(ROOT_DIR)),
    }
    return raw


def as_of(value: object) -> date | None:
    """Normalise a config/DB date-like value to a date."""
    return _parse_date(value)


def stale_days(value: date | None, today: date | None = None) -> int | None:
    if value is None:
        return None
    ref = today or date.today()
    return max(0, (ref - value).days)


def score_indicators(config: dict | None = None) -> list[dict]:
    return list((config or load_config()).get("indicators") or [])


def manual_indicators(config: dict | None = None) -> list[dict]:
    return list((config or load_config()).get("manual") or [])


def phase_band(config: dict, section: str) -> list[dict]:
    return list((config.get(section) or {}).get("phases") or [])
