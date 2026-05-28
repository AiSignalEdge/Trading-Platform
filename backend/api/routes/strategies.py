"""
Strategy Routes - All strategy CRUD and search endpoints.

Section 13: API Server from PLAN-v2.md
"""

import json
from datetime import datetime
from typing import Optional
from uuid import UUID
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from core.redis import get_redis
from models.strategy import Strategy, StrategyVersion

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

# Cache TTL constants
STRATEGY_LIST_TTL = 60  # 60 seconds
STRATEGY_ITEM_TTL = 120  # 120 seconds
STRATEGY_CACHE_PREFIX = "strategy:"
STRATEGY_LIST_CACHE_KEY = "strategies:list"


# ====================
# Pydantic Schemas
# ====================

class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    author: str = ""
    strategy_type: str = "momentum"
    asset_class: str = "crypto"
    pairs: list[str] = []
    timeframes: list[str] = ["1h", "4h", "1d"]
    parameters: dict = {}
    pine_script: str = ""
    tags: list[str] = []
    is_public: bool = False


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    strategy_type: Optional[str] = None
    pairs: Optional[list[str]] = None
    timeframes: Optional[list[str]] = None
    parameters: Optional[dict] = None
    pine_script: Optional[str] = None
    tags: Optional[list[str]] = None
    is_public: Optional[bool] = None


class StrategyVersionCreate(BaseModel):
    parameters: dict
    pine_script: str = ""
    changelog: str = ""


class StrategyResponse(BaseModel):
    id: str
    name: str
    description: str
    author: str
    strategy_type: str
    asset_class: str
    pairs: list[str]
    timeframes: list[str]
    tags: list[str]
    rating: float
    backtest_count: int
    is_public: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, strategy):
        return cls(
            id=str(strategy.id),
            name=str(strategy.name),
            description=str(strategy.description),
            author=str(strategy.author),
            strategy_type=str(strategy.strategy_type),
            asset_class=str(strategy.asset_class),
            pairs=list(strategy.pairs) if strategy.pairs else [],
            timeframes=list(strategy.timeframes) if strategy.timeframes else [],
            tags=list(strategy.tags) if strategy.tags else [],
            rating=float(strategy.rating) if strategy.rating else 0.0,
            backtest_count=int(strategy.backtest_count) if strategy.backtest_count else 0,
            is_public=bool(strategy.is_public),
            created_at=str(strategy.created_at.isoformat()) if strategy.created_at else "",
            updated_at=str(strategy.updated_at.isoformat()) if strategy.updated_at else "",
        )


