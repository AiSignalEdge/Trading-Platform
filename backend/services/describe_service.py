"""
Strategy Describe Service - Convert strategy parameters to plain English description.

Uses MiniMax M2.7 to generate human-readable descriptions of trading strategies.
"""

import json
import logging
from typing import Any, Optional

import httpx
from httpx import HTTPStatusError

from core.config import settings

logger = logging.getLogger(__name__)

# System prompt for strategy description generation
DESCRIBE_SYSTEM_PROMPT = """You are an expert trading strategy analyst. Given a trading strategy's configuration, provide a clear, plain English description that covers:
1. What the strategy does and its overall approach
2. All parameters and their values
3. Entry rules (when to enter a trade)
4. Exit rules (when to exit a trade)
5. Stop loss and take profit levels
6. Risk characteristics

Be concise but thorough. Use simple language that a non-technical trader can understand. Format the output as a well-structured paragraph or bullet points."""


async def describe_strategy(
    strategy_name: str,
    strategy_type: str,
    parameters: dict[str, Any],
    entry_rules: Optional[dict[str, Any]] = None,
    exit_rules: Optional[dict[str, Any]] = None,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    max_position_pct: Optional[float] = None,
    risk_per_trade_pct: Optional[float] = None,
) -> str:
    """
    Generate a plain English description of a trading strategy.
    
    Args:
        strategy_name: Name of the strategy
        strategy_type: Type (momentum, mean_reversion, breakout, trend_following)
        parameters: Dict of parameter names to values
        entry_rules: Entry rule configuration
        exit_rules: Exit rule configuration
        stop_loss_pct: Stop loss percentage
        take_profit_pct: Take profit percentage
        max_position_pct: Maximum position size percentage
        risk_per_trade_pct: Risk per trade percentage
        
    Returns:
        Plain English description of the strategy
    """
    if not settings.anthropic_api_key:
        raise ValueError("AI provider not configured: ANTHROPIC_API_KEY not set")
    
    # Build a comprehensive prompt with all strategy details
    param_str = ", ".join([f"{k}={v}" for k, v in parameters.items()]) if parameters else "default"
    
    entry_desc = _format_rules(entry_rules) if entry_rules else "not specified"
    exit_desc = _format_rules(exit_rules) if exit_rules else "not specified"
    
    user_message = f"""Describe the following trading strategy in plain English:

Strategy Name: {strategy_name}
Strategy Type: {strategy_type}

Parameters: {param_str}

Entry Rules: {entry_desc}
Exit Rules: {exit_desc}

Stop Loss: {f'{stop_loss_pct * 100:.1f}%' if stop_loss_pct is not None else 'default 2%'}
Take Profit: {f'{take_profit_pct * 100:.1f}%' if take_profit_pct is not None else 'default 4%'}
Max Position Size: {f'{max_position_pct * 100:.1f}%' if max_position_pct is not None else 'default 100%'}
Risk Per Trade: {f'{risk_per_trade_pct * 100:.1f}%' if risk_per_trade_pct is not None else 'default 2%'}

Provide a clear, structured description that covers what this strategy does, how it enters/exits trades, and its risk profile."""

    payload = {
        "model": "MiniMax-M2.7",
        "max_tokens": 1000,
        "stream": False,
        "system": DESCRIBE_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_message}
        ],
    }
    
    headers = {
        "Authorization": f"Bearer {settings.anthropic_api_key}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    
    base_url = settings.anthropic_base_url.rstrip("/")
    endpoint = f"{base_url}/v1/messages"
    
    logger.info(f"Generating strategy description for: {strategy_name}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            
            content_blocks = result.get("content", [])
            if not content_blocks:
                raise ValueError("Empty response from AI model")
            
            text_content = None
            for block in content_blocks:
                if block.get("type") == "text":
                    text_content = block.get("text", "")
                    break
            
            if not text_content:
                raise ValueError("No text content in AI response")
            
            description = text_content.strip()
            logger.info(f"Successfully generated description for strategy: {strategy_name}")
            return description
            
    except httpx.TimeoutException:
        logger.error(f"MiniMax API timed out after 60s")
        raise ValueError("AI request timed out after 60 seconds. Please try again.")
    except httpx.HTTPStatusError as e:
        logger.error(f"MiniMax HTTP error: {e.response.status_code}")
        raise ValueError(f"AI service returned error (HTTP {e.response.status_code}). Please try again.") from e
    except Exception as e:
        logger.error(f"Unexpected error generating strategy description: {e}")
        raise ValueError("Failed to generate strategy description. Please try again.") from e


def _format_rules(rules: Optional[dict[str, Any]]) -> str:
    """Format entry/exit rules into a readable string."""
    if not rules:
        return "not specified"
    
    parts = []
    
    condition_type = rules.get("condition_type", "unknown")
    parts.append(f"Condition type: {condition_type}")
    
    indicator = rules.get("indicator", "unknown")
    parts.append(f"Indicator: {indicator}")
    
    params = rules.get("params", {})
    if params:
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        parts.append(f"Parameters: {param_str}")
    
    return "; ".join(parts)


async def describe_strategy_params(
    strategy_name: str,
    strategy_type: str,
    parameters: dict[str, Any],
    entry_rules: Optional[dict[str, Any]] = None,
    exit_rules: Optional[dict[str, Any]] = None,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    max_position_pct: Optional[float] = None,
    risk_per_trade_pct: Optional[float] = None,
) -> str:
    """
    Alias for describe_strategy - accepts raw parameters instead of DB model.
    
    This function can be used for ad-hoc strategy descriptions without a DB entry.
    """
    return await describe_strategy(
        strategy_name=strategy_name,
        strategy_type=strategy_type,
        parameters=parameters,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        max_position_pct=max_position_pct,
        risk_per_trade_pct=risk_per_trade_pct,
    )