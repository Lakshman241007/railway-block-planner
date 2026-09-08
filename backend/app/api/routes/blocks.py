"""
Block API endpoints (Phase 5 — Block Request Lifecycle).

Exposes REST endpoints for querying persistent block records and
submitting new block requests with full operational validation.

BLOCK REQUEST LIFECYCLE:
    SUBMITTED → VALIDATED → STORED (status=Requested)
    or
    SUBMITTED → REJECTED (400 + validation reason)
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db
from backend.app.database.repositories import BlockRepository
from backend.app.schemas.unified_data import BlockRecord, BlockStatus, BlockType, Priority

router = APIRouter(prefix="/blocks", tags=["Blocks"])

# ---------------------------------------------------------------------------
# Request / Validation Schemas
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _parse_hhmm(val: str) -> int:
    """Convert HH:MM string to total minutes since midnight."""
    h, m = val.split(":")
    return int(h) * 60 + int(m)


class BlockSubmitRequest(BaseModel):
    """
    Payload for submitting a new block request through the BDMS interface.

    Validates all required fields and enforces operational constraints:
    - block_id must be non-empty and unique in the database
    - location, reason must be non-empty
    - block_type must be a valid BlockType enum value
    - requested_date must be a valid ISO date (YYYY-MM-DD)
    - requested_start and requested_end must be HH:MM format
    - duration must be > 0 (overnight blocks with end < start are valid)
    - priority must be a valid Priority enum value
    """

    block_id: str = Field(..., min_length=1, description="Unique block request identifier (e.g. BLK-099)")
    location: str = Field(..., min_length=1, description="Railway section / location for the block")
    block_type: BlockType = Field(..., description="Type: Maintenance, Emergency, Non-Interlocked, Traffic")
    requested_date: str = Field(..., description="Requested date (YYYY-MM-DD)")
    requested_start: str = Field(..., description="Requested start time (HH:MM)")
    requested_end: str = Field(..., description="Requested end time (HH:MM, may cross midnight for overnight)")
    reason: str = Field(..., min_length=1, description="Operational reason for the block")
    priority: Priority = Field(..., description="Block priority: Low, Medium, High, Critical")
    source: Optional[str] = Field(default="BDMS-API", description="Data source identifier")

    model_config = {"str_strip_whitespace": True}

    @field_validator("requested_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid date '{v}'. Must be YYYY-MM-DD format.")
        return v

    @field_validator("requested_start", "requested_end")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if not _TIME_RE.match(v):
            raise ValueError(f"Invalid time '{v}'. Must be HH:MM format.")
        h, m = v.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError(f"Time '{v}' is out of range (00:00–23:59).")
        return v

    @model_validator(mode="after")
    def validate_duration(self) -> "BlockSubmitRequest":
        """Validate duration is positive. Overnight blocks (end < start) yield 24h-wraparound duration."""
        s = _parse_hhmm(self.requested_start)
        e = _parse_hhmm(self.requested_end)
        if e < s:
            # Overnight block: duration = (1440 - s) + e
            dur = (1440 - s) + e
        else:
            dur = e - s
        if dur <= 0:
            raise ValueError(
                f"Invalid duration: start={self.requested_start} and end={self.requested_end} "
                f"produce a zero or negative duration. For overnight blocks the end must be after "
                f"the start on the next day (e.g. start=22:00, end=02:00 → 240 min)."
            )
        if dur > 1440:
            raise ValueError(
                f"Block duration of {dur} minutes exceeds 24 hours. "
                "This is an impossible single-possession duration."
            )
        return self


class BlockValidationResponse(BaseModel):
    """Response returned when a block request is validated and stored."""
    status: str = Field(..., description="VALIDATED or REJECTED")
    block_id: str
    location: str
    requested_date: str
    requested_start: str
    requested_end: str
    duration_minutes: int
    priority: str
    block_type: str
    message: str
    data: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# GET /api/blocks — List block requests
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List block requests",
    response_description="List of block records and total count",
)
def get_blocks(
    date: Optional[str] = Query(None, description="Filter by requested date (YYYY-MM-DD)"),
    location: Optional[str] = Query(None, description="Filter by section / location keyword"),
    status: Optional[str] = Query(None, description="Filter by block status (Requested, Approved, etc.)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve block requests with optional date, location, and status filters."""
    repo = BlockRepository(db)
    blocks = repo.get_all(date_filter=date, location=location, status=status, skip=skip, limit=limit)
    total_count = repo.count(date_filter=date, location=location, status=status)
    return {
        "data": [b.to_dict() for b in blocks],
        "count": len(blocks),
        "total": total_count,
    }


# ---------------------------------------------------------------------------
# GET /api/blocks/{block_id} — Get single block
# ---------------------------------------------------------------------------

@router.get(
    "/{block_id}",
    summary="Get block by ID",
    response_description="Single block record",
)
def get_block_by_id(
    block_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve details of a single block by its block_id."""
    repo = BlockRepository(db)
    block = repo.get_by_id(block_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block request '{block_id}' not found",
        )
    return {
        "data": block.to_dict()
    }


# ---------------------------------------------------------------------------
# POST /api/blocks — Submit new block request
# ---------------------------------------------------------------------------

@router.post(
    "",
    summary="Submit a new block request (Phase 5)",
    response_description="Validation result and persisted block record",
    status_code=status.HTTP_201_CREATED,
    response_model=BlockValidationResponse,
)
def submit_block_request(
    payload: BlockSubmitRequest,
    db: Session = Depends(get_db),
) -> BlockValidationResponse:
    """
    Submit and validate a new block/disconnection request.

    Validation checks (in order):
    1. block_id uniqueness
    2. location non-empty
    3. block_type valid enum
    4. requested_date valid ISO date
    5. requested_start and requested_end valid HH:MM
    6. duration > 0 (overnight interval handled correctly)
    7. duration ≤ 1440 minutes
    8. priority valid enum
    9. reason non-empty

    On success: block is persisted with status=Requested and VALIDATED is returned.
    On failure: 400 Bad Request with rejection reason.
    """
    repo = BlockRepository(db)

    # --- Uniqueness check ---
    existing = repo.get_by_id(payload.block_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Block request '{payload.block_id}' already exists. Use a unique block_id.",
        )

    # --- Compute duration ---
    s = _parse_hhmm(payload.requested_start)
    e = _parse_hhmm(payload.requested_end)
    if e < s:
        duration_minutes = (1440 - s) + e  # overnight
    else:
        duration_minutes = e - s

    # --- Build BlockRecord and persist ---
    block_record = BlockRecord(
        block_id=payload.block_id,
        location=payload.location,
        block_type=payload.block_type,
        requested_date=date.fromisoformat(payload.requested_date),
        requested_start=payload.requested_start,
        requested_end=payload.requested_end,
        reason=payload.reason,
        priority=payload.priority,
        status=BlockStatus.REQUESTED,
        source=payload.source or "BDMS-API",
    )

    db_block = repo.create(block_record)

    return BlockValidationResponse(
        status="VALIDATED",
        block_id=db_block.block_id,
        location=db_block.location,
        requested_date=db_block.requested_date.isoformat(),
        requested_start=db_block.requested_start,
        requested_end=db_block.requested_end,
        duration_minutes=duration_minutes,
        priority=db_block.priority,
        block_type=db_block.block_type,
        message=(
            f"Block request '{payload.block_id}' validated and accepted. "
            f"Status: Requested. Run CP-SAT optimization to schedule this block."
        ),
        data=db_block.to_dict(),
    )
