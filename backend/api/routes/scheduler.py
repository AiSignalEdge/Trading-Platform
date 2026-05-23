"""
Scheduler Job CRUD API — APScheduler-backed scheduled jobs backed by PostgreSQL.

Routes:
  POST   /api/v1/scheduler/jobs              — create job
  GET    /api/v1/scheduler/jobs              — list jobs
  GET    /api/v1/scheduler/jobs/{job_id}     — get job
  PUT    /api/v1/scheduler/jobs/{job_id}     — update job
  DELETE /api/v1/scheduler/jobs/{job_id}     — delete job
  POST   /api/v1/scheduler/jobs/{job_id}/run — trigger immediate run
  GET    /api/v1/scheduler/jobs/history      — global execution history
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.scheduler import scheduler_service

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])

VALID_JOB_TYPES = {"backtest", "portfolio", "walk-forward", "walk_forward", "monte-carlo"}
VALID_TRIGGER_TYPES = {"cron", "interval", "date"}


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class JobCreateRequest(BaseModel):
    name: str
    job_type: str
    payload: dict = Field(default_factory=dict)
    trigger_type: str = "interval"
    trigger_config: dict = Field(default_factory=dict)
    enabled: bool = True
    description: Optional[str] = None

    def validate_job_type(self):
        if self.job_type not in VALID_JOB_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid job_type '{self.job_type}'. Must be one of: {VALID_JOB_TYPES}",
            )

    def validate_trigger(self):
        if self.trigger_type not in VALID_TRIGGER_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid trigger_type '{self.trigger_type}'. Must be one of: {VALID_TRIGGER_TYPES}",
            )
        if self.trigger_type == "interval" and not self.trigger_config:
            # Default to 1 hour
            self.trigger_config = {"hours": 1}


class JobUpdateRequest(BaseModel):
    name: Optional[str] = None
    job_type: Optional[str] = None
    payload: Optional[dict] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    name: str
    job_type: str
    payload: dict
    trigger_type: str
    trigger_config: dict
    enabled: bool
    status: str  # scheduled | paused
    created_at: Optional[str]
    next_run: Optional[str]
    last_run: Optional[str]
    last_status: Optional[str]
    run_count: int
    description: Optional[str]


class JobListResponse(BaseModel):
    items: list[dict]
    total: int


class TriggerResponse(BaseModel):
    execution_id: str
    status: str


class HistoryItem(BaseModel):
    execution_id: str
    job_id: str
    started_at: Optional[str]
    finished_at: Optional[str]
    status: str
    result_summary: Optional[str]
    error: Optional[str]


class HistoryResponse(BaseModel):
    items: list[dict]
    total: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(request: JobCreateRequest):
    """Create a new scheduled job."""
    request.validate_job_type()
    request.validate_trigger()

    job_dict = await scheduler_service.add_job({
        "name": request.name,
        "job_type": request.job_type,
        "payload": request.payload,
        "trigger_type": request.trigger_type,
        "trigger_config": request.trigger_config,
        "enabled": request.enabled,
        "description": request.description,
    })
    return job_dict


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all scheduled jobs."""
    items = await scheduler_service.list_jobs(limit=limit, offset=offset)
    total = len(items)
    return JobListResponse(items=items, total=total)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get a single job by ID."""
    job = await scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.put("/jobs/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, request: JobUpdateRequest):
    """Update an existing job."""
    # Validate trigger_type if provided
    if request.trigger_type is not None and request.trigger_type not in VALID_TRIGGER_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid trigger_type '{request.trigger_type}'. Must be one of: {VALID_TRIGGER_TYPES}",
        )

    # Build update dict (exclude None values)
    update_fields = {k: v for k, v in request.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(
            status_code=422,
            detail="No valid fields provided for update",
        )

    updated = await scheduler_service.update_job(job_id, **update_fields)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return updated


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a scheduled job."""
    deleted = await scheduler_service.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return {"deleted": True}


@router.post("/jobs/{job_id}/run", response_model=TriggerResponse)
async def trigger_job(job_id: str):
    """Immediately trigger a job's execution, bypassing its schedule."""
    job = await scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Run in background so we don't block the HTTP response
    import asyncio
    asyncio.create_task(scheduler_service.trigger_job(job_id))

    exec_id = f"exec-{uuid4().hex[:12]}"
    return TriggerResponse(execution_id=exec_id, status="running")


@router.get("/jobs/history", response_model=HistoryResponse)
async def get_global_history(limit: int = Query(50, ge=1, le=200)):
    """Get global execution history across all jobs."""
    all_records = []
    for job_id, records in scheduler_service._history.items():
        all_records.extend(records)

    sorted_records = sorted(all_records, key=lambda r: r.started_at, reverse=True)
    items = [r.to_dict() for r in sorted_records[:limit]]
    return HistoryResponse(items=items, total=len(items))


@router.get("/jobs/{job_id}/history", response_model=HistoryResponse)
async def get_job_history(job_id: str, limit: int = Query(20, ge=1, le=100)):
    """Get execution history for a specific job."""
    job = await scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    items = scheduler_service.get_history(job_id, limit=limit)
    return HistoryResponse(items=items, total=len(items))