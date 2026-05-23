"""
AI Service - Strategy generation using MiniMax M2.7 via Anthropic-compatible API.

This module provides the generate_strategy function that calls the MiniMax M2.7 model
to generate trading strategy definitions in JSON format.
"""

import json
import logging
from typing import Any

import httpx
from httpx import HTTPStatusError

from core.config import settings

logger = logging.getLogger(__name__)

# System prompt instructing the model to output ONLY valid JSON
SYSTEM_PROMPT = """You are an expert trading strategy generator. Generate a JSON strategy definition with these exact fields:
- name: str (strategy name, keep it concise and descriptive)
- description: str (1-2 sentence description of the strategy)
- strategy_type: str (one of: momentum, mean_reversion, breakout, trend_following)
- parameters: dict of parameter name -> {min, max, default, description}
- entry_rules: dict with condition_type (crossover|threshold|pattern), indicator, and params
- exit_rules: dict with condition_type (crossover|threshold|pattern), indicator, and params
- stop_loss_pct: float (default 0.02 = 2%)
- take_profit_pct: float (default 0.04 = 4%)
- max_position_pct: float (default 0.1 = 10% of capital)
- risk_per_trade_pct: float (default 0.01 = 1%)

Available indicators: SMA, EMA, RSI, MACD, Bollinger Bands, ADX, ATR, Supertrend, VWAP, Stochastic, CCI, ROC, Williams %R, OBV, Volume profile

Output ONLY valid JSON. No markdown fences, no explanation. Just the JSON object."""


async def generate_strategy(
    prompt: str,
    strategy_type: str,
    asset_class: str,
    pairs: list[str],
) -> dict[str, Any]:
    """
    Generate a trading strategy using MiniMax M2.7 via Anthropic-compatible API.
    
    Args:
        prompt: User's request/description for the strategy
        strategy_type: Type of strategy (momentum, mean_reversion, breakout, trend_following)
        asset_class: Asset class (crypto, forex, stocks, etc.)
        pairs: List of trading pairs to consider
        
    Returns:
        dict containing the generated strategy definition
        
    Raises:
        HTTPException: If API key is not configured or API call fails
    """
    if not settings.anthropic_api_key:
        raise ValueError("AI provider not configured: ANTHROPIC_API_KEY not set")
    
    # Build user message with context
    user_message = f"""Generate a {strategy_type} strategy for {asset_class}.
Trading pairs: {', '.join(pairs) if pairs else 'any'}
User request: {prompt}

Return a complete strategy definition as JSON."""

    payload = {
        "model": "MiniMax-M2.7",
        "max_tokens": 2000,
        "stream": False,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_message}
        ],
    }
    
    headers = {
        "Authorization": f"Bearer {settings.anthropic_api_key}",
        "Content-Type": "application/json",
    }
    
    base_url = settings.anthropic_base_url.rstrip("/")
    endpoint = f"{base_url}/v1/messages"
    
    logger.info(f"Calling MiniMax M2.7 API at {endpoint}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the text content from the response
            # Anthropic-compatible API returns: {"content": [{"type": "text", "text": "..."}]}
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

            # Strip markdown fences if present (model sometimes returns ```json ... ```)
            text = text_content.strip()
            if text.startswith("```"):
                # Remove opening fence: ```json or ``` — take everything after the first line
                lines = text.split("\n")
                text = "\n".join(lines[1:])  # skip ```json line
                # Remove closing ``` if present
                text = text.rstrip()
                if text.endswith("```"):
                    text = text[:-3].rstrip()

            # Parse the JSON from the model's output
            strategy_def = json.loads(text)
            
            # Validate required fields
            required_fields = ["name", "description", "strategy_type", "parameters", "entry_rules", "exit_rules"]
            for field in required_fields:
                if field not in strategy_def:
                    raise ValueError(f"Missing required field in AI response: {field}")
            
            logger.info(f"Successfully generated strategy: {strategy_def.get('name')}")
            return strategy_def
            
    except HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Invalid API key for MiniMax AI") from e
        elif e.response.status_code == 429:
            raise ValueError("MiniMax API rate limit exceeded") from e
        else:
            logger.error(f"HTTP error from MiniMax API: {e.response.status_code} - {e.response.text}")
            raise ValueError(f"AI API error (HTTP {e.response.status_code}): {e.response.text}") from e
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        raise ValueError("AI returned invalid JSON response") from e
    except Exception as e:
        logger.error(f"Unexpected error calling MiniMax API: {e}")
        raise ValueError(f"Failed to generate strategy: {str(e)}") from e