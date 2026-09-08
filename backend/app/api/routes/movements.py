"""
Movement API endpoints.

Exposes REST endpoints for querying persistent corridor train movement / occupancy records.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db
from backend.app.database.repositories import MovementRepository

router = APIRouter(prefix="/movements", tags=["Movements"])


@router.get(
    "",
    summary="List train corridor movements",
    response_description="List of movement records and total count",
)
def get_movements(
    train_id: Optional[str] = Query(None, description="Filter by train ID (e.g. G123, P204)"),
    section: Optional[str] = Query(None, description="Filter by section / corridor (e.g. Chennai-Perambur)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve train movement and section occupancy records."""
    repo = MovementRepository(db)
    movements = repo.get_all(train_id=train_id, section=section, skip=skip, limit=limit)
    total_count = repo.count(train_id=train_id, section=section)
    return {
        "data": [m.to_dict() for m in movements],
        "count": len(movements),
        "total": total_count,
    }


@router.get(
    "/train/{train_id}",
    summary="Get movements for a train",
    response_description="Movements for the given train across sections",
)
def get_movements_by_train(
    train_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve all corridor movements for a specific train."""
    repo = MovementRepository(db)
    movements = repo.get_by_train_id(train_id)
    if not movements:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No movement records found for train '{train_id}'",
        )
    return {
        "data": [m.to_dict() for m in movements],
        "count": len(movements),
    }


@router.get(
    "/section/{section}",
    summary="Get movements for a corridor section",
    response_description="Movements within the given corridor section",
)
def get_movements_by_section(
    section: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve all movements traversing a specific section."""
    repo = MovementRepository(db)
    movements = repo.get_by_section(section)
    return {
        "data": [m.to_dict() for m in movements],
        "count": len(movements),
    }


@router.get(
    "/{id}",
    summary="Get movement by ID",
    response_description="Single movement record",
)
def get_movement_by_id(
    id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve a single movement record by internal integer ID."""
    repo = MovementRepository(db)
    movement = repo.get_by_id(id)
    if not movement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movement record with ID '{id}' not found",
        )
    return {
        "data": movement.to_dict()
    }
