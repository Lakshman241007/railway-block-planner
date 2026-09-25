"""
Schemas for the AI maintenance prioritization engine (Phase 5 & AI Prioritization Contract).

Defines canonical schemas for:
- 5 normalized priority factors (0-100)
- Configurable priority weights (W1..W5)
- PriorityInformation & MaintenancePriority output payloads
- Request & Response payloads for the Prioritization API
- Re-exports of Priority and PriorityEnrichment for seamless pipeline compatibility.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Re-export canonical Priority and PriorityEnrichment from unified_data
from backend.app.schemas.unified_data import Priority, PriorityEnrichment


class PriorityFactors(BaseModel):
    """Normalized 0-100 factors used to calculate maintenance priority."""

    urgency: float = Field(default=0.0, ge=0.0, le=100.0, description="Time sensitivity and due-date proximity")
    criticality: float = Field(default=0.0, ge=0.0, le=100.0, description="Asset safety and operational importance")
    overdue_factor: float = Field(default=0.0, ge=0.0, le=100.0, description="Degree of schedule overdue severity")
    asset_availability_impact: float = Field(default=0.0, ge=0.0, le=100.0, description="Impact of delay on asset availability")
    operational_impact: float = Field(default=0.0, ge=0.0, le=100.0, description="Impact of delay on railway operations/traffic")

    model_config = {"str_strip_whitespace": True}


class PriorityWeights(BaseModel):
    """
    Configurable weights for the five prioritization factors.
    W1 * Urgency + W2 * Criticality + W3 * Overdue + W4 * Asset Availability + W5 * Operational Impact
    """

    urgency: float = Field(default=0.20, ge=0.0, description="Weight for urgency factor")
    criticality: float = Field(default=0.25, ge=0.0, description="Weight for asset criticality factor")
    overdue_factor: float = Field(default=0.20, ge=0.0, description="Weight for overdue factor")
    asset_availability_impact: float = Field(default=0.15, ge=0.0, description="Weight for asset availability impact")
    operational_impact: float = Field(default=0.20, ge=0.0, description="Weight for operational impact")

    model_config = {"str_strip_whitespace": True}


class PriorityInformation(BaseModel):
    """
    AI-generated prioritization result for a maintenance record.
    Matches the canonical contract consumed by downstream Block Planner and UI.
    """

    maintenance_id: str = Field(..., min_length=1, description="Identifier of the maintenance record or asset")
    factors: PriorityFactors = Field(..., description="The five normalized 0-100 priority factors")
    priority_value: float = Field(..., ge=0.0, le=100.0, description="Deterministic weighted priority score (0-100)")
    explanation: str = Field(..., min_length=1, description="Human-readable explanation of the calculated score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score based on input completeness (0.0-1.0)")

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


class MaintenancePriority(BaseModel):
    """
    Flat priority output model matching the SIH26 AI Prioritization Layer specification.
    """

    maintenance_id: str = Field(..., min_length=1)
    urgency: float = Field(ge=0.0, le=100.0)
    criticality: float = Field(ge=0.0, le=100.0)
    overdue_factor: float = Field(ge=0.0, le=100.0)
    asset_availability_impact: float = Field(ge=0.0, le=100.0)
    operational_impact: float = Field(ge=0.0, le=100.0)
    priority_value: float = Field(ge=0.0, le=100.0)
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    factors: Optional[PriorityFactors] = None

    model_config = {"str_strip_whitespace": True, "extra": "allow"}


__all__ = [
    "Priority",
    "PriorityEnrichment",
    "PriorityFactors",
    "PriorityWeights",
    "PriorityInformation",
    "MaintenancePriority",
]
