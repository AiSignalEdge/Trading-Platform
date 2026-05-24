"""
FastAPI Application — Hermes Trading System.
"""

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from middleware.auth import ApiKeyAuthMiddleware

from core.config import settings
from core.database import init_db, close_db
from core.redis import init_redis, close_redis
from services.backtest.batch_engine import BatchEngine
from services.scheduler import scheduler_service

# API Routes
from api.routes import strategies, backtest, portfolio, jobs, pairs, auth, ai, export, risk, health, data, websocket as ws_routes, signals, scheduler, describe, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    await init_db()
    await init_redis()
    await BatchEngine.initialize()
    scheduler_service.start()
    # Load all enabled jobs from DB into APScheduler
    try:
        await scheduler_service._load_jobs_from_db()
        logger.info("Loaded scheduled jobs from DB into APScheduler")
    except Exception as e:
        logger.warning(f"Could not load scheduled jobs from DB: {e}")
    print(f"🚀 {settings.app_name} started")
    yield
    await scheduler_service.stop()
    await BatchEngine.shutdown()
    await close_db()
    await close_redis()
    print("👋 Server shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
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

    # API Key Auth
    app.add_middleware(ApiKeyAuthMiddleware)

    # Root
    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    # Health check (no auth)
    app.include_router(health.router)

    # Auth routes (no auth)
    app.include_router(auth.router)

    # API v1 routes
    app.include_router(strategies.router)
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
    app.include_router(ws_routes.router, prefix="/ws", tags=["websocket"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=settings.debug)