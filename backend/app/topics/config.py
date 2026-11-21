"""Topic registry loading and validation (``config/topics.yaml``).

The registry is intentionally small: it declares which research topics exist,
which adapter renders them, and which sections the page shows.  Heavy
per-topic parameters (scenario assumptions, position defaults) live next to it
under ``config/topics/<topic>.yaml`` and stay attached to ``TopicSpec.params``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT_DIR / "config" / "topics.yaml"
PARAMS_DIR = ROOT_DIR / "config" / "topics"

RENDERERS = {
    "hero",
    "kpis",
    "factors",
    "charts",
    "bullets",
    "table",
    "valuation",
    "scenarios",
    "position",
    "events",
    "sources",
    "health",
    "methodology",
}


class TopicConfigError(ValueError):
    """Raised when the topic registry is missing or structurally invalid."""


@dataclass(frozen=True)
class TopicSection:
    id: str
    label: str
    kind: str
    anchor: str
    order: int
    enabled: bool = True


@dataclass(frozen=True)
class TopicSpec:
    id: str
    label: str
    subtitle: str
    asset: str
    adapter: str
    enabled: bool
    order: int
    refresh_job: str | None
    sections: tuple[TopicSection, ...]
    signal_weights: dict[str, float] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    def section(self, section_id: str) -> TopicSection | None:
        return next((item for item in self.sections if item.id == section_id), None)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:  # pragma: no cover - misconfigured install
        raise TopicConfigError(f"缺少配置文件：{path}") from exc
    except yaml.YAMLError as exc:
        raise TopicConfigError(f"配置文件解析失败：{path}（{exc}）") from exc
    if not isinstance(payload, dict):
        raise TopicConfigError(f"配置文件根节点必须是对象：{path}")
    return payload


def _as_int(value: Any, *, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TopicConfigError(f"{field_name} 必须是整数：{value!r}") from exc


def _as_float(value: Any, *, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise TopicConfigError(f"{field_name} 必须是数字：{value!r}") from exc


def _parse_section(topic_id: str, raw: dict[str, Any], index: int) -> TopicSection:
    if not isinstance(raw, dict):
        raise TopicConfigError(f"{topic_id}: sections[{index}] 必须是对象")
    section_id = str(raw.get("id") or "").strip()
    label = str(raw.get("label") or "").strip()
    kind = str(raw.get("kind") or "").strip()
    if not section_id or not label:
        raise TopicConfigError(f"{topic_id}: sections[{index}] 缺少 id/label")
    if kind not in RENDERERS:
        raise TopicConfigError(f"{topic_id}.{section_id}: 未知分区类型 {kind!r}")
    anchor = str(raw.get("anchor") or f"topic-{topic_id}-{section_id}")
    return TopicSection(
        id=section_id,
        label=label,
        kind=kind,
        anchor=anchor,
        order=_as_int(raw.get("order", index * 10), field_name=f"{topic_id}.{section_id}.order"),
        enabled=bool(raw.get("enabled", True)),
    )


def _parse_topic(raw: dict[str, Any], index: int) -> TopicSpec:
    if not isinstance(raw, dict):
        raise TopicConfigError(f"topics[{index}] 必须是对象")
    topic_id = str(raw.get("id") or "").strip()
    label = str(raw.get("label") or "").strip()
    adapter = str(raw.get("adapter") or "").strip()
    if not topic_id or not label or not adapter:
        raise TopicConfigError(f"topics[{index}] 缺少 id/label/adapter")

    sections = [
        _parse_section(topic_id, item, position)
        for position, item in enumerate(raw.get("sections") or [])
    ]
    if not sections:
        raise TopicConfigError(f"{topic_id}: 至少需要一个 section")
    section_ids = [item.id for item in sections]
    if len(set(section_ids)) != len(section_ids):
        raise TopicConfigError(f"{topic_id}: section id 重复")
    sections.sort(key=lambda item: (item.order, section_ids.index(item.id)))

    weights_raw = raw.get("signal_weights") or {}
    if not isinstance(weights_raw, dict):
        raise TopicConfigError(f"{topic_id}: signal_weights 必须是对象")
    signal_weights: dict[str, float] = {}
    for key, value in weights_raw.items():
        weight = _as_float(value, field_name=f"{topic_id}.signal_weights.{key}")
        if weight < 0:
            raise TopicConfigError(f"{topic_id}.signal_weights.{key} 不能为负数")
        signal_weights[str(key)] = weight

    params_path = PARAMS_DIR / f"{topic_id}.yaml"
    params = _read_yaml(params_path) if params_path.exists() else {}

    return TopicSpec(
        id=topic_id,
        label=label,
        subtitle=str(raw.get("subtitle") or ""),
        asset=str(raw.get("asset") or ""),
        adapter=adapter,
        enabled=bool(raw.get("enabled", True)),
        order=_as_int(raw.get("order", index * 10), field_name=f"{topic_id}.order"),
        refresh_job=(str(raw["refresh_job"]) if raw.get("refresh_job") else None),
        sections=tuple(sections),
        signal_weights=signal_weights,
        params=params,
    )


def _version_of(path: Path) -> str:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return "missing"
    digest = hashlib.sha256(f"{path}:{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()
    return digest[:12]


def _params_signature() -> tuple[tuple[str, int, int], ...]:
    """Cheap cache key for ``config/topics/*.yaml`` (params are read inside the cache)."""
    if not PARAMS_DIR.exists():
        return ()
    try:
        files = sorted(PARAMS_DIR.glob("*.yaml"))
    except OSError:
        return ()
    signature: list[tuple[str, int, int]] = []
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((path.name, stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


@lru_cache(maxsize=8)
def _load_cached(
    path: str,
    mtime: float,
    params_signature: tuple[tuple[str, int, int], ...],
) -> tuple[dict[str, Any], tuple[TopicSpec, ...]]:
    del params_signature  # part of the cache key only
    raw = _read_yaml(Path(path))
    topics_raw = raw.get("topics")
    if not isinstance(topics_raw, list) or not topics_raw:
        raise TopicConfigError("topics.yaml 至少需要一个 topic")
    topics = tuple(_parse_topic(item, index) for index, item in enumerate(topics_raw))
    ids = [item.id for item in topics]
    if len(set(ids)) != len(ids):
        raise TopicConfigError("topics.yaml 中 topic id 重复")
    topics = tuple(sorted(topics, key=lambda item: item.order))
    return raw, topics


def load_registry() -> dict[str, Any]:
    """Return ``{version, topics}`` with fresh specs (mtime-cached parse)."""
    try:
        stat = CONFIG_PATH.stat()
    except FileNotFoundError as exc:
        raise TopicConfigError(f"缺少配置文件：{CONFIG_PATH}") from exc
    raw, topics = _load_cached(str(CONFIG_PATH), stat.st_mtime_ns, _params_signature())
    version = _version_of(CONFIG_PATH)
    for topic in topics:
        params_path = PARAMS_DIR / f"{topic.id}.yaml"
        if params_path.exists():
            version = f"{version}-{_version_of(params_path)}"
    return {"version": version, "topics": list(topics), "raw": raw}


def list_topics(*, include_disabled: bool = False) -> list[TopicSpec]:
    topics = load_registry()["topics"]
    if include_disabled:
        return list(topics)
    return [item for item in topics if item.enabled]


def get_topic(topic_id: str) -> TopicSpec | None:
    return next((item for item in list_topics(include_disabled=True) if item.id == topic_id), None)


def config_version() -> str:
    return str(load_registry()["version"])


def topic_list_payload() -> dict[str, Any]:
    return {
        "data": [
            {
                "id": item.id,
                "label": item.label,
                "subtitle": item.subtitle,
                "asset": item.asset,
                "adapter": item.adapter,
                "order": item.order,
                "refresh_job": item.refresh_job,
                "sections": [
                    {
                        "id": section.id,
                        "label": section.label,
                        "kind": section.kind,
                        "anchor": section.anchor,
                        "order": section.order,
                        "enabled": section.enabled,
                    }
                    for section in item.sections
                    if section.enabled
                ],
            }
            for item in list_topics()
        ],
        "config_version": config_version(),
    }
