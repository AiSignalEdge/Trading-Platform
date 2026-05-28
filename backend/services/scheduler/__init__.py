"""
APScheduler-based job scheduler service for Hermes Trading System.

Stores jobs in the `scheduled_jobs` database table and registers them
with APScheduler for execution. Jobs are managed via the Job CRUD API.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ExecutionRecord:
    """In-memory execution history record."""
    execution_id: str
    job_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str = "running"  # running | completed | failed
    result_summary: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status,
            "result_summary": self.result_summary,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# SchedulerService
# ---------------------------------------------------------------------------

class SchedulerService:
    """
    APScheduler-backed singleton scheduler service.

    Stores job definitions in the `scheduled_jobs` DB table and registers
    them with APScheduler. On job fire, dispatches to the appropriate engine
    based on job type. Sends webhook notifications on completion if configured.
    """

    _instance: Optional["SchedulerService"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60,
            },
        )
        self._history: dict[str, list[ExecutionRecord]] = {}
        self._started = False
        self._db_ready = False
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        """Register APScheduler event listeners for job completion/failure."""

        def on_job_executed(event):
            job_id = event.job_id.replace("apscheduler.", "")
            logger.info(f"Scheduled job completed: {job_id}")

        def on_job_error(event):
            job_id = event.job_id.replace("apscheduler.", "")
            logger.error(f"Scheduled job error: {job_id} — {event.exception}")

        self._scheduler.add_listener(
            on_job_executed,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
        )

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self):
        """Start the APScheduler event loop."""
        if not self._started:
            self._scheduler.start()
            self._started = True
            logger.info("SchedulerService started")

    async def stop(self):
        """Shutdown the scheduler gracefully."""
        if self._started:
            self._scheduler.shutdown(wait=True)
            self._started = False
            logger.info("SchedulerService stopped")

    # -------------------------------------------------------------------------
    # DB persistence helpers
    # -------------------------------------------------------------------------

    def _get_session(self):
        """Get an async DB session."""
        from core.database import async_session_factory
        return async_session_factory()

    async def _load_jobs_from_db(self):
        """Load all enabled jobs from DB into APScheduler."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import select

        async with self._get_session() as session:
            result = await session.execute(
                select(ScheduledJob).where(ScheduledJob.enabled == True)
            )
            jobs = result.scalars().all()
            for job in jobs:
                self._register_apscheduler_job(job)
            logger.info(f"Loaded {len(jobs)} enabled jobs from DB into APScheduler")

    def _register_apscheduler_job(self, db_job):
        """Register a DB job record with APScheduler."""
        trigger = self._build_trigger(db_job.trigger_type, db_job.trigger_config)
        job_id = db_job.id

        self._scheduler.add_job(
            self._execute_job,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs={"job_id": job_id},
        )

    def _build_trigger(self, trigger_type: str, trigger_config: dict):
        """Build an APScheduler trigger from trigger_type + trigger_config."""
        if trigger_type == "cron":
            return CronTrigger(
                minute=trigger_config.get("minute", "*"),
                hour=trigger_config.get("hour", "*"),
                day=trigger_config.get("day", "*"),
                month=trigger_config.get("month", "*"),
                day_of_week=trigger_config.get("day_of_week", "*"),
            )
        elif trigger_type == "interval":
            return IntervalTrigger(
                seconds=trigger_config.get("seconds") or 0,
                minutes=trigger_config.get("minutes") or 0,
                hours=trigger_config.get("hours") or 0,
            )
        elif trigger_type == "date":
            run_at = trigger_config.get("run_at")
            if run_at:
                return DateTrigger(run_at=datetime.fromisoformat(run_at.replace("Z", "+00:00")))
            return DateTrigger(run_at=datetime.now(timezone.utc))
        raise ValueError(f"Unknown trigger_type: {trigger_type}")

    async def _save_job_to_db(self, job_record: "JobDbRecord") -> "JobDbRecord":
        """Save a job record to the DB."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import select

        async with self._get_session() as session:
            existing = await session.execute(
                select(ScheduledJob).where(ScheduledJob.id == job_record.id)
            )
            db_job = existing.scalar_one_or_none()

            if db_job:
                # Update
                for key in ["name", "job_type", "payload", "trigger_type",
                            "trigger_config", "enabled", "next_run", "last_run",
                            "last_status", "run_count", "description"]:
                    val = getattr(job_record, key, None)
                    if val is not None:
                        setattr(db_job, key, val)
            else:
                # Insert
                db_job = ScheduledJob(
                    id=job_record.id,
                    name=job_record.name,
                    job_type=job_record.job_type,
                    payload=job_record.payload,
                    trigger_type=job_record.trigger_type,
                    trigger_config=job_record.trigger_config,
                    enabled=job_record.enabled,
                    created_at=job_record.created_at,
                    next_run=job_record.next_run,
                    last_run=job_record.last_run,
                    last_status=job_record.last_status,
                    run_count=job_record.run_count,
                    description=job_record.description,
                )
                session.add(db_job)

            await session.commit()
            return job_record

    async def _delete_job_from_db(self, job_id: str):
        """Delete a job from the DB."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import delete

        async with self._get_session() as session:
            await session.execute(
                delete(ScheduledJob).where(ScheduledJob.id == job_id)
            )
            await session.commit()

    # -------------------------------------------------------------------------
    # Job CRUD
    # -------------------------------------------------------------------------

    async def add_job(self, job_data: dict) -> dict:
        """
        Add a new scheduled job: save to DB and register with APScheduler.

        job_data keys:
            name, job_type, payload, trigger_type, trigger_config,
            enabled (default True), description (optional)
        """
        from models.scheduler_job import ScheduledJob

        job_id = f"job-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        trigger_type = job_data.get("trigger_type", "interval")
        trigger_config = job_data.get("trigger_config", {"seconds": 3600})
        enabled = job_data.get("enabled", True)

        # Compute next_run preview (rough estimate)
        next_run = self._estimate_next_run(trigger_type, trigger_config)

        record = JobDbRecord(
            id=job_id,
            name=job_data["name"],
            job_type=job_data["job_type"],
            payload=job_data.get("payload", {}),
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            enabled=enabled,
            created_at=now,
            next_run=next_run,
            description=job_data.get("description"),
        )

        await self._save_job_to_db(record)

        # Register with APScheduler if enabled
        if enabled:
            db_job = await self._get_db_job(job_id)
            if db_job:
                self._register_apscheduler_job(db_job)

        return record.to_dict()

    async def _get_db_job(self, job_id: str):
        """Fetch a job from DB by ID."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import select

        async with self._get_session() as session:
            result = await session.execute(
                select(ScheduledJob).where(ScheduledJob.id == job_id)
            )
            return result.scalar_one_or_none()

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get a single job by ID."""
        db_job = await self._get_db_job(job_id)
        if db_job:
            return self._db_job_to_dict(db_job)
        return None

    async def list_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List all jobs from DB."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import select

        async with self._get_session() as session:
            result = await session.execute(
                select(ScheduledJob)
                .order_by(ScheduledJob.created_at.desc())
                .offset(offset).limit(limit)
            )
            jobs = result.scalars().all()
            return [self._db_job_to_dict(j) for j in jobs]

    async def update_job(self, job_id: str, **fields) -> Optional[dict]:
        """Update a job: DB + reschedule in APScheduler."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import select

        async with self._get_session() as session:
            result = await session.execute(
                select(ScheduledJob).where(ScheduledJob.id == job_id)
            )
            db_job = result.scalar_one_or_none()

            if not db_job:
                return None

            # Apply field updates
            for key, val in fields.items():
                if val is not None and hasattr(db_job, key):
                    setattr(db_job, key, val)

            # Reschedule if trigger fields changed
            if "trigger_type" in fields or "trigger_config" in fields:
                self._remove_apscheduler_job(job_id)
                if db_job.enabled:
                    self._register_apscheduler_job(db_job)

            await session.commit()

            # Refetch to get updated state
            return self._db_job_to_dict(db_job)

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job from DB and APScheduler."""
        self._remove_apscheduler_job(job_id)
        await self._delete_job_from_db(job_id)
        if job_id in self._history:
            del self._history[job_id]
        return True

    def _db_job_to_dict(self, db_job) -> dict:
        """Convert a DB job record to a dict."""
        return {
            "job_id": db_job.id,
            "name": db_job.name,
            "job_type": db_job.job_type,
            "payload": db_job.payload,
            "trigger_type": db_job.trigger_type,
            "trigger_config": db_job.trigger_config,
            "enabled": db_job.enabled,
            "created_at": db_job.created_at.isoformat() if db_job.created_at else None,
            "next_run": db_job.next_run.isoformat() if db_job.next_run else None,
            "last_run": db_job.last_run.isoformat() if db_job.last_run else None,
            "last_status": db_job.last_status,
            "run_count": db_job.run_count,
            "description": db_job.description,
            "status": "scheduled" if db_job.enabled else "paused",
        }

    def _estimate_next_run(self, trigger_type: str, trigger_config: dict) -> Optional[datetime]:
        """Rough estimate of next run time for display."""
        if trigger_type == "interval":
            seconds = trigger_config.get("seconds", 0) or 0
            minutes = trigger_config.get("minutes", 0) or 0
            hours = trigger_config.get("hours", 0) or 0
            total_seconds = seconds + minutes * 60 + hours * 3600
            if total_seconds > 0:
                from datetime import timedelta
                return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=total_seconds)
        elif trigger_type == "cron":
            # Can't easily compute without croniter - return None
            pass
        return None

    def _remove_apscheduler_job(self, job_id: str):
        """Remove a job from APScheduler."""
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Job Execution
    # -------------------------------------------------------------------------

    async def _execute_job(self, job_id: str):
        """Execute a scheduled job from APScheduler."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import select, update

        db_job = await self._get_db_job(job_id)
        if not db_job:
            logger.warning(f"Scheduler execution for unknown job: {job_id}")
            return

        execution_id = f"exec-{uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        exec_record = ExecutionRecord(
            execution_id=execution_id,
            job_id=job_id,
            started_at=started_at,
            status="running",
        )
        if job_id not in self._history:
            self._history[job_id] = []
        self._history[job_id].append(exec_record)

        result_summary = None
        error_msg = None

        try:
            result_summary = await self._dispatch_execution(db_job)
            exec_record.status = "completed"
            exec_record.result_summary = result_summary

            # Update last_run, last_status, run_count
            async with self._get_session() as session:
                await session.execute(
                    update(ScheduledJob)
                    .where(ScheduledJob.id == job_id)
                    .values(
                        last_run=started_at,
                        last_status="success",
                        run_count=db_job.run_count + 1,
                        next_run=self._estimate_next_run(db_job.trigger_type, db_job.trigger_config),
                    )
                )
                await session.commit()

        except Exception as e:
            exec_record.status = "failed"
            error_msg = f"{type(e).__name__}: {e}"
            exec_record.error = error_msg
            logger.error(f"Job execution failed [{job_id}]: {error_msg}")

            async with self._get_session() as session:
                await session.execute(
                    update(ScheduledJob)
                    .where(ScheduledJob.id == job_id)
                    .values(
                        last_run=started_at,
                        last_status="failed",
                    )
                )
                await session.commit()

        finally:
            exec_record.finished_at = datetime.now(timezone.utc)

        # Send webhook if configured
        webhook_url = db_job.payload.get("webhook_url")
        if webhook_url:
            asyncio.create_task(self._send_webhook(webhook_url, exec_record, db_job))

        # Send Telegram/Discord notification if configured
        from services.notification_service import send_job_completion_notification
        asyncio.create_task(send_job_completion_notification(
            job_name=db_job.name,
            status=exec_record.status,
            duration_seconds=(exec_record.finished_at - exec_record.started_at).total_seconds() if exec_record.finished_at else None,
            error_message=exec_record.error,
        ))

    async def _dispatch_execution(self, db_job) -> str:
        """Dispatch execution to the appropriate engine based on job type."""
        job_type = db_job.job_type
        config = db_job.payload

        if job_type == "backtest":
            return await self._run_backtest(config)
        elif job_type == "portfolio":
            return await self._run_portfolio(config)
        elif job_type in ("walk-forward", "walk_forward"):
            return await self._run_walk_forward(config)
        elif job_type == "monte-carlo":
            return await self._run_monte_carlo(config)
        else:
            raise ValueError(f"Unknown job type: {job_type}")

    async def _run_backtest(self, config: dict) -> str:
        """Run a backtest via BacktestEngine."""
        from services.backtest.engine import BacktestEngine, BacktestConfig as EngineConfig
        from datetime import timedelta

        start_date = self._parse_date(config.get("start_date"))
        end_date = self._parse_date(config.get("end_date"))

        cfg = EngineConfig(
            strategy_name=config.get("strategy", "ma_cross"),
            symbols=config.get("pairs", ["BTC/USDT"]),
            timeframe=config.get("timeframe", "1h"),
            start_date=start_date,
            end_date=end_date,
            initial_cash=config.get("initial_capital", 10000.0),
            commission=config.get("commission", 0.0004),
            slippage=config.get("slippage", 0.0005),
            leverage=config.get("leverage", 1.0),
        )
        engine = BacktestEngine(cfg)
        results = await engine.run()

        if results:
            r = results[0]
            return f"total_return={float(r.total_return):.4f}, sharpe={float(r.sharpe_ratio):.2f}, trades={r.total_trades}"
        return "completed (no results)"

    async def _run_portfolio(self, config: dict) -> str:
        """Run portfolio optimization via PortfolioEngine."""
        from services.backtest.portfolio_engine import PortfolioEngine

        start_date = self._parse_date(config.get("start_date"))
        end_date = self._parse_date(config.get("end_date"))

        engine = PortfolioEngine(
            symbols=config.get("pairs", ["BTC/USDT", "ETH/USDT"]),
            start_date=start_date,
            end_date=end_date,
            initial_cash=config.get("initial_capital", 10000.0),
            rebalance_method=config.get("rebalance_method", "equal_weight"),
        )
        result = await engine.run()
        return f"portfolio completed — final_cash={result.get('final_cash', 'N/A')}"

    async def _run_walk_forward(self, config: dict) -> str:
        """Run walk-forward analysis via BacktestEngine with is_walk_forward=True."""
        from services.backtest.engine import BacktestEngine, BacktestConfig as EngineConfig

        start_date = self._parse_date(config.get("start_date"))
        end_date = self._parse_date(config.get("end_date"))

        cfg = EngineConfig(
            strategy_name=config.get("strategy", "ma_cross"),
            symbols=config.get("pairs", ["BTC/USDT"]),
            timeframe=config.get("timeframe", "1h"),
            start_date=start_date,
            end_date=end_date,
            initial_cash=config.get("initial_capital", 10000.0),
            commission=config.get("commission", 0.0004),
            slippage=config.get("slippage", 0.0005),
            leverage=config.get("leverage", 1.0),
            is_walk_forward=True,
            train_window_days=config.get("train_window_days", 30),
            test_window_days=config.get("test_window_days", 7),
        )
        engine = BacktestEngine(cfg)
        results = await engine.run()
        return f"walk_forward completed — {len(results)} window(s) analyzed"

    async def _run_monte_carlo(self, config: dict) -> str:
        """Run Monte Carlo simulation via BacktestEngine with n_runs."""
        from services.backtest.engine import BacktestEngine, BacktestConfig as EngineConfig

        start_date = self._parse_date(config.get("start_date"))
        end_date = self._parse_date(config.get("end_date"))

        cfg = EngineConfig(
            strategy_name=config.get("strategy", "ma_cross"),
            symbols=config.get("pairs", ["BTC/USDT"]),
            timeframe=config.get("timeframe", "1h"),
            start_date=start_date,
            end_date=end_date,
            initial_cash=config.get("initial_capital", 10000.0),
            commission=config.get("commission", 0.0004),
            slippage=config.get("slippage", 0.0005),
            leverage=config.get("leverage", 1.0),
            is_monte_carlo=True,
            n_runs=config.get("n_runs", 100),
        )
        engine = BacktestEngine(cfg)
        results = await engine.run()
        return f"monte_carlo completed — {len(results)} simulation(s)"

    def _parse_date(self, date_val):
        """Parse a date string or return default."""
        from dateutil.parser import parse as parse_date

        if isinstance(date_val, datetime):
            return date_val
        if not date_val:
            return datetime.now(timezone.utc) - timedelta(days=90)
        try:
            return parse_date(date_val)
        except Exception:
            return datetime.now(timezone.utc) - timedelta(days=90)

    # -------------------------------------------------------------------------
    # Manual trigger
    # -------------------------------------------------------------------------

    async def trigger_job(self, job_id: str) -> Optional[ExecutionRecord]:
        """Immediately trigger a job's execution, bypassing schedule."""
        from models.scheduler_job import ScheduledJob
        from sqlalchemy import update

        db_job = await self._get_db_job(job_id)
        if not db_job:
            return None

        execution_id = f"exec-{uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc).replace(tzinfo=None)

        exec_record = ExecutionRecord(
            execution_id=execution_id,
            job_id=job_id,
            started_at=started_at,
            status="running",
        )
        if job_id not in self._history:
            self._history[job_id] = []
        self._history[job_id].append(exec_record)

        result_summary = None
        error_msg = None

        try:
            result_summary = await self._dispatch_execution(db_job)
            exec_record.status = "completed"
            exec_record.result_summary = result_summary

            # Update last_run, last_status, run_count
            async with self._get_session() as session:
                await session.execute(
                    update(ScheduledJob)
                    .where(ScheduledJob.id == job_id)
                    .values(
                        last_run=started_at,
                        last_status="success",
                        run_count=db_job.run_count + 1,
                    )
                )
                await session.commit()

        except Exception as e:
            exec_record.status = "failed"
            error_msg = f"{type(e).__name__}: {e}"
            exec_record.error = error_msg

            async with self._get_session() as session:
                await session.execute(
                    update(ScheduledJob)
                    .where(ScheduledJob.id == job_id)
                    .values(
                        last_run=started_at,
                        last_status="failed",
                    )
                )
                await session.commit()

        finally:
            exec_record.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)

        webhook_url = db_job.payload.get("webhook_url")
        if webhook_url:
            asyncio.create_task(self._send_webhook(webhook_url, exec_record, db_job))

        return exec_record

    # -------------------------------------------------------------------------
    # Execution History
    # -------------------------------------------------------------------------

    def get_history(self, job_id: str, limit: int = 20) -> list[dict]:
        """Return execution history for a job."""
        records = self._history.get(job_id, [])
        sorted_records = sorted(records, key=lambda r: r.started_at, reverse=True)
        return [r.to_dict() for r in sorted_records[:limit]]

    # -------------------------------------------------------------------------
    # Webhook notification
    # -------------------------------------------------------------------------

    async def _send_webhook(self, url: str, exec_record: ExecutionRecord, db_job):
        """POST execution result to configured webhook URL."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    url,
                    json={
                        "job_id": db_job.id,
                        "job_name": db_job.name,
                        "execution_id": exec_record.execution_id,
                        "status": exec_record.status,
                        "result_summary": exec_record.result_summary,
                        "error": exec_record.error,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
        except Exception as e:
            logger.warning(f"Webhook notification failed for job {db_job.id}: {e}")

    # -------------------------------------------------------------------------
    # APScheduler proxy methods
    # -------------------------------------------------------------------------

    def pause_job(self, job_id: str):
        """Pause a scheduled job in APScheduler."""
        try:
            self._scheduler.pause_job(job_id)
        except Exception:
            pass

    def resume_job(self, job_id: str):
        """Resume a paused job in APScheduler."""
        try:
            self._scheduler.resume_job(job_id)
        except Exception:
            pass

    def get_jobs(self) -> list:
        """Return list of APScheduler job info."""
        return self._scheduler.get_jobs()


# ---------------------------------------------------------------------------
# Db-backed job record (for internal use)
# ---------------------------------------------------------------------------

@dataclass
class JobDbRecord:
    """Internal job record matching the DB schema."""
    id: str
    name: str
    job_type: str
    payload: dict
    trigger_type: str
    trigger_config: dict
    enabled: bool
    created_at: datetime
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    run_count: int = 0
    description: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.id,
            "name": self.name,
            "job_type": self.job_type,
            "payload": self.payload,
            "trigger_type": self.trigger_type,
            "trigger_config": self.trigger_config,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_status": self.last_status,
            "run_count": self.run_count,
            "description": self.description,
            "status": "scheduled" if self.enabled else "paused",
        }


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

scheduler_service = SchedulerService()