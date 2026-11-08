"""Database engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.platform.config import settings


def _create_engine():
    url = settings.db_url
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            # 多行 UPSERT 会触发 SQLite 临时文件；在 Windows + 受限环境下列表目录
            # 探测可能失败（SQLITE_CANTOPEN），改为内存临时存储最稳妥。
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

    return engine


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_db() -> None:
    """Create all tables for the current schema (Alembic takes over in M1)."""
    import app.models.core  # noqa: F401  (register models)

    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
