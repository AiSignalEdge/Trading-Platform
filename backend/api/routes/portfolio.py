"""
Portfolio Routes - Portfolio management and analytics endpoints.

Section 13: API Server from PLAN-v2.md
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from models.portfolio import Portfolio

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


# ====================
# Pydantic Schemas
# ====================

class PortfolioStatusUpdate(BaseModel):
    status: str


class PortfolioResponse(BaseModel):
    id: str
    user_id: str
    name: str
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PortfolioListResponse(BaseModel):
    items: list[PortfolioResponse]
    total: int


# ====================
# Routes
# ====================

@router.get("", response_model=PortfolioListResponse)
async def list_portfolios(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List all portfolios for the current user.
    """
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Portfolio).offset(offset).limit(page_size)
    )
    portfolios = result.scalars().all()
    total = len(portfolios)  # TODO: proper count query

    return PortfolioListResponse(
        items=[
            PortfolioResponse.model_validate({
                "id": str(p.id),
                "user_id": str(p.user_id),
                "name": p.name,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            })
            for p in portfolios
        ],
        total=total,
    )


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a portfolio by ID.
    """
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    return PortfolioResponse.model_validate({
        "id": str(portfolio.id),
        "user_id": str(portfolio.user_id),
        "name": portfolio.name,
        "status": portfolio.status,
        "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None,
        "updated_at": portfolio.updated_at.isoformat() if portfolio.updated_at else None,
    })


@router.patch("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio_status(
    portfolio_id: UUID,
    update: PortfolioStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update portfolio status (active/paused/inactive).
    """
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if update.status not in ("active", "paused", "inactive"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    portfolio.status = update.status
    await db.commit()
    await db.refresh(portfolio)

    return PortfolioResponse.model_validate({
        "id": str(portfolio.id),
        "user_id": str(portfolio.user_id),
        "name": portfolio.name,
        "status": portfolio.status,
        "created_at": portfolio.created_at.isoformat() if portfolio.created_at else None,
        "updated_at": portfolio.updated_at.isoformat() if portfolio.updated_at else None,
    })


@router.get("/{portfolio_id}/positions")
async def get_portfolio_positions(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all positions in a portfolio.
    """
    return {"portfolio_id": str(portfolio_id), "positions": []}


@router.get("/{portfolio_id}/performance")
async def get_portfolio_performance(
    portfolio_id: UUID,
 timeframe: Optional[str] = "1d",
    db: AsyncSession = Depends(get_db),
):
    """
    Get portfolio performance metrics.
    """
    return {"portfolio_id": str(portfolio_id), "timeframe": timeframe, "metrics": {}}
