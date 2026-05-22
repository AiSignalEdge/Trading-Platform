"""
Batch Backtest Engine — in-memory job queue with optional Redis pub/sub.

Architecture
============
- Jobs stored in class-level dict (_jobs) for fast in-process access.
- Optional Redis pub/sub for cross-process notification.
- Background asyncio worker processes queued jobs.
- No external task queue (Celery) required — pure async in-process worker.

Usage
=====
from services.backtest.batch_engine import BatchEngine

await BatchEngine.initialize()            # start worker
job = await BatchEngine.enqueue_batch(...)  # enqueue
BatchEngine.get_job(job.job_id)           # poll status
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

import pandas as pd

from services.backtest.engine import BacktestEngine, BacktestConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and dataclasses
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchConfigItem:
    """A single backtest config within a batch job."""

    def __init__(
        self,
        id: str,
        name: str,
        strategy: str,
        pair: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_cash: float = 10000.0,
        commission: float = 0.0004,
        slippage: float = 0.0005,
        leverage: float = 1.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy_params: Optional[dict] = None,
        is_walk_forward: bool = False,
        train_window_days: int = 30,
        test_window_days: int = 7,
    ):
        self.id = id
        self.name = name
        self.strategy = strategy
        self.pair = pair
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage
        self.leverage = leverage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.strategy_params = strategy_params or {}
        self.is_walk_forward = is_walk_forward
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days

    @classmethod
    def from_dict(cls, data: dict) -> "BatchConfigItem":
        """Parse from dict (API request)."""
        from uuid import uuid4
        return cls(
            id=data.get("id", f"cfg-{uuid4().hex[:8]}"),
            name=data.get("name", "Config"),
            strategy=data.get("strategy", "ma_cross"),
            pair=data["pair"],
            timeframe=data["timeframe"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            initial_cash=data.get("initial_cash", 10000.0),
            commission=data.get("commission", 0.0004),
            slippage=data.get("slippage", 0.0005),
            leverage=data.get("leverage", 1.0),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            strategy_params=data.get("strategy_params"),
            is_walk_forward=data.get("is_walk_forward", False),
            train_window_days=data.get("train_window_days", 30),
            test_window_days=data.get("test_window_days", 7),
        )


class BatchJob:
    """A batch job holding individual config results."""

    def __init__(
        self,
        job_id: str,
        name: str,
        created_at: datetime,
        status: JobStatus,
        total: int,
        completed: int = 0,
        failed: int = 0,
        progress_pct: float = 0.0,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        results: Optional[list] = None,
        configs: Optional[list] = None,
    ):
        self.job_id = job_id
        self.name = name
        self.created_at = created_at
        self.status = status
        self.total = total
        self.completed = completed
        self.failed = failed
        self.progress_pct = progress_pct
        self.error = error
        self.started_at = started_at
        self.completed_at = completed_at
        self.results = results if results is not None else []
        self.configs = configs if configs is not None else []

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "status": self.status.value,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "progress_pct": self.progress_pct,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ---------------------------------------------------------------------------
# BatchEngine
# ---------------------------------------------------------------------------

class BatchEngine:
    """
    In-memory batch job manager with optional Redis pub/sub.

    Jobs live in a class-level dict so they persist across requests within
    the same process. Results are stored inline in each BatchJob.
    """

    _jobs: dict[str, BatchJob] = {}
    _redis: Optional["redis.Redis"] = None
    _worker_task: Optional[asyncio.Task] = None
    _redis_url: Optional[str] = None

    @classmethod
    async def initialize(cls, redis_url: str = "redis://localhost:6379/0"):
        """Initialize Redis connection and start background queue worker."""
        cls._redis_url = redis_url
        try:
            import redis
            cls._redis = redis.from_url(redis_url, decode_responses=True)
            await cls._redis.ping()
            logger.info("BatchEngine Redis connected")
        except Exception as e:
            logger.warning(f"BatchEngine Redis unavailable, running without pub/sub: {e}")
            cls._redis = None

        if cls._worker_task is None:
            cls._worker_task = asyncio.create_task(cls._process_queue_loop())
            logger.info("BatchEngine background worker started")

    @classmethod
    async def shutdown(cls):
        if cls._worker_task:
            cls._worker_task.cancel()
            try:
                await cls._worker_task
            except asyncio.CancelledError:
                pass
        if cls._redis:
            await cls._redis.close()

    @classmethod
    async def enqueue_batch(
        cls,
        name: str,
        configs: list[BatchConfigItem],
    ) -> BatchJob:
        """Create and enqueue a new batch job. Returns immediately (async)."""
        job_id = f"batch-{uuid4().hex[:12]}"

        job = BatchJob(
            job_id=job_id,
            name=name,
            created_at=datetime.now(timezone.utc),
            status=JobStatus.QUEUED,
            total=len(configs),
            configs=configs,
        )
        cls._jobs[job_id] = job

        if cls._redis:
            try:
                await cls._redis.publish(
                    "batch:jobs",
                    json.dumps({"type": "enqueue", "job_id": job_id})
                )
            except Exception:
                pass

        return job

    @classmethod
    async def _process_queue_loop(cls):
        """Background worker: pick up queued jobs and process them."""
        while True:
            try:
                queued = [j for j in cls._jobs.values() if j.status == JobStatus.QUEUED]
                if queued:
                    job = queued[0]
                    await cls._run_batch_job(job.job_id)
                else:
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    @classmethod
    async def _run_batch_job(cls, job_id: str):
        """Process a single batch job — run each BacktestConfigItem sequentially."""
        job = cls._jobs.get(job_id)
        if not job:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)

        try:
            for i, cfg_item in enumerate(job.configs):
                try:
                    # Ensure dates are datetime objects (they may be strings from API layer)
                    start_date = cfg_item.start_date
                    end_date = cfg_item.end_date
                    if isinstance(start_date, str):
                        from dateutil.parser import parse as parse_date
                        start_date = parse_date(start_date)
                    if isinstance(end_date, str):
                        from dateutil.parser import parse as parse_date
                        end_date = parse_date(end_date)

                    cfg = BacktestConfig(
                        strategy_name=cfg_item.strategy,
                        symbols=[cfg_item.pair],
                        timeframe=cfg_item.timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        initial_cash=cfg_item.initial_cash,
                        commission=cfg_item.commission,
                        slippage=cfg_item.slippage,
                        leverage=cfg_item.leverage,
                        stop_loss=cfg_item.stop_loss,
                        take_profit=cfg_item.take_profit,
                        is_walk_forward=cfg_item.is_walk_forward,
                        train_window_days=cfg_item.train_window_days,
                        test_window_days=cfg_item.test_window_days,
                    )
                    engine = BacktestEngine(cfg)
                    results = await engine.run()

                    if results:
                        r = results[0]
                        job.results.append({
                            "config_id": cfg_item.id,
                            "name": cfg_item.name,
                            "symbol": cfg_item.pair,
                            "timeframe": cfg_item.timeframe,
                            "total_return": float(r.total_return * 100),
                            "total_return_pct": float(r.total_return_pct),
                            "sharpe_ratio": float(r.sharpe_ratio),
                            "max_drawdown_pct": float(r.max_drawdown_pct),
                            "total_trades": int(r.total_trades),
                            "win_rate": float(r.win_rate),
                            "profit_factor": float(r.profit_factor),
                        })
                        job.completed += 1
                    else:
                        # No results = data unavailable or strategy produced nothing
                        job.failed += 1
                        job.error = f"No results for config {cfg_item.id} ({cfg_item.pair}, {cfg_item.timeframe}) — check data availability"
                        logger.warning(job.error)

                    job.progress_pct = float(job.completed / job.total * 100) if job.total > 0 else 0.0

                except Exception as e:
                    job.failed += 1
                    job.error = f"{type(e).__name__}: {e}"
                    logger.error(f"Batch item error: {job.error}")

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = f"{type(e).__name__}: {e}"
            job.completed_at = datetime.now(timezone.utc)
            logger.error(f"Batch job failed: {job.error}")

    @classmethod
    async def get_results(cls, job_id: str, page: int = 1, page_size: int = 50) -> dict:
        """Return paginated results for a batch job."""
        job = cls._jobs.get(job_id)
        if not job:
            return {"found": False, "total": 0, "items": [], "page": page, "page_size": page_size}

        all_results = getattr(job, "results", [])
        total = len(all_results)
        start = (page - 1) * page_size
        end = start + page_size
        items = all_results[start:end]

        return {
            "found": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    @classmethod
    def get_job(cls, job_id: str) -> Optional[BatchJob]:
        return cls._jobs.get(job_id)

    @classmethod
    def list_jobs(cls, limit: int = 20) -> list[dict]:
        jobs = sorted(cls._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]