"""Database engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

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
            # 报价任务每分钟写一次，而其它任务/并发请求也会写；SQLite 是单写者，
            # 遇到短暂写锁时宁可等（默认 5s 常常不够，会把这一分钟整轮丢掉）。
            cursor.execute("PRAGMA busy_timeout=20000")
            # 多行 UPSERT 会触发 SQLite 临时文件；在 Windows + 受限环境下列表目录
            # 探测可能失败（SQLITE_CANTOPEN），改为内存临时存储最稳妥。
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

    return engine


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)

LEGACY_ENABLE_JOBS = (
    "collect_daily_bars",
    "collect_rates",
    "brief_premarket",
    "brief_postmarket",
)


def _migration_applied(conn, name: str) -> bool:
    conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS app_migrations ("
            "name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
    )
    return conn.execute(text("SELECT 1 FROM app_migrations WHERE name = :n"), {"n": name}).first() is not None


def _mark_migration(conn, name: str) -> None:
    conn.execute(
        text("INSERT OR IGNORE INTO app_migrations (name, applied_at) VALUES (:n, :t)"),
        {"n": name, "t": datetime.now(timezone.utc).isoformat()},
    )


def _migrate_watchlist_sort_order(conn) -> None:
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(watchlist)"))}
    if not columns or "sort_order" in columns:
        return
    conn.execute(text("ALTER TABLE watchlist ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"))
    rows = conn.execute(text("SELECT id FROM watchlist ORDER BY priority ASC, id ASC")).all()
    for index, row in enumerate(rows):
        conn.execute(
            text("UPDATE watchlist SET sort_order = :order WHERE id = :id"),
            {"order": index, "id": row[0]},
        )


def _migrate_enable_legacy_jobs(conn) -> None:
    """Old seeds left scheduler jobs disabled while the scheduler ignored the flag.

    Now that ``Job.enabled`` is authoritative, one-time enable those rows so a
    fresh install and an upgraded install behave the same. Later operator
    toggles are preserved because this migration only ever runs once.
    """
    placeholders = ", ".join(f":n{i}" for i in range(len(LEGACY_ENABLE_JOBS)))
    params = {f"n{i}": name for i, name in enumerate(LEGACY_ENABLE_JOBS)}
    conn.execute(
        text(f"UPDATE jobs SET enabled = 1 WHERE enabled = 0 AND name IN ({placeholders})"), params
    )


def _migrate_calendar_event_values(conn) -> None:
    """Add nullable consensus/actual columns to the economic calendar (UI alignment A7)."""
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(economic_events)"))}
    if not columns:
        return
    additions = (
        ("forecast", "FLOAT"),
        ("previous", "FLOAT"),
        ("actual", "FLOAT"),
        ("unit", "VARCHAR(20)"),
    )
    for name, sql_type in additions:
        if name in columns:
            continue
        conn.execute(text(f"ALTER TABLE economic_events ADD COLUMN {name} {sql_type}"))


def _migrate_jobs_description(conn) -> None:
    """Add the operator-facing ``jobs.description`` column (系统状态 任务描述列)."""
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(jobs)"))}
    if not columns or "description" in columns:
        return
    conn.execute(text("ALTER TABLE jobs ADD COLUMN description TEXT"))


def _migrate_data_check_fields(conn) -> None:
    """Add structured QC/remediation fields to existing ``data_checks`` rows."""
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(data_checks)"))}
    if not columns:
        return
    for name, sql_type in (
        ("batch_id", "VARCHAR(32)"),
        ("severity", "VARCHAR(16)"),
        ("cause", "TEXT"),
        ("impact", "TEXT"),
        ("remediation", "TEXT"),
        ("action_job", "VARCHAR(80)"),
    ):
        if name not in columns:
            conn.execute(text(f"ALTER TABLE data_checks ADD COLUMN {name} {sql_type}"))


def _migrate_operational_indexes(conn) -> None:
    """Indexes used by the scheduler, QC batches and source health panels."""
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_job_runs_job_started ON job_runs(job_name, started_at)")
    )
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_source_health_source_ts ON source_health(source_id, ts)")
    )
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_data_checks_batch ON data_checks(batch_id, check_date)")
    )


MIGRATIONS = (
    ("watchlist.sort_order", _migrate_watchlist_sort_order),
    ("jobs.enable_legacy_scheduler_jobs", _migrate_enable_legacy_jobs),
    ("economic_events.forecast_values", _migrate_calendar_event_values),
    ("jobs.description", _migrate_jobs_description),
    ("data_checks.remediation_fields", _migrate_data_check_fields),
    ("operational.indexes", _migrate_operational_indexes),
)


def _ensure_light_migrations() -> None:
    """Small, idempotent, additive migrations (single-user app, no Alembic runtime)."""
    if not settings.db_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        for name, migration in MIGRATIONS:
            if _migration_applied(conn, name):
                continue
            migration(conn)
            _mark_migration(conn, name)


def init_db() -> None:
    """Create all tables for the current schema (Alembic takes over in M1)."""
    import app.models.core  # noqa: F401  (register models)
    import app.models.v2  # noqa: F401  (register V2.0 glassbox/cycle tables)

    Base.metadata.create_all(engine)
    _ensure_light_migrations()
    from app.provenance.methods import ensure_methods

    with SessionLocal() as session:
        ensure_methods(session)
        session.commit()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
