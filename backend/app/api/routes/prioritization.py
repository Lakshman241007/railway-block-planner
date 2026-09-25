"""
Maintenance prioritization API endpoints.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.prioritization.service import PrioritizationService
from backend.app.prioritization.schemas import (
    PriorityInformation,
    PriorityWeights,
)
from backend.app.schemas.planning_contracts import MaintenanceWork
from backend.app.schemas.unified_data import (
    MaintenanceRecord,
    MaintenanceStatus,
)


router = APIRouter(
    prefix="/prioritization",
    tags=["Prioritization"],
)


class PrioritizationRequest(BaseModel):
    """Request payload for maintenance prioritization."""

    maintenance: MaintenanceWork
    weights: PriorityWeights | None = None
    reference_date: date | None = None


def _work_to_maintenance_record(
    work: MaintenanceWork,
) -> MaintenanceRecord:
    """Convert the planning contract into the existing unified model."""

    try:
        maintenance_status = MaintenanceStatus(work.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid maintenance status: {work.status}",
        ) from exc

    return MaintenanceRecord(
        asset_id=work.asset_id,
        asset_type=work.asset_type,
        location=work.location,
        maintenance_type=work.maintenance_type,
        maintenance_required=work.maintenance_required,
        priority=work.priority,
        duration_minutes=work.duration_minutes,
        requested_date=work.requested_date,
        preferred_start=work.preferred_start,
        required_resources=work.required_resources,
        equipment=work.equipment,
        status=maintenance_status,
        source=work.source,
    )


@router.post(
    "",
    response_model=PriorityInformation,
    summary="Prioritize maintenance work",
)
def prioritize_maintenance(
    payload: PrioritizationRequest,
) -> PriorityInformation:
    """
    Calculate deterministic priority factors and weighted priority score.
    """

    maintenance = _work_to_maintenance_record(payload.maintenance)

    service = PrioritizationService(
        weights=payload.weights,
    )

    return service.prioritize(
        maintenance,
        reference_date=payload.reference_date,
        maintenance_id=payload.maintenance.maintenance_id
    )