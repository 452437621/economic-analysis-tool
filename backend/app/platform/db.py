"""Database engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
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


def _ensure_light_migrations() -> None:
    """Small additive migrations for SQLite (no Alembic in this single-user app)."""
    if not settings.db_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(watchlist)"))}
        if not columns or "sort_order" in columns:
            return
        conn.execute(
            text("ALTER TABLE watchlist ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
        )
        rows = conn.execute(
            text("SELECT id FROM watchlist ORDER BY priority ASC, id ASC")
        ).all()
        for index, row in enumerate(rows):
            conn.execute(
                text("UPDATE watchlist SET sort_order = :order WHERE id = :id"),
                {"order": index, "id": row[0]},
            )


def init_db() -> None:
    """Create all tables for the current schema (Alembic takes over in M1)."""
    import app.models.core  # noqa: F401  (register models)

    Base.metadata.create_all(engine)
    _ensure_light_migrations()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
