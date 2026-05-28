"""
Webhook Routes - Webhook subscription management and event delivery.

POST /api/v1/webhooks/test - Test webhook delivery (echo back payload)
GET /api/v1/webhooks - List configured webhooks
POST /api/v1/webhooks - Create a webhook (url, event_types: list, secret)
DELETE /api/v1/webhooks/{webhook_id} - Delete a webhook
POST /api/v1/webhooks/{webhook_id}/trigger - Manually trigger a webhook

Webhook Event Types:
- backtest.completed
- backtest.failed
- signal.generated
- position.opened
- position.closed
"""

import logging
import hmac
import hashlib
import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from core.database import get_db
from models.webhook import Webhook

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

logger = logging.getLogger(__name__)


# ============================================
# Webhook Event Types
# ============================================

class WebhookEventType:
    """Webhook event type constants."""
    BACKTEST_COMPLETED = "backtest.completed"
    BACKTEST_FAILED = "backtest.failed"
    SIGNAL_GENERATED = "signal.generated"
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"

    ALL = [
        BACKTEST_COMPLETED,
        BACKTEST_FAILED,
        SIGNAL_GENERATED,
        POSITION_OPENED,
        POSITION_CLOSED,
    ]


# ============================================
# Pydantic Schemas
# ============================================

class WebhookCreateRequest(BaseModel):
    """Request to create a new webhook."""
    name: str = ""
    url: str
    event_types: list[str]
    secret: Optional[str] = None


class WebhookResponse(BaseModel):
    """Response for webhook operations."""
    id: str
    name: str
    url: str
    event_types: list[str]
    is_active: bool
    created_at: str
    consecutive_failures: int

    class Config:
        from_attributes = True


class WebhookTestRequest(BaseModel):
    """Request to test webhook delivery."""
    url: str
    secret: Optional[str] = None
    payload: Optional[dict] = None


class WebhookTriggerRequest(BaseModel):
    """Request to manually trigger a webhook."""
    event_type: str = WebhookEventType.BACKTEST_COMPLETED
    data: Optional[dict] = None


# ============================================
# HMAC Signature Helpers
# ============================================

