"""
User Model - Section 5 Database Schema from PLAN-v2.md
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class UserPlan(str):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    """User model for authentication and preferences."""
    
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    username: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    plan: Mapped[str] = mapped_column(
        String(50),
        default=UserPlan.FREE,
    )
    telegram_chat_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    notification_prefs: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    
    # Relationships
    backtest_configs = relationship("BacktestConfig", back_populates="owner")
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "plan": self.plan,
            "telegram_chat_id": self.telegram_chat_id,
            "notification_prefs": self.notification_prefs,
            "created_at": self.created_at.isoformat(),
        }