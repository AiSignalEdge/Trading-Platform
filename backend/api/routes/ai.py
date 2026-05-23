"""
AI Routes - AI-powered strategy generation and analysis endpoints.

Section 13: API Server from PLAN-v2.md
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.config import settings
from models.strategy import Strategy, StrategyVersion
from services.ai_service import generate_strategy

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
async def optimize_strategy(
    strategy_id: UUID,
    target_metric: Optional[str] = "sharpe_ratio",
    db: AsyncSession = Depends(get_db),
):
    """
    Optimize strategy parameters using AI.
    """
    raise HTTPException(status_code=501, detail="AI optimization not implemented")


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