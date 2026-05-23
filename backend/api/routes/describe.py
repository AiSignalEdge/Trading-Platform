"""
Strategy Describe Routes - Convert strategy parameters to plain English.

POST /api/v1/ai/describe/{strategy_id} - Describe a strategy from DB by ID
POST /api/v1/ai/describe - Describe a strategy from raw parameters (ad-hoc)
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.config import settings
from models.strategy import Strategy, StrategyVersion
from services.describe_service import describe_strategy_params

router = APIRouter(prefix="/api/v1/ai/describe", tags=["ai"])

logger = logging.getLogger(__name__)


# ====================
# Pydantic Schemas
# ====================

class DescribeParamsRequest(BaseModel):
    """Request body for ad-hoc strategy description (no DB lookup)."""
    strategy_name: str
    strategy_type: str = "momentum"
    parameters: dict = {}
    entry_rules: Optional[dict] = None
    exit_rules: Optional[dict] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_position_pct: Optional[float] = None
    risk_per_trade_pct: Optional[float] = None


class DescribeResponse(BaseModel):
    """Response containing plain English strategy description."""
    strategy_id: Optional[str] = None
    strategy_name: str
    description: str


# ====================
# Routes
# ====================

@router.post("/{strategy_id}", response_model=DescribeResponse)
async def describe_strategy_by_id(
    strategy_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Describe a strategy by its ID from the database.
    
    Reads the strategy and its latest version parameters, then generates
    a plain English description using AI.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="AI provider not configured: ANTHROPIC_API_KEY not set")
    
    # Fetch strategy from DB
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    
    # Get the latest version parameters
    version_result = await db.execute(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
        .limit(1)
    )
    version = version_result.scalar_one_or_none()
    
    parameters = version.parameters if version else {}
    entry_rules = parameters.get("entry_rules")
    exit_rules = parameters.get("exit_rules")
    stop_loss = parameters.get("stop_loss_pct")
    take_profit = parameters.get("take_profit_pct")
    max_position = parameters.get("max_position_pct")
    risk_per_trade = parameters.get("risk_per_trade_pct")
    
    try:
        description = await describe_strategy_params(
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type or "momentum",
            parameters=parameters,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
            max_position_pct=max_position,
            risk_per_trade_pct=risk_per_trade,
        )
        
        return DescribeResponse(
            strategy_id=str(strategy_id),
            strategy_name=strategy.name,
            description=description,
        )
    except ValueError as e:
        logger.warning(f"Strategy description validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Strategy description failed")
        raise HTTPException(status_code=500, detail=f"Description generation failed: {str(e)}")


@router.post("", response_model=DescribeResponse)
async def describe_strategy_by_params(
    request: DescribeParamsRequest,
):
    """
    Describe a strategy from raw parameters (ad-hoc, no DB lookup).
    
    Useful for testing or describing strategies before they're saved.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="AI provider not configured: ANTHROPIC_API_KEY not set")
    
    try:
        description = await describe_strategy_params(
            strategy_name=request.strategy_name,
            strategy_type=request.strategy_type,
            parameters=request.parameters,
            entry_rules=request.entry_rules,
            exit_rules=request.exit_rules,
            stop_loss_pct=request.stop_loss_pct,
            take_profit_pct=request.take_profit_pct,
            max_position_pct=request.max_position_pct,
            risk_per_trade_pct=request.risk_per_trade_pct,
        )
        
        return DescribeResponse(
            strategy_id=None,
            strategy_name=request.strategy_name,
            description=description,
        )
    except ValueError as e:
        logger.warning(f"Strategy description validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Strategy description failed")
        raise HTTPException(status_code=500, detail=f"Description generation failed: {str(e)}")