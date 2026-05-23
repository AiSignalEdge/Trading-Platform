"""
Unit tests for describe_service.py
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import HTTPStatusError, RequestError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestDescribeService:
    """Tests for strategy description service."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with API key set."""
        with patch("services.describe_service.settings") as mock:
            mock.anthropic_api_key = "test-api-key"
            mock.anthropic_base_url = "https://api.minimax.chat"
            yield mock

    @pytest.mark.asyncio
    async def test_describe_strategy_success(self, mock_settings):
        """Test successful strategy description generation."""
        from services.describe_service import describe_strategy
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "This strategy uses a moving average crossover to identify trend changes and enter positions accordingly."}
            ]
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await describe_strategy(
                strategy_name="MA Cross",
                strategy_type="momentum",
                parameters={"fast_period": 10, "slow_period": 30},
                stop_loss_pct=0.02,
                take_profit_pct=0.04,
            )
            
            assert "MA Cross" in result or "moving average" in result.lower()
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_describe_strategy_api_key_missing(self):
        """Test error when API key is not configured."""
        from services.describe_service import describe_strategy
        
        with patch("services.describe_service.settings") as mock:
            mock.anthropic_api_key = ""
            
            with pytest.raises(ValueError, match="AI provider not configured"):
                await describe_strategy(
                    strategy_name="Test Strategy",
                    strategy_type="momentum",
                    parameters={},
                )

    @pytest.mark.asyncio
    async def test_describe_strategy_http_error(self, mock_settings):
        """Test handling of HTTP errors from AI API."""
        from services.describe_service import describe_strategy
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            with pytest.raises(ValueError, match="rate limit"):
                await describe_strategy(
                    strategy_name="Test Strategy",
                    strategy_type="momentum",
                    parameters={},
                )

    @pytest.mark.asyncio
    async def test_describe_strategy_empty_response(self, mock_settings):
        """Test handling of empty response from AI API."""
        from services.describe_service import describe_strategy
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": []}
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            with pytest.raises(ValueError, match="Empty response"):
                await describe_strategy(
                    strategy_name="Test Strategy",
                    strategy_type="momentum",
                    parameters={},
                )

    @pytest.mark.asyncio
    async def test_format_rules(self):
        """Test rule formatting helper."""
        from services.describe_service import _format_rules
        
        rules = {
            "condition_type": "crossover",
            "indicator": "SMA",
            "params": {"period": 20}
        }
        result = _format_rules(rules)
        assert "crossover" in result
        assert "SMA" in result
        assert "period" in result
        
        # Test None
        result = _format_rules(None)
        assert result == "not specified"
        
        # Test empty dict
        result = _format_rules({})
        assert "unknown" in result

    @pytest.mark.asyncio
    async def test_describe_strategy_with_all_params(self, mock_settings):
        """Test describing strategy with all parameters provided."""
        from services.describe_service import describe_strategy
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "A momentum strategy that buys when RSI crosses above 30 and sells when it crosses below 70."}
            ]
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client_class.return_value = mock_client
            
            result = await describe_strategy(
                strategy_name="RSI Momentum",
                strategy_type="momentum",
                parameters={"rsi_period": 14, "oversold": 30, "overbought": 70},
                entry_rules={"condition_type": "crossover", "indicator": "RSI", "params": {"threshold": 30}},
                exit_rules={"condition_type": "crossover", "indicator": "RSI", "params": {"threshold": 70}},
                stop_loss_pct=0.02,
                take_profit_pct=0.04,
                max_position_pct=0.1,
                risk_per_trade_pct=0.01,
            )
            
            assert len(result) > 0
            # Verify the API was called
            call_args = mock_client.post.call_args
            assert call_args is not None