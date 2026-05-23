"""
Notification Routes - Send test notifications and manage notification history.

POST /api/v1/notifications/test - Send a test notification
GET /api/v1/notifications - List notification history
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from core.database import get_db
from core.config import settings
from models.notification import Notification
from services.notification_service import (
    send_telegram_message,
    send_discord_webhook,
    NotificationType,
    NotificationStatus,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

logger = logging.getLogger(__name__)


# ====================
# Pydantic Schemas
# ====================

class NotificationTestRequest(BaseModel):
    """Request to send a test notification."""
    message: str = "This is a test notification from Hermes Trading Dashboard"
    notification_type: str = "telegram"  # "telegram" or "discord"


class NotificationResponse(BaseModel):
    """Response for notification operations."""
    id: str
    notification_type: str
    destination: str
    message: str
    status: str
    created_at: str
    last_sent_at: Optional[str] = None
    
    class Config:
        from_attributes = True


# ====================
# Routes
# ====================

@router.post("/test")
async def test_notification(
    request: NotificationTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a test notification to verify configuration.
    
    Accepts a message and notification type, sends it, and records
    the result in the notifications table.
    """
    notification_id = uuid4()
    now = datetime.utcnow()
    
    # Store the notification record
    notification = Notification(
        id=notification_id,
        notification_type=request.notification_type,
        destination="test",
        message=request.message,
        status="pending",
        created_at=now,
    )
    db.add(notification)
    await db.flush()
    
    try:
        if request.notification_type == "telegram":
            if not settings.telegram_bot_token or not settings.telegram_chat_id:
                raise HTTPException(
                    status_code=400,
                    detail="Telegram not configured: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required"
                )
            
            result = await send_telegram_message(
                text=request.message,
                chat_id=settings.telegram_chat_id,
                bot_token=settings.telegram_bot_token,
            )
            
            notification.status = result.get("status", NotificationStatus.SENT)
            notification.destination = result.get("chat_id", settings.telegram_chat_id)
            notification.last_sent_at = datetime.utcnow()
            
        elif request.notification_type == "discord":
            if not settings.discord_webhook_url:
                raise HTTPException(
                    status_code=400,
                    detail="Discord not configured: DISCORD_WEBHOOK_URL required"
                )
            
            result = await send_discord_webhook(
                text=request.message,
                webhook_url=settings.discord_webhook_url,
            )
            
            notification.status = result.get("status", NotificationStatus.SENT)
            notification.destination = "discord_webhook"
            notification.last_sent_at = datetime.utcnow()
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown notification type: {request.notification_type}. Use 'telegram' or 'discord'"
            )
        
        await db.commit()
        
        logger.info(f"Test notification sent successfully via {request.notification_type}")
        
        return {
            "success": True,
            "notification_id": str(notification_id),
            "type": request.notification_type,
            "status": notification.status,
            "message": "Notification sent successfully",
        }
        
    except Exception as e:
        logger.error(f"Failed to send test notification: {e}")
        notification.status = NotificationStatus.FAILED
        notification.error_message = str(e)
        await db.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send notification: {str(e)}"
        )


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    notification_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    List notification history with optional filtering.
    """
    query = select(Notification).order_by(desc(Notification.created_at))
    
    if notification_type:
        query = query.where(Notification.notification_type == notification_type)
    
    if status:
        query = query.where(Notification.status == status)
    
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return [
        NotificationResponse(
            id=str(n.id),
            notification_type=n.notification_type,
            destination=n.destination,
            message=n.message,
            status=n.status,
            created_at=n.created_at.isoformat() if n.created_at else "",
            last_sent_at=n.last_sent_at.isoformat() if n.last_sent_at else None,
        )
        for n in notifications
    ]