def compute_hmac_signature(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature of the request body."""
    if not secret:
        return ""
    mac = hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    )
    return f"sha256={mac.hexdigest()}"


# ============================================
# Webhook Delivery with Retry Logic
# ============================================

async def deliver_webhook(
    webhook_id: str,
    url: str,
    payload: dict,
    secret: Optional[str] = None,
    max_retries: int = 3,
) -> tuple[bool, str]:
    """
    Deliver a webhook event to the configured URL.
    
    Uses exponential backoff for retries on failure.
    Returns (success: bool, error_message: str).
    """
    body_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "HermesTrading/1.0",
    }

    if secret:
        signature = compute_hmac_signature(body_bytes, secret)
        headers["X-Hermes-Signature"] = signature

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    url,
                    content=body_bytes,
                    headers=headers,
                )
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        f"Webhook {webhook_id} delivered successfully to {url} "
                        f"(status={response.status_code})"
                    )
                    return True, ""
                else:
                    logger.warning(
                        f"Webhook {webhook_id} delivery failed to {url} "
                        f"(status={response.status_code}, attempt {attempt + 1}/{max_retries})"
                    )
            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook {webhook_id} timed out reaching {url} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
            except httpx.RequestError as e:
                logger.warning(
                    f"Webhook {webhook_id} request error to {url}: {e} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )

            # Exponential backoff before retry
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)

        error_msg = f"Failed after {max_retries} attempts"
        logger.error(f"Webhook {webhook_id} delivery permanently failed to {url}: {error_msg}")
        return False, error_msg


# ============================================
# Routes
# ============================================

@router.post("/test")
async def test_webhook(request: WebhookTestRequest):
    """
    Test webhook delivery - POST to the URL and echo back the response.
    Does not store anything; just tests connectivity.
    """
    test_payload = request.payload or {
        "event": "webhook.test",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": {"message": "This is a test webhook from Hermes Trading Dashboard"},
    }

    body_bytes = str(test_payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "HermesTrading/1.0",
    }

    if request.secret:
        signature = compute_hmac_signature(body_bytes, request.secret)
        headers["X-Hermes-Signature"] = signature

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                request.url,
                content=body_bytes,
                headers=headers,
            )
            return {
                "success": response.status_code >= 200 and response.status_code < 300,
                "status_code": response.status_code,
                "response_body": response.text[:500],
            }
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Webhook test timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Webhook test failed: {str(e)}")


@router.get("")
async def list_webhooks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List all configured webhooks."""
    result = await db.execute(
        select(Webhook)
        .order_by(desc(Webhook.created_at))
        .offset(skip)
        .limit(limit)
    )
    webhooks = result.scalars().all()

    return {
        "webhooks": [w.to_dict() for w in webhooks],
        "total": len(webhooks),
    }


@router.post("")
async def create_webhook(
    request: WebhookCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new webhook subscription."""
    # Validate event types
    for et in request.event_types:
        if et not in WebhookEventType.ALL:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event type: {et}. Valid types: {WebhookEventType.ALL}",
            )

    # Validate URL
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="URL must start with http:// or https://",
        )

    webhook = Webhook(
        name=request.name,
        url=request.url,
        event_types=request.event_types,
        secret=request.secret,
        is_active=True,
        consecutive_failures=0,
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    logger.info(f"Created webhook {webhook.id} for events: {request.event_types}")

    return {"webhook": webhook.to_dict(), "message": "Webhook created successfully"}


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook subscription."""
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()

    logger.info(f"Deleted webhook {webhook_id}")

    return {"message": "Webhook deleted successfully"}


@router.post("/{webhook_id}/trigger")
async def trigger_webhook(
    webhook_id: UUID,
    request: WebhookTriggerRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a webhook for testing purposes.
    Fires the webhook immediately regardless of actual events.
    """
    if request is None:
        request = WebhookTriggerRequest()

    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    payload = {
        "event": request.event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": request.data or {"manual_trigger": True},
    }

    import json
    payload_str = json.dumps(payload)

    success, error = await deliver_webhook(
        webhook_id=str(webhook.id),
        url=webhook.url,
        payload=payload_str,
        secret=webhook.secret,
    )

    # Update failure count
    if success:
        webhook.consecutive_failures = 0
        await db.commit()
        return {
            "success": True,
            "webhook_id": str(webhook.id),
            "event": request.event_type,
            "message": "Webhook triggered successfully",
        }
    else:
        webhook.consecutive_failures += 1
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Webhook delivery failed: {error}",
        )


# ============================================
# Event Trigger Helper (for use by other services)
# ============================================

async def trigger_event(
    event_type: str,
    data: dict,
    db: AsyncSession,
) -> list[dict]:
    """
    Trigger webhooks for a given event type.
    Called by other services when events occur.
    
    Returns list of delivery results.
    """
    result = await db.execute(
        select(Webhook).where(
            Webhook.is_active == True,
        )
    )
    all_webhooks = result.scalars().all()

    # Filter webhooks subscribed to this event type
    matching_webhooks = [
        w for w in all_webhooks
        if event_type in w.event_types
    ]

    if not matching_webhooks:
        logger.debug(f"No webhooks configured for event: {event_type}")
        return []

    payload = {
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data,
    }

    import json
    payload_str = json.dumps(payload)

    results = []
    for webhook in matching_webhooks:
        success, error = await deliver_webhook(
            webhook_id=str(webhook.id),
            url=webhook.url,
            payload=payload_str,
            secret=webhook.secret,
        )

        # Update failure tracking
        if success:
            webhook.consecutive_failures = 0
        else:
            webhook.consecutive_failures += 1

        results.append({
            "webhook_id": str(webhook.id),
            "url": webhook.url,
            "success": success,
            "error": error,
        })

    await db.commit()
    return results