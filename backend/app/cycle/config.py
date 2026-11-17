"""Load and validate the EPIC-C cycle configuration.

All thresholds, indicators and manual observations live in
``config/cycle.yaml`` so that tuning the engine never requires a code change.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT_DIR / "config" / "cycle.yaml"
#: UI-editable alert threshold overrides. Kept beside cycle.yaml but separate so
#: the shipped config stays byte-identical while users tune thresholds.
OVERRIDES_PATH = ROOT_DIR / "config" / "cycle.overrides.yaml"
#: Append-only audit trail for every config mutation (one JSON object per line).
AUDIT_PATH = ROOT_DIR / "data" / "audit" / "cycle-config.jsonl"

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
    _merge_alert_overrides(raw)
    return raw


def _read_overrides() -> dict:
    """Read the optional UI overrides file; a missing file means no overrides."""
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - corrupt file is an operator error
        raise CycleConfigError(f"invalid cycle overrides: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise CycleConfigError("cycle overrides must be a mapping")
    return data


def _merge_alert_overrides(raw: dict) -> None:
    """Overlay ``alerts.<rule_id>.threshold`` from overrides onto cycle.yaml."""
    override = _read_overrides().get("alerts") or {}
    if not isinstance(override, dict) or not override:
        raw["_meta"]["overrides"] = {"path": None, "alerts": {}}
        return
    applied: dict[str, float] = {}
    for alert in raw.get("alerts") or []:
        if not isinstance(alert, dict):
            continue
        rule_id = str(alert.get("id"))
        if rule_id not in override:
            continue
        value = override[rule_id]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        alert["threshold"] = float(value)
        applied[rule_id] = float(value)
    raw["_meta"]["overrides"] = {
        "path": str(OVERRIDES_PATH.relative_to(ROOT_DIR)),
        "alerts": applied,
    }


def _write_overrides(overrides: dict) -> None:
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES_PATH.write_text(
        yaml.safe_dump(overrides, allow_unicode=True, sort_keys=True, default_flow_style=False),
        encoding="utf-8",
    )


def _append_audit(entry: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def apply_alert_overrides(alerts: dict | None = None, note: str | None = None) -> dict:
    """Validate and persist alert-threshold overrides from the UI.

    ``cycle.yaml`` is never modified: thresholds are written to
    ``config/cycle.overrides.yaml`` and merged by :func:`load_config`. Every call
    appends one line to ``data/audit/cycle-config.jsonl``. Raises ``ValueError``
    for unknown rule ids or non-numeric/out-of-range thresholds (API maps to 400).
    """
    config = load_config()
    known = {
        str(item.get("id")): item
        for item in config.get("alerts") or []
        if isinstance(item, dict) and item.get("id") is not None
    }
    overrides = _read_overrides()
    current_alerts = dict(overrides.get("alerts") or {})
    changes: list[dict] = []
    for rule_id, value in (alerts or {}).items():
        rule_id = str(rule_id)
        if rule_id not in known:
            raise ValueError(f"unknown alert rule: {rule_id}")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < float(value) < 1_000_000_000
        ):
            raise ValueError(f"threshold for {rule_id} must be a number in (0, 1e9)")
        new_value = float(value)
        old_value = current_alerts.get(rule_id, known[rule_id].get("threshold"))
        if old_value == new_value:
            continue
        changes.append({"rule_id": rule_id, "from": old_value, "to": new_value})
        current_alerts[rule_id] = new_value
    version = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    if changes:
        payload = dict(overrides)
        payload["alerts"] = current_alerts
        _write_overrides(payload)
    _append_audit(
        {
            "ts": version,
            "note": note,
            "changes": changes,
            "version": version,
        }
    )
    load_config.cache_clear()
    return {
        "ok": True,
        "version": version,
        "changed": [change["rule_id"] for change in changes],
        "overrides": {
            "path": str(OVERRIDES_PATH.relative_to(ROOT_DIR)),
            "alerts": current_alerts,
        },
    }


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
