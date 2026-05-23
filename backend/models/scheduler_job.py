"""
Scheduled Jobs Model — APScheduler-backed job definitions stored in DB.

Maps to the `scheduled_jobs` table created via migration.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ScheduledJob(Base):
    """
    SQLAlchemy model for scheduled jobs.

    Stores job definitions that are loaded into APScheduler at startup
    and at runtime via the Job CRUD API.
    """

    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"job-{uuid4().hex[:12]}",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # "backtest" | "walk-forward" | "portfolio" | "monte-carlo" | "custom"
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )  # the config dict
    trigger_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # "cron" | "interval" | "date"
    trigger_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )  # cron expr or interval seconds
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    next_run: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    last_run: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    last_status: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
    )  # "success" | "failed" | None
    run_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
    )

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
        }