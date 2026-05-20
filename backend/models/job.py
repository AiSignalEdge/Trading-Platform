"""
Automated Jobs Model - Section 5 Database Schema from PLAN-v2.md

Includes: automated_jobs
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.user import User


class AutomatedJob(Base):
    """Automated backtest job model for scheduling."""
    
    __tablename__ = "automated_jobs"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    backtest_config_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    schedule: Mapped[str] = mapped_column(
        String(100),
        default="0 0 * * *",  # Default: daily at midnight
    )
    params: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        index=True,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    total_runs: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    last_run_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    last_result_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(
        String(255),
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "backtest_config_id": str(self.backtest_config_id),
            "schedule": self.schedule,
            "params": self.params,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "total_runs": self.total_runs,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_result_id": str(self.last_result_id) if self.last_result_id else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


class MarketRegime(Base):
    """Market regime analysis results."""
    
    __tablename__ = "market_regimes"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    pair: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    regime: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    trend_strength: Mapped[float] = mapped_column(
        default=0.0,
    )
    volatility_rank: Mapped[float] = mapped_column(
        default=0.0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "pair": self.pair,
            "timeframe": self.timeframe,
            "date": self.date.isoformat() if self.date else None,
            "regime": self.regime,
            "trend_strength": self.trend_strength,
            "volatility_rank": self.volatility_rank,
            "created_at": self.created_at.isoformat(),
        }