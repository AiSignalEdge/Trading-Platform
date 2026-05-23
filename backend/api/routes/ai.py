"""
AI Routes - AI-powered strategy generation and analysis endpoints.

Section 13: API Server from PLAN-v2.md
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.config import settings
from models.strategy import Strategy, StrategyVersion
from services.ai_service import generate_strategy
from services.optimizer import optimize_strategy_parameters

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

logger = logging.getLogger(__name__)


# ====================
# Pydantic Schemas
# ====================

class AIGenerateRequest(BaseModel):
    prompt: str
    strategy_type: Optional[str] = "momentum"
    asset_class: Optional[str] = "crypto"
    pairs: list[str] = []


class AIStrategyResponse(BaseModel):
    id: str
    name: str
    description: str
    parameters: dict
    pine_script: str
    confidence: float
    created_at: str

    class Config:
        from_attributes = True


class AIAnalysisResponse(BaseModel):
    strategy_id: str
    analysis: dict
    suggestions: list[str]
    risks: list[str]

    class Config:
        from_attributes = True


# ====================
# Routes
# ====================

@router.post("/generate", response_model=AIStrategyResponse)
async def generate_strategy_route(
    request: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a trading strategy using AI (MiniMax M2.7)."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="AI provider not configured: ANTHROPIC_API_KEY not set")
    
    try:
        result = await generate_strategy(
            prompt=request.prompt,
            strategy_type=request.strategy_type or "momentum",
            asset_class=request.asset_class or "crypto",
            pairs=request.pairs or [],
        )
        
        # Save generated strategy to DB
        strategy = Strategy(
            id=uuid4(),
            name=result["name"],
            description=result.get("description", ""),
            strategy_type=result.get("strategy_type", "momentum"),
            asset_class=request.asset_class or "crypto",
            pairs=request.pairs or [],
            author="AI Generator",
            is_public=False,
        )
        db.add(strategy)
        await db.flush()
        
        version = StrategyVersion(
            id=uuid4(),
            strategy_id=strategy.id,
            version=1,
            parameters=result.get("parameters", {}),
            pine_script=result.get("pine_script", ""),
            created_by="AI Generator",
            changelog="Initial AI-generated version",
        )
        db.add(version)
        await db.commit()
        
        return AIStrategyResponse(
            id=str(version.id),
            name=result["name"],
            description=result.get("description", ""),
            parameters=result.get("parameters", {}),
            pine_script=result.get("pine_script", ""),
            confidence=result.get("confidence", 0.8),
            created_at=datetime.utcnow().isoformat(),
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"AI generation validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("AI strategy generation failed")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/analyze/{strategy_id}", response_model=AIAnalysisResponse)
async def analyze_strategy(
    strategy_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a strategy using AI and provide feedback.
    """
    raise HTTPException(status_code=501, detail="AI analysis not implemented")


@router.post("/optimize/{strategy_id}")
async def optimize_strategy_params(
    strategy_id: UUID,
    symbols: list[str] = Query(["BTC/USDT"]),
    timeframe: str = Query("4h"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search_space: Optional[dict] = None,
    n_initial: int = Query(5, ge=2, le=20),
    n_iterations: int = Query(20, ge=5, le=100),
    target_metric: str = Query("sharpe_ratio"),
    capital: float = Query(10000),
    db: AsyncSession = Depends(get_db),
):
    """
    Bayesian parameter optimization for a strategy.
    Uses Gaussian Process-based Expected Improvement to find optimal parameters.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="AI provider not configured: ANTHROPIC_API_KEY not set")

    # Validate strategy exists
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")

    # Default date range (90 days if not specified)
    if end_date is None:
        end_date = datetime.utcnow().isoformat()
    if start_date is None:
        start_date = (datetime.utcnow() - timedelta(days=90)).isoformat()

    # Default search space per strategy type
    default_spaces = {
        "ma_cross": {
            "fast_period": {"min": 5, "max": 50, "default": 10},
            "slow_period": {"min": 20, "max": 200, "default": 30},
        },
        "rsi": {
            "period": {"min": 7, "max": 28, "default": 14},
            "oversold": {"min": 20, "max": 40, "default": 30},
            "overbought": {"min": 60, "max": 80, "default": 70},
        },
        "bollinger": {
            "period": {"min": 10, "max": 50, "default": 20},
            "nb_dev": {"min": 1.5, "max": 3.0, "default": 2.0},
        },
        "macd": {
            "signal_period": {"min": 5, "max": 15, "default": 9},
        },
    }

    space = search_space or default_spaces.get(strategy.strategy_type, default_spaces["ma_cross"])

    start = time.time()
    try:
        result = await optimize_strategy_parameters(
            strategy_name=strategy.name,
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            search_space=space,
            n_initial=n_initial,
            n_iterations=n_iterations,
            target_metric=target_metric,
            capital=capital,
        )
        result["optimization_time_seconds"] = round(time.time() - start, 2)
        return result
    except Exception as e:
        logger.exception("Parameter optimization failed")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/backtest/insights")
async def get_backtest_insights(
    backtest_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-generated insights for a backtest result.
    """
    raise HTTPException(status_code=501, detail="AI insights not implemented")


@router.get("/models")
async def list_ai_models():
    """List available AI models."""
    return {
        "models": [
            {"id": "MiniMax-M2.7", "name": "MiniMax M2.7", "provider": "minimax", "supports": ["strategy-generation", "analysis", "optimization"]}
        ]
    }