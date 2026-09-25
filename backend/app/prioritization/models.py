"""
Internal domain models for the AI Prioritization Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class MaintenanceDefectContext:
    """Internal context container for defect and maintenance parameters."""

    maintenance_id: str
    asset_id: str
    asset_type: str
    location: str
    maintenance_type: str
    priority_level: str
    duration_minutes: int
    requested_date: date
    required_resources: int
    equipment: str
    is_required: bool
    status: str
    defect_severity: Optional[str] = None
    corridor_importance: Optional[str] = None
