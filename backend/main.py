"""
FastAPI Application — Hermes Trading System.
"""

import logging
import sys
import traceback

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    from core.database import init_db, close_db
    from core.redis import init_redis, close_redis
    from services.backtest.batch_engine import BatchEngine
    from services.scheduler import scheduler_service

    await init_db()
    await init_redis()
    await BatchEngine.initialize()
    scheduler_service.start()
    try:
        await scheduler_service._load_jobs_from_db()
        logger.info("Loaded scheduled jobs from DB into APScheduler")
    except Exception as e:
        logger.warning(f"Could not load scheduled jobs from DB: {e}")
    print(f"🚀 Hermes Trading Dashboard started")
    yield
    await scheduler_service.stop()
    await BatchEngine.shutdown()
    await close_db()
    await close_redis()
    print("👋 Server shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hermes Trading Dashboard",
        debug=True,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Debug middleware to catch all errors
    @app.middleware("http")
    async def debug_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            print(f"[DEBUG] Exception during {request.method} {request.url.path}: {type(e).__name__}: {e}")
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"detail": str(e)})

    # Import and add auth middleware
    from middleware.auth import ApiKeyAuthMiddleware
    app.add_middleware(ApiKeyAuthMiddleware)

    # Root
    @app.get("/")
    async def root():
        return {"name": "Hermes Trading Dashboard", "version": "1.0.0", "docs": "/docs"}

    # Health check (no auth)
    from api.routes import health, auth
    app.include_router(health.router)
    app.include_router(auth.router)

    # Import all API routes
    from api.routes import (
        auth, strategies, backtest, portfolio, jobs, pairs, ai, export, risk, data,
        signals, scheduler, describe, notifications, execution, webhooks, data_quality,
        dashboard,
    )

    # API routes (each router has its own prefix="/api/v1/...")
    app.include_router(auth.router)
    app.include_router(strategies.router)
    app.include_router(webhooks.router)
    app.include_router(backtest.router)
    app.include_router(portfolio.router)
    app.include_router(jobs.router)
    app.include_router(pairs.router)
    app.include_router(ai.router)
    app.include_router(export.router)
    app.include_router(risk.router)
    app.include_router(data.router)
    app.include_router(signals.router)
    app.include_router(scheduler.router)
    app.include_router(describe.router)
    app.include_router(notifications.router)
    app.include_router(execution.router)
    app.include_router(webhooks.router)  # duplicate removed — now only once
    app.include_router(data_quality.router)
    app.include_router(dashboard.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=False)