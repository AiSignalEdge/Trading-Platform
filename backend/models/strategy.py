"""
Strategy Models - Section 5 Database Schema from PLAN-v2.md

Includes: strategies, strategy_versions
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, DateTime, Integer, Float, Boolean, Text, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Strategy(Base):
    """Strategy model."""
    
    __tablename__ = "strategies"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    author: Mapped[str] = mapped_column(
        String(255),
        default="",
    )
    current_version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    strategy_type: Mapped[str] = mapped_column(
        String(50),
        default="momentum",
        index=True,
    )
    asset_class: Mapped[str] = mapped_column(
        String(50),
        default="crypto",
    )
    pairs: Mapped[list] = mapped_column(
        ARRAY(String),
        default=list,
    )
    timeframes: Mapped[list] = mapped_column(
        ARRAY(String),
        default=list,
    )
    tags: Mapped[list] = mapped_column(
        ARRAY(String),
        default=list,
    )
    rating: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )
    backtest_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    parameters: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )
    pine_script: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    
    # Relationships
    versions = relationship("StrategyVersion", back_populates="strategy", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "current_version_id": str(self.current_version_id) if self.current_version_id else None,
            "strategy_type": self.strategy_type,
            "asset_class": self.asset_class,
            "pairs": self.pairs,
            "timeframes": self.timeframes,
            "tags": self.tags,
            "rating": self.rating,
            "backtest_count": self.backtest_count,
            "is_public": self.is_public,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class StrategyVersion(Base):
    """Strategy version model for versioning support."""
    
    __tablename__ = "strategy_versions"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    strategy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    parameters: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )
    pine_script: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(
        String(255),
        default="",
    )
    changelog: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    
    # Relationships
    strategy = relationship("Strategy", back_populates="versions")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "strategy_id": str(self.strategy_id),
            "version": self.version,
            "parameters": self.parameters,
            "pine_script": self.pine_script,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "changelog": self.changelog,
        }