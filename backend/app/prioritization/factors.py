"""
Factor derivation logic for the AI Prioritization Engine.

Derives the 5 canonical priority factors (each normalized 0–100):
1. Urgency
2. Criticality
3. Overdue Factor
4. Asset Availability Impact
5. Operational Impact
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Union

from backend.app.schemas.unified_data import MaintenanceRecord, Priority
from .schemas import PriorityFactors


def compute_urgency(
    maintenance: Union[MaintenanceRecord, Any],
    defect_severity: Optional[str] = None,
) -> float:
    """
    1️⃣ Urgency (0–100)
    Determines how urgently the maintenance work needs to be performed based on:
    - Maintenance status (Pending, Approved, etc.)
    - Maintenance requirement flag
    - Defect severity if present
    """
    if hasattr(maintenance, "maintenance_required") and not maintenance.maintenance_required:
        return 0.0

    raw_status = getattr(maintenance, "status", "Pending")
    status_val = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
    status_lower = str(status_val).lower().replace("maintenancestatus.", "")

    if status_lower in ("completed", "cancelled", "done", "closed"):
        return 0.0

    status_mapping = {
        "pending": 70.0,
        "approved": 85.0,
        "requested": 75.0,
        "in_progress": 90.0,
        "in progress": 90.0,
    }
    base_urgency = status_mapping.get(status_lower, 50.0)

    # Adjust for defect severity if provided
    sev = (defect_severity or getattr(maintenance, "defect_severity", None) or "").lower()
    if sev in ("critical", "emergency", "urgent"):
        base_urgency = max(base_urgency, 95.0)
    elif sev in ("high", "major"):
        base_urgency = max(base_urgency, 80.0)
    elif sev in ("medium", "moderate"):
        base_urgency = max(base_urgency, 60.0)

    return min(100.0, max(0.0, round(float(base_urgency), 2)))


def compute_criticality(
    maintenance: Union[MaintenanceRecord, Any],
) -> float:
    """
    2️⃣ Criticality (0–100)
    Determines asset importance / safety significance based on:
    - Priority enum / level (Critical, High, Medium, Low)
    - Asset type (Bridge, OHE, Signal, Track, Point)
    """
    priority_val = getattr(maintenance, "priority", Priority.MEDIUM)
    if isinstance(priority_val, str):
        try:
            priority_val = Priority(priority_val)
        except ValueError:
            priority_val = Priority.MEDIUM

    mapping = {
        Priority.LOW: 25.0,
        Priority.MEDIUM: 50.0,
        Priority.HIGH: 75.0,
        Priority.CRITICAL: 100.0,
    }
    base_criticality = mapping.get(priority_val, 50.0)

    # Asset type weighting
    asset_type = str(getattr(maintenance, "asset_type", "")).lower()
    if any(k in asset_type for k in ["bridge", "ohe", "traction"]):
        base_criticality = min(100.0, base_criticality + 10.0)
    elif any(k in asset_type for k in ["signal", "point", "interlocking"]):
        base_criticality = min(100.0, base_criticality + 5.0)

    return min(100.0, max(0.0, round(float(base_criticality), 2)))


def compute_overdue_factor(
    maintenance: Union[MaintenanceRecord, Any],
    reference_date: Optional[date] = None,
) -> float:
    """
    3️⃣ Overdue Factor (0–100)
    Determines how far the work has exceeded its required maintenance date:
    - requested_date / due_date vs reference date (defaults to today)
    - Saturates at 100% after 30 days overdue
    """
    ref_date = reference_date or date.today()
    req_date = getattr(maintenance, "requested_date", None) or getattr(maintenance, "due_date", None)

    if not req_date:
        return 0.0

    if isinstance(req_date, str):
        try:
            req_date = date.fromisoformat(req_date)
        except Exception:
            return 0.0

    days_overdue = (ref_date - req_date).days
    if days_overdue <= 0:
        return 0.0

    # Saturates at 100 after 30 overdue days
    score = (days_overdue / 30.0) * 100.0
    return min(100.0, max(0.0, round(float(score), 2)))


def compute_asset_availability_impact(
    maintenance: Union[MaintenanceRecord, Any],
) -> float:
    """
    4️⃣ Asset Availability Impact (0–100)
    Estimates potential impact on asset availability:
    - Duration of required maintenance possession
    - 8 hours (480 mins) or more represents maximum 100% impact
    """
    duration = getattr(maintenance, "duration_minutes", None) or getattr(maintenance, "duration", 120)
    try:
        duration_mins = float(duration)
    except (ValueError, TypeError):
        duration_mins = 120.0

    if duration_mins <= 0:
        return 0.0

    score = (duration_mins / 480.0) * 100.0
    return min(100.0, max(0.0, round(float(score), 2)))


def compute_operational_impact(
    maintenance: Union[MaintenanceRecord, Any],
    corridor_importance_multiplier: float = 1.0,
) -> float:
    """
    5️⃣ Operational Impact (0–100)
    Estimates the potential effect on railway operations:
    - Resource intensity (crew/personnel required)
    - Maintenance necessity flag
    - Corridor importance
    """
    resources = getattr(maintenance, "required_resources", 1)
    try:
        res_count = float(resources)
    except (ValueError, TypeError):
        res_count = 1.0

    resource_score = min(100.0, (res_count / 10.0) * 100.0)
    is_req = getattr(maintenance, "maintenance_required", True)
    required_score = 100.0 if is_req else 0.0

    raw_score = ((resource_score * 0.4) + (required_score * 0.6)) * corridor_importance_multiplier
    return min(100.0, max(0.0, round(float(raw_score), 2)))


def compute_confidence(
    maintenance: Union[MaintenanceRecord, Any],
) -> float:
    """
    Calculate confidence score (0.0–1.0) based on completeness of available inputs.
    """
    fields = [
        getattr(maintenance, "asset_id", None) or getattr(maintenance, "maintenance_id", None),
        getattr(maintenance, "asset_type", None),
        getattr(maintenance, "location", None),
        getattr(maintenance, "maintenance_type", None),
        getattr(maintenance, "equipment", None),
        getattr(maintenance, "requested_date", None) or getattr(maintenance, "due_date", None),
        getattr(maintenance, "duration_minutes", None) or getattr(maintenance, "duration", None),
        getattr(maintenance, "required_resources", None),
        getattr(maintenance, "priority", None),
        getattr(maintenance, "status", None),
    ]

    valid_count = sum(1 for v in fields if v is not None and str(v).strip() != "")
    completeness = valid_count / len(fields)
    return round(float(completeness), 2)


def generate_explanation(
    factors: PriorityFactors,
    priority_value: float,
    asset_name: Optional[str] = None,
) -> str:
    """
    Generate clear, human-readable reasoning for the calculated priority score.
    """
    name = f"Asset {asset_name}: " if asset_name else ""
    return (
        f"{name}Deterministic priority score {priority_value:.2f}/100 derived from "
        f"urgency {factors.urgency:.1f}, "
        f"criticality {factors.criticality:.1f}, "
        f"overdue factor {factors.overdue_factor:.1f}, "
        f"asset availability impact {factors.asset_availability_impact:.1f}, "
        f"and operational impact {factors.operational_impact:.1f}."
    )
