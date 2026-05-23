"""
Notification Model - Database table for notification history.

Stores sent notifications to Telegram and Discord.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, DateTime, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Notification(Base):
    """Notification history model."""
    
    __tablename__ = "notifications"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    notification_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    destination: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    last_sent_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "notification_type": self.notification_type,
            "destination": self.destination,
            "message": self.message,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_sent_at": self.last_sent_at.isoformat() if self.last_sent_at else None,
        }