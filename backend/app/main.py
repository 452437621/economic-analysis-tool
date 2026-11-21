"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import (
    alerts,
    analytics,
    cycle,
    decisions,
    events,
    glassbox,
    gold,
    journal,
    knowledge,
    ledger,
    lenses,
    market,
    overview,
    system,
    theses,
    timeline,
    topics,
    trades,
    watchlist,
)
from app.platform import api_docs
from app.platform.config import ROOT_DIR, settings
from app.platform.db import SessionLocal, init_db
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
    # A run interrupted by the previous process would otherwise stay 'running'.
    from app.jobs.runner import reconcile_stale_runs

    reconcile_stale_runs(all_jobs=True)
    # 同理收尾中断的分析运行（analysis_runs 由 RunRecorder 自己写，jobs 对账管不到）。
    from app.provenance import reconcile_stale_analysis_runs

    with SessionLocal() as session:
        interrupted = reconcile_stale_analysis_runs(session, all=True)
        session.commit()
    if interrupted:
        logger.warning("marked %s interrupted analysis runs", interrupted)
    from app.jobs.supervisor import reconcile_stale_checks

    stale_checks = reconcile_stale_checks()
    if stale_checks:
        logger.warning("marked %s interrupted schedule checks", stale_checks)
    start_scheduler()
    if settings.env != "test":
        # 停机期间错过的作业在启动后由调度自检统一补跑（同步任务丢线程池，别阻塞事件循环）。
        app.state.catch_up_task = asyncio.create_task(_catch_up_after_startup())
    try:
        yield
    finally:
        task = getattr(app.state, "catch_up_task", None)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        stop_scheduler()


async def _catch_up_after_startup() -> None:
    """启动后做一次调度自检：先补数据，数据可用后再补研判/信号/简报。"""
    await asyncio.sleep(max(5, settings.schedule_startup_delay_seconds))
    from app.jobs.supervisor import ScheduleBusy, run_schedule_check

    try:
        report = await asyncio.to_thread(run_schedule_check, trigger="startup")
    except ScheduleBusy:
        logger.info("startup schedule check is already running")
        return
    except Exception:  # noqa: BLE001 - 补跑失败不能拖垮应用启动
        logger.exception("startup schedule check failed")
        return
    logger.info(
        "startup schedule check -> %s (data %s, executed %s)",
        report.get("status"),
        (report.get("readiness") or {}).get("status"),
        len(report.get("jobs") or []),
    )


app = FastAPI(
    title=f"{settings.app_name} - 个人市场分析工具",
    version=settings.app_version,
    lifespan=lifespan,
    # 默认 /docs 依赖 cdn.jsdelivr.net 的 swagger-ui 资源，受限网络下会白屏；
    # 改用 app/platform/api_docs.py 的本地自托管页面（见下方 /docs 路由）。
    docs_url=None,
    redoc_url=None,
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
app.include_router(glassbox.router)
app.include_router(cycle.router)
app.include_router(timeline.router)
app.include_router(ledger.router)
app.include_router(lenses.router)
app.include_router(topics.router)
app.include_router(trades.router)

if WEB_DIR.exists():
    assets_dir = WEB_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return _web_index()


@app.get("/docs", include_in_schema=False)
def api_docs_page() -> HTMLResponse:
    """本地自托管的接口文档（不依赖外部 CDN）。"""
    return HTMLResponse(api_docs.render_html(settings.app_name, settings.app_version))


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
            detail=(
                "前端尚未构建：请运行 build 脚本"
                "（scripts\\build.ps1、scripts\\build.cmd、./scripts/build.sh）"
                "或 python scripts/epic.py build"
            ),
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
