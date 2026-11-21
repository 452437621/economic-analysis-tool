"""Topic research framework: config, scoring, storage and adapters."""

from __future__ import annotations

import importlib
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.topics.config import TopicSpec, TopicConfigError, TopicSection

# adapter name -> "module:function".  Imports stay lazy so the API can start
# without loading pandas-heavy analysis modules.
ADAPTERS: dict[str, str] = {
    "gold": "app.topics.gold:build_overview",
    "luoyang": "app.topics.luoyang:build_overview",
}


class TopicAdapterMissing(LookupError):
    pass


def _resolve(adapter: str) -> Callable[..., dict[str, Any]]:
    target = ADAPTERS.get(adapter)
    if not target:
        raise TopicAdapterMissing(f"未注册的研判适配器：{adapter}")
    module_name, func_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def build_overview(spec: TopicSpec, session: Session, **kwargs: Any) -> dict[str, Any]:
    builder = _resolve(spec.adapter)
    return builder(spec, session, **kwargs)


__all__ = [
    "ADAPTERS",
    "TopicAdapterMissing",
    "TopicConfigError",
    "TopicSection",
    "TopicSpec",
    "build_overview",
]