class StrategyListResponse(BaseModel):
    items: list[StrategyResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ====================
# Routes
# ====================

@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    strategy_type: Optional[str] = None,
    asset_class: Optional[str] = None,
    is_public: Optional[bool] = True,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    """
    List strategies with pagination and filters.
    """
    # Build cache key based on query params
    cache_params = f"{page}:{page_size}:{strategy_type}:{asset_class}:{is_public}:{sort_by}:{sort_order}"
    cache_key = f"{STRATEGY_LIST_CACHE_KEY}:{cache_params}"

    # Try to get from Redis cache
    redis = await get_redis()
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    query = select(Strategy)
    count_query = select(func.count(Strategy.id))
    
    # Apply filters
    if strategy_type:
        query = query.where(Strategy.strategy_type == strategy_type)
        count_query = count_query.where(Strategy.strategy_type == strategy_type)
    if asset_class:
        query = query.where(Strategy.asset_class == asset_class)
        count_query = count_query.where(Strategy.asset_class == asset_class)
    if is_public is not None:
        query = query.where(Strategy.is_public == is_public)
        count_query = count_query.where(Strategy.is_public == is_public)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply sorting
    sort_column = getattr(Strategy, sort_by, Strategy.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    strategies = result.scalars().all()

    response = StrategyListResponse(
        items=[StrategyResponse.from_orm(s) for s in strategies],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )

    # Cache the response
    response_json = json.dumps(response.model_dump(mode='json'))
    await redis.setex(cache_key, STRATEGY_LIST_TTL, response_json)

    return response


@router.get("/search")
async def search_strategies(
    q: Optional[str] = None,
    strategy_type: Optional[str] = None,
    pairs: Optional[str] = None,
    min_sharpe: Optional[float] = None,
    max_drawdown: Optional[float] = None,
    tags: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text and structured search for strategies.
    """
    query = select(Strategy).where(Strategy.is_public == True)
    
    if q:
        search_filter = Strategy.name.ilike(f"%{q}%") | Strategy.description.ilike(f"%{q}%")
        query = query.where(search_filter)
    
    if strategy_type:
        query = query.where(Strategy.strategy_type == strategy_type)
    
    if pairs:
        pair_list = pairs.split(",")
        query = query.where(Strategy.pairs.overlap(pair_list))
    
    if tags:
        tag_list = tags.split(",")
        query = query.where(Strategy.tags.overlap(tag_list))
    
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    strategies = result.scalars().all()
    
    return {
        "items": [s.to_dict() for s in strategies],
        "query": q,
        "filters": {
            "strategy_type": strategy_type,
            "pairs": pairs,
            "min_sharpe": min_sharpe,
            "max_drawdown": max_drawdown,
            "tags": tags,
        },
    }


@router.post("", response_model=StrategyResponse)
async def create_strategy(
    strategy_data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new strategy.
    """
    strategy = Strategy(
        name=strategy_data.name,
        description=strategy_data.description,
        author=strategy_data.author,
        strategy_type=strategy_data.strategy_type,
        asset_class=strategy_data.asset_class,
        pairs=strategy_data.pairs,
        timeframes=strategy_data.timeframes,
        tags=strategy_data.tags,
        is_public=strategy_data.is_public,
    )
    db.add(strategy)
    await db.flush()
    await db.refresh(strategy)
    return StrategyResponse.from_orm(strategy)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a strategy by ID.
    """
    cache_key = f"{STRATEGY_CACHE_PREFIX}{strategy_id}"

    # Try to get from Redis cache
    redis = await get_redis()
    cached = await redis.get(cache_key)
    if cached:
        data = json.loads(cached)
        return StrategyResponse(**data)

    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    response = StrategyResponse.from_orm(strategy)

    # Cache the response
    response_json = json.dumps(response.model_dump(mode='json'))
    await redis.setex(cache_key, STRATEGY_ITEM_TTL, response_json)

    return response


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: UUID,
    strategy_data: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a strategy (creates a new version).
    """
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Update fields
    update_data = strategy_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(strategy, field, value)

    strategy.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(strategy)

    # Invalidate caches
    redis = await get_redis()
    await redis.delete(f"{STRATEGY_CACHE_PREFIX}{strategy_id}")
    await redis.delete(STRATEGY_LIST_CACHE_KEY + ":*")  # List cache has pattern

    return StrategyResponse.from_orm(strategy)


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a strategy and all its versions.
    """
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    await db.delete(strategy)
    await db.flush()
    return {"message": "Strategy deleted successfully"}


@router.get("/{strategy_id}/versions")
async def get_strategy_versions(
    strategy_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all versions of a strategy.
    """
    result = await db.execute(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
    )
    versions = result.scalars().all()
    
    return {
        "strategy_id": str(strategy_id),
        "versions": [v.to_dict() for v in versions],
    }


@router.post("/{strategy_id}/versions")
async def create_strategy_version(
    strategy_id: UUID,
    version_data: StrategyVersionCreate,
    created_by: str = "system",
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new version of a strategy.
    """
    # Get current max version
    result = await db.execute(
        select(func.max(StrategyVersion.version))
        .where(StrategyVersion.strategy_id == strategy_id)
    )
    max_version = result.scalar() or 0
    
    version = StrategyVersion(
        strategy_id=strategy_id,
        version=max_version + 1,
        parameters=version_data.parameters,
        pine_script=version_data.pine_script,
        changelog=version_data.changelog,
        created_by=created_by,
    )
    db.add(version)
    
    # Update strategy's current version pointer
    strategy_result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = strategy_result.scalar_one_or_none()
    if strategy:
        strategy.current_version_id = version.id
        strategy.version = max_version + 1
        strategy.updated_at = datetime.utcnow()
    
    await db.flush()
    await db.refresh(version)
    return version.to_dict()


@router.post("/{strategy_id}/revert/{version}")
async def revert_to_version(
    strategy_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Revert strategy to a previous version.
    """
    # Get the version to revert to
    result = await db.execute(
        select(StrategyVersion)
        .where(
            StrategyVersion.strategy_id == strategy_id,
            StrategyVersion.version == version,
        )
    )
    old_version = result.scalar_one_or_none()
    
    if not old_version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Create new version with old parameters
    return await create_strategy_version(
        strategy_id,
        StrategyVersionCreate(
            parameters=old_version.parameters,
            pine_script=old_version.pine_script,
            changelog=f"Reverted to version {version}",
        ),
        created_by="system",
        db=db,
    )