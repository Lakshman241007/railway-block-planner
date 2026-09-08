"""
Block API endpoints.

Exposes REST endpoints for querying and mutating persistent block /
disconnection records. Write operations are performed through the
existing BlockRepository.update() method — no schema changes required.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db
from backend.app.database.repositories import BlockRepository
from backend.app.schemas.unified_data import BlockStatus, Priority

router = APIRouter(prefix="/blocks", tags=["Blocks"])


class BlockUpdateRequest(BaseModel):
    """
    Partial-update payload for a block / disconnection record.

    All fields are optional — only include what needs to change.
    Time strings must be in HH:MM 24-hour format.
    """

    requested_start: Optional[str] = None  # HH:MM
    requested_end: Optional[str] = None    # HH:MM
    priority: Optional[str] = None         # Critical | High | Medium | Low
    status: Optional[str] = None           # Requested | Approved | Rejected | Completed | Cancelled
    reason: Optional[str] = None


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


@router.patch(
    "/{block_id}",
    summary="Partially update a block request",
    response_description="Updated block record",
)
def update_block(
    block_id: str,
    payload: BlockUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Partially update a block / disconnection record by its block_id.

    Only the fields included in the request body are written to the database;
    omitted fields remain unchanged.  The endpoint validates ``priority`` and
    ``status`` against their respective enumerations before persisting.
    """
    repo = BlockRepository(db)

    # Fetch before writing so we return a clear 404 rather than silently
    # calling update() on a non-existent row — avoids ambiguous DB behaviour.
    existing = repo.get_by_id(block_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block request '{block_id}' not found",
        )

    # Collect only explicitly supplied keys so unmentioned attributes keep their
    # existing database values, adhering strictly to partial-update (PATCH) semantics.
    update_values: Dict[str, Any] = {
        key: val
        for key, val in payload.model_dump().items()
        if val is not None
    }

    if not update_values:
        # Nothing to update — return the record as-is.
        return {"data": existing.to_dict()}

    # Validate enum fields so the DB never stores an invalid value.
    if "priority" in update_values:
        allowed_priorities = [p.value for p in Priority]
        if update_values["priority"] not in allowed_priorities:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid priority '{update_values['priority']}'. "
                    f"Allowed values: {allowed_priorities}"
                ),
            )

    if "status" in update_values:
        allowed_statuses = [s.value for s in BlockStatus]
        if update_values["status"] not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid status '{update_values['status']}'. "
                    f"Allowed values: {allowed_statuses}"
                ),
            )

    updated = repo.update(block_id, update_values)
    return {"data": updated.to_dict()}
