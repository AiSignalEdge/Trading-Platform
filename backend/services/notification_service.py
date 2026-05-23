"""
Notification Service - Send alerts to Telegram and Discord.

Handles rate limiting, retries, and error handling for both platforms.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# Rate limiting: Telegram allows 30 msg/sec, we'll be conservative
TELEGRAM_RATE_LIMIT_DELAY = 0.5  # 500ms between messages = 2 msg/sec
DISCORD_RATE_LIMIT_DELAY = 1.0  # 1 second between messages


async def send_telegram_message(
    text: str,
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None,
) -> dict:
    """
    Send a message via Telegram bot API.
    
    Args:
        text: Message text to send
        chat_id: Target chat ID (uses settings.telegram_chat_id if not provided)
        bot_token: Bot token (uses settings.telegram_bot_token if not provided)
        
    Returns:
        dict with status, message_id, and timestamp
        
    Raises:
        ValueError: If Telegram is not configured
        httpx.HTTPError: On network/API errors
    """
    token = bot_token or settings.telegram_bot_token
    target_chat_id = chat_id or settings.telegram_chat_id
    
    if not token or not target_chat_id:
        raise ValueError("Telegram not configured: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    
    headers = {
        "Content-Type": "application/json",
    }
    
    logger.info(f"Sending Telegram message to chat {target_chat_id}")
    
    # Retry logic with exponential backoff
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("ok"):
                    message_id = result.get("result", {}).get("message_id", 0)
                    logger.info(f"Telegram message sent successfully, message_id={message_id}")
                    return {
                        "status": NotificationStatus.SENT,
                        "message_id": message_id,
                        "type": NotificationType.TELEGRAM,
                        "timestamp": datetime.utcnow().isoformat(),
                        "chat_id": target_chat_id,
                    }
                else:
                    error_desc = result.get("description", "Unknown error")
                    logger.error(f"Telegram API error: {error_desc}")
                    raise ValueError(f"Telegram API error: {error_desc}")
                    
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(e.response.headers.get("Retry-After", 5))
                logger.warning(f"Telegram rate limited, waiting {retry_after}s before retry")
                await asyncio.sleep(retry_after)
            elif e.response.status_code == 401:
                logger.error("Telegram bot token invalid")
                raise ValueError("Invalid Telegram bot token") from e
            else:
                logger.error(f"Telegram HTTP error {e.response.status_code}: {e.response.text}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
                
        except httpx.RequestError as e:
            last_error = e
            logger.error(f"Telegram request error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
            
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error sending Telegram message: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    
    raise ValueError(f"Failed to send Telegram message after {max_retries} attempts: {last_error}")


async def send_discord_webhook(
    text: str,
    webhook_url: Optional[str] = None,
) -> dict:
    """
    Send a message via Discord webhook.
    
    Args:
        text: Message text to send
        webhook_url: Discord webhook URL (uses settings.discord_webhook_url if not provided)
        
    Returns:
        dict with status, message_id, and timestamp
        
    Raises:
        ValueError: If Discord is not configured
        httpx.HTTPError: On network/API errors
    """
    url = webhook_url or settings.discord_webhook_url
    
    if not url:
        raise ValueError("Discord webhook not configured. Set DISCORD_WEBHOOK_URL in .env to enable Discord notifications.")
    
    # Discord webhooks have a max length of 2000 characters
    # Split into multiple messages if needed
    max_length = 2000
    
    if len(text) > max_length:
        # Split into chunks - try to break at newlines
        chunks = []
        current_chunk = ""
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk = current_chunk + "\n" + line if current_chunk else line
        
        if current_chunk:
            chunks.append(current_chunk)
    else:
        chunks = [text]
    
    headers = {
        "Content-Type": "application/json",
    }
    
    logger.info(f"Sending Discord webhook with {len(chunks)} message(s)")
    
    results = []
    for i, chunk in enumerate(chunks):
        payload = {
            "content": chunk,
            "username": "Hermes Trading Bot",
        }
        
        # Retry logic
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    
                    logger.info(f"Discord message {i+1}/{len(chunks)} sent successfully")
                    results.append({
                        "status": NotificationStatus.SENT,
                        "chunk_index": i,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    break
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 5))
                    logger.warning(f"Discord rate limited, waiting {retry_after}s before retry")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"Discord HTTP error {e.response.status_code}: {e.response.text}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                    
            except httpx.RequestError as e:
                last_error = e
                logger.error(f"Discord request error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
                
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error sending Discord message: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
                
        else:
            results.append({
                "status": NotificationStatus.FAILED,
                "chunk_index": i,
                "error": str(last_error),
            })
    
    # Return summary
    all_sent = all(r.get("status") == NotificationStatus.SENT for r in results)
    
    return {
        "status": NotificationStatus.SENT if all_sent else NotificationStatus.FAILED,
        "chunks_sent": len([r for r in results if r.get("status") == NotificationStatus.SENT]),
        "total_chunks": len(chunks),
        "type": NotificationType.DISCORD,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def send_notification(
    text: str,
    notification_type: NotificationType,
    chat_id: Optional[str] = None,
    webhook_url: Optional[str] = None,
    bot_token: Optional[str] = None,
) -> dict:
    """
    Send a notification to the specified platform.
    
    Args:
        text: Message text
        notification_type: TELEGRAM or DISCORD
        chat_id: For Telegram only
        webhook_url: For Discord only
        bot_token: For Telegram only
        
    Returns:
        dict with status and details
    """
    if notification_type == NotificationType.TELEGRAM:
        return await send_telegram_message(
            text=text,
            chat_id=chat_id,
            bot_token=bot_token,
        )
    elif notification_type == NotificationType.DISCORD:
        return await send_discord_webhook(
            text=text,
            webhook_url=webhook_url,
        )
    else:
        raise ValueError(f"Unknown notification type: {notification_type}")


async def send_job_completion_notification(
    job_name: str,
    status: str,
    duration_seconds: Optional[float] = None,
    error_message: Optional[str] = None,
) -> dict:
    """
    Send a job completion notification.
    
    Args:
        job_name: Name of the completed job
        status: "success" or "failed"
        duration_seconds: How long the job took
        error_message: Error message if failed
        
    Returns:
        dict with notification result
    """
    if status == "success":
        duration_str = f" (took {duration_seconds:.1f}s)" if duration_seconds else ""
        text = f"✅ *Job Completed*\n\n*Job:* {job_name}\n*Status:* Success{duration_str}"
    else:
        text = f"❌ *Job Failed*\n\n*Job:* {job_name}\n*Error:* {error_message or 'Unknown error'}"
    
    # Try both Telegram and Discord if configured
    results = []
    
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            result = await send_telegram_message(text)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
    
    if settings.discord_webhook_url:
        try:
            result = await send_discord_webhook(text)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
    
    if not results:
        logger.warning("No notification channels configured")
        return {"status": "no_channels_configured"}
    
    return {
        "status": "completed",
        "channels": results,
    }