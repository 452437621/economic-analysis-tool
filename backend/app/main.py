"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import (
    alerts,
    analytics,
    decisions,
    events,
    gold,
    journal,
    knowledge,
    market,
    overview,
    system,
    theses,
    watchlist,
)
from app.platform.config import ROOT_DIR, settings
from app.platform.db import init_db
from app.platform.logging import setup_logging
from app.platform.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)
WEB_DIR = ROOT_DIR / "web"
LEGACY_DIR = ROOT_DIR / "web-legacy"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_path)
    logger.info("starting %s %s (env=%s)", settings.app_name, settings.app_version, settings.env)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    from app.init_db import seed_instruments, seed_jobs

    seed_instruments()
    seed_jobs()
    # A run interrupted by the previous process would otherwise stay 'running'.
    from app.jobs.runner import reconcile_stale_runs

    reconcile_stale_runs(all_jobs=True)
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=f"{settings.app_name} - 个人市场分析工具",
    version=settings.app_version,
    lifespan=lifespan,
)
app.include_router(system.router)
app.include_router(overview.router)
app.include_router(gold.router)
app.include_router(market.router)
app.include_router(knowledge.router)
app.include_router(analytics.router)
app.include_router(decisions.router)
app.include_router(alerts.router)
app.include_router(journal.router)
app.include_router(theses.router)
app.include_router(events.router)
app.include_router(watchlist.router)

if WEB_DIR.exists():
    assets_dir = WEB_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return _web_index()


@app.get("/legacy", include_in_schema=False)
def legacy_index() -> FileResponse:
    """过渡期保留旧版零构建看板（web-legacy/index.html），V1.1 验收后删除。"""
    legacy = LEGACY_DIR / "index.html"
    if not legacy.exists():
        raise HTTPException(status_code=404, detail="legacy frontend not found")
    return FileResponse(legacy)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}


def _web_index() -> FileResponse:
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=503,
            detail="前端尚未构建：请运行 scripts\\build.ps1（或 npm run build）",
        )
    return FileResponse(index_file)


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str) -> FileResponse:
    """Vue SPA 回退：非 /api 路径统一返回 index.html，静态资源按文件命中。"""
    if full_path.startswith(("api/", "assets/")):
        raise HTTPException(status_code=404, detail="not found")
    candidate = (WEB_DIR / full_path).resolve()
    if full_path and candidate.is_file() and WEB_DIR.resolve() in candidate.parents:
        return FileResponse(candidate)
    return _web_index()
