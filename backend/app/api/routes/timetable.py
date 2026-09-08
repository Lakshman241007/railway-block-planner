"""
Timetable API endpoints.

Exposes REST endpoints for querying persistent timetable stop records.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db
from backend.app.database.repositories import TimetableRepository

router = APIRouter(prefix="/timetable", tags=["Timetable"])


@router.get(
    "",
    summary="List timetable scheduled stops",
    response_description="List of timetable records and total count",
)
def get_timetable(
    train_id: Optional[str] = Query(None, description="Filter by train ID (e.g. G123, P204)"),
    service_date: Optional[str] = Query(None, description="Filter by service date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve timetable records with optional train_id and service_date filters."""
    repo = TimetableRepository(db)
    parsed_date = None
    if service_date:
        try:
            parsed_date = date.fromisoformat(service_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid date format for service_date: '{service_date}'. Expected YYYY-MM-DD.",
            )

    entries = repo.get_all(train_id=train_id, service_date=parsed_date, skip=skip, limit=limit)
    total_count = repo.count(train_id=train_id, service_date=parsed_date)
    return {
        "data": [t.to_dict() for t in entries],
        "count": len(entries),
        "total": total_count,
    }


@router.get(
    "/train/{train_id}",
    summary="Get timetable stops for a train",
    response_description="All scheduled stops for the given train",
)
def get_timetable_by_train(
    train_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve all scheduled stops for a specific train, ordered by sequence."""
    repo = TimetableRepository(db)
    entries = repo.get_by_train_id(train_id)
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No timetable stops found for train '{train_id}'",
        )
    return {
        "data": [t.to_dict() for t in entries],
        "count": len(entries),
    }


@router.get(
    "/{id}",
    summary="Get timetable stop by ID",
    response_description="Single timetable stop record",
)
def get_timetable_by_id(
    id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve a single timetable stop by internal ID."""
    repo = TimetableRepository(db)
    entry = repo.get_by_id(id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timetable stop with ID '{id}' not found",
        )
    return {
        "data": entry.to_dict()
    }
