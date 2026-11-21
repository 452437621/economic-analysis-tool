"""Shared test helpers: isolated databases, API clients and provider fakes."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
WORKSPACE_TEST_DATA = ROOT / "data" / "test"


def _register_models() -> None:
    """Import every model module so Base.metadata is complete."""
    import app.models  # noqa: F401
    import app.models.v2  # noqa: F401


def make_db(
    tmp_path: Path,
    name: str = "test.db",
) -> tuple[Any, sessionmaker]:
    """Create an isolated SQLite engine + session factory with the full schema."""
    _register_models()
    from app.models.base import Base

    path = Path(tmp_path) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    return engine, factory


def memory_db() -> tuple[Any, sessionmaker]:
    """In-memory SQLite with StaticPool (single connection, no repo writes)."""
    from sqlalchemy.pool import StaticPool

    _register_models()
    from app.models.base import Base

    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    return engine, factory


@contextmanager
def api_client(factory: sessionmaker) -> Iterator[Any]:
    """TestClient with ``get_session`` overridden to an isolated session factory."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.platform.db import get_session

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


class FakeResponse:
    """Minimal httpx-like response used by provider parser tests."""

    def __init__(
        self,
        text: str = "",
        *,
        status_code: int = 200,
        json_data: Any = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self._json = json_data
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = headers or {}

    def json(self) -> Any:
        if self._json is not None:
            return self._json
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeClient:
    """Queue of responses; records calls. Matches the HttpClient subset used by providers."""

    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[tuple[tuple, dict]] = []

    def _next(self, *args, **kwargs) -> FakeResponse:
        self.calls.append((args, kwargs))
        if not self.responses:
            raise AssertionError("FakeClient has no response queued")
        return self.responses.pop(0)

    def get(self, *args, **kwargs) -> FakeResponse:
        return self._next(*args, **kwargs)

    def post(self, *args, **kwargs) -> FakeResponse:
        return self._next(*args, **kwargs)

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def read_fixture(relative: str) -> str:
    return (Path(__file__).parent / "fixtures" / relative).read_text(encoding="utf-8")


def workspace_db(name: str) -> tuple[Any, sessionmaker]:
    """Create an isolated DB under the git-ignored workspace data/test directory."""
    target = WORKSPACE_TEST_DATA / name
    if target.exists():
        target.unlink()
    return make_db(target.parent, target.name)


__all__ = [
    "ROOT",
    "BACKEND",
    "WORKSPACE_TEST_DATA",
    "FakeClient",
    "FakeResponse",
    "api_client",
    "make_db",
    "memory_db",
    "read_fixture",
    "workspace_db",
]
