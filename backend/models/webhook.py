"""
Webhook Model - Database table for webhook configurations.

Stores webhook subscriptions for event notifications.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, DateTime, Boolean, Text, ARRAY, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Webhook(Base):
    """Webhook subscription model."""

    __tablename__ = "webhooks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        default="",
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    event_types: Mapped[list] = mapped_column(
        ARRAY(String),
        nullable=False,
    )
    secret: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "url": self.url,
            "event_types": self.event_types,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "consecutive_failures": self.consecutive_failures,
        }