"""
Unit tests for notification_service.py
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import HTTPStatusError, RequestError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestNotificationService:
    """Tests for notification service."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with notification credentials."""
        with patch("services.notification_service.settings") as mock:
            mock.telegram_bot_token = "test-bot-token"
            mock.telegram_chat_id = "test-chat-id"
            mock.discord_webhook_url = "https://discord.com/api/webhooks/test/webhook"
            yield mock

    @pytest.mark.asyncio
    async def test_send_telegram_message_success(self, mock_settings):
        """Test successful Telegram message sending."""
        from services.notification_service import send_telegram_message
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 12345}
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await send_telegram_message(
                text="Test message",
                chat_id="test-chat-id",
                bot_token="test-bot-token",
            )
            
            assert result["status"] == "sent"
            assert result["message_id"] == 12345
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_telegram_message_config_missing(self):
        """Test error when Telegram is not configured."""
        from services.notification_service import send_telegram_message
        
        with patch("services.notification_service.settings") as mock:
            mock.telegram_bot_token = ""
            mock.telegram_chat_id = ""
            
            with pytest.raises(ValueError, match="Telegram not configured"):
                await send_telegram_message(text="Test")

    @pytest.mark.asyncio
    async def test_send_telegram_message_rate_limit(self, mock_settings):
        """Test handling of Telegram rate limiting."""
        from services.notification_service import send_telegram_message
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "1"}
        mock_response.text = "Too many requests"
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            # Should retry and eventually fail after max retries
            with pytest.raises(ValueError, match="Failed to send Telegram"):
                await send_telegram_message(text="Test")

    @pytest.mark.asyncio
    async def test_send_discord_webhook_success(self, mock_settings):
        """Test successful Discord webhook sending."""
        from services.notification_service import send_discord_webhook
        
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await send_discord_webhook(
                text="Test message",
                webhook_url="https://discord.com/api/webhooks/test/webhook",
            )
            
            assert result["status"] == "sent"
            assert result["chunks_sent"] == 1
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_discord_webhook_config_missing(self):
        """Test error when Discord is not configured."""
        from services.notification_service import send_discord_webhook
        
        with patch("services.notification_service.settings") as mock:
            mock.discord_webhook_url = ""
            
            with pytest.raises(ValueError, match="Discord not configured"):
                await send_discord_webhook(text="Test")

    @pytest.mark.asyncio
    async def test_send_discord_long_message_split(self, mock_settings):
        """Test that long Discord messages are split."""
        from services.notification_service import send_discord_webhook
        
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            # Create a message longer than 2000 chars
            long_message = "A" * 2500
            
            result = await send_discord_webhook(text=long_message)
            
            # Should have been called twice (split into 2 chunks)
            assert mock_client.post.call_count == 2
            assert result["total_chunks"] == 2

    @pytest.mark.asyncio
    async def test_send_notification_telegram(self, mock_settings):
        """Test send_notification with Telegram type."""
        from services.notification_service import send_notification, NotificationType
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123}
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await send_notification(
                text="Test",
                notification_type=NotificationType.TELEGRAM,
            )
            
            assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_notification_discord(self, mock_settings):
        """Test send_notification with Discord type."""
        from services.notification_service import send_notification, NotificationType
        
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await send_notification(
                text="Test",
                notification_type=NotificationType.DISCORD,
            )
            
            assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_job_completion_notification_success(self, mock_settings):
        """Test job completion notification sending."""
        from services.notification_service import send_job_completion_notification
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123}
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await send_job_completion_notification(
                job_name="Backtest Job",
                status="completed",
                duration_seconds=120.5,
            )
            
            assert result["status"] == "completed"
            assert len(result["channels"]) == 1

    @pytest.mark.asyncio
    async def test_send_job_completion_notification_no_channels(self):
        """Test job notification when no channels configured."""
        from services.notification_service import send_job_completion_notification
        
        with patch("services.notification_service.settings") as mock:
            mock.telegram_bot_token = ""
            mock.telegram_chat_id = ""
            mock.discord_webhook_url = ""
            
            result = await send_job_completion_notification(
                job_name="Test Job",
                status="success",
            )
            
            assert result["status"] == "no_channels_configured"

    @pytest.mark.asyncio
    async def test_send_telegram_invalid_token(self, mock_settings):
        """Test error handling for invalid Telegram token."""
        from services.notification_service import send_telegram_message
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            with pytest.raises(ValueError, match="Invalid Telegram bot token"):
                await send_telegram_message(text="Test")

    @pytest.mark.asyncio
    async def test_send_telegram_retry_on_network_error(self, mock_settings):
        """Test that Telegram retries on network errors."""
        from services.notification_service import send_telegram_message
        
        # First call fails, second succeeds
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "ok": True,
            "result": {"message_id": 456}
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [RequestError("Network error"), mock_response_success]
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await send_telegram_message(text="Test")
            
            assert result["status"] == "sent"
            assert mock_client.post.call_count == 2