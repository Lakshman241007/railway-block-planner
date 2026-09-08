"""
Maintenance API endpoints.

Exposes REST endpoints for querying and mutating persistent railway
maintenance records. Write operations are performed through the existing
MaintenanceRepository.update() method — no schema changes required.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db
from backend.app.database.repositories import MaintenanceRepository
from backend.app.schemas.unified_data import MaintenanceStatus, Priority

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


class MaintenanceUpdateRequest(BaseModel):
    """
    Partial-update payload for a maintenance record.

    All fields are optional — only include what needs to change.
    The record is identified by its integer ``id`` (primary key), not
    ``asset_id``, so callers can target a single record precisely even
    when multiple records share the same asset.
    """

    preferred_start: Optional[str] = None   # HH:MM
    duration_minutes: Optional[int] = None  # must be > 0
    priority: Optional[str] = None          # Critical | High | Medium | Low
    status: Optional[str] = None            # Pending | Approved | Completed | Cancelled


@router.get(
    "",
    summary="List maintenance records",
    response_description="List of maintenance records and total count",
)
def get_maintenance_records(
    priority: Optional[str] = Query(None, description="Filter by priority (Low, Medium, High, Critical)"),
    status: Optional[str] = Query(None, description="Filter by status (Pending, Approved, Completed, Cancelled)"),
    asset_id: Optional[str] = Query(None, description="Filter by asset ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve maintenance records with optional filters and pagination."""
    repo = MaintenanceRepository(db)
    records = repo.get_all(priority=priority, status=status, asset_id=asset_id, skip=skip, limit=limit)
    total_count = repo.count(priority=priority, status=status, asset_id=asset_id)
    return {
        "data": [m.to_dict() for m in records],
        "count": len(records),
        "total": total_count,
    }


@router.get(
    "/{asset_id}",
    summary="Get maintenance records for an asset",
    response_description="Maintenance records for the asset",
)
def get_maintenance_by_asset(
    asset_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve all maintenance records associated with a specific asset_id."""
    repo = MaintenanceRepository(db)
    records = repo.get_by_asset_id(asset_id)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No maintenance records found for asset '{asset_id}'",
        )
    return {
        "data": [m.to_dict() for m in records],
        "count": len(records),
    }


@router.patch(
    "/{id}",
    summary="Partially update a maintenance record",
    response_description="Updated maintenance record",
)
def update_maintenance_record(
    id: str,
    payload: MaintenanceUpdateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Partially update a maintenance record by its integer primary-key ``id``
    or string ``asset_id``.

    Only the supplied fields are written; omitted fields stay unchanged.
    Enum fields and numeric constraints are validated before the record is persisted.
    """
    repo = MaintenanceRepository(db)

    # Fetch before writing so we return a clear 404 rather than silently
    # calling update() on a non-existent row — avoids ambiguous DB behaviour.
    existing = repo.get_by_identifier(id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance record with id={id} not found",
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

    # A zero or negative duration is physically impossible for track maintenance possessions;
    # reject non-positive values at the boundary to prevent corrupted schedule windows.
    if "duration_minutes" in update_values and update_values["duration_minutes"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="duration_minutes must be a positive integer greater than zero",
        )

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
        allowed_statuses = [s.value for s in MaintenanceStatus]
        if update_values["status"] not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid status '{update_values['status']}'. "
                    f"Allowed values: {allowed_statuses}"
                ),
            )

    updated = repo.update(existing.id, update_values)
    return {"data": updated.to_dict()}
