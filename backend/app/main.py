"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import analytics, knowledge, market, system
from app.platform.config import ROOT_DIR, settings
from app.platform.db import init_db
from app.platform.logging import setup_logging
from app.platform.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)
WEB_DIR = ROOT_DIR / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_path)
    logger.info("starting %s %s (env=%s)", settings.app_name, settings.app_version, settings.env)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    from app.init_db import seed_instruments, seed_jobs

    seed_instruments()
    seed_jobs()
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
app.include_router(market.router)
app.include_router(knowledge.router)
app.include_router(analytics.router)

if WEB_DIR.exists():
    assets_dir = WEB_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}
