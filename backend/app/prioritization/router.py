"""
FastAPI router for the AI Prioritization Engine.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.schemas.unified_data import MaintenanceRecord, MaintenanceStatus, Priority
from .schemas import (
    MaintenancePriority,
    PriorityFactors,
    PriorityInformation,
    PriorityWeights,
)
from .service import PrioritizationService

router = APIRouter(prefix="/prioritization", tags=["Prioritization"])


class PrioritizationRequest(BaseModel):
    """Request payload for maintenance prioritization."""

    maintenance: Optional[Dict[str, Any]] = Field(default=None, description="Maintenance or defect data")
    weights: Optional[PriorityWeights] = Field(default=None, description="Custom factor weights")
    reference_date: Optional[date] = Field(default=None, description="Reference date for overdue calculation")

    model_config = {"extra": "allow"}


class BatchPrioritizationRequest(BaseModel):
    """Request payload for batch maintenance prioritization."""

    items: List[Dict[str, Any]] = Field(..., description="List of maintenance or defect items")
    weights: Optional[PriorityWeights] = Field(default=None, description="Custom factor weights")
    reference_date: Optional[date] = Field(default=None, description="Reference date for overdue calculation")


def _dict_to_maintenance_record(data: Dict[str, Any]) -> MaintenanceRecord:
    """Safely convert incoming JSON dict to MaintenanceRecord model."""
    try:
        raw_status = data.get("status", "Pending")
        if isinstance(raw_status, str):
            try:
                m_status = MaintenanceStatus(raw_status.capitalize())
            except ValueError:
                m_status = MaintenanceStatus.PENDING
        else:
            m_status = MaintenanceStatus.PENDING

        raw_prio = data.get("priority", "Medium")
        if isinstance(raw_prio, str):
            try:
                m_prio = Priority(raw_prio.capitalize())
            except ValueError:
                m_prio = Priority.MEDIUM
        else:
            m_prio = Priority.MEDIUM

        req_d = data.get("requested_date") or data.get("due_date")
        if isinstance(req_d, str):
            req_d = date.fromisoformat(req_d)
        elif not isinstance(req_d, date):
            req_d = date.today()

        pref_s = data.get("preferred_start", "10:00")
        if isinstance(pref_s, str) and ":" in pref_s:
            from datetime import time
            h, m = map(int, pref_s.split(":")[:2])
            pref_s = time(h, m)

        return MaintenanceRecord(
            asset_id=str(data.get("asset_id") or data.get("maintenance_id") or "MNT-001"),
            asset_type=str(data.get("asset_type") or "Track"),
            location=str(data.get("location") or "Main Corridor"),
            maintenance_type=str(data.get("maintenance_type") or "Preventive"),
            maintenance_required=bool(data.get("maintenance_required", True)),
            priority=m_prio,
            duration_minutes=int(data.get("duration_minutes") or data.get("duration") or 120),
            requested_date=req_d,
            preferred_start=pref_s if hasattr(pref_s, "hour") else time(10, 0),
            required_resources=int(data.get("required_resources") or 1),
            equipment=str(data.get("equipment") or "Standard"),
            status=m_status,
            source=data.get("source"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid maintenance data payload: {exc}",
        )


@router.post(
    "",
    response_model=PriorityInformation,
    summary="Prioritize maintenance work (AI Engine)",
)
def prioritize_maintenance_endpoint(
    payload: PrioritizationRequest,
) -> PriorityInformation:
    """
    POST /api/prioritization
    Calculate 5 normalized priority factors and deterministic weighted priority score.
    """
    data = payload.maintenance if payload.maintenance is not None else payload.model_dump()
    if not data:
        raise HTTPException(status_code=400, detail="Missing maintenance data in request body")

    record = _dict_to_maintenance_record(data)
    service = PrioritizationService(weights=payload.weights)
    m_id = data.get("maintenance_id") or data.get("asset_id") or record.asset_id
    return service.prioritize(
        record,
        reference_date=payload.reference_date,
        maintenance_id=str(m_id),
    )


@router.post(
    "/batch",
    response_model=List[PriorityInformation],
    summary="Batch prioritize maintenance works",
)
def batch_prioritize_endpoint(
    payload: BatchPrioritizationRequest,
) -> List[PriorityInformation]:
    """
    POST /api/prioritization/batch
    Calculate priority factors and scores for a list of maintenance items.
    """
    records = [_dict_to_maintenance_record(item) for item in payload.items]
    service = PrioritizationService(weights=payload.weights)
    return [
        service.prioritize(
            rec,
            reference_date=payload.reference_date,
            maintenance_id=payload.items[i].get("maintenance_id") or payload.items[i].get("asset_id"),
        )
        for i, rec in enumerate(records)
    ]
